"""Regions of the source: transient slicing, duration limit, edge clean-up for export."""
import numpy as np

from .. import features
from .session import SamplerSession

CHUNK_S = 30.0     # onset detection runs on chunks: a 20-minute STFT would not fit in memory
OVERLAP_S = 1.0
LEAD_IN_S = 0.05    # silence added before the source for onset detection
PRE_ROLL_S = 0.005  # detected onsets sit a few ms after the real attack
MIN_REGION_S = 0.03
TAIL_DB = -50.0     # a slice ends where its level stays below this (relative to its peak)


def rise_db(sensitivity: float) -> float:
    """Sensitivity 0..1 -> minimum dB rise for an onset (higher sensitivity = more slices)."""
    return float(np.interp(np.clip(sensitivity, 0, 1), [0, 1], [18.0, 4.0]))


def onset_times(x: np.ndarray, sr: int, sensitivity: float = 0.5) -> np.ndarray:
    # each chunk owns [a + ov/2, a + hop + ov/2): the start of a chunk (where a decaying tail can look
    # like an onset) is owned by the previous chunk, which sees it with context
    # the first chunk gets a little silence in front, so a hit right at 0 still shows an energy rise
    hop, ov, pad = int(CHUNK_S * sr), int(OVERLAP_S * sr), int(LEAD_IN_S * sr)
    out: list[float] = []
    for a in range(0, max(1, x.size), hop):
        seg = x[a:a + hop + ov]
        if seg.size < sr * 0.05:
            break
        lead = 0 if a else pad
        if lead:
            seg = np.concatenate([np.zeros(lead, dtype=seg.dtype), seg])
        lo = (a + ov / 2) / sr if a else 0.0
        for t in features.onsets(seg, sr, rise_db(sensitivity), fallback=False) + (a - lead) / sr:
            t = max(0.0, t)
            if lo <= t < (a + hop + ov / 2) / sr and (not out or t - out[-1] > 0.03):
                out.append(float(t))
    return np.array(out)


def clamp(start: float, end: float, max_s: float = float("inf"), total: float | None = None) -> tuple[float, float]:
    start, end = sorted((float(start), float(end)))
    start = max(0.0, start)
    if total is not None:
        end = min(end, total)
    return start, min(end, start + max_s)


def _tail_end(x: np.ndarray, sr: int) -> int:
    """Last sample above TAIL_DB (10 ms RMS windows), so slices don't carry the next hit's silence."""
    win = max(1, int(0.01 * sr))
    n = x.size // win
    if n == 0:
        return x.size
    rms = np.sqrt((x[:n * win].reshape(n, win) ** 2).mean(1) + 1e-12)
    loud = np.flatnonzero(20 * np.log10(rms / rms.max()) > TAIL_DB)
    return min(x.size, (loud[-1] + 2) * win) if loud.size else x.size


def auto_slices(s: SamplerSession, sensitivity: float = 0.5, start: float = 0.0, end: float | None = None) -> list[dict]:
    """One region per transient between start and end, each cut where the next one begins."""
    a, b = clamp(start, s.duration if end is None else end, total=s.duration)
    x = s.mono()[int(a * s.sr):int(b * s.sr)]
    times = onset_times(x, s.sr, sensitivity)
    regions = []
    for i, t in enumerate(times):
        r0 = max(0.0, t - PRE_ROLL_S)
        r1 = times[i + 1] - PRE_ROLL_S if i + 1 < len(times) else x.size / s.sr
        seg = x[int(r0 * s.sr):int(r1 * s.sr)]
        r1 = r0 + _tail_end(seg, s.sr) / s.sr
        if r1 - r0 >= MIN_REGION_S:
            regions.append({"start": round(float(a + r0), 4), "end": round(float(a + r1), 4)})
    return regions


def _zero_cross(x: np.ndarray, i: int, radius: int) -> int:
    """Nearest sign change at or before i (within radius) on the mono signal."""
    lo = max(1, i - radius)
    seg = x[lo - 1:i + 1]
    zc = np.flatnonzero(np.signbit(seg[:-1]) != np.signbit(seg[1:]))
    return lo + int(zc[-1]) if zc.size else i


def _peak(s: SamplerSession, start: float, end: float, fade_in_ms: float, fade_out_ms: float) -> float:
    """The peak of render(start, end) before normalising, without rendering it (a region can be minutes long)."""
    start, end = clamp(start, end, total=s.duration)
    a, b = int(start * s.sr), int(end * s.sr)
    a = _zero_cross(s.mono(), a, int(0.002 * s.sr)) if a > 0 else 0
    y = s.audio[a:b]
    n = y.shape[0]
    fi, fo = min(n // 2, int(fade_in_ms / 1000 * s.sr)), min(n // 2, int(fade_out_ms / 1000 * s.sr))
    peaks = [float(np.abs(y[fi:n - fo]).max(initial=0))]
    if fi:
        peaks.append(float(np.abs(y[:fi] * np.linspace(0, 1, fi, dtype=np.float32)[:, None]).max()))
    if fo:
        peaks.append(float(np.abs(y[n - fo:] * np.linspace(1, 0, fo, dtype=np.float32)[:, None]).max()))
    return max(peaks)


def render(s: SamplerSession, start: float, end: float, max_s: float = float("inf"),
           fade_in_ms: float = 1.0, fade_out_ms: float = 10.0, normalize: bool = False,
           span: tuple[float, float] | None = None) -> np.ndarray:
    """The audio of one region, ready to write: clamped, start on a zero crossing, short fades. With span (the
    whole region), [start, end) is one block of it, for listening to a long region piece by piece: the zero
    crossing and the fades only where the region begins and ends, the normalisation of the whole region."""
    start, end = clamp(start, end, max_s, s.duration)
    first = span is None or start <= span[0] + 1e-6
    last = span is None or end >= min(span[1], s.duration) - 1e-6
    a, b = int(start * s.sr), int(end * s.sr)
    a = _zero_cross(s.mono(), a, int(0.002 * s.sr)) if a > 0 and first else a
    y = s.audio[a:b].copy()
    n = y.shape[0]
    if n == 0:
        return y
    fi = min(n // 2, int(fade_in_ms / 1000 * s.sr)) if first else 0
    fo = min(n // 2, int(fade_out_ms / 1000 * s.sr)) if last else 0
    if fi:
        y[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    if fo:
        y[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    if normalize:
        peak = _peak(s, *span, fade_in_ms, fade_out_ms) if span else float(np.abs(y).max())
        if peak > 0:
            y *= 10 ** (-0.3 / 20) / peak  # -0.3 dBFS
    return np.clip(y, -1, 1)
