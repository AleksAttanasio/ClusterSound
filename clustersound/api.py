"""Bridge exposed to the web UI through pywebview's js_api."""
import base64
import hashlib
import io
import json
import mimetypes
import os
import subprocess
import threading
import urllib.parse
import urllib.request
import webbrowser

import numpy as np
import soundfile as sf

from . import dynamics, export, taxonomy
from .features import TYPES
from .library import Library
from .online import search as online
from .online.base import LICENSES, USER_AGENT
from .online.downloads import DEFAULT_DIR, Downloader, host_allowed
from .paths import data_dir

PREVIEW_MAX_SECONDS = 60
PREVIEW_MAX_BYTES = 60 << 20
PREVIEW_CACHE = os.path.expanduser("~/Library/Caches/ClusterSound/previews")


def _wav_data_url(src) -> str | None:
    """Decode any libsndfile-readable file (path or file object) to a 16-bit WAV data URL."""
    try:
        with sf.SoundFile(src) as f:
            n = min(f.frames, PREVIEW_MAX_SECONDS * f.samplerate) if f.frames > 0 else -1
            data = f.read(frames=n, dtype="float32", always_2d=True)
            sr = f.samplerate
    except Exception:
        return None
    if data.shape[1] > 2:
        data = data[:, :2]
    buf = io.BytesIO()
    sf.write(buf, np.clip(data, -1, 1), sr, format="WAV", subtype="PCM_16")
    return "data:audio/wav;base64," + base64.b64encode(buf.getvalue()).decode()


