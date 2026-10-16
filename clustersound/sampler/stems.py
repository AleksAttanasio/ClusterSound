"""Stem separation (drums, bass, guitar, piano, vocals, rest) with Demucs, on this computer only.

Demucs and PyTorch are the optional extra `stems`: nothing is imported until a separation starts. The model
weights are downloaded once, when the user confirms, into the app's support folder; after that everything
runs offline. Long sources are separated in blocks, so memory stays bounded and the job can be cancelled.
"""
import importlib.util
import os
import threading
from typing import Callable

import numpy as np
import soundfile as sf
import soxr

from ..i18n import N_, tr
from ..online.downloads import safe_name, unique_path
from ..paths import data_dir_path, torch_device
from . import export as sampler_export
from .session import SamplerSession

MODEL = "htdemucs_6s"  # 6 sources: drums, bass, other, vocals, guitar, piano
MODEL_DIR = str(data_dir_path() / "models" / "demucs")
MODEL_MB = 55
STEMS = [("drums", N_("Drums")), ("bass", N_("Bass")), ("guitar", N_("Guitar")), ("piano", "Piano"), ("vocals", N_("Vocals")),
         ("other", N_("Other"))]
CHOOSABLE = [k for k, _ in STEMS if k != "other"]
INSTRUMENTAL = N_("Instrumental")  # the name of a track with every stem but the vocals  # "other" is always written: whatever wasn't chosen
INSTALL_HINT = 'pip install -e ".[stems]"'
BLOCK_S = 60.0   # separated per block: a 20-minute source at once would need several GB
OVERLAP_S = 2.0  # blocks overlap and are crossfaded, so the seams don't click

_lock = threading.Lock()
_model = None


class Cancelled(Exception):
    pass


def _marker() -> str:
    return os.path.join(MODEL_DIR, MODEL + ".ready")


def installed() -> bool:
    return all(importlib.util.find_spec(m) is not None for m in ("torch", "demucs"))


def status() -> dict:
    ok = installed()
    return {"installed": ok, "model_ready": ok and os.path.isfile(_marker()), "model_mb": MODEL_MB,
            "install_hint": INSTALL_HINT, "stems": [{"key": k, "label": tr(l), "choosable": k in CHOOSABLE} for k, l in STEMS]}


def _local_bag():
    """The model from MODEL_DIR only, never from the network (None if it isn't there)."""
    yml = os.path.join(MODEL_DIR, MODEL + ".yaml")
    if os.path.isfile(yml):  # demucs >= 4.1: yaml + one safetensors per model of the bag
        import yaml
        from demucs.apply import BagOfModels
        from demucs.hf import load_safetensors_model
        with open(yml, encoding="utf-8") as f:
            bag = yaml.safe_load(f)
        models = [load_safetensors_model(os.path.join(MODEL_DIR, f"{sig}.safetensors")) for sig in bag["models"]]
        return BagOfModels(models, bag.get("weights"), bag.get("segment"))
    import torch
    from demucs.pretrained import get_model
    if importlib.util.find_spec("demucs.hf") is not None:
        return None  # 4.1 would look the name up online first
    torch.hub.set_dir(MODEL_DIR)  # demucs 4.0: torch.hub cache in MODEL_DIR, no request once it's there
    return get_model(MODEL)


