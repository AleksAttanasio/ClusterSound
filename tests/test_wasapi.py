"""Windows Recorder backend (WASAPI loopback) against a fake `soundcard` module, on any OS."""
import sys
import time
import types

import numpy as np
import pytest
import soundfile as sf

from clustersound.sampler import recorder as R
from clustersound.sampler import wasapi
from clustersound.sampler.capture import CaptureError


class _Speaker:
    def __init__(self, id, name, channels=2):
        self.id, self.name, self.channels = id, name, channels


class _Rec:
    def __init__(self, channels, fail):
        self.channels, self.fail = channels, fail

    def __enter__(self):
        if self.fail:
            raise RuntimeError("device in use")
        return self

    def __exit__(self, *a):
        return False

    def record(self, numframes):
        time.sleep(0.002)
        return np.full((numframes, self.channels), 0.25, np.float32)


@pytest.fixture
def fake_sc(monkeypatch):
    spk = [_Speaker("{b}", "Cuffie"), _Speaker("{a}", "Altoparlanti", 6)]
    sc = types.SimpleNamespace(
        all_speakers=lambda: spk, default_speaker=lambda: spk[1],
        get_speaker=lambda id: next(s for s in spk if s.id == id),
        opened=[], fail=False)

    def get_microphone(id, include_loopback=False):
        assert include_loopback
        sc.opened.append(id)
        return types.SimpleNamespace(recorder=lambda samplerate, channels, blocksize: _Rec(channels, sc.fail))
    sc.get_microphone = get_microphone
    monkeypatch.setitem(sys.modules, "soundcard", sc)
    monkeypatch.setattr(wasapi, "_com_init", lambda: None)
    monkeypatch.setattr(R, "IS_WIN", True)
    return sc


def test_devices(fake_sc):
    devs = R.output_devices()
    assert [d["id"] for d in devs] == [R.ALL, "{a}", "{b}"]
    assert devs[1]["default"] and devs[1]["channels"] == 6
    assert all(d["backend"] == "wasapi" for d in devs) and devs[0]["note"]


def test_no_soundcard(monkeypatch):
    monkeypatch.setitem(sys.modules, "soundcard", None)  # import fails
    monkeypatch.setattr(R, "IS_WIN", True)
    assert R.output_devices() == []
    assert "soundcard" in R.unavailable_hint()
    with pytest.raises(CaptureError):
        wasapi.LoopbackBackend(None, lambda b: None)


def test_record_default_and_device(fake_sc, tmp_path):
    rec = R.Recorder()
    devs = {d["id"]: d for d in R.output_devices()}
    rec.start([devs[R.ALL], devs["{b}"]], {"format": "wav", "rate": 0, "channels": "all"}, str(tmp_path))
    time.sleep(0.3)
    st = rec.stop()
    assert fake_sc.opened == ["{a}", "{b}"]  # the mix entry is the default output
    assert [r["error"] for r in st["recordings"]] == [None, None]
    for r, ch in zip(sorted(st["recordings"], key=lambda r: r["device"] != "Default output"), (6, 2)):
        info = sf.info(r["path"])
        assert info.samplerate == wasapi.RATE and info.channels == ch and info.frames > 0


def test_open_error_reaches_start(fake_sc, tmp_path):
    fake_sc.fail = True
    with pytest.raises(CaptureError, match="device in use"):
        R.Recorder().start([R.output_devices()[1]], {"format": "wav"}, str(tmp_path))
