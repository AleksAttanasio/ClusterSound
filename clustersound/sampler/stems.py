"""Stem separation (drums, bass, guitar, vocals, rest) with Demucs, on this Mac only.

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

from ..online.downloads import safe_name, unique_path
from . import export as sampler_export
from .session import SamplerSession

MODEL = "htdemucs_6s"  # 6 sources: drums, bass, other, vocals, guitar, piano
MODEL_DIR = os.path.expanduser("~/Library/Application Support/ClusterSound/models/demucs")
MODEL_MB = 55
STEMS = [("drums", "Batteria"), ("bass", "Basso"), ("guitar", "Chitarra"), ("vocals", "Voce"), ("other", "Altro")]
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
            "install_hint": INSTALL_HINT, "stems": [{"key": k, "label": l} for k, l in STEMS]}


def download_model() -> None:
    """The only step that uses the network: fetches the weights into MODEL_DIR (once)."""
    import torch
    from demucs.pretrained import get_model
    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.hub.set_dir(MODEL_DIR)
    get_model(MODEL)
    with open(_marker(), "w") as f:
        f.write(MODEL + "\n")


class _Demucs:
    """Demucs wrapper: (2, n) float32 at `samplerate` -> {source: (2, n)}."""

    def __init__(self):
        import torch
        from demucs.pretrained import get_model
        if not os.path.isfile(_marker()):
            raise RuntimeError("modello Demucs non scaricato")
        torch.hub.set_dir(MODEL_DIR)
        self.torch = torch
        self.model = get_model(MODEL)  # from MODEL_DIR: no network once downloaded
        self.model.eval()
        self.samplerate = int(self.model.samplerate)
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"

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


def _split(model, x: np.ndarray, sr: int) -> np.ndarray:
    """One block (frames, channels) at sr -> (len(STEMS), frames, channels), stems summing to x."""
    n, ch = x.shape
    st = np.repeat(x, 2, axis=1) if ch == 1 else x
    msr = model.samplerate
    if msr != sr:
        st = soxr.resample(st, sr, msr)
    src = model.separate(st.T)
    keys = [k for k, _ in STEMS]
    out = np.zeros((len(keys), st.shape[0], 2), dtype=np.float32)
    for name, y in src.items():  # sources outside the named stems (piano, other) go to "other"
        out[keys.index(name) if name in keys else keys.index("other")] += y.T[: st.shape[0]]
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


def separate(s: SamplerSession, start: float, end: float, folder: str, base_name: str,
             on_progress: Callable[[float], None] | None = None,
             cancelled: Callable[[], bool] | None = None) -> list[dict]:
    """Separate [start, end) s of the session into one 24-bit WAV per stem in folder.
    Returns [{key, label, path}]; on cancel or error no partial file is left."""
    a, b = s._span(start, end)
    x = s.audio[a:b]
    if x.shape[0] == 0:
        raise ValueError("regione vuota")
    model = _load_model()
    os.makedirs(folder, exist_ok=True)
    paths = [unique_path(os.path.join(folder, safe_name(f"{base_name} - {label}") + ".wav")) for _, label in STEMS]
    files = [sf.SoundFile(p, "w", s.sr, x.shape[1], subtype="PCM_24") for p in paths]
    hop, ov, n = int(BLOCK_S * s.sr), int(OVERLAP_S * s.sr), x.shape[0]
    try:
        tail = None
        for i in range(0, n, hop):
            if cancelled and cancelled():
                raise Cancelled()
            y = _split(model, x[i:i + hop + ov], s.sr)
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
    return [{"key": k, "label": l, "path": p} for (k, l), p in zip(STEMS, paths)]