def download_model() -> None:
    """The only step that uses the network: fetches the weights into MODEL_DIR (once)."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    if importlib.util.find_spec("demucs.hf") is not None:
        import yaml
        from demucs.hf import DEFAULT_NAMESPACE, hf_repo_name
        from huggingface_hub import hf_hub_download
        repo = f"{DEFAULT_NAMESPACE}/{hf_repo_name(MODEL)}"
        with open(hf_hub_download(repo, f"{MODEL}.yaml", local_dir=MODEL_DIR), encoding="utf-8") as f:
            sigs = yaml.safe_load(f)["models"]
        for sig in sigs:
            hf_hub_download(repo, f"{sig}.safetensors", local_dir=MODEL_DIR)
    if _local_bag() is None:
        raise RuntimeError(tr("model not found after the download"))
    with open(_marker(), "w", encoding="utf-8") as f:
        f.write(MODEL + "\n")


class _Demucs:
    """Demucs wrapper: (2, n) float32 at `samplerate` -> {source: (2, n)}."""

    def __init__(self):
        import torch
        self.model = _local_bag() if os.path.isfile(_marker()) else None
        if self.model is None:
            raise RuntimeError(tr("Demucs model not downloaded"))
        self.torch = torch
        self.model.eval()
        self.samplerate = int(self.model.samplerate)
        self.device = torch_device(torch)

    def _run(self, wav, device: str):
        from demucs.apply import apply_model
        return apply_model(self.model, wav[None], device=device, split=True, overlap=0.25, progress=False)[0]

    def separate(self, x: np.ndarray) -> dict[str, np.ndarray]:
        torch = self.torch
        wav = torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32))
        ref = wav.mean(0)
        mean, std = float(ref.mean()), float(ref.std()) or 1.0
        wav = (wav - mean) / std
        with torch.inference_mode():
            try:
                out = self._run(wav, self.device)
            except Exception:  # an op missing on this GPU: CPU from now on
                if self.device == "cpu":
                    raise
                self.device = "cpu"
                out = self._run(wav, "cpu")
        out = (out * std + mean).cpu().numpy()
        return dict(zip(self.model.sources, out))


def _load_model():
    global _model
    with _lock:
        if _model is None:
            _model = _Demucs()
        return _model


def _split(model, x: np.ndarray, sr: int, groups: list[list[str]]) -> np.ndarray:
    """One block (frames, channels) at sr -> (len(groups), frames, channels): each track is the sum of the
    sources in its group (a source can be in several groups; one in no group is dropped)."""
    n, ch = x.shape
    st = np.repeat(x, 2, axis=1) if ch == 1 else x
    msr = model.samplerate
    if msr != sr:
        st = soxr.resample(st, sr, msr)
    src = model.separate(st.T)
    out = np.zeros((len(groups), st.shape[0], 2), dtype=np.float32)
    for name, y in src.items():
        for i, g in enumerate(groups):
            if name in g:
                out[i] += y.T[: st.shape[0]]
    if msr != sr:
        out = np.stack([soxr.resample(o, msr, sr) for o in out])
    out = out[:, :n]
    if out.shape[1] < n:
        out = np.pad(out, ((0, 0), (0, n - out.shape[1]), (0, 0)))
    return out.mean(axis=2, keepdims=True) if ch == 1 else out


def out_folder(s: SamplerSession, scope: str, sampler_root: str) -> str:
    """Whole recording -> next to it; anything else (and regions) -> the samples folder of the source."""
    if scope == "all" and s.origin == "capture" and s.path:
        return os.path.splitext(s.path)[0] + " - stem"
    return os.path.join(sampler_export.folder_for(s, sampler_root), "stem")


def chosen(keys: list[str] | None) -> list[str]:
    """The stems to write, in STEMS order, "other" last; all of them when keys is None."""
    if keys is None:
        return [k for k, _ in STEMS]
    bad = set(keys) - set(CHOOSABLE)
    if bad or not keys:
        raise ValueError(tr("unknown stems: {stems}", stems=", ".join(sorted(bad))) if bad else tr("choose at least one stem"))
    return [k for k in CHOOSABLE if k in keys] + ["other"]


def plan_tracks(groups: list[list[str]], rest: bool = True) -> list[dict]:
    """The tracks to write, one per group of stems (any of STEMS, "other" too), in the given order: each group
    de-duplicated and in STEMS order, label "Guitar + Vocals" ("Instrumental": everything but the vocals).
    Repeated groups stay (the user chose them). With rest, if some source is in no group, one more track gets
    it: "Other" (as when choosing stems one by one), or "Rest" when "other" itself is in a group; without, those
    sources are dropped. Returns [{key, keys, label}]."""
    order = [k for k, _ in STEMS]
    labels = dict(STEMS)
    if not groups or any(not g for g in groups):
        raise ValueError(tr("choose at least one stem"))
    bad = {str(k) for g in groups for k in g} - set(order)
    if bad:
        raise ValueError(tr("unknown stems: {stems}", stems=", ".join(sorted(bad))))
    tracks = []
    for g in groups:
        keys = [k for k in order if k in g]
        label = tr(INSTRUMENTAL) if keys == [k for k in order if k != "vocals"] else " + ".join(tr(labels[k]) for k in keys)
        tracks.append({"key": "+".join(keys), "keys": keys, "label": label})
    used = {k for t in tracks for k in t["keys"]}
    left = [k for k in order if k not in used]
    if rest and left:
        key = "rest" if "other" in used else "other"
        tracks.append({"key": key, "keys": left, "label": tr(N_("Rest") if key == "rest" else labels["other"])})
    return tracks


def legacy_groups(keys: list[str] | None) -> list[list[str]]:
    """Stems chosen one by one (the old way): one track each; all six when keys is None."""
    ks = chosen(keys)
    return [[k] for k in (ks if keys is None else ks[:-1])]


def separate(s: SamplerSession, start: float, end: float, folder: str, base_name: str,
             on_progress: Callable[[float], None] | None = None,
             cancelled: Callable[[], bool] | None = None, keys: list[str] | None = None,
             tracks: list[dict] | None = None) -> list[dict]:
    """Separate [start, end) s of the session into one 24-bit WAV per track in folder: tracks from plan_tracks,
    or (without them) one per chosen stem + "other". Returns [{key, keys, label, path}]; on cancel or error no
    partial file is left."""
    if tracks is None:
        tracks = plan_tracks(legacy_groups(keys))
    groups = [t["keys"] for t in tracks]
    a, b = s._span(start, end)
    x = s.audio[a:b]
    if x.shape[0] == 0:
        raise ValueError(tr("empty region"))
    model = _load_model()
    os.makedirs(folder, exist_ok=True)
    paths = []
    for t in tracks:  # one at a time: a repeated track gets "… (2).wav"
        paths.append(unique_path(os.path.join(folder, safe_name(f"{base_name} - {t['label']}") + ".wav")))
        open(paths[-1], "wb").close()
    files = [sf.SoundFile(p, "w", s.sr, x.shape[1], subtype="PCM_24") for p in paths]
    hop, ov, n = int(BLOCK_S * s.sr), int(OVERLAP_S * s.sr), x.shape[0]
    try:
        tail = None
        for i in range(0, n, hop):
            if cancelled and cancelled():
                raise Cancelled()
            y = _split(model, x[i:i + hop + ov], s.sr, groups)
            if tail is not None:  # crossfade the previous block's overlap into this one's head
                k = tail.shape[1]
                fade = np.linspace(0, 1, k, dtype=np.float32)[None, :, None]
                y[:, :k] = tail * (1 - fade) + y[:, :k] * fade
            last = i + hop >= n
            keep = y.shape[1] if last else hop
            for f, stem in zip(files, y):
                f.write(np.clip(stem[:keep], -1, 1))
            tail = None if last else y[:, hop:]
            if on_progress:
                on_progress(min(1.0, (i + hop) / n))
    except BaseException:
        for f, p in zip(files, paths):
            f.close()
            if os.path.exists(p):
                os.remove(p)
        raise
    for f in files:
        f.close()
    t0, t1 = a / s.sr, b / s.sr
    for p in paths:
        sampler_export.write_note(s, p, t0, t1)
    return [{**t, "path": p} for t, p in zip(tracks, paths)]
