"""Dynamics view data for the detail panel: waveform, RMS envelope, ADSR and levels."""
import numpy as np

from . import audio_io, frontend


def _minmax(x: np.ndarray, n: int) -> tuple[list, list]:
    if len(x) == 0:
        return [], []
    n = min(n, len(x))
    edges = np.linspace(0, len(x), n + 1).astype(int)
    mins = np.minimum.reduceat(x, edges[:-1])
    maxs = np.maximum.reduceat(x, edges[:-1])
    return np.round(mins, 4).tolist(), np.round(maxs, 4).tolist()


def adsr(env_db: np.ndarray, dt: float) -> dict:
    """Estimate Attack/Decay/Sustain/Release from an RMS envelope in dB re peak."""
    n = len(env_db)
    if n == 0:
        return {}
    lin = 10 ** (env_db / 20)
    peak_i = int(np.argmax(lin))
    a_start = int(np.argmax(lin[: peak_i + 1] >= 0.1))
    attack_end = peak_i
    total = n * dt
    after = env_db[peak_i:]
    # sustain = median level of the 40%-80% part of what follows the peak
    if len(after) > 10:
        mid = after[int(len(after) * 0.4): int(len(after) * 0.8)]
        sustain_db = float(np.median(mid))
    else:
        sustain_db = float(after[-1])
    sustain_db = min(0.0, sustain_db)
    # decay ends when the envelope first gets within 3 dB of the sustain level
    reach = np.flatnonzero(after <= sustain_db + 3)
    decay_end = peak_i + (int(reach[0]) if reach.size else 0)
    # release starts at the last frame still within 3 dB of sustain
    above = np.flatnonzero(env_db >= sustain_db - 3)
    release_start = max(decay_end, int(above[-1]) if above.size else decay_end)
    floor = np.flatnonzero(env_db[release_start:] < -60)
    release_end = release_start + (int(floor[0]) if floor.size else n - 1 - release_start)
    return {
        "attack_start": a_start * dt,
        "attack_end": attack_end * dt,
        "decay_end": decay_end * dt,
        "sustain_db": sustain_db,
        "release_start": release_start * dt,
        "release_end": release_end * dt,
        "attack_ms": (attack_end - a_start) * dt * 1000,
        "decay_ms": (decay_end - attack_end) * dt * 1000,
        "release_ms": (release_end - release_start) * dt * 1000,
        "total": total,
    }


def details(path: str, points: int = 1000) -> dict:
    x, sr = audio_io.load_mono(path)
    dur = len(x) / sr if sr else 0.0
    out: dict = {"duration": dur}
    if len(x) == 0:
        return out
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x ** 2)))
    out["peak_dbfs"] = 20 * np.log10(peak + 1e-12)
    out["rms_dbfs"] = 20 * np.log10(rms + 1e-12)
    out["crest_db"] = out["peak_dbfs"] - out["rms_dbfs"]
    out["wave_min"], out["wave_max"] = _minmax(x, points)

    hop = max(1, int(0.005 * sr))
    win = 2 * hop
    xp = np.pad(x, (0, max(0, win - len(x))))
    nfr = 1 + (len(xp) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(nfr)[:, None]
    env = np.sqrt(np.mean(xp[idx] ** 2, axis=1) + 1e-12)
    env_db = 20 * np.log10(env / env.max())
    dt = hop / sr
    out["adsr"] = adsr(env_db, dt)
    out["t60"] = None
    tail = np.flatnonzero(env_db[int(np.argmax(env_db)):] < -60)
    if tail.size:
        out["t60"] = float(tail[0] * dt)
    # envelope downsampled for drawing (dB, clamped to -80)
    step = max(1, len(env_db) // points)
    out["env_db"] = np.round(np.maximum(env_db[::step], -80), 2).tolist()
    out["env_dt"] = dt * step

    mel = frontend.log_mel(frontend.pad_waveform(audio_io.resample(x, sr, frontend.SR)))
    frames = int(np.ceil(dur / 0.010)) + 1
    mel = mel[: max(1, frames)]
    if mel.shape[0] > 400:
        sel = np.linspace(0, mel.shape[0] - 1, 400).astype(int)
        mel = mel[sel]
    lo, hi = float(mel.min()), float(mel.max())
    out["mel"] = np.round((mel - lo) / (hi - lo + 1e-9) * 255).astype(np.uint8).tolist()
    return out
