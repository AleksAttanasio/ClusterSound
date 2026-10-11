"""Saved 64-pad racks, as JSON in the app data folder."""
import json
import threading
import time
import uuid

from ..paths import data_dir
from . import layouts

_lock = threading.Lock()


def _path():
    return data_dir() / "racks.json"


def _load() -> list[dict]:
    try:
        data = json.loads(_path().read_text())
        return data.get("racks", []) if isinstance(data, dict) else []
    except (OSError, ValueError):
        return []


def _save(items: list[dict]) -> None:
    tmp = _path().with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "racks": items}))
    tmp.replace(_path())


def list_racks() -> list[dict]:
    with _lock:
        return _load()


def save(rack: dict) -> dict:
    """Insert or update a rack; returns it with its id."""
    rack = layouts.validate(rack)
    with _lock:
        items = _load()
        if not str(rack.get("id", "")).startswith("rack:"):
            rack["id"] = "rack:" + uuid.uuid4().hex[:10]
            rack["created"] = time.time()
        rack["updated"] = time.time()
        _save([x for x in items if x.get("id") != rack["id"]] + [rack])
    return rack


def delete(rid: str) -> bool:
    with _lock:
        items = _load()
        kept = [x for x in items if x.get("id") != rid]
        if len(kept) == len(items):
            return False
        _save(kept)
    return True
