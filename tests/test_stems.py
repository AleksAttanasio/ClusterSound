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
    assert np.allclose(y["other"][inner], 0.1 * x[inner], atol=2e-3)
    assert np.allclose(y["piano"][inner], 0.1 * x[inner], atol=2e-3)
    assert os.path.basename(res[0]["path"]) == "Brano - Drums.wav"


def test_mono_region_same_rate(tmp_path, fake, monkeypatch):
    x = _noise(2.0, ch=1)
    s = S.from_array(x, SR)
    res = stems.separate(s, 0.5, 1.5, str(tmp_path), "r")
    y = _read(res)
    assert y["drums"].shape == (SR, 1)
    assert np.allclose(y["drums"], 0.3 * x[int(0.5 * SR):int(1.5 * SR)], atol=1e-4)


def test_chosen_stems_rest_in_other(tmp_path, fake):
    x = _noise(1.0)
    s = S.from_array(x, SR)
    res = stems.separate(s, 0, 1, str(tmp_path), "c", keys=["piano", "drums"])
    assert [r["key"] for r in res] == ["drums", "piano", "other"]
    assert [r["label"] for r in res] == ["Drums", "Piano", "Other"]
    assert sorted(os.listdir(tmp_path)) == ["c - Drums.wav", "c - Other.wav", "c - Piano.wav"]
    y = _read(res)
    assert np.allclose(y["other"], (1 - .3 - .1) * x, atol=1e-4)  # bass, guitar, vocals, other
    assert np.allclose(sum(y.values()), x, atol=1e-4)


@pytest.mark.parametrize("keys", [[], ["other"], ["brass"]])
def test_chosen_rejects(keys):
    with pytest.raises(ValueError):
        stems.chosen(keys)


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
    assert "personal use" in open(res[0]["path"] + ".source.txt").read()
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


# ---------------------------------------------------------------- api job
@pytest.fixture
def api(tmp_path, fake, monkeypatch):
    import threading
    import time

    from clustersound.api import Api
    a = object.__new__(Api)
    a._stems_lock = threading.Lock()
    a._stems_job = {"state": "idle", "progress": 0.0, "scope": None, "stems": [], "error": None}
    a._stems_source = None
    a._stems_cancel = threading.Event()
    a._sampler = None
    monkeypatch.setattr(Api, "_settings", lambda self: {"sampler_dir": str(tmp_path / "samples")})
    monkeypatch.setattr(Api, "_inside_library", lambda self, folder: False)
    monkeypatch.setattr(stems, "status", lambda: {"installed": True, "model_ready": True})

    def wait():
        for _ in range(200):
            if a.stems_status()["job"]["state"] not in ("running", "downloading"):
                return a.stems_status()["job"]
            time.sleep(0.01)
        raise TimeoutError
    a.wait = wait
    return a


def test_api_region_job_and_open(api, tmp_path):
    assert api.stems_start()["error"] == "no audio open"
    api._sampler = S.from_array(_noise(2.0), SR, origin="capture", title="Rec", meta={"device": "Cuffie"})
    assert api.stems_start("region")["error"] == "no region selected"
    assert api.stems_start("region", 0.5, 1.5, [])["error"] == "choose at least one stem"
    assert api.stems_start("region", 0.5, 1.5)["error"] is None
    job = api.wait()
    assert job["state"] == "done" and job["scope"] == "region" and len(job["stems"]) == len(stems.STEMS)
    assert job["stems"][0]["path"].startswith(str(tmp_path / "samples"))
    assert api.stems_open(str(tmp_path / "other.wav"))["error"] == "stem not found"
    r = api.stems_open(job["stems"][0]["path"])
    assert r["error"] is None and r["session"]["title"] == "Rec · Drums" and r["session"]["origin"] == "capture"
    assert api._sampler.meta["device"] == "Cuffie" and abs(api._sampler.duration - 1.0) < 1e-3
    assert api.stems_start("all", keys=["vocals"])["error"] is None
    assert [r["label"] for r in api.wait()["stems"]] == ["Vocals", "Other"]
