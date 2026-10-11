"""SQLite cache of per-file analysis results, user labels and 3D projections."""
import io
import json
import sqlite3
import threading
from pathlib import Path

import numpy as np

ANALYSIS_VERSION = 4


def _pack(arrays: dict, meta: dict) -> bytes:
    buf = io.BytesIO()
    np.savez(buf, __meta__=np.frombuffer(json.dumps(meta).encode(), dtype=np.uint8), **arrays)
    return buf.getvalue()


def unpack(blob: bytes) -> tuple[dict, dict]:
    with np.load(io.BytesIO(blob), allow_pickle=False) as z:
        meta = json.loads(z["__meta__"].tobytes().decode())
        arrays = {k: z[k] for k in z.files if k != "__meta__"}
    return arrays, meta


class Cache:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY, mtime REAL, size INTEGER, version INTEGER, blob BLOB);
            CREATE TABLE IF NOT EXISTS labels (path TEXT PRIMARY KEY, cls TEXT);
            CREATE TABLE IF NOT EXISTS projections (key TEXT PRIMARY KEY, blob BLOB);
        """)
        self._db.commit()

    def get(self, path: str, mtime: float, size: int):
        with self._lock:
            row = self._db.execute(
                "SELECT blob FROM files WHERE path=? AND mtime=? AND size=? AND version=?",
                (path, mtime, size, ANALYSIS_VERSION)).fetchone()
        return unpack(row[0]) if row else None

    def get_many(self, root: str) -> dict[str, tuple[float, int, bytes]]:
        """Raw cached rows under a folder, in one query: path -> (mtime, size, blob)."""
        prefix = root.rstrip("/") + "/"
        with self._lock:
            rows = self._db.execute(
                "SELECT path, mtime, size, blob FROM files WHERE path >= ? AND path < ? AND version=?",
                (prefix, prefix[:-1] + "0", ANALYSIS_VERSION)).fetchall()
        return {p: (m, s, b) for p, m, s, b in rows}

    def put(self, path: str, mtime: float, size: int, arrays: dict, meta: dict) -> None:
        blob = _pack(arrays, meta)
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?)",
                             (path, mtime, size, ANALYSIS_VERSION, blob))

    def commit(self) -> None:
        with self._lock:
            self._db.commit()

    def labels(self) -> dict[str, str]:
        with self._lock:
            return dict(self._db.execute("SELECT path, cls FROM labels").fetchall())

    def set_label(self, path: str, cls: str | None) -> None:
        with self._lock:
            if cls is None:
                self._db.execute("DELETE FROM labels WHERE path=?", (path,))
            else:
                self._db.execute("INSERT OR REPLACE INTO labels VALUES (?,?)", (path, cls))
            self._db.commit()

    def get_projection(self, key: str):
        with self._lock:
            row = self._db.execute("SELECT blob FROM projections WHERE key=?", (key,)).fetchone()
        return unpack(row[0])[0]["xyz"] if row else None

    def put_projection(self, key: str, xyz: np.ndarray) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO projections VALUES (?,?)",
                             (key, _pack({"xyz": xyz.astype(np.float32)}, {})))
            self._db.commit()
