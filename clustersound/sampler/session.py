"""The audio open in the sampler, with where it came from."""
import os
from dataclasses import dataclass, field

import numpy as np
import soundfile as sf

from ..online.base import OnlineResult

MAX_SOURCE_SECONDS = 20 * 60  # longer sources are opened on their first 20 minutes
DEFAULT_MAX_SAMPLE_SECONDS = 30.0
ORIGINS = ("file", "link", "capture")


@dataclass
class SamplerSession:
    audio: np.ndarray            # float32, shape (frames, channels), channels in 1..2
    sr: int
    origin: str = "file"         # file | link | capture
    title: str = ""
    path: str = ""               # local file (file/link origins)
    result: OnlineResult | None = None  # licence and attribution (link origin)
    truncated: bool = False
    meta: dict = field(default_factory=dict)

    @property
    def frames(self) -> int:
        return int(self.audio.shape[0])

    @property
    def duration(self) -> float:
        return self.frames / self.sr if self.sr else 0.0

    def mono(self) -> np.ndarray:
        return self.audio.mean(axis=1) if self.audio.shape[1] > 1 else self.audio[:, 0]

    def _span(self, start: float, end: float) -> tuple[int, int]:
        a = int(np.clip(round(start * self.sr), 0, self.frames))
        b = int(np.clip(round(end * self.sr), 0, self.frames))
        return (a, b) if a <= b else (b, a)

    def clip(self, start: float, end: float) -> np.ndarray:
        a, b = self._span(start, end)
        return self.audio[a:b]

    def peaks(self, start: float = 0.0, end: float | None = None, cols: int = 1200) -> dict:
        """Min/max columns of the mono signal between start and end (s), for the waveform view."""
        a, b = self._span(start, self.duration if end is None else end)
        cols = max(1, min(int(cols), 4000))
        x = self.mono()[a:b]
        if x.size == 0:
            return {"start": a / self.sr, "end": b / self.sr, "wave_min": [], "wave_max": []}
        if x.size < cols:
            cols = x.size
        edges = np.linspace(0, x.size, cols + 1).astype(int)
        mn = np.minimum.reduceat(x, edges[:-1])
        mx = np.maximum.reduceat(x, edges[:-1])
        return {"start": a / self.sr, "end": b / self.sr,
                "wave_min": np.round(mn, 4).tolist(), "wave_max": np.round(mx, 4).tolist()}

    def describe(self) -> dict:
        r = self.result
        return {"origin": self.origin, "title": self.title, "path": self.path, "duration": round(self.duration, 3),
                "sr": self.sr, "channels": int(self.audio.shape[1]), "truncated": self.truncated,
                "source": r.to_dict() if r else None}


def from_array(audio: np.ndarray, sr: int, **kw) -> SamplerSession:
    a = np.asarray(audio, dtype=np.float32)
    if a.ndim == 1:
        a = a[:, None]
    if a.shape[1] > 2:
        a = a[:, :2]
    return SamplerSession(np.nan_to_num(np.ascontiguousarray(a)), int(sr), **kw)


def load_file(path: str, origin: str = "file", result: OnlineResult | None = None,
              max_seconds: float = MAX_SOURCE_SECONDS) -> SamplerSession:
    with sf.SoundFile(path) as f:
        sr = f.samplerate
        n = f.frames if f.frames > 0 else -1
        truncated = n > max_seconds * sr
        if n > 0:
            n = min(n, int(max_seconds * sr))
        data = f.read(frames=n, dtype="float32", always_2d=True)
    title = result.title if result else os.path.splitext(os.path.basename(path))[0]
    return from_array(data, sr, origin=origin, title=title, path=path, result=result, truncated=truncated)
