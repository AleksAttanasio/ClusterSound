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


def _load() -> list[dict]:
    try:
        data = json.loads(_path().read_text())
        return data.get("patterns", []) if isinstance(data, dict) else []
    except (OSError, ValueError):
        return []


def _save(items: list[dict]) -> None:
    tmp = _path().with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "patterns": items}))
    tmp.replace(_path())


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
