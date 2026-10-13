"""One "Migliora" job on the sampler's audio: the span goes to a temp WAV, the worker enhances it, the result lands
next to where the source's samples go, with the same licence/provenance note."""
import os
import tempfile
from typing import Callable

import soundfile as sf

from ..i18n import tr
from ..online.downloads import safe_name, unique_path
from ..sampler import export as sampler_export
from ..sampler.session import SamplerSession
from . import runner

SUFFIX = " ({enhanced})"  # the word follows the interface language


def out_path(s: SamplerSession, scope: str, base: str, sampler_root: str) -> str:
    """Whole recording -> next to it; anything else (and regions) -> the samples folder of the source."""
    if scope == "all" and s.origin == "capture" and s.path:
        folder = os.path.dirname(s.path)
    else:
        folder = sampler_export.folder_for(s, sampler_root)
    return unique_path(os.path.join(folder, safe_name(base + SUFFIX.format(enhanced=tr("enhanced"))) + ".wav"))


def run(s: SamplerSession, start: float, end: float, model: str, dst: str,
        on_progress: Callable[[float], None] | None = None, cancelled: Callable[[], bool] | None = None) -> dict:
    """Enhance [start, end) s of the session into dst; returns {path, sr}. Raises runner.Cancelled or RuntimeError."""
    a, b = s._span(start, end)
    x = s.audio[a:b]
    if x.shape[0] == 0:
        raise ValueError(tr("empty region"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    fd, src = tempfile.mkstemp(suffix=".wav", prefix="cs-enhance-")
    os.close(fd)
    try:
        sf.write(src, x, s.sr, subtype="FLOAT")  # lossless hand-off to the worker
        out = runner.run(model, src, dst, on_progress, cancelled)
    finally:
        os.remove(src)
    sampler_export.write_note(s, dst, a / s.sr, b / s.sr)
    return {"path": dst, "sr": int(out.get("sr", 0))}
