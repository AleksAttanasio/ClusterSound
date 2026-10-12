import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np
import pytest
import soundfile as sf

from clustersound.sampler import recorder as R
from clustersound.sampler.capture import CaptureError

SR = 48000


def _blocks(seconds=1.0, sr=SR, channels=2, block=1024):
    t = np.arange(int(seconds * sr)) / sr
    x = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    x = np.repeat(x[:, None], channels, axis=1)
    return [x[i:i + block] for i in range(0, len(x), block)]


def _write(tmp_path, fmt, sr=SR, channels=2, seconds=1.0):
    fmt = R.normalize_format(fmt)
    path = str(tmp_path / f"rec{R.FORMATS[fmt['format']]['ext']}")
    w = R.Writer(path, fmt, sr, channels)
    for b in _blocks(seconds, sr, channels):
        w.write(b)
    assert abs(w.seconds - seconds) < 1e-3
    return w.close()


# ---------------------------------------------------------------- formats
@pytest.mark.parametrize("fmt,subtype", [
    ({"format": "wav", "quality": "PCM_24"}, "PCM_24"),
    ({"format": "wav", "quality": "FLOAT"}, "FLOAT"),
    ({"format": "aiff", "quality": "PCM_16"}, "PCM_16"),
    ({"format": "flac"}, "PCM_24"),
    ({"format": "caf", "quality": "FLOAT"}, "FLOAT"),
    ({"format": "mp3", "quality": "320"}, "MPEG_LAYER_III"),
    ({"format": "ogg", "quality": "medium"}, "VORBIS"),
])
def test_writer_formats(tmp_path, fmt, subtype):
    path = _write(tmp_path, fmt)
    info = sf.info(path)
    assert info.subtype == subtype and info.channels == 2 and info.samplerate == SR
    assert abs(info.duration - 1.0) < 0.06  # lossy encoders pad a little


def test_writer_opus_resamples_to_48k(tmp_path):
    path = _write(tmp_path, {"format": "opus", "rate": 44100}, sr=44100)
    info = sf.info(path)
    assert info.samplerate == 48000 and abs(info.duration - 1.0) < 0.06


def test_writer_resample_and_channels(tmp_path):
    path = _write(tmp_path, {"format": "wav", "rate": 44100, "channels": "mono"}, sr=SR, channels=4)
    info = sf.info(path)
    assert (info.samplerate, info.channels) == (44100, 1) and abs(info.frames - 44100) <= 2
    path = _write(tmp_path, {"format": "flac", "channels": "all"}, channels=4)
    assert sf.info(path).channels == 4
    assert R.normalize_format({"format": "mp3", "channels": "all"})["channels"] == "stereo"


@pytest.mark.skipif(not shutil.which("afconvert"), reason="afconvert is macOS only")
def test_writer_m4a(tmp_path):
    path = _write(tmp_path, {"format": "m4a", "quality": "128"})
    assert path.endswith(".m4a") and os.path.exists(path) and not os.path.exists(path + ".part.caf")
    info = subprocess.run(["afinfo", path], capture_output=True, text=True).stdout
    assert "aac" in info.lower()


def test_normalize_format_defaults():
    assert R.normalize_format(None) == {"format": "wav", "quality": "PCM_24", "rate": 0, "channels": "stereo"}
    assert R.normalize_format({"format": "nope", "quality": "x", "rate": 12345})["format"] == "wav"


# ---------------------------------------------------------------- tap backend (fake helper)
FAKE = r'''import json, sys, time, struct
if sys.argv[1] == "list":
    print(json.dumps([{{"uid": "spk", "name": "Speakers", "channels": 2, "sample_rate": 48000, "default": True}}]))
    sys.exit(0)
dev = sys.argv[sys.argv.index("--device") + 1]
if dev == "broken":
    sys.stderr.write(json.dumps({{"error": "dispositivo non trovato: broken", "code": 0}}) + "\n")
    sys.exit(1)
out = sys.stdout.buffer
out.write(b'{{"sample_rate": 48000.0, "channels": 2}}\n'); out.flush()
block = struct.pack("<" + "f" * 2048, *([0.5, -0.5] * 1024))
while True:
    out.write(block[:4096 + 4])  # odd sizes: frames split across reads
    out.write(block[4096 + 4:]); out.flush()
    time.sleep(0.01)
'''


