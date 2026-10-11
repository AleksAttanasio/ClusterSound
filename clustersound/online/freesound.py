"""Freesound APIv2 (needs a free API key: https://freesound.org/apiv2/apply)."""
import re
from concurrent.futures import ThreadPoolExecutor

from . import instruments as inst
from .base import OnlineResult, SourceError, clean_tags, http_get, normalize_license

API = "https://freesound.org/apiv2/search/"
PACK_API = "https://freesound.org/apiv2/packs/{id}/"
USER_PACKS_API = "https://freesound.org/apiv2/users/{user}/packs/"
LABEL = "Freesound"
PAGE_SIZE = 30
FIELDS = ("id,name,username,license,duration,tags,previews,images,type,samplerate,filesize,url,"
          "bpm,tonality,single_event,loopable,pack,pack_name,num_downloads,avg_rating")
PACK_TTL = 3600
SORT = {"relevance": "score", "downloads": "downloads_desc", "rating": "rating_desc",
        "newest": "created_desc", "duration": "duration_asc"}
# Freesound licence names per filter group
LIC_NAMES = {"cc0": ['"Creative Commons 0"'], "by": ['"Attribution"'],
             "nc": ['"Attribution NonCommercial"', '"Sampling+"']}
# filters this source applies server-side (shown in the UI)
SERVER_FILTERS = {"instrument", "license", "commercial", "duration", "bpm", "key", "type", "lossless", "sort"}


def _range(lo, hi) -> str:
    return f"[{lo if lo is not None else '*'} TO {hi if hi is not None else '*'}]"


def build_params(p: dict, page: int) -> dict:
    flt = []
    if p.get("instruments"):
        tags = inst.tag_terms(p["instruments"])
        flt.append("tag:(" + " OR ".join(tags) + ")")
    names = []
    if p.get("commercial"):
        names = LIC_NAMES["cc0"] + LIC_NAMES["by"]
    elif p.get("licenses"):
        for g in p["licenses"]:
            names += LIC_NAMES.get(g, [])
    if names:
        flt.append("license:(" + " OR ".join(dict.fromkeys(names)) + ")")
    if p.get("dur_min") is not None or p.get("dur_max") is not None:
        flt.append("duration:" + _range(p.get("dur_min"), p.get("dur_max")))
    if p.get("bpm_min") is not None or p.get("bpm_max") is not None:
        flt.append("bpm:" + _range(p.get("bpm_min"), p.get("bpm_max")))
    if p.get("key"):
        flt.append(f'tonality:"{p["key"]}"')
    types = set(p.get("types") or [])
    if types == {"One-shot"}:
        flt.append("single_event:true")
    elif types == {"Loop"}:
        flt.append("loopable:true")
    if p.get("lossless"):
        flt.append("type:(wav OR aiff OR flac)")
    out = {"query": p.get("q", ""), "fields": FIELDS, "page": page, "page_size": PAGE_SIZE,
           "sort": SORT.get(p.get("sort"), "score")}
    if flt:
        out["filter"] = " ".join(flt)
    return out


def parse(data: dict) -> list[OnlineResult]:
    out = []
    for s in data.get("results", []):
        previews = s.get("previews") or {}
        hq = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
        tags = clean_tags(s.get("tags"))
        typ = "One-shot" if s.get("single_event") else "Loop" if s.get("loopable") else None
        out.append(OnlineResult(
            uid=f"freesound:{s['id']}", source="freesound", source_label=LABEL,
            title=s.get("name", ""), author=s.get("username", ""),
            license=normalize_license(s.get("license")), license_url=s.get("license", ""),
            duration=s.get("duration"), tags=tags, bpm=s.get("bpm"), key=s.get("tonality"),
            preview_url=hq, download_url=hq,
            download_note="anteprima HQ mp3 · l'originale si scarica dalla pagina Freesound",
            page_url=s.get("url") or f"https://freesound.org/s/{s['id']}/",
            waveform_img=(s.get("images") or {}).get("waveform_m"), format=s.get("type", ""),
            samplerate=s.get("samplerate"), filesize=s.get("filesize"), type=typ,
            extra={"pack_id": pack_id(s.get("pack")), "pack_title": s.get("pack_name"),
                   "downloads": s.get("num_downloads"), "rating": s.get("avg_rating")}))
    return out


