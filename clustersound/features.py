"""Hand-crafted acoustic features, sample type detection and light acoustic rules."""
import numpy as np

from .taxonomy import CLASS_INDEX, N_CLASSES

FEAT_SR = 32000
FEATURE_NAMES = [
    "duration", "log_duration", "attack", "decay20", "t60", "tail_ratio",
    "centroid", "rolloff", "flatness", "zcr",
    "band_sub", "band_low", "band_lowmid", "band_highmid", "band_high",
    "centroid_slope", "env_slope", "harmonicity", "f0", "onset_count", "onset_rate",
    "ioi_regularity",
]

TYPES = ["One-shot", "Loop", "Long/Texture"]


def _envelope(x: np.ndarray, sr: int, hop_s: float = 0.005, win_s: float = 0.010):
    hop = max(1, int(hop_s * sr))
    win = max(hop, int(win_s * sr))
    if len(x) < win:
        x = np.pad(x, (0, win - len(x)))
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    rms = np.sqrt(np.mean(x[idx] ** 2, axis=1) + 1e-12)
    return rms, hop / sr


def _stft_mag(x: np.ndarray, n_fft: int = 2048, hop: int = 512) -> np.ndarray:
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    n = 1 + (len(x) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n)[:, None]
    win = np.hanning(n_fft).astype(np.float32)
    return np.abs(np.fft.rfft(x[idx] * win, axis=1)).astype(np.float32)


def onsets(x: np.ndarray, sr: int, rise_db: float = 9.0, fallback: bool = True) -> np.ndarray:
    """Onset times (s): fast energy rises (dB) in log-spaced bands.

    Sustained sounds with beating or vibrato don't rise by several dB within ~16 ms, so they
    don't produce spurious onsets; every drum hit does. With fallback, a sound without any onset
    still gets one at its loudest frame.
    """
    hop = 256
    mag = _stft_mag(x, 1024, hop)
    if mag.shape[0] < 3:
        return np.array([0.0]) if fallback else np.array([])
    power = mag ** 2
    edges = np.unique(np.geomspace(2, power.shape[1] - 1, 9).astype(int))
    bands = np.add.reduceat(power, edges[:-1], axis=1)
    db = 10 * np.log10(bands + 1e-10)
    total_db = 10 * np.log10(power.sum(1) + 1e-10)
    lag = 2
    # near-silent bands fluctuate wildly in dB: floor every band at 35 dB below the loudest one
    db = np.maximum(db, db.max() - 35)
    rise = np.maximum(0, db[lag:] - db[:-lag])
    # mean of the 3 strongest band rises; frames far below the peak level are ignored
    nov = np.sort(rise, axis=1)[:, -3:].mean(1)
    nov = np.concatenate([np.zeros(lag), nov])
    nov[total_db < total_db.max() - 45] = 0
    peaks = []
    min_gap = int(0.07 * sr / hop)
    last = -min_gap
    for i in range(1, len(nov) - 1):
        if nov[i] >= rise_db and nov[i] >= nov[i - 1] and nov[i] >= nov[i + 1] and i - last >= min_gap:
            peaks.append(i)
            last = i
    if not peaks and fallback:
        peaks = [int(np.argmax(total_db))]
    return np.array(peaks) * hop / sr


