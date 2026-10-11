"""Parallel search across sources, normalisation and the client-side half of the filters."""
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from . import archive, ccmixter, freesound, openverse
from . import instruments as inst
from .base import LICENSE_GROUPS, OnlineResult, SourceError

SOURCES = OrderedDict([("freesound", freesound), ("openverse", openverse),
                       ("archive", archive), ("ccmixter", ccmixter)])
LABELS = {k: m.LABEL for k, m in SOURCES.items()}
LOSSLESS = {"wav", "wave", "aif", "aiff", "flac"}
ALL_FILTERS = ["instrument", "license", "commercial", "type", "duration", "bpm", "key", "lossless", "packs", "sort"]

_registry: "OrderedDict[str, OnlineResult]" = OrderedDict()
_reg_lock = threading.Lock()


def remember(results: list[OnlineResult]) -> None:
    with _reg_lock:
        for r in results:
            _registry[r.uid] = r
            _registry.move_to_end(r.uid)
        while len(_registry) > 20000:
            _registry.popitem(last=False)


def get(uid: str) -> OnlineResult | None:
    with _reg_lock:
        return _registry.get(uid)


def server_filters() -> dict[str, list[str]]:
    """For each filter: which sources apply it server-side (the rest is filtered here)."""
    return {f: [k for k, m in SOURCES.items() if f in m.SERVER_FILTERS] for f in ALL_FILTERS}


def enrich(r: OnlineResult) -> OnlineResult:
    """Fill instrument/type/bpm/key from title and tags when the source didn't."""
    if r.instrument is None and not r.is_pack:
        r.instrument = inst.infer(r.title, r.tags, r.path)
    elif r.instrument is None and r.is_pack:
        r.instrument = inst.infer(r.title, r.tags)
    if r.bpm is None:
        r.bpm = inst.bpm_from_text(r.title)
    if not r.key:
        r.key = inst.key_from_text(r.title)
    if r.type is None and not r.is_pack:
        r.type = inst.infer_type(r.duration, r.title, r.tags)
    if r.format:
        r.format = r.format.lower().lstrip(".")
    return r


def passes(r: OnlineResult, p: dict) -> bool:
    if not p.get("include_suspect") and r.suspect:
        return False
    if not inst.keep(r, p.get("instruments") or []):
        return False
    if p.get("licenses"):
        allowed = {lic for g in p["licenses"] for lic in LICENSE_GROUPS.get(g, [])}
        if r.license not in allowed:
            return False
    if p.get("commercial") and not r.commercial_ok:
        return False
    packs = p.get("packs", "all")
    if (packs == "files" and r.is_pack) or (packs == "packs" and not r.is_pack):
        return False
    if r.is_pack:
        return True  # per-file filters apply to the files inside, once expanded
    if p.get("types") and r.type and r.type not in p["types"]:
        return False
    if r.duration is not None:
        if p.get("dur_min") is not None and r.duration < p["dur_min"]:
            return False
        if p.get("dur_max") is not None and r.duration > p["dur_max"]:
            return False
    if p.get("bpm_min") is not None or p.get("bpm_max") is not None:
        if r.bpm is None:
            return False
        if p.get("bpm_min") is not None and r.bpm < p["bpm_min"]:
            return False
        if p.get("bpm_max") is not None and r.bpm > p["bpm_max"]:
            return False
    if p.get("key") and (r.key or "").lower() != p["key"].lower():
        return False
    if p.get("lossless") and r.format and r.format not in LOSSLESS:
        return False
    return True


def search_source(name: str, p: dict, page: int, settings: dict) -> dict:
    mod = SOURCES[name]
    try:
        results, total, more = mod.search(p, page, settings)
    except SourceError as e:
        return {"source": name, "label": LABELS[name], "results": [], "total": 0, "more": False,
                "page": page, "error": str(e), "needs_key": "API key" in str(e)}
    except Exception as e:  # unexpected payloads must not break the other sources
        return {"source": name, "label": LABELS[name], "results": [], "total": 0, "more": False,
                "page": page, "error": f"risposta inattesa ({type(e).__name__})", "needs_key": False}
    results = [enrich(r) for r in results]
    remember(results)
    kept = [r for r in results if passes(r, p)]
    return {"source": name, "label": LABELS[name], "results": [r.to_dict() for r in kept],
            "total": total, "more": more, "page": page, "error": None, "needs_key": False,
            "fetched": len(results)}


def search(p: dict, settings: dict) -> dict:
    names = [s for s in (p.get("sources") or list(SOURCES)) if s in SOURCES]
    with ThreadPoolExecutor(max_workers=len(names) or 1) as ex:
        futs = {n: ex.submit(search_source, n, p, 1, settings) for n in names}
        return {n: f.result() for n, f in futs.items()}


def expand(uid: str, p: dict) -> dict:
    parent = get(uid)
    if parent is None or parent.source != "archive":
        return {"error": "pack non trovato", "files": [], "archives": []}
    try:
        files, archives = archive.expand(parent)
    except SourceError as e:
        return {"error": str(e), "files": [], "archives": []}
    files = [enrich(f) for f in files]
    remember(files)
    child_p = dict(p, packs="all", include_suspect=True)
    # inside a pack the instrument comes from file/folder names, no server-side match
    shown = [f for f in files if passes(f, child_p)]
    return {"error": None, "total": len(files), "files": [f.to_dict() for f in shown],
            "archives": archives}
