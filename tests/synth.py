"""Synthetic drum/sound generators used by the tests."""
import numpy as np

SR = 44100


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _noise(n, rng):
    return rng.standard_normal(n).astype(np.float32)


def _hp_fast(x, cutoff_hz):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[f < cutoff_hz] = 0
    return np.fft.irfft(X, len(x)).astype(np.float32)


def _lp_fast(x, cutoff_hz):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[f > cutoff_hz] = 0
    return np.fft.irfft(X, len(x)).astype(np.float32)


def kick(rng, dur=0.45):
    t = _t(dur)
    f0 = rng.uniform(45, 60)
    f = f0 + rng.uniform(120, 200) * np.exp(-t * rng.uniform(25, 40))
    ph = 2 * np.pi * np.cumsum(f) / SR
    click = _hp_fast(_noise(len(t), rng), 2000) * np.exp(-t * 300) * 0.3
    return (np.sin(ph) * np.exp(-t * rng.uniform(7, 10)) + click).astype(np.float32)


def sub808(rng, dur=1.6):
    t = _t(dur)
    f0 = rng.uniform(40, 55)
    f = f0 + 60 * np.exp(-t * 40)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * np.exp(-t * rng.uniform(1.2, 2.0))).astype(np.float32)


def snare(rng, dur=0.3):
    t = _t(dur)
    body = np.sin(2 * np.pi * rng.uniform(180, 220) * t) * np.exp(-t * 25)
    noise = _hp_fast(_noise(len(t), rng), 1500) * np.exp(-t * rng.uniform(14, 20))
    return (0.6 * body + 0.5 * noise).astype(np.float32)


def closed_hat(rng, dur=0.08):
    t = _t(dur)
    return (_hp_fast(_noise(len(t), rng), 7000) * np.exp(-t * rng.uniform(50, 70))).astype(np.float32)


def open_hat(rng, dur=0.7):
    t = _t(dur)
    return (_hp_fast(_noise(len(t), rng), 6500) * np.exp(-t * rng.uniform(5, 7))).astype(np.float32)


def clap(rng, dur=0.35):
    t = _t(dur)
    env = np.zeros_like(t)
    for k, off in enumerate([0, 0.011, 0.022, 0.034]):
        m = t >= off
        env[m] += np.exp(-(t[m] - off) * (200 if k < 3 else 18))
    n = _hp_fast(_lp_fast(_noise(len(t), rng), 5000), 800)
    return (n * env * 0.5).astype(np.float32)


def pad(rng, dur=4.0):
    t = _t(dur)
    f = rng.uniform(150, 300)
    x = sum(np.sin(2 * np.pi * f * h * t * (1 + 0.003 * d)) / h
            for h in (1, 2, 3) for d in (-1, 0, 1))
    env = np.minimum(1, t / 1.0) * np.minimum(1, (dur - t) / 1.0)
    return (0.2 * x * env).astype(np.float32)


def riser(rng, dur=4.0):
    t = _t(dur)
    n = _noise(len(t), rng)
    # crude moving band-pass: sum of high-passed noise with rising amplitude
    out = np.zeros_like(n)
    seg = len(t) // 8
    for k in range(8):
        s = slice(k * seg, (k + 1) * seg)
        out[s] = _hp_fast(n[s], 300 * 2 ** (k * 0.6))
    return (out * (t / dur) ** 2 * 0.5).astype(np.float32)


def drum_loop(rng, bars=1, bpm=120):
    beat = 60 / bpm
    n = int(4 * bars * beat * SR)
    out = np.zeros(n, np.float32)

    def place(x, at):
        i = int(at * SR)
        j = min(n, i + len(x))
        out[i:j] += x[: j - i]

    for b in range(4 * bars):
        place(kick(rng) if b % 2 == 0 else snare(rng), b * beat)
        place(closed_hat(rng) * 0.5, b * beat + beat / 2)
    return out / np.max(np.abs(out)) * 0.9


GENERATORS = {
    "kick": kick, "sub808": sub808, "snare": snare, "closed_hat": closed_hat,
    "open_hat": open_hat, "clap": clap, "pad": pad, "riser": riser,
}
