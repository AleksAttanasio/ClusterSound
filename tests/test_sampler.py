import numpy as np
import soundfile as sf

from clustersound.sampler import session as S
from clustersound.sampler import slicing

from .synth import SR


# ---------------------------------------------------------------- session
def test_load_file_and_peaks(tmp_path):
    t = np.arange(SR * 2) / SR
    x = np.stack([np.sin(2 * np.pi * 220 * t), np.zeros_like(t)], axis=1).astype(np.float32) * 0.5
    p = tmp_path / "tone.wav"
    sf.write(p, x, SR)
    s = S.load_file(str(p))
    assert s.title == "tone" and s.origin == "file" and s.audio.shape == (SR * 2, 2)
    assert abs(s.duration - 2.0) < 1e-6 and not s.truncated
    pk = s.peaks(0.5, 1.5, cols=100)
    assert len(pk["wave_min"]) == len(pk["wave_max"]) == 100
    assert max(pk["wave_max"]) <= 0.25 + 1e-3 and min(pk["wave_min"]) >= -0.25 - 1e-3  # mono mix halves it
    assert s.clip(1.0, 0.5).shape[0] == SR // 2  # reversed bounds are swapped


def test_load_file_truncates(tmp_path):
    p = tmp_path / "long.wav"
    sf.write(p, np.zeros(SR * 3, dtype=np.float32), SR)
    s = S.load_file(str(p), max_seconds=1)
    assert s.truncated and s.frames == SR


def test_from_array_keeps_two_channels():
    s = S.from_array(np.zeros((10, 4)), SR)
    assert s.audio.shape == (10, 2) and s.audio.dtype == np.float32
    assert S.from_array(np.zeros(10), SR).audio.shape == (10, 1)


# ---------------------------------------------------------------- slicing
def _hits(n=6, gap=0.5, seed=0):
    rng = np.random.default_rng(seed)
    from . import synth
    x = np.zeros(int(SR * (n * gap + 0.5)), dtype=np.float32)
    starts = []
    for i in range(n):
        h = (synth.kick if i % 2 == 0 else synth.snare)(rng)[: int(gap * SR * 0.8)]
        a = int((0.25 + i * gap) * SR)
        x[a:a + h.size] += h
        starts.append(a / SR)
    return x, starts


def test_auto_slices_one_region_per_hit():
    x, starts = _hits()
    s = S.from_array(x, SR)
    regions = slicing.auto_slices(s, sensitivity=0.5)
    assert len(regions) == len(starts)
    for r, t in zip(regions, starts):
        assert abs(r["start"] - t) < 0.03
        assert r["end"] <= t + 0.5  # cut before the next hit (silent tail trimmed)


def test_auto_slices_respects_max_and_window():
    x, starts = _hits()
    s = S.from_array(x, SR)
    regions = slicing.auto_slices(s, max_s=0.1)
    assert all(r["end"] - r["start"] <= 0.1 + 1e-6 for r in regions)
    inner = slicing.auto_slices(s, start=1.0, end=2.0)
    assert inner and all(1.0 <= r["start"] < 2.0 for r in inner)


def test_onsets_across_chunks(monkeypatch):
    monkeypatch.setattr(slicing, "CHUNK_S", 1.0)  # force several chunks with overlap
    x, starts = _hits(n=8)
    t = slicing.onset_times(x, SR)
    assert len(t) == len(starts)


def test_clamp_and_render():
    assert slicing.clamp(5, 1, max_s=2) == (1.0, 3.0)
    assert slicing.clamp(-1, 100, max_s=30, total=10) == (0.0, 10.0)
    s = S.from_array(np.full(SR, 0.25, dtype=np.float32), SR)
    y = slicing.render(s, 0.0, 0.5, fade_in_ms=10, fade_out_ms=10, normalize=True)
    assert y.shape == (SR // 2, 1)
    assert y[0, 0] == 0 and y[-1, 0] == 0
    assert abs(np.abs(y).max() - 10 ** (-0.3 / 20)) < 1e-4
    assert slicing.render(s, 0, 10, max_s=0.2).shape[0] == int(0.2 * SR)