@pytest.fixture
def fake_tap(tmp_path):
    script = tmp_path / "fake_tap.py"
    script.write_text(FAKE.format())
    p = tmp_path / "cs-tap"  # sh wrapper: the interpreter path may contain spaces, which a shebang can't take
    p.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    p.chmod(0o755)
    return str(p)


def test_tap_backend_streams_blocks(fake_tap):
    got = []
    b = R.TapBackend("spk", lambda blk: got.append(blk.copy()), binary=fake_tap)
    b.start()
    assert (b.sr, b.channels) == (48000, 2)
    time.sleep(0.3)
    b.stop()
    a = np.concatenate(got)
    assert a.shape[1] == 2 and len(a) >= 1024
    assert np.allclose(a[:, 0], 0.5) and np.allclose(a[:, 1], -0.5)  # frame alignment survived split reads


def test_tap_backend_reports_helper_error(fake_tap):
    with pytest.raises(CaptureError, match="dispositivo non trovato"):
        R.TapBackend("broken", lambda b: None, binary=fake_tap).start()


# ---------------------------------------------------------------- recorder
class FakeBackend:
    def __init__(self, device, on_block, fail=False):
        self.sr, self.channels, self.on_block, self.fail, self.error = SR, 2, on_block, fail, None
        self.device = device

    def start(self):
        if self.fail:
            raise CaptureError("permesso negato")
        for b in _blocks(0.5):
            self.on_block(b)

    def stop(self):
        pass


def test_recorder_two_devices_one_file_each(tmp_path):
    rec = R.Recorder(lambda d, cb: FakeBackend(d, cb, fail=d["id"] == "bad"))
    devices = [{"id": "all", "name": "Tutte le uscite (mix)"}, {"id": "spk", "name": "Speakers"},
               {"id": "bad", "name": "Cuffie"}]
    st = rec.start(devices, {"format": "flac"}, str(tmp_path))
    assert st["running"] and [t["error"] for t in st["tracks"]] == [None, None, "permesso negato"]
    done = rec.stop()
    assert not done["running"] and len(done["recordings"]) == 2
    for r in done["recordings"]:
        assert r["path"].endswith(".flac") and abs(sf.info(r["path"]).duration - 0.5) < 0.01
        assert "uso personale" in open(r["path"] + ".source.txt").read()
    assert {r["device"] for r in done["recordings"]} == {"Tutte le uscite (mix)", "Speakers"}


def test_recorder_all_devices_failing(tmp_path):
    rec = R.Recorder(lambda d, cb: FakeBackend(d, cb, fail=True))
    with pytest.raises(CaptureError, match="Speakers: permesso negato"):
        rec.start([{"id": "spk", "name": "Speakers"}], {}, str(tmp_path))
    assert not rec.running
    with pytest.raises(CaptureError):
        R.Recorder().start([], {}, str(tmp_path))


def test_output_devices_with_fake_helper(monkeypatch, fake_tap):
    monkeypatch.setattr(R, "tap_binary", lambda build=True: fake_tap)
    devs = R.output_devices()
    assert [d["id"] for d in devs] == ["all", "spk"] and devs[1]["default"]


# ---------------------------------------------------------------- real helper
@pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("swiftc"), reason="needs macOS and swiftc")
def test_real_helper_lists_outputs():
    binary = R.tap_binary()
    assert binary
    devices = json.loads(subprocess.run([binary, "list"], capture_output=True, text=True, timeout=30).stdout)
    assert isinstance(devices, list) and all({"uid", "name", "channels"} <= set(d) for d in devices)
