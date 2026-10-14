"""Library scan: walk a folder, analyse every sample (cached), classify, cluster, lay out in 3D."""
import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import audio_io, classifier, clustering, embedder, features, projection, snapshot
from .cache import Cache, unpack
from .i18n import tr
from .paths import data_dir

EMBED_SECONDS = 10.0
AUDIO_EXT = {".wav", ".wave", ".aif", ".aiff", ".aifc", ".flac", ".ogg", ".oga", ".mp3", ".caf", ".w64"}


def scan_files(root: str) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and not d.endswith(".app"))
        for fn in sorted(filenames):
            if fn.startswith(".") or fn.startswith("._"):
                continue
            if os.path.splitext(fn)[1].lower() in AUDIO_EXT:
                out.append(os.path.join(dirpath, fn))
    return out


def analyse_file(path: str) -> tuple[dict, dict]:
    """Decode + features + YAMNet. Returns (arrays, meta) ready for the cache."""
    inf = audio_io.info(path)
    x, sr = audio_io.load_mono(path)
    x = audio_io.trim_silence(x, sr)
    x16 = audio_io.resample(x, sr, 16000)
    xf = audio_io.resample(x, sr, features.FEAT_SR)
    if x16.size and np.max(np.abs(x16)) > 0:
        x16 = x16 / np.max(np.abs(x16)) * 0.9  # loudness-normalise for the network
    # the network sees at most EMBED_SECONDS (loops repeat themselves; this bounds the cost)
    x16 = x16[: int(EMBED_SECONDS * 16000)]
    emb = embedder.embed(x16)
    feats = features.compute(xf, features.FEAT_SR)
    arrays = {
        "embedding": emb["embedding"].astype(np.float16),
        "profile": features.mel_profile(emb["mel"], len(x16) // 160 + 1).astype(np.float16),
        "scores_max": emb["scores_max"].astype(np.float16),
        "scores_mean": emb["scores_mean"].astype(np.float16),
    }
    meta = {"feats": feats, "info": {"samplerate": inf.samplerate, "channels": inf.channels,
                                     "frames": inf.frames, "subtype": inf.subtype,
                                     "format": inf.format, "duration": inf.duration}}
    return arrays, meta


def head_features(emb: np.ndarray, prof: np.ndarray, feats: list[dict]) -> np.ndarray:
    """Fixed (library-independent) input of the classifier heads: 1024 + 144 + 22 values."""
    F = np.array([features.vector(f) for f in feats], np.float32).reshape(len(feats), -1)
    return np.hstack([clustering.l2norm(emb), prof, F]).astype(np.float32)


class Library:
    def __init__(self, cache: Cache | None = None):
        self.cache = cache or Cache(data_dir() / "cache.sqlite")
        self.root: str | None = None
        self.items: list[dict] = []
        self.X: np.ndarray = np.zeros((0, 0), np.float32)
        self.emb: np.ndarray = np.zeros((0, 1024), np.float32)
        self.xyz: np.ndarray = np.zeros((0, 3), np.float32)
        self.layout_kind = "none"
        self.stats: dict = {}
        self.errors: list[dict] = []
        self.progress = {"phase": "idle", "done": 0, "total": 0, "message": ""}
        self.version = 0  # bumps every time results change (UI polls it)
        self._lock = threading.RLock()
        self._scan_thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._files_sig: str | None = None  # snapshot signature of the scanned folder

    # ------------------------------------------------------------------ scanning
    def start_scan(self, root: str, snapshot_only: bool = False) -> None:
        if self._scan_thread and self._scan_thread.is_alive():
            self._cancel.set()
            self._scan_thread.join()
        self._cancel.clear()
        self._scan_thread = threading.Thread(target=self.scan, args=(root, snapshot_only), daemon=True)
        self._scan_thread.start()

    def _set_progress(self, phase, done=0, total=0, message=""):
        self.progress = {"phase": phase, "done": done, "total": total, "message": message}

    def scan(self, root: str, snapshot_only: bool = False) -> None:
        """Full scan; with snapshot_only, just restore an up-to-date snapshot (phase 'stale' if none)."""
        try:
            self._scan(root, snapshot_only)
        except Exception as e:  # surface to the UI instead of dying silently
            self._set_progress("error", message=f"{type(e).__name__}: {e}")
            raise

    def _scan(self, root: str, snapshot_only: bool = False) -> None:
        root = os.path.abspath(os.path.expanduser(root))
        listing = self._list(root)
        if self._load_snapshot(root, listing):
            self._set_progress("layout", 0, 0, tr("3D layout…"))
            self.compute_layout()
            n = len(self.items)
            self._set_progress("done", n, n, tr("{n} samples, {errors} errors · from snapshot", n=n, errors=len(self.errors)))
            return
        if snapshot_only:
            self._set_progress("stale", message=tr("No up-to-date snapshot for this folder: press Rescan"))
            return
        if not self.scan_analysis_only(root, listing):
            return
        self._set_progress("classifying", 0, 0, tr("Classification…"))
        self.reclassify()
        self._set_progress("layout", 0, 0, tr("3D layout…"))
        self.compute_layout()
        n = len(self.items)
        self._set_progress("done", n, n, tr("{n} samples, {errors} errors", n=n, errors=len(self.errors)))

    def _list(self, root: str) -> list[tuple[str, os.stat_result | None]]:
        self._set_progress("scanning", message=tr("Finding audio files…"))
        listing = []
        for p in scan_files(root):
            try:
                listing.append((p, os.stat(p)))
            except OSError:
                listing.append((p, None))
        return listing

    def _load_snapshot(self, root: str, listing) -> bool:
        files_sig = snapshot.files_signature(root, listing)
        paths = [p for p, _ in listing]
        snap = snapshot.load(self._snapshot_dir(), root,
                             snapshot.fingerprint(files_sig, paths, self.cache.labels()))
        if snap is None:
            return False
        a = snap["arrays"]
        with self._lock:
            self.root = root
            self.items = snap["items"]
            self.errors = snap["errors"]
            self.stats = snap["stats"]
            self.emb = a["emb"].reshape(-1, 1024)
            self.prof = a["prof"].reshape(len(self.items), -1)
            self.X = self._head_features()
            self.probs = a.get("probs")
            self._files_sig = files_sig
            self.version += 1
        return True

    def _snapshot_dir(self) -> Path:
        return self.cache.path.parent / "snapshots"

    def _save_snapshot(self) -> None:
        if not self._files_sig or self.root is None:
            return
        try:
            paths = [it["path"] for it in self.items] + [e["path"] for e in self.errors]
            fp = snapshot.fingerprint(self._files_sig, paths, self.cache.labels())
            snapshot.save(self._snapshot_dir(), self.root, fp, self.items, {
                "emb": self.emb, "prof": self.prof, "probs": self.probs,
                "scores_max": np.array([it["scores_max"] for it in self.items]).reshape(len(self.items), -1),
                "scores_mean": np.array([it["scores_mean"] for it in self.items]).reshape(len(self.items), -1),
            }, self.stats, self.errors)
        except Exception as e:  # a missing snapshot only costs speed next time
            print("snapshot not saved:", type(e).__name__, e)

    def scan_analysis_only(self, root: str, listing=None) -> bool:
        """Walk + analyse (with cache). Returns False if cancelled."""
        root = os.path.abspath(os.path.expanduser(root))
        if listing is None:
            listing = self._list(root)
        total = len(listing)
        self._set_progress("analysing", 0, total)
        results: list[tuple[str, dict, dict] | None] = [None] * total
        errors = []
        done = 0
        todo = []
        rows = self.cache.get_many(root)
        for i, (p, st) in enumerate(listing):
            if st is None:
                errors.append({"path": p, "error": tr("unreadable file")})
                continue
            row = rows.get(p)
            if row is not None and row[0] == st.st_mtime and row[1] == st.st_size:
                results[i] = (p, *unpack(row[2]))
                done += 1
            else:
                todo.append((i, p, st))
        del rows
        self._set_progress("analysing", done, total, tr("{n} in cache", n=done))

        def work(job):
            i, p, st = job
            if self._cancel.is_set():
                return i, p, st, None, "cancelled"
            try:
                return i, p, st, analyse_file(p), None
            except Exception as e:
                return i, p, st, None, f"{type(e).__name__}: {e}"

        t0 = time.time()
        with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as ex:
            for i, p, st, res, err in ex.map(work, todo):
                done += 1
                if err:
                    if err != "cancelled":
                        errors.append({"path": p, "error": err})
                else:
                    arrays, meta = res
                    self.cache.put(p, st.st_mtime, st.st_size, arrays, meta)
                    results[i] = (p, arrays, meta)
                if done % 25 == 0 or done == total:
                    rate = (done - (total - len(todo))) / max(time.time() - t0, 1e-3)
                    self._set_progress("analysing", done, total, f"{rate:.0f} file/s")
                if done % 200 == 0:
                    self.cache.commit()
        self.cache.commit()
        if self._cancel.is_set():
            self._set_progress("idle", message=tr("Scan cancelled"))
            return False

        items, embs, profs = [], [], []
        for r in results:
            if r is None:
                continue
            p, arrays, meta = r
            rel = os.path.relpath(p, root)
            items.append({
                "id": len(items), "path": p, "rel": rel.replace(os.sep, "/"),
                "name": os.path.basename(p), "feats": meta["feats"], "info": meta["info"],
                "scores_max": arrays["scores_max"].astype(np.float32),
                "scores_mean": arrays["scores_mean"].astype(np.float32),
            })
            embs.append(arrays["embedding"].astype(np.float32))
            profs.append(arrays["profile"].astype(np.float32))
        with self._lock:
            self.root = root
            self.items = items
            self.errors = errors
            self.emb = np.array(embs, np.float32).reshape(-1, 1024)
            self.prof = (np.array(profs, np.float32).reshape(len(items), -1) if items
                         else np.zeros((0, 144), np.float32))
            self.X = self._head_features()
            self.probs = None
            self._files_sig = snapshot.files_signature(root, listing)
        return True

    def _head_features(self) -> np.ndarray:
        if not self.items:
            return np.zeros((0, 1), np.float32)
        return head_features(self.emb, self.prof, [it["feats"] for it in self.items])

    # --------------------------------------------------------- classification
    def reclassify(self) -> None:
        with self._lock:
            items = self.items
            labels = self.cache.labels()
            for it in items:
                # loop/one-shot type also listens to the file name
                _, loop = classifier.name_scores(it["rel"])
                f = it["feats"]
                if loop and f.get("duration", 0) > 1.0:
                    f["type"] = "Loop"
            res = classifier.classify(items, self.X, labels)
            self.probs = res.pop("probs", None)
            self.stats = res
            self._subclusters()
            self.version += 1
            self._save_snapshot()

    def _subclusters(self) -> None:
        by_cls: dict[str, list[int]] = {}
        for it in self.items:
            by_cls.setdefault(it["cls"], []).append(it["id"])
        for cls, ids in by_cls.items():
            lab = clustering.subclusters(self.emb[ids])
            for i, l in zip(ids, lab):
                self.items[i]["sub"] = int(l) + 1

    def relabel(self, item_id: int, cls: str | None) -> None:
        it = self.items[item_id]
        self.cache.set_label(it["path"], cls)
        self.reclassify()

    # ---------------------------------------------------------------- layout
    def _layout_input(self) -> np.ndarray:
        E = projection.pca(clustering.l2norm(self.emb), min(30, max(1, len(self.emb) - 1)))
        E /= (np.sqrt((E ** 2).sum(1)).mean() + 1e-9)
        P = self.probs if self.probs is not None else np.zeros((len(E), 0))
        return np.hstack([E, 0.8 * P]).astype(np.float32)

    def _layout_key(self) -> str:
        h = hashlib.sha1()
        h.update((self.root or "").encode())
        for it in self.items:
            h.update(it["path"].encode())
        return h.hexdigest()

    def compute_layout(self) -> None:
        if not self.items:
            self.xyz = np.zeros((0, 3), np.float32)
            return
        key = self._layout_key()
        cached = self.cache.get_projection(key)
        if cached is not None and len(cached) == len(self.items):
            self.xyz, self.layout_kind = cached, "tsne"
            self.version += 1
            return
        Xl = self._layout_input()
        self.xyz, self.layout_kind = projection.quick_layout(Xl), "pca"
        self.version += 1

        def prog(f):
            self._set_progress("layout", int(f * 100), 100, tr("3D layout (t-SNE)…"))

        xyz = projection.layout(Xl, progress=prog)
        self.cache.put_projection(key, xyz)
        self.xyz, self.layout_kind = xyz, "tsne"
        self.version += 1

    # ---------------------------------------------------------------- queries
    def public_items(self) -> list[dict]:
        out = []
        for it in self.items:
            xyz = self.xyz[it["id"]] if len(self.xyz) == len(self.items) else (0, 0, 0)
            out.append({
                "id": it["id"], "name": it["name"], "rel": it["rel"],
                "dur": round(float(it["info"].get("duration", 0.0)), 3),
                "cls": it["cls"], "conf": it["conf"], "user": it.get("user", False),
                "sub": it.get("sub", 1), "type": it["feats"].get("type", "One-shot"),
                "alts": it.get("alts", []),
                "x": round(float(xyz[0]), 2), "y": round(float(xyz[1]), 2), "z": round(float(xyz[2]), 2),
            })
        return out

    def similar(self, item_id: int, k: int = 12) -> list[dict]:
        """The k nearest items in embedding space, most similar first, with cosine similarity."""
        if len(self.emb) <= 1:
            return []
        ids, sims = clustering.knn(self.emb, item_id, k, return_sims=True)
        return [{"id": int(i), "sim": float(s)} for i, s in zip(ids, sims)]


__all__ = ["Library", "scan_files", "analyse_file", "Path"]
