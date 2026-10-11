"""Per-folder snapshot of a finished scan (items, classes, sub-clusters, arrays).

Reopening an unchanged folder loads it in one read instead of unpacking every cached file,
retraining the head and re-running the sub-clustering. Valid only while the fingerprint
(files + mtimes + sizes, user labels, analysis/model versions) matches.
"""
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from .cache import ANALYSIS_VERSION
from .paths import resource_path

SNAPSHOT_VERSION = 1
KEEP = 5  # most recently used folders kept on disk
ARRAYS = ("emb", "prof", "probs", "scores_max", "scores_mean")


def files_signature(root: str, listing: list[tuple[str, os.stat_result | None]]) -> str:
    """Hash of everything on disk the scan depends on (not the user labels)."""
    h = hashlib.sha1()
    base = resource_path("models/base_head.npz")
    try:
        st = base.stat()
        h.update(f"{st.st_mtime}:{st.st_size}".encode())
    except OSError:
        h.update(b"no-base-head")
    h.update(f"{SNAPSHOT_VERSION}:{ANALYSIS_VERSION}:{root}\n".encode())
    for p, st in listing:
        h.update(f"{p}\0{st.st_mtime}\0{st.st_size}\n".encode() if st else f"{p}\0err\n".encode())
    return h.hexdigest()


def fingerprint(files_sig: str, paths: list[str], labels: dict[str, str]) -> str:
    h = hashlib.sha1(files_sig.encode())
    for p in sorted(labels.keys() & set(paths)):
        h.update(f"{p}\0{labels[p]}\n".encode())
    return h.hexdigest()


def _file(dirpath: Path, root: str) -> Path:
    return dirpath / f"{hashlib.sha1(root.encode()).hexdigest()}.npz"


def save(dirpath: Path, root: str, fp: str, items: list[dict], arrays: dict, stats: dict,
         errors: list[dict]) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    meta = {"fingerprint": fp, "root": root, "stats": stats, "errors": errors,
            "items": [{k: v for k, v in it.items() if k not in ("scores_max", "scores_mean")}
                      for it in items]}
    out = {k: np.asarray(arrays[k], np.float16) for k in ARRAYS if arrays.get(k) is not None}
    dst = _file(dirpath, root)
    tmp = dst.with_suffix(".tmp.npz")
    np.savez(tmp, __meta__=np.frombuffer(json.dumps(meta).encode(), dtype=np.uint8), **out)
    os.replace(tmp, dst)
    _prune(dirpath)


def load(dirpath: Path, root: str, fp: str) -> dict | None:
    """Snapshot for `root` if its fingerprint matches, else None (missing/stale/corrupt)."""
    path = _file(dirpath, root)
    if not path.exists():
        return None
    try:
        with np.load(path, allow_pickle=False) as z:
            meta = json.loads(z["__meta__"].tobytes().decode())
            if meta.get("fingerprint") != fp:
                return None
            arrays = {k: z[k].astype(np.float32) for k in ARRAYS if k in z.files}
    except Exception:
        return None
    os.utime(path)  # recency for pruning
    for i, it in enumerate(meta["items"]):
        it["scores_max"] = arrays["scores_max"][i]
        it["scores_mean"] = arrays["scores_mean"][i]
    return {**meta, "arrays": arrays}


def _prune(dirpath: Path) -> None:
    snaps = sorted(dirpath.glob("*.npz"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in snaps[KEEP:]:
        p.unlink(missing_ok=True)
