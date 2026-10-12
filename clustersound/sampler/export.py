"""Write sampler regions as WAV files, with the source's licence (links) or provenance (capture) next to them."""
import os
import time

import soundfile as sf

from ..online.downloads import license_text, safe_name, unique_path
from . import slicing
from .session import DEFAULT_MAX_SAMPLE_SECONDS, SamplerSession

DEFAULT_DIR = os.path.expanduser("~/Music/ClusterSound Samples")
ORIGIN_FOLDER = {"file": "Da file", "capture": "Cattura audio"}
CAPTURE_NOTE = ("Registrazione dall'audio di sistema, per uso personale (copia privata). "
                "I diritti sul brano originale restano dei titolari: verificali prima di pubblicare "
                "o distribuire qualcosa che contiene questo sample.")


def folder_for(s: SamplerSession, root: str) -> str:
    if s.origin == "link" and s.result:
        top = safe_name(s.result.source_label.split(" · ")[-1])
    else:
        top = ORIGIN_FOLDER.get(s.origin, "Sampler")
    return os.path.join(root, top, safe_name(s.title or "sample"))


def source_text(s: SamplerSession, start: float, end: float) -> str:
    lines = [f"Sorgente: {s.title or 'senza titolo'}", f"Regione: {start:.3f}–{end:.3f} s"]
    if s.origin == "capture":
        lines += [f"Registrato il: {s.meta.get('captured_at', '')}", f"Dispositivo: {s.meta.get('device', 'audio di sistema')}",
                  "", CAPTURE_NOTE]
    elif s.path:
        lines.append(f"File: {s.path}")
    lines.append(f"\nEstratto con ClusterSound il {time.strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines) + "\n"


def export(s: SamplerSession, regions: list[dict], root: str = DEFAULT_DIR,
           max_s: float = DEFAULT_MAX_SAMPLE_SECONDS, fade_in_ms: float = 1.0, fade_out_ms: float = 10.0,
           normalize: bool = False) -> list[str | None]:
    """One WAV per region ({start, end, name?}); returns the written paths, aligned with the regions
    (None for a region outside the audio)."""
    folder = folder_for(s, root)
    os.makedirs(folder, exist_ok=True)
    out = []
    for i, r in enumerate(regions, 1):
        start, end = slicing.clamp(r["start"], r["end"], max_s, s.duration)
        y = slicing.render(s, start, end, max_s, fade_in_ms, fade_out_ms, normalize)
        if y.shape[0] == 0:
            out.append(None)
            continue
        name = safe_name(r.get("name") or f"{s.title or 'sample'} - {i:02d}")
        path = unique_path(os.path.join(folder, name + ".wav"))
        sf.write(path, y, s.sr, subtype="PCM_24")
        if s.origin == "link" and s.result:
            text = license_text(s.result, s.result.download_url or s.result.page_url)
            text += f"Regione: {start:.3f}–{end:.3f} s\n"
            with open(path + ".license.txt", "w", encoding="utf-8") as f:
                f.write(text)
        elif s.origin == "capture":
            with open(path + ".source.txt", "w", encoding="utf-8") as f:
                f.write(source_text(s, start, end))
        out.append(path)
    return out
