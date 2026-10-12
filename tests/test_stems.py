import os

import numpy as np
import pytest
import soundfile as sf

from clustersound.sampler import session as S
from clustersound.sampler import stems

from .synth import SR

FRACTIONS = {"drums": .3, "bass": .2, "other": .1, "vocals": .15, "guitar": .15, "piano": .1}


class FakeModel:
    """Each source is a fixed fraction of the mix, so the stems must sum back to the source."""
    samplerate = 44100

    def __init__(self):
        self.calls = 0

    def separate(self, x):
        self.calls += 1
        return {k: x * f for k, f in FRACTIONS.items()}


@pytest.fixture
def fake(monkeypatch):
    m = FakeModel()
    monkeypatch.setattr(stems, "_load_model", lambda: m)
    return m


def _noise(seconds, ch=2, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * SR)) / SR
    # band-limited (white noise would lose its top octave in the resampler round trip)
    x = sum(a * np.sin(2 * np.pi * f * t[:, None] + rng.uniform(0, 6.3, ch))
            for f, a in ((110, .3), (440, .1), (3100, .05), (9000, .02)))
    return x.astype(np.float32)


def _read(res):
    return {r["key"]: sf.read(r["path"], dtype="float32", always_2d=True)[0] for r in res}


def test_stems_sum_to_source_across_blocks(tmp_path, fake, monkeypatch):
    monkeypatch.setattr(stems, "BLOCK_S", 1.0)
    monkeypatch.setattr(stems, "OVERLAP_S", 0.2)
    fake.samplerate = 48000  # source at 44.1 kHz: resampled both ways
    x = _noise(3.5)
    s = S.from_array(x, SR, title="Brano")
    seen = []
    res = stems.separate(s, 0, s.duration, str(tmp_path), "Brano", on_progress=seen.append)
    assert [r["key"] for r in res] == [k for k, _ in stems.STEMS] and fake.calls == 4
    assert seen[-1] == 1.0 and seen == sorted(seen)
    y = _read(res)
    assert all(v.shape == x.shape for v in y.values())
    total = sum(y.values())
    inner = slice(int(0.01 * SR), -int(0.01 * SR))  # resampling edges
    assert np.abs(total[inner] - x[inner]).max() < 2e-3
    assert np.allclose(y["other"][inner], 0.2 * x[inner], atol=2e-3)  # other + piano
    assert os.path.basename(res[0]["path"]) == "Brano - Batteria.wav"


def test_mono_region_same_rate(tmp_path, fake, monkeypatch):
    x = _noise(2.0, ch=1)
    s = S.from_array(x, SR)
    res = stems.separate(s, 0.5, 1.5, str(tmp_path), "r")
    y = _read(res)
    assert y["drums"].shape == (SR, 1)
    assert np.allclose(y["drums"], 0.3 * x[int(0.5 * SR):int(1.5 * SR)], atol=1e-4)


def test_cancel_leaves_no_files(tmp_path, fake, monkeypatch):
    monkeypatch.setattr(stems, "BLOCK_S", 0.5)
    s = S.from_array(_noise(2.0), SR)
    calls = iter([False, True])
    with pytest.raises(stems.Cancelled):
        stems.separate(s, 0, 2, str(tmp_path), "x", cancelled=lambda: next(calls))
    assert os.listdir(tmp_path) == []


def test_folders_and_notes(tmp_path, fake):
    rec = tmp_path / "rec" / "2026-10-12 - Altoparlanti.wav"
    rec.parent.mkdir()
    sf.write(rec, _noise(0.5), SR)
    s = S.load_file(str(rec), origin="capture")
    s.meta = {"captured_at": "2026-10-12 10:00"}
    folder = stems.out_folder(s, "all", str(tmp_path / "samples"))
    assert folder == str(rec)[:-4] + " - stem"
    res = stems.separate(s, 0, s.duration, folder, s.title)
    assert "uso personale" in open(res[0]["path"] + ".source.txt").read()
    region = stems.out_folder(s, "region", str(tmp_path / "samples"))
    assert region.startswith(str(tmp_path / "samples")) and region.endswith("stem")


def test_status_without_extra(monkeypatch):
    monkeypatch.setattr(stems, "installed", lambda: False)
    st = stems.status()
    assert not st["installed"] and not st["model_ready"] and "stems" in st["install_hint"]


@pytest.mark.skipif(not (stems.installed() and os.environ.get("CS_STEMS_REAL")), reason="demucs reale: CS_STEMS_REAL=1")
def test_real_demucs(tmp_path):
    s = S.from_array(_noise(8.0), SR)
    res = stems.separate(s, 0, s.duration, str(tmp_path), "real")
    assert all(os.path.getsize(r["path"]) > 0 for r in res)
