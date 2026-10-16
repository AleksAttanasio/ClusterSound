"""Write sampler regions as WAV files, with the source's licence (links) or provenance (capture) next to them."""
import os
import time

import soundfile as sf

from ..i18n import N_, tr
from ..online.downloads import license_text, safe_name, unique_path
from . import slicing
from .session import SamplerSession

DEFAULT_DIR = os.path.expanduser("~/Music/ClusterSound Samples")
ORIGIN_FOLDER = {"file": "From file", "capture": "Audio capture"}
CAPTURE_NOTE = N_("Recorded from the system audio, for personal use (private copy). "
                  "The rights to the original track stay with their owners: check them before publishing "
                  "or distributing anything that contains this sample.")


def folder_for(s: SamplerSession, root: str) -> str:
    if s.origin == "link" and s.result:
        top = safe_name(s.result.source_label.split(" · ")[-1])
    else:
        top = ORIGIN_FOLDER.get(s.origin, "Sampler")
    return os.path.join(root, top, safe_name(s.title or "sample"))


def region_line(start: float, end: float) -> str:
    return tr("Region: {start}–{end} s", start=f"{start:.3f}", end=f"{end:.3f}")


def source_text(s: SamplerSession, start: float, end: float) -> str:
    lines = [tr("Source: {v}", v=s.title or tr("untitled")), region_line(start, end)]
    if s.origin == "capture":
        lines += [tr("Recorded on: {v}", v=s.meta.get("captured_at", "")),
                  tr("Device: {v}", v=s.meta.get("device", tr("system audio"))), "", tr(CAPTURE_NOTE)]
    elif s.path:
        lines.append(tr("File: {v}", v=s.path))
    lines.append("\n" + tr("Extracted with ClusterSound on {date}", date=time.strftime("%Y-%m-%d %H:%M")))
    return "\n".join(lines) + "\n"


def write_note(s: SamplerSession, path: str, start: float, end: float) -> None:
    """The source's licence (links) or provenance (capture) next to a file cut from it."""
    if s.origin == "link" and s.result:
        text = license_text(s.result, s.result.download_url or s.result.page_url)
        text += region_line(start, end) + "\n"
        with open(path + ".license.txt", "w", encoding="utf-8") as f:
            f.write(text)
    elif s.origin == "capture":
        with open(path + ".source.txt", "w", encoding="utf-8") as f:
            f.write(source_text(s, start, end))


def export(s: SamplerSession, regions: list[dict], root: str = DEFAULT_DIR, fade_in_ms: float = 1.0, fade_out_ms: float = 10.0,
           normalize: bool = False) -> list[str | None]:
    """One WAV per region ({start, end, name?}); returns the written paths, aligned with the regions
    (None for a region outside the audio)."""
    folder = folder_for(s, root)
    os.makedirs(folder, exist_ok=True)
    out = []
    for i, r in enumerate(regions, 1):
        start, end = slicing.clamp(r["start"], r["end"], total=s.duration)
        y = slicing.render(s, start, end, fade_in_ms=fade_in_ms, fade_out_ms=fade_out_ms, normalize=normalize)
        if y.shape[0] == 0:
            out.append(None)
            continue
        name = safe_name(r.get("name") or f"{s.title or 'sample'} - {i:02d}")
        path = unique_path(os.path.join(folder, name + ".wav"))
        sf.write(path, y, s.sr, subtype="PCM_24")
        write_note(s, path, start, end)
        out.append(path)
    return out
