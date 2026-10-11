"""Internet Archive (anonymous): whole sample packs, browsable file by file (also inside ZIPs)."""
import html
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from . import instruments as inst
from .base import OnlineResult, http_get, normalize_license

SEARCH = "https://archive.org/advancedsearch.php"
META = "https://archive.org/metadata/{id}"
LABEL = "Internet Archive"
PAGE_SIZE = 30
SERVER_FILTERS = {"instrument", "license", "sort"}
FIELDS = ["identifier", "title", "creator", "licenseurl", "downloads", "subject", "date", "item_size"]
# items about samples (otherwise IA returns concerts, podcasts, …)
CONTEXT = ('subject:("sample pack" OR "samples" OR "drum kit" OR "drum samples" OR "one shot" OR '
           '"one shots" OR "loops" OR "sound effects" OR "soundfont") OR '
           'title:("sample pack" OR samples OR "drum kit" OR "drum samples" OR "one shots" OR loops)')
AUDIO_EXT = (".wav", ".aif", ".aiff", ".flac", ".mp3", ".ogg")
ARCHIVE_EXT = (".zip", ".rar", ".7z")
MAX_CHILDREN = 3000

# Commercial libraries often re-uploaded to IA with a "free" licence they don't have.
_VENDORS = re.compile(
    r"big fish audio|sound ?ideas|sony pictures|zero[- ]?g\b|native instruments|spectrasonics|loopmasters|"
    r"splice|garage ?band|logic (pro|10)|apple loops|ableton (live )?(packs?|suite)|vengeance|sample magic|"
    r"producer loops|prime loops|black octopus|toolroom|output (arcade|exhale)|kshmr|cymatics|"
    r"\bleak(ed)?\b|cracked|\bwarez\b|torrent", re.I)


def _terms_expr(terms: list[str]) -> str:
    return " OR ".join(f'"{t}"' if " " in t else t for t in terms)


def build_params(p: dict, page: int) -> dict:
    q = [f"mediatype:audio AND ({CONTEXT}) AND NOT subject:(midi OR \"midi files\")"]
    if p.get("instruments"):
        e = _terms_expr(inst.query_terms(p["instruments"]))
        q.append(f"(title:({e}) OR subject:({e}))")
    if p.get("q"):
        q.append(f"({p['q']})")
    if "unknown" not in (p.get("licenses") or []) or p.get("commercial"):
        q.append("licenseurl:*")  # undeclared licences only when explicitly asked for
    params = {"q": " AND ".join(q), "fl[]": FIELDS, "rows": PAGE_SIZE, "page": page, "output": "json"}
    sort = {"downloads": "downloads desc", "newest": "date desc", "relevance": None}.get(
        p.get("sort"), "downloads desc")
    if sort:
        params["sort[]"] = sort
    return params


def _as_list(v) -> list[str]:
    if v is None:
        return []
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]


def parse(data: dict) -> list[OnlineResult]:
    out = []
    for d in (data.get("response") or {}).get("docs", []):
        ident = d["identifier"]
        title = d.get("title") or ident
        if isinstance(title, list):
            title = title[0]
        subjects = [s.lower() for s in _as_list(d.get("subject"))]
        creator = ", ".join(_as_list(d.get("creator")))
        r = OnlineResult(
            uid=f"archive:{ident}", source="archive", source_label=LABEL, title=title, author=creator,
            license=normalize_license(d.get("licenseurl")), license_url=d.get("licenseurl") or "",
            tags=subjects[:20], page_url=f"https://archive.org/details/{ident}",
            filesize=d.get("item_size"), is_pack=True,
            suspect=bool(_VENDORS.search(" ".join([title, creator] + subjects))),
            extra={"identifier": ident, "downloads": d.get("downloads")})
        out.append(r)
    return out


def search(p: dict, page: int, settings: dict):
    data = http_get(SEARCH, build_params(p, page))
    results = parse(data)
    if p.get("instruments"):
        for r in results:
            r.matched = True
    total = (data.get("response") or {}).get("numFound")
    return results, total, (total or 0) > page * PAGE_SIZE


# ------------------------------------------------------------------ pack contents
def _dl(ident: str, path: str) -> str:
    return f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(path)}"


_ZIP_ROW = re.compile(r'<a href="(//archive\.org/download/[^"]+)">([^<]+)</a>.*?<td id="size">(\d*)', re.S)


def list_zip(ident: str, zip_name: str) -> list[tuple[str, str, int | None]]:
    """(inner path, url, size) of audio files inside a ZIP of an item (IA renders a listing page)."""
    page = http_get(_dl(ident, zip_name) + "/", as_json=False)
    out = []
    for href, name, size in _ZIP_ROW.findall(page):
        name = html.unescape(name)
        if name.lower().endswith(AUDIO_EXT) and "/__macosx/" not in ("/" + name.lower()):
            out.append((name, "https:" + html.unescape(href), int(size) if size else None))
    return out


def expand(parent: OnlineResult) -> tuple[list[OnlineResult], list[dict]]:
    """Files of a pack: loose audio files and the audio inside its ZIPs. Also returns its archives."""
    ident = parent.extra["identifier"]
    meta = http_get(META.format(id=ident))
    md = meta.get("metadata") or {}
    lic = normalize_license(md.get("licenseurl")) if md.get("licenseurl") else parent.license
    children, archives = [], []
    for f in meta.get("files", []):
        name = f.get("name", "")
        low = name.lower()
        size = int(f["size"]) if str(f.get("size") or "").isdigit() else None
        if low.endswith(ARCHIVE_EXT):
            archives.append({"name": name, "url": _dl(ident, name), "size": size})
        elif low.endswith(AUDIO_EXT) and f.get("source") == "original":
            children.append((name, _dl(ident, name), size, f.get("length")))
    zips = [a for a in archives if a["name"].lower().endswith(".zip")]

    def listing(a):
        try:
            return list_zip(ident, a["name"])
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=4) as ex:
        for a, files in zip(zips, ex.map(listing, zips)):
            a["browsable"] = files is not None
            for name, url, size in files or []:
                children.append((name, url, size, None))
    # packs often ship the same sounds as WAV and AIFF (or MP3): keep one, preferring lossless WAV
    rank = {".wav": 0, ".aif": 1, ".aiff": 1, ".flac": 2, ".ogg": 3, ".mp3": 4}
    best: dict[str, tuple] = {}
    for c in children:
        base = c[0].rsplit("/", 1)[-1]
        stem, ext = (base.rsplit(".", 1) + [""])[:2]
        k = stem.lower()
        if k not in best or rank.get("." + ext.lower(), 9) < rank.get("." + best[k][0].rsplit(".", 1)[-1].lower(), 9):
            best[k] = c
    children = [c for c in children if best.get(c[0].rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()) is c]
    out = []
    for name, url, size, length in children[:MAX_CHILDREN]:
        base = name.rsplit("/", 1)[-1]
        try:
            dur = float(length) if length else None
        except ValueError:
            dur = None
        r = OnlineResult(
            uid=f"archive:{ident}:{name}", source="archive", source_label=LABEL,
            title=base, author=parent.author, license=lic, license_url=parent.license_url,
            duration=dur, preview_url=url, download_url=url, page_url=parent.page_url,
            format=base.rsplit(".", 1)[-1].lower(), filesize=size, path=name, suspect=parent.suspect,
            extra={"pack_title": parent.title})
        r.instrument = inst.infer(base, [], path=name)
        out.append(r)
    return out, archives
