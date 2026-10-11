"""Shared pieces for online sources: normalised result, licences, HTTP with a small cache."""
import http.client
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field

# ccMixter repeats the whole JSON body in an "X-JSON" response header, which exceeds
# http.client's default 64 KB header-line limit.
http.client._MAXLINE = max(getattr(http.client, "_MAXLINE", 65536), 1 << 24)

USER_AGENT ="ClusterSound/0.1 (+https://github.com/; sample browser)"
TIMEOUT = 20
CACHE_TTL = 600


class SourceError(Exception):
    """A user-presentable error from one source (the others keep working)."""


@dataclass
class OnlineResult:
    uid: str
    source: str               # freesound | openverse | archive | ccmixter
    source_label: str         # e.g. "Openverse · Wikimedia"
    title: str
    author: str = ""
    license: str = "unknown"  # see LICENSES
    license_url: str = ""
    duration: float | None = None
    tags: list[str] = field(default_factory=list)
    bpm: float | None = None
    key: str | None = None
    preview_url: str | None = None
    download_url: str | None = None
    download_note: str = ""   # e.g. "preview HQ mp3"
    page_url: str = ""
    waveform_img: str | None = None
    format: str = ""
    samplerate: int | None = None
    filesize: int | None = None
    is_pack: bool = False
    path: str = ""            # file path inside a pack
    instrument: str | None = None
    type: str | None = None   # One-shot | Loop | Long/Texture
    suspect: bool = False     # likely commercial content re-uploaded under a free licence
    matched: bool = False     # the source matched the instrument query server-side
    extra: dict = field(default_factory=dict)

    @property
    def commercial_ok(self) -> bool:
        return LICENSES.get(self.license, LICENSES["unknown"])["commercial"]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["commercial_ok"] = self.commercial_ok
        d["license_label"] = LICENSES.get(self.license, LICENSES["unknown"])["label"]
        d.pop("extra", None)
        return d


# commercial = usable in a commercial production as a sample (no NC, no ND).
LICENSES = {
    "cc0": {"label": "CC0", "commercial": True},
    "pd": {"label": "Pubblico dominio", "commercial": True},
    "by": {"label": "CC BY", "commercial": True},
    "by-sa": {"label": "CC BY-SA", "commercial": True},
    "by-nd": {"label": "CC BY-ND", "commercial": False},
    "by-nc": {"label": "CC BY-NC", "commercial": False},
    "by-nc-sa": {"label": "CC BY-NC-SA", "commercial": False},
    "by-nc-nd": {"label": "CC BY-NC-ND", "commercial": False},
    "sampling+": {"label": "Sampling+", "commercial": False},
    "rf": {"label": "Royalty-free", "commercial": True},  # site licence (curated packs), not CC
    "unknown": {"label": "Non dichiarata", "commercial": False},
}
# filter groups shown in the UI
LICENSE_GROUPS = {
    "cc0": ["cc0", "pd"],
    "by": ["by"],
    "by-sa": ["by-sa"],
    "nc": ["by-nc", "by-nc-sa", "by-nc-nd", "sampling+"],
    "nd": ["by-nd", "by-nc-nd"],
    "unknown": ["unknown"],
}


def normalize_license(text: str | None) -> str:
    """Licence URL or name (any source) -> key of LICENSES."""
    if not text:
        return "unknown"
    t = text.lower().strip()
    if "publicdomain/zero" in t or t in ("cc0", "zero", "creative commons 0") or "cczero" in t:
        return "cc0"
    if "publicdomain/mark" in t or t in ("pdm", "pd", "public domain") or "public domain" in t:
        return "pd"
    if "sampling+" in t or "sampling-plus" in t or "sampling plus" in t:
        return "sampling+"
    m = re.search(r"licenses/([a-z-]+)/", t)
    code = m.group(1) if m else t
    code = code.replace("attribution", "by").replace("noncommercial", "nc").replace("non-commercial", "nc")
    code = code.replace("sharealike", "sa").replace("share-alike", "sa").replace("noderivatives", "nd")
    code = code.replace("noderivs", "nd").replace("creative commons", "").replace(" ", "-").strip("-")
    parts = [p for p in re.split(r"[-_ ()0-9.]+", code) if p]
    has = set(parts)
    if "by" not in has:
        return "unknown"
    key = "by" + ("-nc" if "nc" in has else "") + ("-sa" if "sa" in has else "") + ("-nd" if "nd" in has else "")
    return key if key in LICENSES else "unknown"


# ------------------------------------------------------------------- HTTP
_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()


def _key(url: str, params: dict | None, headers: dict | None) -> str:
    return url + "?" + urllib.parse.urlencode(sorted((params or {}).items()), doseq=True) + \
        json.dumps(sorted((headers or {}).items()))


def build_url(url: str, params: dict | None) -> str:
    if not params:
        return url
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)


def http_get(url: str, params: dict | None = None, headers: dict | None = None,
             as_json: bool = True, ttl: int = CACHE_TTL):
    k = _key(url, params, headers)
    now = time.time()
    with _cache_lock:
        hit = _cache.get(k)
        if hit and now - hit[0] < ttl:
            return hit[1]
    req = urllib.request.Request(build_url(url, params),
                                 headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SourceError("accesso negato (API key mancante o non valida)") from e
        if e.code == 429:
            raise SourceError("troppe richieste: riprova tra qualche minuto") from e
        raise SourceError(f"errore HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SourceError(f"non raggiungibile ({getattr(e, 'reason', e)})") from e
    data = json.loads(body) if as_json else body.decode("utf-8", "replace")
    with _cache_lock:
        if len(_cache) > 500:
            _cache.clear()
        _cache[k] = (now, data)
    return data


def clean_tags(tags) -> list[str]:
    out = []
    for t in tags or []:
        t = (t.get("name") if isinstance(t, dict) else str(t)).strip().lower()
        if t and t not in out:
            out.append(t)
    return out
