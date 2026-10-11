"""Bridge exposed to the web UI through pywebview's js_api."""
import base64
import io
import json
import mimetypes
import os
import subprocess
import threading
import time
import urllib.parse
import webbrowser

import numpy as np
import soundfile as sf

from . import classifier, dynamics, export, taxonomy
from .chords import export as chord_export
from .chords import harmony as chord_harmony
from .chords import melody as chord_melody
from .chords import midi_in as chord_midi_in
from .chords import perform as chord_perform
from .chords import variations as chord_variations
from .chords.library import CATEGORIES as CHORD_CATEGORIES
from .chords.library import DEFAULT_DIR as CHORD_DIR
from .chords.library import ChordLibrary
from .features import TYPES
from .library import Library
from .live import payload as live_payload
from .live import server as live_server
from .online import cache as online_cache
from .online import search as online
from .online.base import LICENSES, OnlineResult
from .online.downloads import DEFAULT_DIR, Downloader, safe_name
from .patterns import ableton as pat_ableton
from .patterns import arrange as pat_arrange
from .patterns import genres as pat_genres
from .patterns import midi as pat_midi
from .patterns import model as pat_model
from .patterns import render as pat_render
from .patterns import store as pat_store
from .paths import data_dir
from .racks import ableton as rack_ableton
from .racks import dynamics_match
from .racks import layouts as rack_layouts
from .racks import select as rack_select
from .racks import store as rack_store

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
        self._protected: dict[str, list[str]] = {}  # owner (pattern, rack) -> cached online files in use
        self._rack_cache: dict = {}
        self._rack_lock = threading.Lock()  # js_api calls run on several threads
        self._chords: ChordLibrary | None = None
        self._recorder = chord_midi_in.Recorder()
        self._live = live_server.Bridge(self._live_stage(), self._resolve, self._describe, self._title)
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

    def similar(self, item_id: int, k: int = 12) -> list[dict]:
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
                "download_dir": s.get("download_dir") or DEFAULT_DIR, "live_port": self._live_port(),
                "live_library": s.get("live_library") or live_payload.USER_LIBRARY}

    def set_setting(self, key: str, value) -> dict:
        if key not in ("freesound_key", "download_dir", "cache_mb", "live_port", "live_library"):
            return self.get_settings()
        if key == "live_port":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return self.get_settings()
            if 1024 <= value <= 65535 and value != self._live_port():
                self._save_settings(live_port=value)
                self._live.stop()
                self.live_start()
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
        if key in ("download_dir", "live_library") and value:
            value = os.path.expanduser(value)
        self._save_settings(**{key: value})
        if key == "live_library":
            self._live.stage = self._live_stage()
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

    def _bus_selection(self, bus_id: str, query: str = "", strict: bool = False) -> tuple[list[dict], list[str]]:
        classes = pat_model.BUS_BY_ID[bus_id][2] if bus_id in pat_model.BUS_BY_ID else []
        q = (query or "").lower().strip()
        rank = {c: i for i, c in enumerate(classes)}
        sel = [it for it in self._lib.items if (it["cls"] in rank if not q else q in it["rel"].lower())]
        if strict:
            ok = {"One-shot"} if bus_id != "bass" else {"One-shot", "Long/Texture"}
            sel = [it for it in sel if it["feats"].get("type") in ok and not classifier.name_scores(it["rel"])[1]]
        return sel, classes

    def _dyn_scores(self, ref_ids) -> np.ndarray | None:
        """Envelope similarity of every library item to the mean of ref_ids (None without a reference)."""
        if not ref_ids or not self._lib.items:
            return None
        D = self._rack_arrays()["dyn"]
        ref = dynamics_match.reference(D, ref_ids)
        return None if ref is None else dynamics_match.scores(D, ref)

    def pattern_candidates(self, bus_id: str, query: str = "", limit: int = 200, strict: bool = False,
                           ref_ids: list | None = None) -> list[dict]:
        """Library samples for a bus: its classes first (by confidence), then the rest if searching.
        strict (auto-fill): never a loop, and drum buses only take one-shots. With ref_ids (samples on the
        other buses) every ref also gets "dyn": how close its envelope is to theirs."""
        sel, classes = self._bus_selection(bus_id, query, strict)
        sc = self._dyn_scores(ref_ids)
        out = [self._library_ref_of(it) for it in self._ranked(sel, classes)[: int(limit)]]
        if sc is not None:
            for r in out:
                r["dyn"] = round(float(sc[r["id"]]), 3)
        return out

    def dynamic_suggestions(self, bus_id: str, ref_ids: list, k: int = 8) -> list[dict]:
        """The bus's samples whose envelope best matches the samples on the other buses."""
        sc = self._dyn_scores(ref_ids)
        if sc is None:
            return []
        exclude = {int(i) for i in ref_ids}
        sel = [it for it in self._bus_selection(bus_id, "", True)[0] if it["id"] not in exclude]
        sel.sort(key=lambda it: -sc[it["id"]])
        return [self._library_ref_of(it) | {"dyn": round(float(sc[it["id"]]), 3)} for it in sel[: int(k)]]

    @staticmethod
    def _ranked(sel: list[dict], classes: list[str]) -> list[dict]:
        """Classes in the given order, one-shots first (a "snare roll" loop is a poor default for a
        snare pad), then confidence."""
        rank = {c: i for i, c in enumerate(classes)}
        return sorted(sel, key=lambda it: (rank.get(it["cls"], 99), it["feats"].get("type") != "One-shot",
                                           bool(classifier.name_scores(it["rel"])[1]), -it["conf"]))

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

    def protect_samples(self, refs: list, owner: str = "pattern") -> None:
        """Online samples used by the open pattern / rack must survive cache pruning."""
        self._protected[owner] = [online_cache.path_for(r["url"]) for r in refs or [] if r and r.get("url")]
        online_cache.protect([p for paths in self._protected.values() for p in paths])

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


    # ================================================================== compose (chord progressions)
    def _chord_lib(self) -> ChordLibrary:
        root = self._settings().get("chord_pack_dir") or CHORD_DIR
        if self._chords is None or self._chords.root != root:
            self._chords = ChordLibrary(root)
        return self._chords

    def compose_init(self) -> dict:
        lib = self._chord_lib()
        return {"dir": lib.root, "exists": lib.exists(), "keys": lib.available_keys() if lib.exists() else [],
                "categories": CHORD_CATEGORIES, "styles": chord_perform.meta(),
                "clipKinds": chord_variations.CLIP_KINDS, "progKinds": chord_variations.PROG_KINDS, "modeKinds": chord_variations.MODE_KINDS,
                "melody": {"densities": chord_melody.DENSITIES, "contours": chord_melody.CONTOURS, "rates": chord_melody.RATES},
                "saved": pat_store.list_progressions()}

    def compose_pick_folder(self, path: str | None = None) -> dict:
        if path is None:
            path = self.pick_folder()
        if path:
            self._save_settings(chord_pack_dir=os.path.expanduser(path))
        return self.compose_init()

    def compose_rescan(self) -> dict:
        self._chord_lib().scan(force=True)
        return self.compose_init()

    def compose_chords(self, tonic: int, mode: str) -> dict:
        return self._chord_lib().chords_for_key(int(tonic), mode)

    @staticmethod
    def _seq_key(seq: dict) -> dict:
        k = seq.get("key") or {}
        return {"tonic": int(k.get("tonic", 0)) % 12, "mode": "minor" if k.get("mode") == "minor" else "major"}

    def _pool(self, seq: dict, related: bool = False) -> list[dict]:
        key = self._seq_key(seq)
        lib = self._chord_lib()
        pool = list(lib.chords_for_key(key["tonic"], key["mode"])["chords"])
        if related or seq.get("keyMode") == "free":
            seen = {(c["root"], tuple(p for p, _ in c["notes"])) for c in pool}
            for k in chord_harmony.related_keys(key):
                for c in lib.chords_for_key(k["tonic"], k["mode"])["chords"]:
                    sig = (c["root"], tuple(p for p, _ in c["notes"]))
                    if sig not in seen:
                        seen.add(sig)
                        pool.append(c)
        return pool

    def compose_suggest(self, seq: dict, after_id: str | None = None, limit: int = 8) -> dict:
        """Next chord after clip after_id (default: the last one), leading into the clip that follows it."""
        key = self._seq_key(seq)
        clips = sorted(seq.get("clips", []), key=lambda c: c["start"])
        i = next((j for j, c in enumerate(clips) if c["id"] == after_id), len(clips) - 1)
        prev = clips[max(0, i - 1):i + 1] if i >= 0 else []
        nxt = clips[i + 1] if 0 <= i + 1 < len(clips) and after_id else None
        out = chord_harmony.suggest(prev, self._pool(seq), key, self._chord_lib().bigrams(key["mode"]), nxt=nxt, limit=limit)
        return {"after": clips[i]["id"] if i >= 0 and clips else None, "items": out}

    def compose_render(self, seq: dict) -> dict:
        key = self._seq_key(seq)
        clips = seq.get("clips", [])
        labels = []
        for c in clips:
            d = chord_harmony.describe(c)
            labels.append({"id": c["id"], **chord_harmony.label(d, key)} if d["notes"] else {"id": c["id"]})
        return {"ppq": chord_perform.PPQ, "events": chord_perform.render(seq), "labels": labels,
                "melody": chord_melody.render(seq)}

    # ---------------------------------------------------------------- melody
    def compose_melody_generate(self, seq: dict, opts: dict | None = None, seed: int = 1) -> list[dict]:
        return chord_melody.generate(seq, self._seq_key(seq), opts or {}, int(seed))

    def compose_harmonize(self, seq: dict, opts: dict | None = None, seed: int = 1) -> dict:
        """Harmony versions for the melody of seq; opts.key == 'auto' detects the key from the melody."""
        opts = opts or {}
        key = self._seq_key(seq)
        if opts.get("key") == "auto":
            key = chord_melody.detect_key(chord_melody.notes_of(seq))
            seq = {**seq, "key": key}
        pool = self._pool(seq, related=bool(opts.get("related")))
        items = chord_melody.harmonize(seq, pool, key, self._chord_lib().bigrams(key["mode"]), opts, int(seed))
        return {"key": key, "items": items}

    def compose_melody_import(self, grid: int = 1) -> dict | None:
        """A melody from a .mid file (all tracks, top line)."""
        import webview
        res = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("MIDI (*.mid;*.midi)",))
        if not res:
            return None
        path = res[0] if isinstance(res, (list, tuple)) else res
        try:
            ppq, spans = pat_midi.read_note_spans(path)
        except Exception as e:
            return {"error": f"File MIDI non leggibile: {e}"}
        notes = chord_melody.from_spans(spans, ppq, max(1, int(grid)))
        return {"name": os.path.splitext(os.path.basename(path))[0], "notes": notes,
                "key": chord_melody.detect_key(notes) if notes else None}

    def compose_vary_clip(self, seq: dict, clip_id: str, kinds: list, seed: int = 1) -> list[dict]:
        key = self._seq_key(seq)
        pool = self._pool(seq)
        return chord_variations.vary_clip(seq, clip_id, kinds, int(seed), pool, key, self._chord_lib().bigrams(key["mode"]))

    def compose_vary_progression(self, seq: dict, kinds: list, amount: float = .5, seed: int = 1) -> list[dict]:
        key = self._seq_key(seq)
        pool = self._pool(seq)
        return chord_variations.vary_progression(seq, kinds, amount, int(seed), pool, key, self._chord_lib().bigrams(key["mode"]))

    def compose_vary_mode(self, mode: dict, kinds: list, amount: float = .5, seed: int = 1) -> list[dict]:
        return chord_variations.vary_mode(mode, kinds, amount, int(seed))

    @staticmethod
    def _prog_title(seq: dict) -> str:
        return f"{seq.get('name') or 'Accordi'} {int(round(seq.get('bpm', 120)))}bpm - {seq.get('bars', 4)} battute"

    def compose_melody_from_live(self, grid: int = 1) -> dict:
        """The last clip sent by the Max for Live device ("Clip → Melodia")."""
        clip = self._live.last_clip()
        if not clip:
            return {"error": "Nessuna clip ricevuta: in Live seleziona una clip MIDI e premi «Clip → Melodia» nel device ClusterSound"}
        ppq = chord_perform.PPQ
        spans = [(round(s * ppq), round((s + d) * ppq), p, v) for p, s, d, v in clip["notes"]]
        notes = chord_melody.from_spans(spans, ppq, max(1, int(grid)))
        return {"name": clip["name"], "notes": notes, "key": chord_melody.detect_key(notes) if notes else None,
                "age": round(time.time() - clip["at"])}

    def compose_midi_inputs(self) -> dict:
        if not self._recorder.available():
            return {"available": False, "ports": [], "hint": chord_midi_in.HINT}
        try:
            return {"available": True, "ports": self._recorder.ports()}
        except Exception as e:
            return {"available": False, "ports": [], "hint": f"MIDI non disponibile: {e}"}

    def compose_record_start(self, port: int = 0) -> dict:
        try:
            self._recorder.start(int(port))
        except Exception as e:
            return {"error": str(e)}
        return {"ok": True}

    def compose_record_stop(self, offset: float, bpm: float, bars: int, grid: int = 1, loop: bool = False) -> dict:
        """The take: offset = seconds from record start to the transport's first beat."""
        notes = self._recorder.stop()
        ppq = chord_perform.PPQ
        spans = chord_midi_in.to_ticks(notes, float(offset), float(bpm), ppq, int(bars) * 4 * ppq if loop else None)
        return {"notes": chord_melody.from_spans(spans, ppq, max(1, int(grid)), keep=True)}

    def compose_export_midi(self, seq: dict, pure: bool = False, parts: str = "both") -> str | None:
        path = self._save_dialog(safe_name(self._prog_title(seq)) + ".mid", ("MIDI (*.mid)",))
        if path:
            chord_export.write(path, seq, pure, parts)
        return path

    def compose_export_versions(self, seqs: list, pure: bool = False, parts: str = "both") -> dict:
        import webview
        os.makedirs(EXPORT_DIR, exist_ok=True)
        res = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=EXPORT_DIR)
        if not res:
            return {"cancelled": True}
        return self._write_versions(res[0] if isinstance(res, (list, tuple)) else res, seqs, pure, parts)

    def _write_versions(self, folder: str, seqs: list, pure: bool, parts: str = "both") -> dict:
        files = []
        for seq in seqs:
            name = safe_name(f"{self._prog_title(seq)} - {seq.get('version', '')}".rstrip(" -"))
            path = os.path.join(folder, name + ".mid")
            chord_export.write(path, seq, pure, parts)
            files.append(path)
        subprocess.run(["open", folder], check=False)
        return {"folder": folder, "files": files}

    def list_progressions(self) -> list[dict]:
        return pat_store.list_progressions()

    def save_progression(self, proj: dict) -> dict:
        return pat_store.save_progression(proj)

    def delete_progression(self, pid: str) -> bool:
        return pat_store.delete_progression(pid)

    # ================================================================== 64-pad racks
    def racks_init(self) -> dict:
        return {**rack_layouts.ui_layouts(), "saved": rack_store.list_racks()}

    def _rack_arrays(self) -> dict:
        """Normalised embeddings and per-item class / type arrays, rebuilt when the library changes."""
        with self._rack_lock:
            return self._rack_arrays_locked()

    def _rack_arrays_locked(self) -> dict:
        lib = self._lib
        c = self._rack_cache
        if c.get("emb") is not lib.emb:
            c.clear()
            c["emb"] = lib.emb
            c["Xn"] = rack_select.l2norm(lib.emb) if len(lib.emb) else lib.emb
        if c.get("version") != (lib.version, len(lib.items)):
            c["version"] = (lib.version, len(lib.items))
            c["cls"] = np.array([it["cls"] for it in lib.items], dtype=object)
            c["oneshot"] = np.array([it["feats"].get("type") == "One-shot" for it in lib.items], bool)
            c["group"] = np.array([f'{it["cls"]}:{it.get("sub", 0)}' for it in lib.items], dtype=object)
            c["dyn"] = dynamics_match.dyn_matrix([it["feats"] for it in lib.items], c["cls"])
        return c

    def _rack_mask(self, seed: int | None, opts: dict) -> np.ndarray | None:
        """Allowed companions: same class as the seed, the group's family, or anything; optionally one-shots only."""
        a = self._rack_arrays()
        mask = np.ones(len(a["cls"]), bool)
        flt = opts.get("filter", "class")
        if flt == "class" and seed is not None:
            mask &= a["cls"] == a["cls"][seed]
        elif flt == "family":
            classes = rack_layouts.family_classes(opts.get("family", "any"))
            if classes:
                mask &= np.isin(a["cls"], classes)
        if opts.get("oneshot", True):
            mask &= a["oneshot"]
        return mask

    def _rack_refs(self, picks: list[tuple[int, float]]) -> list[dict]:
        return [self._library_ref_of(self._lib.items[i]) | {"sim": round(s, 4)} for i, s in picks]

    def rack_browse(self, query: str = "", family: str = "any", limit: int = 300) -> list[dict]:
        """Library samples for the browser: a family's classes and/or a name search."""
        classes = rack_layouts.family_classes(family)
        q = (query or "").lower().strip()
        sel = [it for it in self._lib.items
               if (not classes or it["cls"] in classes) and (not q or q in it["rel"].lower())]
        return [self._library_ref_of(it) for it in self._ranked(sel, classes)[: int(limit)]]

    def rack_fill(self, seed_id: int, count: int, mode: str = "nearest", opts: dict | None = None) -> list[dict]:
        """The seed followed by `count` - 1 companions (most similar first)."""
        opts = opts or {}
        seed = int(seed_id)
        if not 0 <= seed < len(self._lib.items):
            return []
        a = self._rack_arrays()
        picks = rack_select.pick(a["Xn"], seed, int(count) - 1, mode, self._rack_mask(seed, opts),
                                 float(opts.get("variation", 0.3)), set(map(int, opts.get("exclude") or [])),
                                 opts.get("rng_seed"))
        return self._rack_refs([(seed, 1.0)] + picks)

    def rack_trail_fill(self, ids: list, count: int, opts: dict | None = None) -> list[dict]:
        opts = opts or {}
        n = len(self._lib.items)
        ids = [int(i) for i in ids or [] if 0 <= int(i) < n]
        if not ids:
            return []
        a = self._rack_arrays()
        picks = rack_select.trail(a["Xn"], ids, int(count), self._rack_mask(ids[-1], opts),
                                  set(map(int, opts.get("exclude") or [])))
        return self._rack_refs(picks)

    def rack_candidates(self, seed_id: int, k: int = 60, opts: dict | None = None) -> list[dict]:
        """Neighbours of the seed for manual picking."""
        seed = int(seed_id)
        if not 0 <= seed < len(self._lib.items):
            return []
        opts = opts or {}
        a = self._rack_arrays()
        return self._rack_refs(rack_select.neighbours(a["Xn"], seed, int(k), self._rack_mask(seed, opts)))

    def rack_autofill(self, rack: dict, only_empty: bool = True, variation: float = 0.3) -> dict:
        """Fill every (empty) group: seed = best one-shot of its family not used yet, trying a different
        sub-cluster for groups that share a family, then its nearest companions with a little variation."""
        rack = rack_layouts.validate(rack)
        items = self._lib.items
        if not items:
            return rack
        a = self._rack_arrays()
        used = {r["id"] for r in rack["pads"] if r and r.get("kind") == "library"}
        used_subs: dict[str, set] = {}
        settings = rack_layouts.group_settings(rack)
        for g, pads in enumerate(rack_layouts.groups(rack["geometry"])):
            if settings[g]["lock"] or (only_empty and any(rack["pads"][p] for p in pads)):
                continue
            fam = settings[g]["family"]
            classes = rack_layouts.family_classes(fam)
            pool = [it for it in items if (not classes or it["cls"] in classes) and it["id"] not in used
                    and it["feats"].get("type") == "One-shot"]
            if not pool:
                continue
            pool = self._ranked(pool, classes)[:300]
            subs = used_subs.setdefault(fam, set())
            seed = next((it for it in pool if (it["cls"], it.get("sub")) not in subs), pool[0])
            subs.add((seed["cls"], seed.get("sub")))
            opts = {"filter": "family", "family": fam, "oneshot": True}
            picks = rack_select.pick(a["Xn"], seed["id"], len(pads) - 1, "random", self._rack_mask(None, opts),
                                     variation, used | {seed["id"]})
            for p, ref in zip(pads, self._rack_refs([(seed["id"], 1.0)] + picks)):
                rack["pads"][p] = ref
                used.add(ref["id"])
        return rack

    def _random_mask(self, classes: list[str], opts: dict) -> np.ndarray:
        a = self._rack_arrays()
        mask = np.isin(a["cls"], classes) if classes else np.ones(len(a["cls"]), bool)
        if opts.get("oneshot", True):
            mask &= a["oneshot"]
        folder = (opts.get("folder") or "").lower().strip()
        if folder:
            mask &= np.array([folder in it["rel"].lower() for it in self._lib.items], bool)
        mask[[int(i) for i in opts.get("exclude") or [] if 0 <= int(i) < len(mask)]] = False
        margin = opts.get("dyn_margin")
        if margin is not None and float(margin) < 1:
            ref = dynamics_match.reference(a["dyn"], opts.get("dyn_ref"))
            mask = dynamics_match.margin_mask(a["dyn"], ref, mask, float(margin))
        return mask

    def random_refs(self, classes: list[str], count: int, opts: dict | None = None) -> list[dict]:
        """Random samples of the given classes: a random sample group (class + sub-cluster), a random
        seed in it and similar companions. opts: oneshot, folder (path substring), exclude, variation, and
        dyn_ref + dyn_margin (keep only the dyn_margin fraction whose envelope is closest to dyn_ref's)."""
        opts = opts or {}
        if not self._lib.items:
            return []
        a = self._rack_arrays()
        picks = rack_select.random_group(a["Xn"], a["group"], self._random_mask(classes or [], opts), int(count),
                                         float(opts.get("variation", 0.6)), opts.get("rng_seed"))
        return self._rack_refs(picks)

    def rack_randomize(self, rack: dict, only_empty: bool = False, opts: dict | None = None) -> dict:
        """Every unlocked (or every empty) group: random samples from a random group of its family.
        With opts["dyn_margin"] each group's envelopes stay close to the groups kept or generated before it."""
        opts = dict(opts or {})
        rack = rack_layouts.validate(rack)
        settings = rack_layouts.group_settings(rack)
        groups = rack_layouts.groups(rack["geometry"])
        used = {r["id"] for g, pads in enumerate(groups) if settings[g]["lock"] or only_empty
                for p in pads if (r := rack["pads"][p]) and r.get("kind") == "library"}
        for g, pads in enumerate(groups):
            if settings[g]["lock"] or (only_empty and any(rack["pads"][p] for p in pads)):
                continue
            refs = self.random_refs(rack_layouts.family_classes(settings[g]["family"]), len(pads),
                                    {**opts, "exclude": list(used), "dyn_ref": list(used)})
            for p, ref in zip(pads, refs + [None] * len(pads)):
                rack["pads"][p] = ref
            used |= {r["id"] for r in refs}
        return rack

    def list_racks(self) -> list[dict]:
        return rack_store.list_racks()

    def save_rack(self, rack: dict) -> dict:
        return rack_store.save(rack)

    def delete_rack(self, rid: str) -> bool:
        return rack_store.delete(rid)

    def export_rack(self, rack: dict) -> dict:
        import webview
        os.makedirs(EXPORT_DIR, exist_ok=True)
        res = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=EXPORT_DIR)
        if not res:
            return {"cancelled": True}
        root = res[0] if isinstance(res, (list, tuple)) else res
        try:
            folder = rack_ableton.export_rack(rack, root, self._resolve, self._describe)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        subprocess.run(["open", folder], check=False)
        return {"folder": folder}

    # ================================================================== Ableton Live (Max for Live bridge)
    def _live_stage(self) -> live_payload.Stage:
        """Presets for Live go to the User Library (always indexed by Live's browser), else to Places."""
        return live_payload.Stage.default(EXPORT_DIR, self._settings().get("live_library"))

    def _live_port(self) -> int:
        return int(self._settings().get("live_port") or live_server.DEFAULT_PORT)

    def live_start(self) -> dict:
        """Start the localhost bridge for the Max for Live device (app start, or after a port change)."""
        if not self._live.server:
            self._live.error = None
            self._live.start(self._live_port())
        return self.live_status()

    def live_status(self) -> dict:
        return {"running": self._live.server is not None, "port": self._live.port or self._live_port(),
                "error": self._live.error, "pending": self._live.pending(),
                "stage": os.path.join(self._live.stage.base, self._live.stage.sub), "stage_root": self._live.stage.root}

    def live_set_kit(self, p: dict) -> None:
        """The Sequencer reports its kit, used for saved sequences that do not carry one."""
        live_server.save_current_kit(p)

    def live_send(self, kind: str, data: dict, opts: dict | None = None) -> dict:
        """Build the payload of what is open in the UI and queue it for the device in Live ("Invia a Live")."""
        try:
            item = self._live.build(kind, data, **(opts or {}))
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        return {"queued": self._live.push(item), "name": item["name"],
                "tracks": [t["name"] for t in item["tracks"]], **self.live_status()}


def _media_data_url(path: str) -> str | None:
    out = _wav_data_url(path)
    if out is None:  # a format libsndfile can't read: hand the bytes to the web view
        mime = mimetypes.guess_type(path)[0] or "audio/mpeg"
        with open(path, "rb") as f:
            out = f"data:{mime};base64," + base64.b64encode(f.read()).decode()
    return out
