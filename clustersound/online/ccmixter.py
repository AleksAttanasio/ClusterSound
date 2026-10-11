"""ccMixter query API (anonymous): samples, stems and a cappellas under CC licences."""
from . import instruments as inst
from .base import OnlineResult, clean_tags, http_get, normalize_license

API = "http://ccmixter.org/api/query"
LABEL = "ccMixter"
PAGE_SIZE = 30
SERVER_FILTERS = {"instrument", "sort"}
# system tags that describe the file, not the sound
_SYSTEM = {"media", "audio", "mp3", "flac", "wav", "zip", "archive", "44k", "48k", "22k", "stereo", "mono",
           "cbr", "vbr", "sample", "remix", "preview", "multiple_formats", "attribution", "non_commercial",
           "cczero", "sharealike", "noderives", "stem"}
_LOSSLESS = ("flac", "wav", "aif", "aiff")


def build_params(p: dict, page: int) -> dict:
    out = {"f": "json", "reqtags": "sample", "limit": PAGE_SIZE, "offset": (page - 1) * PAGE_SIZE}
    if p.get("instruments"):
        tags = [t.replace("-", "_") for t in inst.tag_terms(p["instruments"])]
        out["tags"] = ",".join(tags)
        out["type"] = "any"
    if p.get("q"):
        out["search"] = p["q"]
        out["search_type"] = "all"
    if p.get("sort") == "newest":
        out["sort"], out["ord"] = "date", "desc"
    else:
        out["sort"] = "rank"
    return out


def _seconds(ps: str | None) -> float | None:
    try:
        parts = [float(x) for x in (ps or "").split(":")]
    except ValueError:
        return None
    sec = 0.0
    for x in parts:
        sec = sec * 60 + x
    return sec or None


def parse(data: list) -> list[OnlineResult]:
    out = []
    for u in data or []:
        files = u.get("files") or []
        audio = [f for f in files if (f.get("file_format_info") or {}).get("media-type") == "audio"]
        archives = [f for f in files if (f.get("file_format_info") or {}).get("default-ext") == "zip"]
        mp3 = next((f for f in audio if (f.get("file_format_info") or {}).get("default-ext") == "mp3"), None)
        lossless = next((f for f in audio if (f.get("file_format_info") or {}).get("default-ext") in _LOSSLESS), None)
        best = lossless or (archives[0] if archives else None) or mp3
        info = (best or {}).get("file_format_info") or {}
        extra = u.get("upload_extra") or {}
        tags = [t for t in clean_tags((u.get("upload_tags") or "").split(",")) if t not in _SYSTEM
                and not t.startswith("bpm_")]
        try:
            bpm = float(extra.get("bpm")) if extra.get("bpm") else None
        except (TypeError, ValueError):
            bpm = None
        out.append(OnlineResult(
            uid=f"ccmixter:{u['upload_id']}", source="ccmixter", source_label=LABEL,
            title=u.get("upload_name") or "", author=u.get("user_real_name") or u.get("user_name") or "",
            license=normalize_license(u.get("license_url") or u.get("license_name")),
            license_url=u.get("license_url") or "",
            duration=_seconds(((mp3 or best or {}).get("file_format_info") or {}).get("ps")),
            tags=tags, bpm=bpm,
            preview_url=(mp3 or {}).get("download_url"), download_url=(best or {}).get("download_url"),
            download_note="archivio zip (stem/sample)" if best in archives else "",
            page_url=u.get("file_page_url") or "", format=info.get("default-ext", ""),
            filesize=(best or {}).get("file_rawsize"), is_pack=bool(archives) and best in archives))
    return out


def search(p: dict, page: int, settings: dict):
    data = http_get(API, build_params(p, page))
    results = parse(data)
    if p.get("instruments"):
        for r in results:
            r.matched = True
    return results, None, len(data or []) >= PAGE_SIZE