class Api:
    def __init__(self):
        self._lib = Library()
        self._window = None
        self._settings_path = data_dir() / "settings.json"
        self._relabel_lock = threading.Lock()
        self._downloader = Downloader()

    # pywebview exposes public attributes too, so keep internals underscored
    def _set_window(self, window):
        self._window = window

    def _settings(self) -> dict:
        try:
            return json.loads(self._settings_path.read_text())
        except (OSError, ValueError):
            return {}

    def _save_settings(self, **kw) -> None:
        s = self._settings() | kw
        self._settings_path.write_text(json.dumps(s))

    # ------------------------------------------------------------------ setup
    def init(self) -> dict:
        return {"classes": taxonomy.ui_classes(), "groups": taxonomy.GROUPS, "types": TYPES,
                "last_folder": self._settings().get("last_folder")}

    def pick_folder(self) -> str | None:
        import webview
        res = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if not res:
            return None
        return res[0] if isinstance(res, (list, tuple)) else res

    def start_scan(self, path: str) -> bool:
        if not path or not os.path.isdir(path):
            return False
        self._save_settings(last_folder=path)
        self._lib.start_scan(path)
        return True

    def progress(self) -> dict:
        return {**self._lib.progress, "version": self._lib.version,
                "layout": self._lib.layout_kind}

    # ---------------------------------------------------------------- results
    def results(self) -> dict:
        """Columnar payload: compact enough for tens of thousands of points."""
        lib = self._lib
        items = lib.public_items()
        cls_index = {c["id"]: i for i, c in enumerate(taxonomy.ui_classes())}
        return {
            "version": lib.version,
            "root": lib.root,
            "layout": lib.layout_kind,
            "stats": {k: v for k, v in lib.stats.items() if isinstance(v, (int, float, str))},
            "errors": len(lib.errors),
            "name": [it["name"] for it in items],
            "rel": [it["rel"] for it in items],
            "cls": [cls_index[it["cls"]] for it in items],
            "conf": [it["conf"] for it in items],
            "user": [1 if it["user"] else 0 for it in items],
            "sub": [it["sub"] for it in items],
            "type": [TYPES.index(it["type"]) if it["type"] in TYPES else 0 for it in items],
            "dur": [it["dur"] for it in items],
            "xyz": [v for it in items for v in (it["x"], it["y"], it["z"])],
        }

    def details(self, item_id: int) -> dict:
        it = self._lib.items[int(item_id)]
        try:
            dyn = dynamics.details(it["path"])
        except Exception as e:
            dyn = {"error": f"{type(e).__name__}: {e}"}
        f = it["feats"]
        return {
            "id": it["id"], "name": it["name"], "rel": it["rel"], "path": it["path"],
            "cls": it["cls"], "conf": it["conf"], "user": it.get("user", False),
            "alts": it.get("alts", []), "sub": it.get("sub", 1), "type": f.get("type"),
            "info": it["info"],
            "features": {k: round(float(f.get(k, 0.0)), 4) for k in
                         ("centroid", "harmonicity", "f0", "flatness", "band_sub", "band_low",
                          "band_lowmid", "band_highmid", "band_high", "onset_count")},
            "dyn": dyn,
        }

    def audio(self, item_id: int) -> str | None:
        """The sample as a base64 WAV data URL (decoded here so every format plays)."""
        return _wav_data_url(self._lib.items[int(item_id)]["path"])

    def reveal(self, item_id: int) -> bool:
        path = self._lib.items[int(item_id)]["path"]
        if not os.path.exists(path):
            return False
        subprocess.run(["open", "-R", path], check=False)
        return True

    def similar(self, item_id: int, k: int = 12) -> list[int]:
        return self._lib.similar(int(item_id), int(k))

    def relabel(self, item_id: int, cls: str | None) -> dict:
        """Set (or clear, with cls=None) a user label, then retrain in the background."""
        lib = self._lib
        item_id = int(item_id)
        if cls is not None and cls not in taxonomy.BY_ID:
            return {"ok": False}
        it = lib.items[item_id]
        lib.cache.set_label(it["path"], cls)
        if cls:
            it["cls"], it["conf"], it["user"] = cls, 1.0, True
        lib.version += 1

        def work():
            with self._relabel_lock:
                lib._set_progress("classifying", 0, 0, "Ri-addestramento…")
                lib.reclassify()
                lib._set_progress("done", len(lib.items), len(lib.items), "Classi aggiornate")

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True, "version": lib.version}

    def export_report(self) -> str | None:
        import webview
        if not self._lib.items:
            return None
        res = self._window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename="clustersound_report.csv",
            file_types=("CSV (*.csv)", "JSON (*.json)"))
        if not res:
            return None
        path = res[0] if isinstance(res, (list, tuple)) else res
        export.write(self._lib.items, path)
        return path

    # ================================================================== online
    def online_init(self) -> dict:
        return {"sources": [{"id": k, "label": v} for k, v in online.LABELS.items()],
                "licenses": {k: v["label"] for k, v in LICENSES.items()},
                "server_filters": online.server_filters(),
                "settings": self.get_settings()}

    def get_settings(self) -> dict:
        s = self._settings()
        key = s.get("freesound_key") or ""
        return {"freesound_key_set": bool(key),
                "freesound_key_hint": (key[:4] + "…" + key[-3:]) if len(key) > 8 else "",
                "download_dir": s.get("download_dir") or DEFAULT_DIR}

    def set_setting(self, key: str, value) -> dict:
        if key not in ("freesound_key", "download_dir"):
            return self.get_settings()
        value = (value or "").strip() or None
        if key == "download_dir" and value:
            value = os.path.expanduser(value)
        self._save_settings(**{key: value})
        return self.get_settings()

    def online_search(self, params: dict) -> dict:
        return online.search(params or {}, self._settings())

    def online_more(self, source: str, params: dict, page: int) -> dict:
        if source not in online.SOURCES:
            return {"error": "fonte sconosciuta", "results": []}
        return online.search_source(source, params or {}, int(page), self._settings())

    def online_expand(self, uid: str, params: dict) -> dict:
        return online.expand(uid, params or {})

    def online_preview(self, uid: str) -> str | None:
        """Fetch (and cache on disk) a result's audio, returned as a playable data URL."""
        r = online.get(uid)
        url = r and (r.preview_url or r.download_url)
        if not url or not host_allowed(url):
            return None
        os.makedirs(PREVIEW_CACHE, exist_ok=True)
        ext = os.path.splitext(url.split("?")[0])[1][:6] or ".bin"
        path = os.path.join(PREVIEW_CACHE, hashlib.sha1(url.encode()).hexdigest() + ext)
        if not os.path.exists(path):
            data = _fetch_bytes(url, PREVIEW_MAX_BYTES)
            if data is None:
                return None
            with open(path, "wb") as f:
                f.write(data)
        out = _wav_data_url(path)
        if out is None:  # a format libsndfile can't read: hand the bytes to the web view
            mime = mimetypes.guess_type(path)[0] or "audio/mpeg"
            with open(path, "rb") as f:
                out = f"data:{mime};base64," + base64.b64encode(f.read()).decode()
        return out

    def online_download(self, uid: str, url: str | None = None) -> dict:
        """Queue a download. For packs, `url` picks one of the pack's archives."""
        r = online.get(uid)
        if r is None:
            return {"error": "risultato non trovato"}
        if url:
            ident = r.extra.get("identifier", "")
            if not (r.is_pack and url.startswith(f"https://archive.org/download/{urllib.parse.quote(ident)}/")):
                return {"error": "file non appartenente al pack"}
        root = self._settings().get("download_dir") or DEFAULT_DIR
        try:
            return self._downloader.enqueue(r, url or r.download_url, root)
        except ValueError as e:
            return {"error": str(e)}

    def downloads(self) -> list[dict]:
        return self._downloader.status()

    def reveal_path(self, path: str) -> bool:
        root = os.path.realpath(self._settings().get("download_dir") or DEFAULT_DIR)
        path = os.path.realpath(path or "")
        if not (path == root or path.startswith(root + os.sep)) or not os.path.exists(path):
            return False
        subprocess.run(["open", "-R", path] if os.path.isfile(path) else ["open", path], check=False)
        return True

    def open_download_dir(self) -> bool:
        root = self._settings().get("download_dir") or DEFAULT_DIR
        os.makedirs(root, exist_ok=True)
        subprocess.run(["open", root], check=False)
        return True

    def open_url(self, url: str) -> bool:
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            return False
        webbrowser.open(url)
        return True


def _fetch_bytes(url: str, limit: int) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if not host_allowed(r.geturl()):
                return None
            data = r.read(limit + 1)
    except Exception:
        return None
    return data if len(data) <= limit else None

