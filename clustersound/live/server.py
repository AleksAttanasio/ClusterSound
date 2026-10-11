"""Localhost HTTP bridge for the Max for Live device.

    GET /live/ping                     -> {"app", "version", "pending"}
    GET /live/catalog                  -> saved user patterns, sequences, racks and progressions
    GET /live/payload?kind=…&id=…      -> payload.py output for a saved item (kind: pattern|sequence|rack|compose)
    GET /live/next                     -> the oldest item pushed from the app ("Invia a Live"), or 204

Only these routes exist (no generic RPC) and the server binds to 127.0.0.1.
"""
import json
import os
import threading
import urllib.parse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..paths import data_dir
from ..patterns import arrange as pat_arrange
from ..patterns import genres as pat_genres
from ..patterns import store as pat_store
from ..racks import store as rack_store
from . import payload

DEFAULT_PORT = 8770
VERSION = 1
KIT_FILE = "live_kit.json"


def save_current_kit(p: dict) -> None:
    """The pattern open in the Sequencer (its samples, layers and mix): the kit for sequences saved without one."""
    path = data_dir() / KIT_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(p))
    os.replace(tmp, path)


def current_kit() -> dict | None:
    try:
        p = json.loads((data_dir() / KIT_FILE).read_text())
    except (OSError, ValueError):
        return None
    return p if isinstance(p, dict) and p.get("buses") else None


def _has_samples(p: dict) -> bool:
    return any(ly.get("ref") for bus in (p.get("buses") or {}).values() for ly in bus.get("layers") or [])


class Bridge:
    """Builds payloads and keeps the queue of pushed items. resolve/describe: as for the Ableton exports."""

    def __init__(self, stage: payload.Stage, resolve, describe, title=lambda p: p.get("name") or "Pattern"):
        self.stage = stage
        self.resolve, self.describe, self.title = resolve, describe, title
        self._queue: deque = deque()
        self._lock = threading.Lock()
        self.server: ThreadingHTTPServer | None = None
        self.error: str | None = None

    # ------------------------------------------------------------ payloads
    def build(self, kind: str, data: dict, **opts) -> dict:
        if kind in ("pattern", "sequence"):
            return payload.pattern(data, self.stage, self.resolve, self.describe, self.title(data))
        if kind == "rack":
            return payload.rack(data, self.stage, self.resolve, self.describe)
        if kind == "compose":
            return payload.compose(data, pure=bool(opts.get("pure")), versions=opts.get("versions"))
        raise ValueError(f"tipo sconosciuto: {kind}")

    @staticmethod
    def sequence_kit(seq: dict) -> tuple[dict | None, str]:
        """(kit pattern, note for the catalogue) of a saved sequence: the kit saved with it, else the user
        pattern its first block comes from, else the kit open in the Sequencer now, else that block's genre
        preset (no samples: MIDI only)."""
        if seq.get("kit"):
            return seq["kit"], ""
        src = next((b.get("source") or {} for b in seq.get("blocks", []) if b.get("groove")), {})
        if src.get("user"):
            user = next((p for p in pat_store.list_user() if p.get("id") == src["user"]), None)
            if user:
                return user, ""
        kit = current_kit()
        if kit and _has_samples(kit):
            return kit, " (kit attuale)"
        if src.get("genre") in pat_genres.GENRE_BY_ID:
            n = len(pat_genres.variants(src["genre"]))
            return pat_genres.build(src["genre"], min(int(src.get("variant") or 0), n - 1)), " (solo MIDI)"
        return None, ""

    @classmethod
    def find(cls, kind: str, item_id: str) -> dict | None:
        if kind == "sequence":
            seq = next((s for s in pat_store.list_sequences() if s.get("id") == item_id), None)
            if seq is None:
                return None
            kit, _ = cls.sequence_kit(seq)
            if kit is None:
                raise ValueError("sequenza senza kit: aprila nel Sequencer e salvala di nuovo")
            flat = pat_arrange.flatten(kit, seq)
            flat["name"] = seq.get("name") or "Sequenza"
            return flat
        items = {"pattern": pat_store.list_user, "rack": rack_store.list_racks,
                 "compose": pat_store.list_progressions}.get(kind)
        return next((x for x in items() if x.get("id") == item_id), None) if items else None

    @classmethod
    def catalog(cls) -> dict:
        return {
            "pattern": [{"id": p["id"], "name": p.get("name") or "Pattern"} for p in pat_store.list_user()],
            "sequence": [{"id": s["id"], "name": (s.get("name") or "Sequenza") + cls.sequence_kit(s)[1]}
                         for s in pat_store.list_sequences()],
            "rack": [{"id": r["id"], "name": r.get("name") or "Rack"} for r in rack_store.list_racks()],
            "compose": [{"id": p["id"], "name": p.get("name") or "Progressione"} for p in pat_store.list_progressions()],
        }

    # ------------------------------------------------------------ push queue
    def push(self, item: dict) -> int:
        with self._lock:
            self._queue.append(item)
            return len(self._queue)

    def next(self) -> dict | None:
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def pending(self) -> int:
        with self._lock:
            return len(self._queue)

    # ------------------------------------------------------------ server
    def start(self, port: int = DEFAULT_PORT) -> bool:
        """Serve in a daemon thread; False (and self.error) if the port is taken."""
        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", int(port)), _handler(self))
        except OSError as e:
            self.error = f"porta {port} non disponibile: {e.strerror or e}"
            return False
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return True

    @property
    def port(self) -> int | None:
        return self.server.server_address[1] if self.server else None

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None


def _handler(bridge: Bridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, obj, status: int = 200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            try:
                if url.path == "/live/ping":
                    return self._json({"app": "ClusterSound", "version": VERSION, "pending": bridge.pending()})
                if url.path == "/live/catalog":
                    return self._json(bridge.catalog())
                if url.path == "/live/payload":
                    kind, item_id = q.get("kind", ""), q.get("id", "")
                    data = bridge.find(kind, item_id)
                    if data is None:
                        return self._json({"error": f"{kind} {item_id} non trovato"}, 404)
                    return self._json(bridge.build(kind, data))
                if url.path == "/live/next":
                    item = bridge.next()
                    if item is None:
                        self.send_response(204)
                        self.end_headers()
                        return
                    return self._json(item)
            except Exception as e:
                return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
            self._json({"error": "not found"}, 404)

    return Handler
