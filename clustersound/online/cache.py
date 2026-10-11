"""Temporary on-disk cache for online audio (previews and samples tried in the sequencer).

Bounded in size (LRU by access time); files the open pattern uses are protected from pruning.
Nothing here is permanent: samples become real files only when a pattern is exported.
"""
import hashlib
import os
import threading
import time
import urllib.request

from .base import USER_AGENT
from .downloads import host_allowed

CACHE_DIR = os.path.expanduser("~/Library/Caches/ClusterSound/previews")
DEFAULT_MAX_MB = 300
MAX_FILE_BYTES = 60 << 20

_lock = threading.Lock()
_protected: set[str] = set()


def path_for(url: str) -> str:
    ext = os.path.splitext(url.split("?")[0])[1][:6] or ".bin"
    return os.path.join(CACHE_DIR, hashlib.sha1(url.encode()).hexdigest() + ext)


def fetch(url: str, limit: int = MAX_FILE_BYTES) -> bytes | None:
    if not host_allowed(url):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if not host_allowed(r.geturl()):
                return None
            data = r.read(limit + 1)
    except Exception:
        return None
    return data if len(data) <= limit else None


def ensure(url: str, max_mb: float | None = None) -> str | None:
    """Local path of url's content, downloading it into the cache if needed."""
    path = path_for(url)
    if os.path.exists(path):
        os.utime(path)  # LRU: mark as recently used
        return path
    data = fetch(url)
    if data is None:
        return None
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    prune(max_mb)
    return path


def protect(paths) -> None:
    """Files used by the open pattern: never pruned (replaces the previous set)."""
    with _lock:
        _protected.clear()
        _protected.update(os.path.realpath(p) for p in paths if p)


def _files() -> list[tuple[float, int, str]]:
    if not os.path.isdir(CACHE_DIR):
        return []
    out = []
    for name in os.listdir(CACHE_DIR):
        p = os.path.join(CACHE_DIR, name)
        try:
            st = os.stat(p)
        except OSError:
            continue
        if name.endswith(".part") and time.time() - st.st_mtime < 3600:
            continue
        out.append((st.st_mtime, st.st_size, p))
    return out


def size() -> int:
    return sum(s for _, s, _ in _files())


def prune(max_mb: float | None = None) -> int:
    """Delete least recently used files until the cache fits; returns bytes freed."""
    limit = int((max_mb or DEFAULT_MAX_MB) * (1 << 20))
    files = sorted(_files())
    total = sum(s for _, s, _ in files)
    freed = 0
    with _lock:
        prot = set(_protected)
    for _, s, p in files:
        if total <= limit:
            break
        if os.path.realpath(p) in prot:
            continue
        try:
            os.remove(p)
        except OSError:
            continue
        total -= s
        freed += s
    return freed


def clear() -> int:
    """Remove every unprotected file."""
    freed = 0
    with _lock:
        prot = set(_protected)
    for _, s, p in _files():
        if os.path.realpath(p) in prot:
            continue
        try:
            os.remove(p)
            freed += s
        except OSError:
            pass
    return freed