def _harmonicity(x: np.ndarray, sr: int) -> tuple[float, float]:
    """Peak normalized autocorrelation (40-1000 Hz) on the loudest 100 ms, after the first dip."""
    n = int(0.100 * sr)
    if len(x) < n:
        return 0.0, 0.0
    # loudest window, skipping the first 20 ms (transient)
    rms, hop_s = _envelope(x, sr, 0.016, n / sr)
    skip = int(0.02 / hop_s)
    start_frame = skip + int(np.argmax(rms[skip:])) if len(rms) > skip else 0
    s = min(int(start_frame * hop_s * sr), len(x) - n)
    seg = x[s: s + n] * np.hanning(n)
    seg = seg - seg.mean()
    spec = np.fft.rfft(seg, 2 * n)
    ac = np.fft.irfft(np.abs(spec) ** 2)[:n]
    if ac[0] <= 0:
        return 0.0, 0.0
    # unbiased estimate: compensate for the shrinking overlap at long lags
    ac = ac / ac[0] / np.maximum(1 - np.arange(n) / n, 0.25)
    lo, hi = int(sr / 1000), min(int(sr / 40), n // 2)
    # skip the main lobe around lag 0: start after the autocorrelation first goes negative
    neg = np.flatnonzero(ac[:hi] < 0)
    if neg.size == 0:
        return 0.0, 0.0
    lo = max(lo, int(neg[0]))
    if hi <= lo:
        return 0.0, 0.0
    lag = lo + int(np.argmax(ac[lo:hi]))
    return float(np.clip(ac[lag], 0.0, 1.0)), float(sr / lag)


def compute(x: np.ndarray, sr: int, name_is_loop: bool = False) -> dict:
    """Features of a (trimmed) mono signal at FEAT_SR."""
    dur = len(x) / sr
    f: dict = {"duration": dur, "log_duration": float(np.log10(max(dur, 1e-3)))}
    if len(x) == 0 or np.max(np.abs(x)) <= 0:
        for k in FEATURE_NAMES:
            f.setdefault(k, 0.0)
        f["type"] = "One-shot"
        return f

    env, dt = _envelope(x, sr)
    peak_i = int(np.argmax(env))
    peak = env[peak_i]
    env_db = 20 * np.log10(env / peak + 1e-9)
    # attack: 10% -> 90% of peak amplitude before the peak
    pre = env[: peak_i + 1]
    a10 = int(np.argmax(pre >= 0.1 * peak))
    a90 = int(np.argmax(pre >= 0.9 * peak))
    f["attack"] = max(0.0, (a90 - a10) * dt)
    post = env_db[peak_i:]
    below20 = np.flatnonzero(post < -20)
    f["decay20"] = (below20[0] if below20.size else len(post)) * dt
    below60 = np.flatnonzero(post < -60)
    if below60.size:
        f["t60"] = below60[0] * dt
    elif len(post) < 3:
        f["t60"] = 0.0  # peak at the very end (e.g. a riser)
    else:
        # extrapolate from the slope of the decay down to -20 dB (or whatever is reached)
        end = max(2, below20[0] if below20.size else len(post))
        slope = (post[end - 1] - post[0]) / max((end - 1) * dt, dt)
        f["t60"] = float(min(10.0, 60.0 / max(-slope, 1.0))) if slope < 0 else dur
    t200 = int(0.2 / dt)
    energy = env ** 2
    f["tail_ratio"] = float(energy[peak_i + t200:].sum() / energy.sum()) if len(energy) > peak_i + t200 else 0.0

    mag = _stft_mag(x)
    power = mag ** 2
    freqs = np.fft.rfftfreq(2048, 1 / sr)
    frame_e = power.sum(axis=1) + 1e-12
    w = frame_e / frame_e.sum()
    centroid_t = (power @ freqs) / frame_e
    f["centroid"] = float((centroid_t * w).sum())
    cum = np.cumsum(power.sum(axis=0))
    f["rolloff"] = float(freqs[min(len(freqs) - 1, int(np.searchsorted(cum, 0.85 * cum[-1])))])
    # flatness over the active band only (bins within 50 dB of the frame peak), so a
    # high-passed noise burst still reads as noise
    active = power > power.max(axis=1, keepdims=True) * 1e-5
    logp = np.where(active, np.log(power + 1e-20), 0.0)
    cnt = np.maximum(active.sum(1), 1)
    gm = np.exp(logp.sum(1) / cnt)
    am = np.where(active, power, 0.0).sum(1) / cnt + 1e-20
    f["flatness"] = float(((gm / am) * w).sum())
    f["zcr"] = float(np.mean(np.abs(np.diff(np.signbit(x).astype(np.int8)))))
    total = power.sum() + 1e-12
    bands = [(0, 60), (60, 250), (250, 2000), (2000, 6000), (6000, sr / 2 + 1)]
    for name, (lo, hi) in zip(["band_sub", "band_low", "band_lowmid", "band_highmid", "band_high"], bands):
        m = (freqs >= lo) & (freqs < hi)
        f[name] = float(power[:, m].sum() / total)

    # trends, weighted to the audible part of the sound
    t = np.arange(len(centroid_t)) * 512 / sr
    loud = w > (0.05 / max(len(w), 1))
    if loud.sum() >= 3 and dur > 0.3:
        tt = t[loud]
        f["centroid_slope"] = float(np.polyfit(tt, np.log2(centroid_t[loud] + 1), 1)[0])
        et = np.arange(len(env_db)) * dt
        f["env_slope"] = float(np.polyfit(et, env_db, 1)[0])
    else:
        f["centroid_slope"] = 0.0
        f["env_slope"] = 0.0

    f["harmonicity"], f["f0"] = _harmonicity(x, sr)
    on = onsets(x, sr)
    f["onset_count"] = float(len(on))
    f["onset_rate"] = float(len(on) / max(dur, 0.1))
    if len(on) >= 3:
        ioi = np.diff(on)
        f["ioi_regularity"] = float(np.std(ioi) / (np.mean(ioi) + 1e-9))
    else:
        f["ioi_regularity"] = 1.0

    if (name_is_loop and dur > 1.0) or (dur >= 1.5 and len(on) >= 4):
        f["type"] = "Loop"
    elif dur >= 2.5:
        f["type"] = "Long/Texture"
    else:
        f["type"] = "One-shot"
    return f


PROFILE_TIMES = np.concatenate([[0.0], np.geomspace(0.01, 2.0, 15)])  # s after the peak


def mel_profile(mel: np.ndarray, n_valid: int) -> np.ndarray:
    """Compact spectro-temporal descriptor from the YAMNet log-mel (10 ms frames):
    attack spectrum (first 60 ms from the peak), body spectrum (60-400 ms), and the energy
    envelope sampled at log-spaced times after the peak. 64 + 64 + 16 = 144 values."""
    mel = mel[: max(1, n_valid)]
    lin = np.exp(mel)
    energy = np.log(lin.sum(1) + 1e-6)
    p = int(np.argmax(energy))
    floor = mel.min()

    def seg_mean(a, b):
        s = mel[p + a: p + b]
        return s.mean(0) if len(s) else np.full(mel.shape[1], floor)

    attack = seg_mean(0, 6)
    body = seg_mean(6, 40)
    idx = p + np.round(PROFILE_TIMES / 0.010).astype(int)
    env = np.where(idx < len(energy), energy[np.minimum(idx, len(energy) - 1)], energy.min() - 2.0)
    env = env - energy[p]
    # spectra relative to their own peak band: level-independent shape
    return np.concatenate([attack - attack.max(), body - attack.max(), env]).astype(np.float32)


def vector(f: dict) -> np.ndarray:
    v = np.array([float(f.get(k, 0.0)) for k in FEATURE_NAMES], dtype=np.float32)
    # compress heavy-tailed values
    for k in ("attack", "decay20", "t60", "centroid", "rolloff", "f0", "onset_count", "duration"):
        i = FEATURE_NAMES.index(k)
        v[i] = np.log1p(max(v[i], 0.0) * (1e-2 if k in ("centroid", "rolloff", "f0") else 10))
    return v


def _sig(x, center, width):
    return 1.0 / (1.0 + np.exp(np.clip(-(x - center) / width, -50, 50)))


def rule_logits(f: dict) -> np.ndarray:
    """Soft acoustic priors as additive log-scores per class (0 = neutral)."""
    r = np.zeros(N_CLASSES, dtype=np.float32)
    if not f or f.get("duration", 0) <= 0:
        return r

    def add(cid, val):
        r[CLASS_INDEX[cid]] += val

    low = f["band_sub"] + f["band_low"]
    high = f["band_high"]
    dur, decay, t60 = f["duration"], f["decay20"], f["t60"]
    harm, flat = f["harmonicity"], f["flatness"]
    one_shot = f.get("type") == "One-shot"

    # Low-frequency dominated sounds
    lo_s = _sig(low, 0.55, 0.1)
    for cid in ("kick", "sub808", "bass", "tom"):
        add(cid, 1.5 * lo_s - 0.75)
    for cid in ("closed_hat", "open_hat", "shaker", "ride", "crash", "cymbal_other", "tambourine", "snap"):
        add(cid, -1.5 * lo_s)
    # High-frequency dominated sounds
    hi_s = _sig(high, 0.35, 0.08)
    for cid in ("closed_hat", "open_hat", "shaker", "ride", "crash", "cymbal_other", "tambourine"):
        add(cid, 1.6 * hi_s - 0.6)
    for cid in ("kick", "sub808", "bass", "tom"):
        add(cid, -1.5 * hi_s)
    # Closed vs open hat, kick vs 808: decay
    long_s = _sig(decay, 0.25, 0.06)
    add("closed_hat", -1.5 * long_s + 0.4)
    add("open_hat", 1.5 * long_s - 0.6)
    add("crash", 1.0 * _sig(t60, 0.8, 0.2) - 0.4)
    tonal_tail = _sig(t60, 1.3, 0.25) * _sig(harm, 0.6, 0.1) * lo_s
    add("sub808", 2.0 * tonal_tail - 0.6)
    add("kick", -1.0 * tonal_tail)
    # Percussive low thump (fast attack, decays within ~0.35 s): drum rather than bass note
    thump = lo_s * (1 - _sig(decay, 0.35, 0.06)) * (1 - _sig(f["attack"], 0.01, 0.003))
    add("kick", 0.8 * thump)
    add("tom", 0.4 * thump)
    add("bass", -0.6 * thump)
    # Very short clicks
    short_s = 1 - _sig(dur, 0.12, 0.03)
    for cid in ("snap", "rimshot", "woodblock", "closed_hat"):
        add(cid, 0.6 * short_s)
    # Long, evolving material
    lng = _sig(dur, 2.0, 0.4)
    for cid in ("pad", "noise", "riser", "downlifter"):
        add(cid, 0.8 * lng - 0.3)
    if one_shot:
        for cid in ("pad", "noise", "riser", "downlifter"):
            add(cid, -0.6 * (1 - lng))
    # Tonality: melodic vs noisy
    ton = _sig(harm, 0.7, 0.08) * (1 - _sig(flat, 0.3, 0.08))
    for cid in ("bass", "synth", "pad", "keys", "guitar", "strings", "brass", "mallets", "vocal", "bell"):
        add(cid, 1.0 * ton - 0.4)
    noisy = _sig(flat, 0.25, 0.06)
    for cid in ("closed_hat", "open_hat", "shaker", "snare", "clap", "noise", "riser", "downlifter", "crash"):
        add(cid, 0.5 * noisy)
    # Sweeps: direction of the spectral centroid / envelope
    up = _sig(f["centroid_slope"], 0.4, 0.15) + _sig(f["env_slope"], 6, 2)
    down = _sig(-f["centroid_slope"], 0.4, 0.15) + _sig(-f["env_slope"], 25, 6)
    add("riser", 1.2 * up * lng - 0.4)
    add("downlifter", 1.2 * down * lng * (1 - _sig(f["env_slope"], 0, 3)) - 0.4)
    # Clap: several bursts within ~40 ms usually raise the attack time a little
    add("clap", 0.6 * _sig(f["attack"], 0.008, 0.003) * noisy)
    return r
