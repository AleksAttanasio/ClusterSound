"""Openverse audio API (anonymous): aggregates Freesound, Wikimedia Commons and Jamendo."""
from concurrent.futures import ThreadPoolExecutor

from . import instruments as inst
from .base import OnlineResult, clean_tags, http_get, normalize_license

API = "https://api.openverse.org/v1/audio/"
LABEL = "Openverse"
PAGE_SIZE = 20  # anonymous maximum
SUB_SOURCES = {"freesound": "Freesound", "wikimedia_audio": "Wikimedia", "jamendo": "Jamendo",
               "ccmixter": "ccMixter"}
LIC = {"cc0": ["cc0", "pdm"], "by": ["by"], "by-sa": ["by-sa"],
       "nc": ["by-nc", "by-nc-sa", "by-nc-nd", "sampling+", "nc-sampling+"], "nd": ["by-nd", "by-nc-nd"]}
SERVER_FILTERS = {"instrument", "license", "commercial", "duration", "sort"}


# one plain query per instrument (Openverse's OR syntax is unreliable with phrases)
QUERY = {"closed_hat": "hihat", "open_hat": "open hihat", "sub808": "808", "cymbal_other": "cymbal",
         "hand_drum": "conga", "perc_other": "percussion", "woodblock": "woodblock", "spoken": "speech"}
MAX_INSTRUMENT_QUERIES = 4


def instrument_query(cid: str) -> str:
    return QUERY.get(cid) or inst.TERMS.get(cid, [cid])[0]


def build_params(p: dict, page: int, instrument: str | None = None) -> dict:
    q = " ".join(x for x in [(p.get("q") or "").strip(), instrument_query(instrument) if instrument else ""] if x)
    out = {"q": q or "sample", "page": page, "page_size": PAGE_SIZE,
           # Jamendo is full songs: not samples
           "source": "freesound,wikimedia_audio"}
    lic = []
    for g in p.get("licenses") or []:
        lic += LIC.get(g, [])
    if lic:
        out["license"] = ",".join(dict.fromkeys(lic))
    if p.get("commercial"):
        out["license_type"] = "commercial,modification"
    if p.get("dur_max") is not None and p["dur_max"] <= 30:
        out["length"] = "shortest"
    if p.get("sort") == "newest":
        out["sort_by"] = "indexed_on"
    return out


def parse(data: dict) -> list[OnlineResult]:
    out = []
    for a in data.get("results", []):
        sub = a.get("source") or a.get("provider") or ""
        dur = a.get("duration")
        out.append(OnlineResult(
            uid=f"openverse:{a['id']}", source="openverse",
            source_label=f"{LABEL} · {SUB_SOURCES.get(sub, sub)}",
            title=a.get("title") or "", author=a.get("creator") or "",
            license=normalize_license(a.get("license_url") or a.get("license")),
            license_url=a.get("license_url") or "",
            duration=dur / 1000.0 if dur else None, tags=clean_tags(a.get("tags")),
            preview_url=a.get("url"), download_url=a.get("url"),
            download_note="anteprima mp3 di Freesound" if sub == "freesound" else "",
            page_url=a.get("foreign_landing_url") or "", format=a.get("filetype") or "",
            samplerate=a.get("sample_rate"), filesize=a.get("filesize"),
            extra={"attribution": a.get("attribution")}))
    return out


def search(p: dict, page: int, settings: dict):
    ins = (p.get("instruments") or [])[:MAX_INSTRUMENT_QUERIES]
    if not ins:
        data = http_get(API, build_params(p, page))
        return parse(data), data.get("result_count"), page < (data.get("page_count") or 0)
    results, seen, total, more = [], set(), 0, False
    with ThreadPoolExecutor(max_workers=len(ins)) as ex:
        datas = list(ex.map(lambda cid: http_get(API, build_params(p, page, cid)), ins))
    batches = [parse(d) for d in datas]
    for d in datas:
        total += d.get("result_count") or 0
        more = more or page < (d.get("page_count") or 0)
    # interleave so every instrument shows up near the top
    for i in range(max(len(b) for b in batches)):
        for b in batches:
            if i < len(b) and b[i].uid not in seen:
                seen.add(b[i].uid)
                b[i].matched = True
                results.append(b[i])
    return results, total, more
