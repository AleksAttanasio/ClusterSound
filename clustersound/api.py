"""Bridge exposed to the web UI through pywebview's js_api."""
import base64
import io
import json
import mimetypes
import os
import subprocess
import threading
import urllib.parse
import webbrowser

import numpy as np
import soundfile as sf

from . import classifier, dynamics, export, taxonomy
from .features import TYPES
from .library import Library
from .online import cache as online_cache
from .online import search as online
from .online.base import LICENSES, OnlineResult
from .online.downloads import DEFAULT_DIR, Downloader
from .patterns import ableton as pat_ableton
from .patterns import arrange as pat_arrange
from .patterns import genres as pat_genres
from .patterns import midi as pat_midi
from .patterns import model as pat_model
from .patterns import render as pat_render
from .patterns import store as pat_store
from .paths import data_dir

PREVIEW_MAX_SECONDS = 60
EXPORT_DIR = os.path.expanduser("~/Music/ClusterSound Patterns")
AUDIO_TYPES = ("Audio (*.wav;*.aif;*.aiff;*.flac;*.mp3;*.ogg)",)


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
        threading.Thread(target=online_cache.prune, args=(self._cache_mb(),), daemon=True).start()

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

    def restore(self, path: str) -> bool:
        """At startup: show the last folder from its snapshot, without re-analysing it."""
        if not path or not os.path.isdir(path):
            return False
        self._lib.start_scan(path, snapshot_only=True)
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
        return {"freesound_key_set": bool(key), "cache_mb": self._cache_mb(),
                "cache_used_mb": round(online_cache.size() / (1 << 20), 1),
                "freesound_key_hint": (key[:4] + "…" + key[-3:]) if len(key) > 8 else "",
                "download_dir": s.get("download_dir") or DEFAULT_DIR}

    def set_setting(self, key: str, value) -> dict:
        if key not in ("freesound_key", "download_dir", "cache_mb"):
            return self.get_settings()
        if key == "cache_mb":
            try:
                value = max(50, min(10000, int(value)))
            except (TypeError, ValueError):
                return self.get_settings()
            self._save_settings(cache_mb=value)
            online_cache.prune(value)
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
        """Fetch (into the bounded temporary cache) a result's audio, as a playable data URL."""
        r = online.get(uid)
        url = r and (r.preview_url or r.download_url)
        if not url:
            return None
        path = online_cache.ensure(url, self._cache_mb())
        return _media_data_url(path) if path else None

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


    def _cache_mb(self) -> int:
        return int(self._settings().get("cache_mb") or online_cache.DEFAULT_MAX_MB)

    def clear_cache(self) -> dict:
        online_cache.clear()
        return self.get_settings()

    # ================================================================== patterns
    def patterns_init(self) -> dict:
        return {"genres": pat_genres.catalog(), "groups": pat_genres.GROUPS, "buses": pat_model.ui_buses(),
                "user": pat_store.list_user(), "sequences": pat_store.list_sequences(),
                "note_names": pat_model.NOTE_NAMES}

    def pattern_build(self, genre_id: str, variant: int) -> dict:
        return pat_genres.build(genre_id, int(variant))

    def pattern_candidates(self, bus_id: str, query: str = "", limit: int = 200, strict: bool = False) -> list[dict]:
        """Library samples for a bus: its classes first (by confidence), then the rest if searching.
        strict (auto-fill): never a loop, and drum buses only take one-shots."""
        classes = pat_model.BUS_BY_ID[bus_id][2] if bus_id in pat_model.BUS_BY_ID else []
        q = (query or "").lower().strip()
        items = self._lib.items
        rank = {c: i for i, c in enumerate(classes)}
        sel = [it for it in items if (it["cls"] in rank if not q else q in it["rel"].lower())]
        if strict:
            ok = {"One-shot"} if bus_id != "bass" else {"One-shot", "Long/Texture"}
            sel = [it for it in sel if it["feats"].get("type") in ok and not classifier.name_scores(it["rel"])[1]]
        # one-shots first (a "snare roll" loop is a poor default for a snare pad), then confidence
        sel.sort(key=lambda it: (rank.get(it["cls"], 99), it["feats"].get("type") != "One-shot",
                                 bool(classifier.name_scores(it["rel"])[1]), -it["conf"]))
        return [self._library_ref_of(it) for it in sel[: int(limit)]]

    def _library_ref_of(self, it: dict) -> dict:
        f = it["feats"]
        root = None
        if f.get("f0") and f.get("harmonicity", 0) > 0.5:
            root = round(69 + 12 * np.log2(f["f0"] / 440.0))
        return {"kind": "library", "id": it["id"], "path": it["path"], "name": it["name"], "cls": it["cls"],
                "conf": it["conf"], "dur": round(float(it["info"].get("duration", 0)), 3), "root": root,
                "type": f.get("type")}

    def library_ref(self, item_id: int) -> dict:
        return self._library_ref_of(self._lib.items[int(item_id)])

    def online_ref(self, uid: str) -> dict | None:
        r = online.get(uid)
        url = r and (r.preview_url or r.download_url)
        if not url:
            return None
        return {"kind": "online", "uid": uid, "url": url, "name": r.path.rsplit("/", 1)[-1] if r.path else r.title,
                "cls": r.instrument, "source_label": r.source_label, "license": r.license,
                "license_label": LICENSES.get(r.license, LICENSES["unknown"])["label"], "author": r.author,
                "license_url": r.license_url, "page_url": r.page_url, "download_note": r.download_note,
                "title": r.title, "root": None}

    def pick_sample_file(self) -> dict | None:
        import webview
        res = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=AUDIO_TYPES)
        if not res:
            return None
        path = res[0] if isinstance(res, (list, tuple)) else res
        return {"kind": "file", "path": path, "name": os.path.basename(path), "cls": None, "root": None}

    def _resolve(self, ref: dict | None) -> str | None:
        """Local file for a sample ref (online samples come from the temporary cache)."""
        if not ref:
            return None
        if ref.get("kind") == "online":
            return online_cache.ensure(ref["url"], self._cache_mb()) if ref.get("url") else None
        path = ref.get("path")
        return path if path and os.path.isfile(path) else None

    def _describe(self, ref: dict) -> OnlineResult | None:
        if not ref or ref.get("kind") != "online":
            return None
        return OnlineResult(uid=ref.get("uid", ""), source="online", source_label=ref.get("source_label", ""),
                            title=ref.get("title") or ref.get("name", ""), author=ref.get("author", ""),
                            license=ref.get("license", "unknown"), license_url=ref.get("license_url", ""),
                            page_url=ref.get("page_url", ""), download_url=ref.get("url"),
                            download_note=ref.get("download_note", ""))

    def sample_audio(self, ref: dict) -> str | None:
        path = self._resolve(ref)
        return _media_data_url(path) if path else None

    def sample_root(self, ref: dict) -> int | None:
        """MIDI note of a (tonal) sample, for tuning bass layers."""
        if ref and ref.get("root") is not None:
            return ref["root"]
        path = self._resolve(ref)
        if not path:
            return None
        from . import audio_io, features
        try:
            x, sr = audio_io.load_mono(path, max_seconds=3)
            x = audio_io.resample(audio_io.trim_silence(x, sr), sr, features.FEAT_SR)
            harm, f0 = features._harmonicity(x, features.FEAT_SR)
        except Exception:
            return None
        return round(69 + 12 * np.log2(f0 / 440.0)) if f0 and harm > 0.4 else None

    def protect_samples(self, refs: list) -> None:
        """Online samples used by the open pattern must survive cache pruning."""
        online_cache.protect([online_cache.path_for(r["url"]) for r in refs or [] if r and r.get("url")])

    def sequence_flatten(self, kit: dict, seq: dict) -> dict:
        try:
            return pat_arrange.flatten(kit, seq)
        except ValueError as e:
            return {"error": str(e)}

    def list_sequences(self) -> list[dict]:
        return pat_store.list_sequences()

    def save_sequence(self, seq: dict) -> dict:
        return pat_store.save_sequence(seq)

    def delete_sequence(self, sid: str) -> bool:
        return pat_store.delete_sequence(sid)

    def save_user_pattern(self, p: dict) -> dict:
        return pat_store.save(p)

    def delete_user_pattern(self, pid: str) -> bool:
        return pat_store.delete(pid)

    def _save_dialog(self, filename: str, types: tuple) -> str | None:
        import webview
        os.makedirs(EXPORT_DIR, exist_ok=True)
        res = self._window.create_file_dialog(webview.FileDialog.SAVE, directory=EXPORT_DIR,
                                              save_filename=filename, file_types=types)
        if not res:
            return None
        return res[0] if isinstance(res, (list, tuple)) else res

    @staticmethod
    def _title(p: dict) -> str:
        if p.get("sections"):
            return f"{p.get('name') or 'Sequenza'} {int(round(p.get('bpm', 120)))}bpm - {p['bars']} battute"
        g = pat_genres.GENRE_BY_ID.get(p.get("genre"), {})
        return f"{g.get('name', 'Pattern')} - {p.get('name', 'Main')} {int(round(p.get('bpm', 120)))}bpm"

    def export_midi(self, p: dict, mapping: str = "drumrack") -> str | None:
        path = self._save_dialog(self._title(p) + ".mid", ("MIDI (*.mid)",))
        if path:
            pat_midi.write(path, p, "both", "gm" if mapping == "gm" else "drumrack")
        return path

    def export_wav(self, p: dict) -> str | None:
        path = self._save_dialog(self._title(p) + ".wav", ("WAV (*.wav)",))
        if path:
            pat_render.write_wav(path, p, self._resolve)
        return path

    def export_ableton(self, p: dict) -> dict:
        import webview
        os.makedirs(EXPORT_DIR, exist_ok=True)
        res = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=EXPORT_DIR)
        if not res:
            return {"cancelled": True}
        root = res[0] if isinstance(res, (list, tuple)) else res
        try:
            folder = pat_ableton.export_package(p, root, self._resolve, self._describe, self._title(p))
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        subprocess.run(["open", folder], check=False)
        return {"folder": folder}


def _media_data_url(path: str) -> str | None:
    out = _wav_data_url(path)
    if out is None:  # a format libsndfile can't read: hand the bytes to the web view
        mime = mimetypes.guess_type(path)[0] or "audio/mpeg"
        with open(path, "rb") as f:
            out = f"data:{mime};base64," + base64.b64encode(f.read()).decode()
    return out
