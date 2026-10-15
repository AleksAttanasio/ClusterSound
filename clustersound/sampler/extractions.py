"""What was extracted from a source (stems, enhanced files): new results are temporary, in a work folder of this run
of the app, until «Export all» moves them into the export folder; at the end of the run what was not saved is
deleted. Saved files are found again on disk, and files can be copied elsewhere (the library) with their notes."""
import os
import shutil

import soundfile as sf

from ..i18n import LANGUAGES, load_catalog
from ..online.downloads import safe_name, unique_path
from . import export as sampler_export
from . import stems as sampler_stems
from .session import SamplerSession

NOTE_EXT = (".source.txt", ".license.txt")
WORK_DIR = "Recorder work"  # in the app's data folder, one subfolder per running app (by process id)


# ---------------------------------------------------------------- work folder (temporary results)
def work_dir(data_dir: str, pid: int | None = None) -> str:
    return os.path.join(data_dir, WORK_DIR, str(os.getpid() if pid is None else pid))


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True  # exists (or can't tell): keep its files
    return True


def clean_stale(data_dir: str) -> None:
    """Delete the work folders of runs of the app that ended without cleaning up (a crash, a forced quit)."""
    root = os.path.join(data_dir, WORK_DIR)
    try:
        names = os.listdir(root)
    except OSError:
        return
    for n in names:
        if n.isdigit() and int(n) != os.getpid() and not _alive(int(n)):
            shutil.rmtree(os.path.join(root, n), ignore_errors=True)


def stem_folder(home: SamplerSession, work: str) -> str:
    """Where a stems job writes (temporary): like the saved layout, under the work folder."""
    return os.path.join(sampler_export.folder_for(home, work), "stem")


def saved_path(path: str, work: str, saved_root: str) -> str:
    """Where a temporary file goes when it is saved: the same place under the export folder."""
    return os.path.join(saved_root, os.path.relpath(path, work))


# ---------------------------------------------------------------- listing
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


def scan(s: SamplerSession, sampler_root: str, work: str | None = None) -> dict:
    """{stems: [...], enhanced: [...]} on disk for the source s, each item {path, name, dur, sr, saved}: the saved
    ones (export folder, or next to a recording for older versions) and the temporary ones of this run (work)."""
    own = os.path.realpath(s.path) if s.path else None
    seen: set[str] = set()

    def items(paths, saved):
        out = []
        for p in paths:
            real = os.path.realpath(p)
            if real == own or real in seen:
                continue
            seen.add(real)
            it = _item(p)
            if it:
                out.append({**it, "saved": saved})
        return out

    suffixes = tuple(f" ({w}).wav" for w in _enhanced_words())
    title = safe_name(s.title or "sample")
    stem_dirs = dict.fromkeys(sampler_stems.out_folder(s, scope, sampler_root) for scope in ("all", "region"))
    stems = items((p for d in stem_dirs for p in _wavs(d)), True)
    enh = [p for p in _wavs(sampler_export.folder_for(s, sampler_root)) if p.endswith(suffixes)]
    if s.origin == "capture" and s.path:  # a whole recording's result sat next to it, among other recordings
        enh += [p for p in _wavs(os.path.dirname(s.path))
                if p.endswith(suffixes) and os.path.basename(p).startswith(title + " ")]
    enhanced = items(enh, True)
    if work:
        stems += items(_wavs(stem_folder(s, work)), False)
        enhanced += items((p for p in _wavs(sampler_export.folder_for(s, work)) if p.endswith(suffixes)), False)
    return {"stems": stems, "enhanced": enhanced}


# ---------------------------------------------------------------- saving, copying, deleting
def _notes(path: str) -> list[str]:
    return [path + ext for ext in NOTE_EXT if os.path.isfile(path + ext)]


def move_to(path: str, dst: str) -> str:
    """Move a file and its notes to dst (made unique); returns where it went."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    dst = unique_path(dst)
    shutil.move(path, dst)
    for n in _notes(path):
        shutil.move(n, dst + n[len(path):])
    return dst


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
        for n in _notes(p):
            shutil.copy2(n, dst + n[len(p):])
        out.append(dst)
    return out


def remove(path: str, trash=None) -> None:
    """Delete a file and its notes; with trash (a function), move them there instead."""
    for p in [path, *_notes(path)]:
        if trash:
            trash(p)
        else:
            os.remove(p)
