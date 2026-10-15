"""Parallel search across sources, normalisation and the client-side half of the filters."""
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from ..i18n import tr
from . import archive, catalog, ccmixter, freesound, openverse
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
    if r.instrument is None and r.label_state is None:
        cid, state = inst.infer_label(r.title, r.tags, "" if r.is_pack else r.path)
        r.instrument, r.label_state = cid, state or ""
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


# sources that group their results in packs (store "Pack" view)
PACK_SOURCES = ["freesound", "archive", "ccmixter"]


def _packs_fn(name: str):
    if name == "freesound":
        return freesound.packs
    # Internet Archive items are always packs; ccMixter uploads are packs when they ship a zip
    return lambda p, page, settings: SOURCES[name].search(dict(p, packs="packs"), page, settings)


def search_source(name: str, p: dict, page: int, settings: dict, packs: bool = False) -> dict:
    mod = SOURCES[name]
    if packs:
        p = dict(p, packs="packs")
    try:
        results, total, more = (_packs_fn(name) if packs else mod.search)(p, page, settings)
    except SourceError as e:
        return {"source": name, "label": LABELS[name], "results": [], "total": 0, "more": False,
                "page": page, "error": str(e), "needs_key": "API key" in str(e)}
    except Exception as e:  # unexpected payloads must not break the other sources
        return {"source": name, "label": LABELS[name], "results": [], "total": 0, "more": False,
                "page": page, "error": tr("unexpected response ({error})", error=type(e).__name__), "needs_key": False}
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
        return {"error": tr("pack not found"), "files": [], "archives": []}
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


# ------------------------------------------------------------------ store: packs
def _pack_card(parent: OnlineResult) -> dict:
    return enrich(parent).to_dict()


def pack(uid: str, page: int, settings: dict) -> dict:
    """Pack page: details, one page of its sounds, the archives to download and more packs by the author."""
    parent = get(uid)
    try:
        if uid.startswith("freesound:pack:"):
            pid = uid.rsplit(":", 1)[-1]
            info = freesound.pack_info(pid, settings)
            card = freesound.parse_pack(info, parent if parent and parent.waveform_img else None)
            if parent:  # keep what the search card knew (licence, matching sounds)
                card.extra = {**parent.extra, **card.extra}
            remember([card])
            files, total, more = freesound.pack_sounds(pid, page, settings)
            for f in files:
                f.extra["pack_title"] = card.title
            others = []
            if page == 1:
                try:
                    others = [o for o in freesound.user_packs(card.author, settings) if o.uid != uid]
                except SourceError:
                    pass
                remember(others)
            files = [enrich(f) for f in files]
            remember(files)
            if not card.license or card.license == "unknown":
                lics = {f.license for f in files}
                card.license = lics.pop() if len(lics) == 1 else card.license
            return {"error": None, "pack": _pack_card(card), "files": [f.to_dict() for f in files],
                    "total": total, "more": more, "page": page, "archives": [],
                    "others": [_pack_card(o) for o in others]}
        if parent is None or not parent.is_pack:
            return {"error": tr("pack not found")}
        if parent.source == "archive":
            files, archives = archive.expand(parent)
            files = [enrich(f) for f in files]
            remember(files)
            return {"error": None, "pack": _pack_card(parent), "files": [f.to_dict() for f in files],
                    "total": len(files), "more": False, "page": 1, "archives": archives, "others": []}
        # ccMixter: a single upload with its zip
        return {"error": None, "pack": _pack_card(parent), "files": [], "total": 0, "more": False, "page": 1,
                "archives": [{"name": parent.title + ".zip", "url": parent.download_url, "size": parent.filesize}]
                if parent.download_url else [], "others": []}
    except SourceError as e:
        return {"error": str(e)}


MAX_PACK_DOWNLOAD = 500


def pack_files(uid: str, settings: dict) -> list[OnlineResult]:
    """Every downloadable file of a pack (Freesound: HQ previews; Internet Archive: loose files)."""
    if uid.startswith("freesound:pack:"):
        pid = uid.rsplit(":", 1)[-1]
        title = (get(uid).title if get(uid) else None) or freesound.pack_info(pid, settings).get("name") or pid
        out, page, more = [], 1, True
        while more and len(out) < MAX_PACK_DOWNLOAD:
            files, _, more = freesound.pack_sounds(pid, page, settings)
            if not files:
                break
            out += files
            page += 1
        for f in out:
            f.extra["pack_title"] = title
        remember(out)
        return out[:MAX_PACK_DOWNLOAD]
    parent = get(uid)
    if parent is None or parent.source != "archive":
        return []
    files, _ = archive.expand(parent)
    return files[:MAX_PACK_DOWNLOAD]


# ------------------------------------------------------------------ store: home
def featured(settings: dict) -> dict:
    """Home rows of the store. Each row is independent: a failing source just leaves its row empty."""
    has_key = bool((settings or {}).get("freesound_key"))
    jobs = {
        "freesound_packs": lambda: search_source("freesound", {"sort": "downloads"}, 1, settings, packs=True)
        if has_key else {"results": [], "error": tr("API key missing"), "needs_key": True},
        "archive_packs": lambda: search_source("archive", {"sort": "downloads"}, 1, settings),
        "cc0_new": lambda: search_source("freesound" if has_key else "openverse",
                                         {"licenses": ["cc0"], "sort": "newest"}, 1, settings),
    }
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {k: ex.submit(fn) for k, fn in jobs.items()}
        return {k: f.result() for k, f in futs.items()}


def showcase_source(name: str, settings: dict) -> dict:
    """Store home: a varied carousel of one source's samples, a few per category.

    Only results surely labelled as the queried category are kept,
    so the category badge on every card is the one the user would expect.
    """
    if name not in SOURCES:
        return {"source": name, "results": [], "error": tr("unknown source"), "needs_key": False}
    if name == "freesound" and not (settings or {}).get("freesound_key"):
        return {"source": name, "results": [], "error": tr("API key missing"), "needs_key": True}
    cats = catalog.SHOWCASE_LIMITED.get(name, catalog.SHOWCASE_CATEGORIES)
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(lambda c: search_source(name, {"instruments": [c], "sort": "downloads"}, 1, settings), cats))
    buckets, errors, seen, authors = [], [], set(), {}
    for cid, d in zip(cats, res):
        if d.get("error"):
            errors.append(d["error"])
            continue
        rows = [r for r in d["results"] if r["instrument"] == cid and r["label_state"] == "sure"]
        picked = []
        for r in rows:
            if r["uid"] in seen or authors.get(r["author"], 0) >= 2:
                continue  # one prolific uploader must not fill the carousel
            picked.append(r)
            seen.add(r["uid"])
            authors[r["author"]] = authors.get(r["author"], 0) + 1
            if len(picked) == catalog.SHOWCASE_PER_CATEGORY:
                break
        buckets.append(picked)
    # round robin across categories: kick, snare, hat, … then the second of each
    out = [b[i] for i in range(catalog.SHOWCASE_PER_CATEGORY) for b in buckets if i < len(b)]
    error = errors[0] if errors and not out else None
    return {"source": name, "results": out, "error": error, "needs_key": bool(error and "API key" in error)}
