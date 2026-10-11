"""Freesound APIv2 (needs a free API key: https://freesound.org/apiv2/apply)."""
from . import instruments as inst
from .base import OnlineResult, SourceError, clean_tags, http_get, normalize_license

API = "https://freesound.org/apiv2/search/"
LABEL = "Freesound"
PAGE_SIZE = 30
FIELDS = ("id,name,username,license,duration,tags,previews,images,type,samplerate,filesize,url,"
          "bpm,tonality,single_event,loopable")
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
            samplerate=s.get("samplerate"), filesize=s.get("filesize"), type=typ))
    return out


def search(p: dict, page: int, settings: dict):
    key = (settings or {}).get("freesound_key")
    if not key:
        raise SourceError("API key mancante: aggiungila nelle impostazioni (⚙)")
    data = http_get(API, build_params(p, page), headers={"Authorization": f"Token {key}"})
    results = parse(data)
    if p.get("instruments"):
        for r in results:
            r.matched = True  # came from the exact tag filter
    return results, data.get("count"), bool(data.get("next"))

