"""Audio decoding: any libsndfile format -> mono float32, plus resampling helpers."""
from dataclasses import dataclass

import numpy as np
import soundfile as sf
import soxr

MAX_SECONDS = 30.0  # longer files are analysed on their first 30 s only


@dataclass
class AudioInfo:
    samplerate: int
    channels: int
    frames: int
    subtype: str
    format: str

    @property
    def duration(self) -> float:
        return self.frames / self.samplerate if self.samplerate else 0.0


def info(path: str) -> AudioInfo:
    i = sf.info(path)
    return AudioInfo(i.samplerate, i.channels, i.frames, i.subtype or "", i.format or "")


def load_mono(path: str, max_seconds: float = MAX_SECONDS) -> tuple[np.ndarray, int]:
    """Decode to mono float32 at the native sample rate (truncated to max_seconds)."""
    with sf.SoundFile(path) as f:
        sr = f.samplerate
        n = f.frames if f.frames > 0 else -1
        if max_seconds and n > 0:
            n = min(n, int(max_seconds * sr))
        data = f.read(frames=n, dtype="float32", always_2d=True)
    mono = data.mean(axis=1) if data.shape[1] > 1 else data[:, 0]
    mono = np.nan_to_num(mono, copy=False)
    return np.ascontiguousarray(mono, dtype=np.float32), sr


def resample(x: np.ndarray, sr: int, target: int) -> np.ndarray:
    if sr == target or x.size == 0:
        return x
    return soxr.resample(x, sr, target, quality="HQ").astype(np.float32)


def trim_silence(x: np.ndarray, sr: int, threshold_db: float = -60.0) -> np.ndarray:
    """Trim leading/trailing samples below threshold relative to peak."""
    if x.size == 0:
        return x
    peak = float(np.max(np.abs(x)))
    if peak <= 0:
        return x[:0]
    thr = peak * 10 ** (threshold_db / 20)
    idx = np.flatnonzero(np.abs(x) > thr)
    if idx.size == 0:
        return x[:0]
    # keep a few ms before the first transient so attacks are not cut
    start = max(0, idx[0] - int(0.002 * sr))
    return x[start: idx[-1] + 1]