def pack_id(uri: str | None) -> str | None:
    m = re.search(r"/packs/(\d+)", uri or "")
    return m.group(1) if m else None


def _auth(settings: dict) -> dict:
    key = (settings or {}).get("freesound_key")
    if not key:
        raise SourceError("API key mancante: aggiungila nelle impostazioni (⚙)")
    return {"Authorization": f"Token {key}"}


def search(p: dict, page: int, settings: dict):
    data = http_get(API, build_params(p, page), headers=_auth(settings))
    results = parse(data)
    if p.get("instruments"):
        for r in results:
            r.matched = True  # came from the exact tag filter
    return results, data.get("count"), bool(data.get("next"))



# ------------------------------------------------------------------ packs
def parse_pack(d: dict, sample: OnlineResult | None = None) -> OnlineResult:
    """A Freesound pack (Pack Instance response) as a pack result."""
    pid = str(d["id"])
    r = OnlineResult(
        uid=f"freesound:pack:{pid}", source="freesound", source_label=LABEL,
        title=d.get("name") or f"Pack {pid}", author=d.get("username", ""),
        page_url=f"https://freesound.org/people/{d.get('username', '')}/packs/{pid}/",
        is_pack=True,
        extra={"pack_id": pid, "num_sounds": d.get("num_sounds"), "downloads": d.get("num_downloads"),
               "description": d.get("description") or "", "created": d.get("created")})
    if sample is not None:  # the search hit that stands for the pack
        r.license, r.license_url, r.tags = sample.license, sample.license_url, sample.tags
        r.instrument = sample.instrument
        r.waveform_img, r.preview_url = sample.waveform_img, sample.preview_url
    return r


def pack_info(pid: str, settings: dict) -> dict:
    return http_get(PACK_API.format(id=pid), headers=_auth(settings), ttl=PACK_TTL)


def pack_card(hit: OnlineResult, raw: dict) -> OnlineResult:
    """Pack card from a grouped search hit (pack_name is returned by the search: no extra request)."""
    user = raw.get("username", "")
    card = parse_pack({"id": hit.extra["pack_id"], "name": hit.extra.get("pack_title"), "username": user}, hit)
    card.extra["matching"] = (raw.get("n_from_same_pack") or 0) + 1
    return card


def packs(p: dict, page: int, settings: dict):
    """Search grouped by pack: one card per pack, from its best matching sound."""
    params = dict(build_params(p, page), group_by_pack=1)
    # only sounds that belong to a pack (without a query Freesound would not group otherwise)
    params["filter"] = (params.get("filter", "") + " pack:*").strip()
    data = http_get(API, params, headers=_auth(settings))
    raws = data.get("results", [])
    cards = [pack_card(r, raw) for r, raw in zip(parse(data), raws) if r.extra.get("pack_id")]
    if not p.get("q") and params["filter"] == "pack:*":  # nothing narrows the match: it is the whole pack
        for c in cards:
            c.extra["num_sounds"] = c.extra.pop("matching")
    return cards, data.get("count"), bool(data.get("next"))


def pack_sounds(pid: str, page: int, settings: dict):
    data = http_get(PACK_API.format(id=pid) + "sounds/", {"fields": FIELDS, "page": page, "page_size": 50},
                    headers=_auth(settings), ttl=PACK_TTL)
    return parse(data), data.get("count"), bool(data.get("next"))


def user_packs(username: str, settings: dict, limit: int = 12) -> list[OnlineResult]:
    data = http_get(USER_PACKS_API.format(user=username), {"page_size": limit},
                    headers=_auth(settings), ttl=PACK_TTL)
    return [parse_pack(d) for d in data.get("results", [])]
