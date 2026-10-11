"""Download queue: files go to <download dir>/<Source>/ with a .license.txt next to each one."""
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .base import LICENSES, USER_AGENT, OnlineResult

DEFAULT_DIR = os.path.expanduser("~/Music/ClusterSound Downloads")
# only fetch from the hosts of the sources we search
ALLOWED_HOSTS = ("freesound.org", "archive.org", "ccmixter.org", "wikimedia.org", "jamendo.com",
                 "openverse.org")
CHUNK = 1 << 16


def host_allowed(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def safe_name(text: str, limit: int = 120) -> str:
    text = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", " ", text or "").strip(" .")
    text = re.sub(r"\s+", " ", text)
    return text[:limit].rstrip(" .") or "sample"


def unique_path(path: str) -> str:
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(path):
        path = f"{base} ({n}){ext}"
        n += 1
    return path


def target_path(root: str, r: OnlineResult, url: str) -> str:
    src = safe_name(r.source_label.split(" · ")[-1] if r.source == "openverse" else r.source_label)
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower() or (f".{r.format}" if r.format else "")
    title = os.path.splitext(r.path.rsplit("/", 1)[-1] if r.path else r.title)[0]
    name = safe_name(f"{r.author} - {title}" if r.author else title)
    folder = os.path.join(root, src)
    if r.path:  # file inside a pack: keep it grouped by pack
        folder = os.path.join(folder, safe_name(r.extra.get("pack_title") or "pack"))
    return unique_path(os.path.join(folder, name + ext))


def license_text(r: OnlineResult, url: str) -> str:
    lic = LICENSES.get(r.license, LICENSES["unknown"])
    lines = [
        f"Titolo: {r.title}",
        f"Autore: {r.author or 'sconosciuto'}",
        f"Fonte: {r.source_label}",
        f"Pagina: {r.page_url}",
        f"File: {url}",
        f"Licenza: {lic['label']}" + (f" ({r.license_url})" if r.license_url else ""),
        f"Uso commerciale come sample: {'sì' if lic['commercial'] else 'no / da verificare'}",
    ]
    if r.download_note:
        lines.append(f"Nota: {r.download_note}")
    if r.license not in ("cc0", "pd"):
        attribution = r.extra.get("attribution") or (
            f'"{r.title}" di {r.author or "autore sconosciuto"} ({r.page_url}), licenza {lic["label"]}')
        lines += ["", "Attribuzione richiesta:", attribution]
    if r.license == "unknown":
        lines += ["", "ATTENZIONE: licenza non dichiarata dalla fonte. Verifica i diritti prima dell'uso."]
    lines.append(f"\nScaricato con ClusterSound il {time.strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines) + "\n"


class Downloader:
    def __init__(self):
        self.jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=3)
        self._seq = 0

    def enqueue(self, r: OnlineResult, url: str, root: str) -> dict:
        if not url:
            raise ValueError("nessun file scaricabile per questo risultato")
        if not host_allowed(url):
            raise ValueError("host non consentito")
        with self._lock:
            self._seq += 1
            job = {"id": str(self._seq), "uid": r.uid, "title": r.path.rsplit("/", 1)[-1] if r.path else r.title,
                   "source": r.source_label, "url": url, "status": "queued", "bytes": 0,
                   "total": r.filesize, "path": None, "error": None}
            self.jobs[job["id"]] = job
        self._pool.submit(self._run, job, r, root)
        return dict(job)

    def _run(self, job: dict, r: OnlineResult, root: str) -> None:
        job["status"] = "downloading"
        dest = target_path(root, r, job["url"])
        tmp = dest + ".part"
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            req = urllib.request.Request(job["url"], headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
                if not host_allowed(resp.geturl()):
                    raise ValueError("redirect verso un host non consentito")
                total = resp.headers.get("Content-Length")
                job["total"] = int(total) if total and total.isdigit() else job["total"]
                while chunk := resp.read(CHUNK):
                    f.write(chunk)
                    job["bytes"] += len(chunk)
            os.replace(tmp, dest)
            with open(dest + ".license.txt", "w", encoding="utf-8") as f:
                f.write(license_text(r, job["url"]))
            job["path"], job["status"] = dest, "done"
        except Exception as e:
            job["status"], job["error"] = "error", str(e)
            if os.path.exists(tmp):
                os.remove(tmp)

    def status(self) -> list[dict]:
        with self._lock:
            return [dict(j) for j in self.jobs.values()]
