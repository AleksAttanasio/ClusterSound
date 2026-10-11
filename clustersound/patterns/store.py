"""User patterns (custom variants) saved as JSON in the app data folder."""
import json
import threading
import time
import uuid

from ..paths import data_dir
from . import model

_lock = threading.Lock()


def _path():
    return data_dir() / "patterns.json"


def _read() -> dict:
    try:
        data = json.loads(_path().read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data: dict) -> None:
    tmp = _path().with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "patterns": data.get("patterns", []),
                               "sequences": data.get("sequences", [])}))
    tmp.replace(_path())


def _load(key: str = "patterns") -> list[dict]:
    return _read().get(key, [])


def _save(items: list[dict], key: str = "patterns") -> None:
    data = _read()
    data[key] = items
    _write(data)


def list_user() -> list[dict]:
    with _lock:
        return _load()


def save(p: dict) -> dict:
    """Insert or update a user pattern; returns it with its id."""
    p = model.validate(p)
    with _lock:
        items = _load()
        if not str(p.get("id", "")).startswith("user:"):
            p["id"] = "user:" + uuid.uuid4().hex[:10]
            p["created"] = time.time()
        p["updated"] = time.time()
        items = [x for x in items if x.get("id") != p["id"]] + [p]
        _save(items)
    return p


def delete(pid: str) -> bool:
    with _lock:
        items = _load()
        kept = [x for x in items if x.get("id") != pid]
        if len(kept) == len(items):
            return False
        _save(kept)
    return True


# ------------------------------------------------------------------ sequences
def list_sequences() -> list[dict]:
    with _lock:
        return _load("sequences")


def save_sequence(seq: dict) -> dict:
    seq = dict(seq)
    with _lock:
        items = _load("sequences")
        if not str(seq.get("id", "")).startswith("seq:"):
            seq["id"] = "seq:" + uuid.uuid4().hex[:10]
            seq["created"] = time.time()
        seq["updated"] = time.time()
        items = [x for x in items if x.get("id") != seq["id"]] + [seq]
        _save(items, "sequences")
    return seq


def delete_sequence(sid: str) -> bool:
    with _lock:
        items = _load("sequences")
        kept = [x for x in items if x.get("id") != sid]
        if len(kept) == len(items):
            return False
        _save(kept, "sequences")
    return True
