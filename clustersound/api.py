"""Bridge exposed to the web UI through pywebview's js_api."""
import base64
import io
import json
import os
import subprocess
import threading

import numpy as np
import soundfile as sf

from . import dynamics, export, taxonomy
from .features import TYPES
from .library import Library
from .paths import data_dir

PREVIEW_MAX_SECONDS = 60


class Api:
    def __init__(self):
        self._lib = Library()
        self._window = None
        self._settings_path = data_dir() / "settings.json"
        self._relabel_lock = threading.Lock()

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
        path = self._lib.items[int(item_id)]["path"]
        try:
            with sf.SoundFile(path) as f:
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
