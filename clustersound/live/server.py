"""Localhost HTTP bridge for the Max for Live device.

    GET /live/ping                     -> {"app", "version", "pending"}
    GET /live/catalog                  -> saved user patterns, genre presets, racks and progressions
    GET /live/payload?kind=…&id=…      -> payload.py output for a saved item (kind: pattern|genre|rack|compose)
    GET /live/next                     -> the oldest item pushed from the app ("Invia a Live"), or 204

Only these routes exist (no generic RPC) and the server binds to 127.0.0.1.
"""
import json
import threading
import urllib.parse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..patterns import genres as pat_genres
from ..patterns import store as pat_store
from ..racks import store as rack_store
from . import payload

DEFAULT_PORT = 8770
VERSION = 1


class Bridge:
    """Builds payloads and keeps the queue of pushed items. resolve/describe: as for the Ableton exports."""

    def __init__(self, export_dir: str, resolve, describe, title=lambda p: p.get("name") or "Pattern"):
        self.export_dir = export_dir
        self.resolve, self.describe, self.title = resolve, describe, title
        self._queue: deque = deque()
        self._lock = threading.Lock()
        self.server: ThreadingHTTPServer | None = None
        self.error: str | None = None

    # ------------------------------------------------------------ payloads
    def build(self, kind: str, data: dict, **opts) -> dict:
        if kind in ("pattern", "genre", "sequence"):
            return payload.pattern(data, self.export_dir, self.resolve, self.describe, self.title(data))
        if kind == "rack":
            return payload.rack(data, self.export_dir, self.resolve, self.describe)
        if kind == "compose":
            return payload.compose(data, pure=bool(opts.get("pure")), versions=opts.get("versions"))
        raise ValueError(f"tipo sconosciuto: {kind}")

    @staticmethod
    def find(kind: str, item_id: str) -> dict | None:
        if kind == "genre":
            gid, _, variant = item_id.rpartition(":")
            return pat_genres.build(gid, int(variant)) if gid in pat_genres.GENRE_BY_ID else None
        items = {"pattern": pat_store.list_user, "rack": rack_store.list_racks,
                 "compose": pat_store.list_progressions}.get(kind)
        return next((x for x in items() if x.get("id") == item_id), None) if items else None

    @staticmethod
    def catalog() -> dict:
        return {
            "pattern": [{"id": p["id"], "name": p.get("name") or "Pattern"} for p in pat_store.list_user()],
            "genre": [{"id": f"{g['id']}:{i}", "name": f"{g['name']} – {v}"}
                      for g in pat_genres.catalog() for i, v in enumerate(g["variants"])],
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
