"""Offline render of a pattern to a seamless stereo loop (numpy), matching the UI sequencer."""
import numpy as np
import soundfile as sf
import soxr

from . import model

SR = 44100


def vel_gain(vel: int) -> float:
    return (vel / 127.0) ** 1.5  # same curve as ui/sequencer.js


def pan_gains(pan: float) -> tuple[float, float]:
    a = (pan + 1) * np.pi / 4  # equal power
    return float(np.cos(a)), float(np.sin(a))


class SampleCache:
    def __init__(self, resolve):
        self.resolve = resolve  # ref -> local path (or None)
        self._raw: dict[str, np.ndarray] = {}
        self._pitched: dict[tuple, np.ndarray] = {}

    def get(self, ref: dict, semitones: float = 0.0) -> np.ndarray | None:
        path = self.resolve(ref)
        if not path:
            return None
        if path not in self._raw:
            try:
                x, sr = sf.read(path, dtype="float32", always_2d=True, frames=30 * 48000)
            except Exception:
                return None
            x = x[:, :2] if x.shape[1] >= 2 else np.repeat(x, 2, axis=1)
            if sr != SR:
                x = soxr.resample(x, sr, SR).astype(np.float32)
            self._raw[path] = x
        key = (path, round(semitones, 3))
        if key not in self._pitched:
            x = self._raw[path]
            ratio = 2 ** (semitones / 12.0)
            if abs(semitones) > 1e-3 and len(x) > 8:
                # resampling = sampler-style repitch (pitch and length change together)
                x = soxr.resample(x, SR, SR / ratio).astype(np.float32)
            self._pitched[key] = x
        return self._pitched[key]


def _filter(buf: np.ndarray, hp: float, lp: float) -> np.ndarray:
    """2nd-order Butterworth magnitude response applied in the frequency domain (zero phase)."""
    if not hp and not lp:
        return buf
    n = len(buf)
    spec = np.fft.rfft(buf, axis=0)
    f = np.fft.rfftfreq(n, 1 / SR)
    h = np.ones_like(f)
    if lp:
        h *= 1 / np.sqrt(1 + (f / lp) ** 4)
    if hp:
        with np.errstate(divide="ignore"):
            h *= 1 / np.sqrt(1 + (hp / np.maximum(f, 1e-6)) ** 4)
    return np.fft.irfft(spec * h[:, None], n=n, axis=0).astype(np.float32)


def _add(out: np.ndarray, x: np.ndarray, start: int, gain: float, length: int | None = None) -> None:
    """Mix x into out at start, wrapping around the loop end; optional gate with a short fade."""
    if length is not None and length < len(x):
        x = x[:length].copy()
        fade = min(len(x), int(0.01 * SR))
        if fade:
            x[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    n = len(out)
    pos = start % n
    remaining = x * gain
    while len(remaining):
        take = min(len(remaining), n - pos)
        out[pos:pos + take] += remaining[:take]
        remaining = remaining[take:]
        pos = 0


def bass_semitones(p: dict, layer: dict, note_semi: int) -> float:
    """Repitch for a bass note: target note minus the sample's own root (if known)."""
    target = model.bass_root_midi(p) + note_semi
    root = layer.get("root")
    if root is None:
        root = model.bass_root_midi(p)
    return target - root + layer.get("pitch", 0)


def render(p: dict, resolve) -> np.ndarray:
    p = model.validate(p)
    sec_per_tick = 60.0 / p["bpm"] / model.PPQ
    total = int(round(model.n_steps(p) * model.TICKS_PER_STEP * sec_per_tick * SR))
    mix = np.zeros((total, 2), np.float32)
    cache = SampleCache(resolve)
    audible = model.audible_buses(p)
    # closed hat chokes the open hat (choke group 1 in the exported Drum Rack)
    chokes = sorted(t for ly in model.active_layers(p["buses"]["chat"]) for t, _ in model.drum_hits(p, "chat", ly)) \
        if "chat" in audible else []
    loop_ticks = model.n_steps(p) * model.TICKS_PER_STEP
    for bid in audible:
        bus = p["buses"][bid]
        layers = model.active_layers(bus)
        if not layers:
            continue
        busbuf = np.zeros_like(mix)
        for layer in layers:
            off = int(layer.get("offset_ms", 0) / 1000 * SR)
            if bid == "bass":
                for nt in bus["notes"]:
                    x = cache.get(layer["ref"], bass_semitones(p, layer, nt["semi"]))
                    if x is None:
                        break
                    start = int(model.step_tick(nt["step"], p["swing"]) * sec_per_tick * SR) + off
                    length = int(nt["len"] * model.TICKS_PER_STEP * sec_per_tick * SR)
                    _add(busbuf, x, start, layer["volume"] * vel_gain(nt.get("vel", 100)), length)
            else:
                x = cache.get(layer["ref"], layer.get("pitch", 0))
                if x is None:
                    continue
                for tick, vel in model.drum_hits(p, bid, layer):
                    start = int(tick * sec_per_tick * SR) + off
                    gate = None
                    if bid == "ohat" and chokes:
                        nxt = next((c for c in chokes if c > tick), chokes[0] + loop_ticks)
                        gate = int((nxt - tick) * sec_per_tick * SR)
                    _add(busbuf, x, start, layer["volume"] * vel_gain(vel), gate)
        busbuf = _filter(busbuf, bus.get("hp", 0), bus.get("lp", 0))
        gl, gr = pan_gains(bus.get("pan", 0.0))
        busbuf[:, 0] *= gl * np.sqrt(2) * bus["volume"]
        busbuf[:, 1] *= gr * np.sqrt(2) * bus["volume"]
        mix += busbuf
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0.98:
        mix *= 0.98 / peak
    return mix


def write_wav(path: str, p: dict, resolve, loops: int = 1) -> float:
    x = render(p, resolve)
    if loops > 1:
        x = np.tile(x, (loops, 1))
    sf.write(path, x, SR, subtype="PCM_24")
    return len(x) / SR
