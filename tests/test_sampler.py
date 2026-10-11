import numpy as np
import soundfile as sf

from clustersound.sampler import session as S

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
