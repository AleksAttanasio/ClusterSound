"""Pasted links -> openly licensed audio files (with licence and attribution).

Only sources whose content can be downloaded under its licence are accepted. Streaming services
(YouTube, Spotify, Tidal, …) are refused: their terms forbid downloading, and most protect the audio
with DRM.
"""
import html
import re
import urllib.parse

from ..i18n import N_, tr
from ..online import archive, ccmixter, freesound, openverse
from ..online.base import OnlineResult, SourceError, http_get, normalize_license

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
FREESOUND_SOUND = "https://freesound.org/apiv2/sounds/{id}/"

BLOCKED = {
    "youtube.com": "YouTube", "youtu.be": "YouTube", "music.youtube.com": "YouTube Music",
    "spotify.com": "Spotify", "tidal.com": "Tidal", "music.apple.com": "Apple Music",
    "deezer.com": "Deezer", "soundcloud.com": "SoundCloud", "music.amazon.com": "Amazon Music",
    "amazon.com": "Amazon Music", "qobuz.com": "Qobuz", "pandora.com": "Pandora",
}
BLOCKED_MESSAGE = N_(
    "{name} does not allow downloading its audio: its terms forbid it and the stream is often DRM "
    "protected, so extracting samples from it is not legal, not even for a few seconds. "
    "For personal use you can use «Audio capture» while listening; for public use you need a "
    "licence (or a sample that is already free: try the Store).")
SUPPORTED = "Freesound, Internet Archive, ccMixter, Openverse, Wikimedia Commons"


def _host(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower().removeprefix("www.").removeprefix("m.")


def _matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def classify(url: str) -> tuple[str, str]:
    """(provider, id) of a supported link; SourceError for streaming services and unknown sites."""
    url = (url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    host = _host(url)
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    for domain, name in BLOCKED.items():
        if _matches(host, domain):
            raise SourceError(tr(BLOCKED_MESSAGE, name=name))
    if _matches(host, "freesound.org"):
        m = re.search(r"/sounds/(\d+)", path) or re.match(r"/s/(\d+)", path)
        if m:
            return "freesound", m.group(1)
    elif _matches(host, "archive.org"):
        m = re.match(r"/(?:details|download)/([^/]+)(?:/(.+))?", path)
        if m:
            return "archive", m.group(1) + ("/" + m.group(2) if m.group(2) and path.startswith("/download/") else "")
    elif _matches(host, "ccmixter.org"):
        m = re.search(r"/files/[^/]+/(\d+)", path)
        if m:
            return "ccmixter", m.group(1)
    elif _matches(host, "openverse.org"):
        m = re.search(r"/audio/([0-9a-f-]{36})", path)
        if m:
            return "openverse", m.group(1)
    elif _matches(host, "wikimedia.org") or _matches(host, "wikipedia.org"):
        m = re.search(r"/(?:wiki/)?(File:.+)$", path)
        if m:
            return "commons", m.group(1)
        if host == "upload.wikimedia.org":
            return "commons", "File:" + path.rsplit("/", 1)[-1]
    raise SourceError(tr("link not recognised: paste the page of a sound on {sites}", sites=SUPPORTED))


# ------------------------------------------------------------------ providers
def _freesound(sid: str, settings: dict) -> list[OnlineResult]:
    d = http_get(FREESOUND_SOUND.format(id=sid), {"fields": freesound.FIELDS}, headers=freesound._auth(settings))
    return freesound.parse({"results": [d]})


def archive_parent(meta: dict, ident: str) -> OnlineResult:
    md = meta.get("metadata") or {}
    one = lambda v: (v[0] if isinstance(v, list) and v else v) or ""  # noqa: E731
    title, creator = one(md.get("title")) or ident, ", ".join(archive._as_list(md.get("creator")))
    return OnlineResult(
        uid=f"archive:{ident}", source="archive", source_label=archive.LABEL, title=title, author=creator,
        license=normalize_license(md.get("licenseurl")), license_url=md.get("licenseurl") or "",
        page_url=f"https://archive.org/details/{ident}", is_pack=True,
        suspect=bool(archive._VENDORS.search(f"{title} {creator}")), extra={"identifier": ident})


def _archive(key: str) -> list[OnlineResult]:
    ident, _, file = key.partition("/")
    meta = http_get(archive.META.format(id=ident))
    if not meta.get("metadata"):
        raise SourceError(tr("Internet Archive item not found"))
    files, _ = archive.expand(archive_parent(meta, ident))
    if file:
        files = [f for f in files if f.path == file] or files
    if not files:
        raise SourceError(tr("no audio file in this Internet Archive item"))
    return files


def _ccmixter(uid: str) -> list[OnlineResult]:
    out = ccmixter.parse(http_get(ccmixter.API, {"f": "json", "ids": uid}))
    for r in out:
        if r.is_pack:  # the sampler needs an audio file, not the zip of stems
            r.download_url, r.is_pack = r.preview_url, False
    return [r for r in out if r.download_url]


def _openverse(uid: str) -> list[OnlineResult]:
    return openverse.parse({"results": [http_get(openverse.API + uid + "/")]})


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(text or ""))).strip()


def parse_commons(data: dict) -> list[OnlineResult]:
    out = []
    for page in ((data.get("query") or {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if not info.get("url") or info.get("mediatype") not in (None, "AUDIO"):
            continue
        meta = {k: _strip_html(v.get("value")) for k, v in (info.get("extmetadata") or {}).items()}
        title = page.get("title", "").removeprefix("File:")
        out.append(OnlineResult(
            uid=f"commons:{page.get('pageid')}", source="commons", source_label="Wikimedia Commons",
            title=meta.get("ObjectName") or title.rsplit(".", 1)[0], author=meta.get("Artist", ""),
            license=normalize_license(meta.get("LicenseUrl") or meta.get("LicenseShortName")),
            license_url=meta.get("LicenseUrl", ""), duration=info.get("duration"),
            preview_url=info["url"], download_url=info["url"], page_url=info.get("descriptionurl", ""),
            format=title.rsplit(".", 1)[-1].lower(), filesize=info.get("size"),
            extra={"attribution": meta.get("Attribution") or None}))
    return out


def _commons(title: str) -> list[OnlineResult]:
    data = http_get(COMMONS_API, {"action": "query", "titles": title, "prop": "imageinfo", "format": "json",
                                  "iiprop": "url|size|mediatype|extmetadata"})
    out = parse_commons(data)
    if not out:
        raise SourceError(tr("audio file not found on Wikimedia Commons"))
    return out


def resolve(url: str, settings: dict) -> list[OnlineResult]:
    """The audio files a link points to (several for an Internet Archive item)."""
    provider, key = classify(url)
    results = {"freesound": lambda: _freesound(key, settings), "archive": lambda: _archive(key),
               "ccmixter": lambda: _ccmixter(key), "openverse": lambda: _openverse(key),
               "commons": lambda: _commons(key)}[provider]()
    if not results:
        raise SourceError(tr("no downloadable audio file for this link"))
    return results
