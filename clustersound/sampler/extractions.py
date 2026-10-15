"""What was already extracted from a source (stems, enhanced files), found again on disk, and copies of those
files into the export folder, with their licence/provenance notes."""
import os
import shutil

import soundfile as sf

from ..i18n import LANGUAGES, load_catalog
from ..online.downloads import safe_name, unique_path
from . import export as sampler_export
from . import stems as sampler_stems
from .session import SamplerSession

NOTE_EXT = (".source.txt", ".license.txt")


def _enhanced_words() -> set[str]:
    """The «enhanced» word of every interface language: a file keeps the one of the language it was made in."""
    words = {"enhanced"}
    for lang in LANGUAGES:
        try:
            words.add(load_catalog(lang).get("enhanced") or "enhanced")
        except (OSError, ValueError):
            pass
    return words


def _item(path: str) -> dict | None:
    try:
        info = sf.info(path)
    except (RuntimeError, OSError):
        return None
    return {"path": path, "name": os.path.splitext(os.path.basename(path))[0],
            "dur": round(info.frames / info.samplerate, 3) if info.samplerate else 0.0, "sr": info.samplerate}


def _wavs(folder: str) -> list[str]:
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return [os.path.join(folder, n) for n in sorted(names, key=str.lower) if n.lower().endswith(".wav")]


def scan(s: SamplerSession, sampler_root: str) -> dict:
    """{stems: [...], enhanced: [...]} already on disk for the source s, each item {path, name, dur, sr}."""
    own = os.path.realpath(s.path) if s.path else None
    seen: set[str] = set()

    def items(paths):
        out = []
        for p in paths:
            real = os.path.realpath(p)
            if real == own or real in seen:
                continue
            seen.add(real)
            it = _item(p)
            if it:
                out.append(it)
        return out

    stem_dirs = dict.fromkeys(sampler_stems.out_folder(s, scope, sampler_root) for scope in ("all", "region"))
    stems = items(p for d in stem_dirs for p in _wavs(d))
    suffixes = tuple(f" ({w}).wav" for w in _enhanced_words())
    title = safe_name(s.title or "sample")
    enh = [p for p in _wavs(sampler_export.folder_for(s, sampler_root)) if p.endswith(suffixes)]
    if s.origin == "capture" and s.path:  # a whole recording's result sits next to it, among other recordings
        enh += [p for p in _wavs(os.path.dirname(s.path))
                if p.endswith(suffixes) and os.path.basename(p).startswith(title + " ")]
    return {"stems": stems, "enhanced": items(enh)}


def copy_to(paths: list[str], folder: str) -> list[str | None]:
    """Copy files (and their notes) into folder; a file already there is kept as it is. Aligned with paths."""
    os.makedirs(folder, exist_ok=True)
    out: list[str | None] = []
    for p in paths:
        if not p or not os.path.isfile(p):
            out.append(None)
            continue
        if os.path.realpath(os.path.dirname(p)) == os.path.realpath(folder):
            out.append(p)
            continue
        dst = unique_path(os.path.join(folder, os.path.basename(p)))
        shutil.copy2(p, dst)
        for ext in NOTE_EXT:
            if os.path.isfile(p + ext):
                shutil.copy2(p + ext, dst + ext)
        out.append(dst)
    return out
