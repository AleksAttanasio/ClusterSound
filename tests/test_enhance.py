import json
import os
import sys

import numpy as np
import pytest
import soundfile as sf

from clustersound.enhance import models, runner, worker

from .synth import SR


def _tones(seconds, ch=2, sr=SR):
    t = np.arange(int(seconds * sr)) / sr
    x = sum(a * np.sin(2 * np.pi * f * t[:, None] + np.arange(ch)) for f, a in ((110, .3), (440, .1), (3100, .05)))
    return x.astype(np.float32)


class Gain:
    """Model stand-in: a fixed gain, so a correct block/crossfade pass returns exactly gain * x."""

    def __init__(self, g=0.5):
        self.g, self.calls, self.widths = g, 0, []

    def __call__(self, x):
        assert x.dtype == np.float32 and x.ndim == 2 and x.shape[0] <= 2
        self.calls += 1
        self.widths.append(x.shape[1])
        return x * self.g


@pytest.mark.parametrize("seconds", [0.3, worker.CHUNK_S, 7.3])
def test_process_blocks_add_up_to_one_pass(seconds):
    x, m = _tones(seconds), Gain()
    y = worker.process(m, x, SR)
    assert y.shape == x.shape
    np.testing.assert_allclose(y, x * 0.5, atol=1e-6)  # padding discarded, crossfades sum to one
    assert m.calls == int(np.ceil(len(x) / (worker.CHUNK_S * SR)))
    assert max(m.widths) <= int((worker.CHUNK_S + worker.XFADE_S + 2 * worker.PAD_S) * SR)  # memory stays bounded


def test_process_reports_progress_to_one():
    seen = []
    worker.process(Gain(), _tones(5), SR, seen.append)
    assert seen == sorted(seen) and seen[-1] == 1.0


def test_enhance_upsamples_low_rate_sources():
    x = _tones(1.0, sr=22050)
    y, sr = worker.enhance(Gain(1.0), 44100, x, 22050)
    assert sr == 44100 and y.shape == (44100, 2)


def test_enhance_keeps_higher_source_rate_and_mono():
    x = _tones(1.0, ch=1, sr=48000)
    y, sr = worker.enhance(Gain(1.0), 44100, x, 48000)
    assert sr == 48000 and y.shape == (48000, 1)
    np.testing.assert_allclose(y[1000:-1000], x[1000:-1000], atol=1e-3)  # resampling round trip


def test_enhance_scales_down_instead_of_clipping():
    y, _ = worker.enhance(Gain(4.0), SR, _tones(1.0), SR)
    assert np.abs(y).max() == pytest.approx(0.999, abs=1e-4)


def test_worker_main_writes_the_result(tmp_path, monkeypatch, capsys):
    src, dst = tmp_path / "in.wav", tmp_path / "out.wav"
    sf.write(src, _tones(1.0, sr=22050), 22050)
    m = Gain()
    m.sr, m.device = SR, "cpu"
    monkeypatch.setattr(worker, "load_model", lambda key: m)
    assert worker.main(["--model", "apollo", str(src), str(dst)]) == 0
    msgs = [json.loads(l) for l in capsys.readouterr().out.splitlines()]
    assert msgs[-1] == {"done": str(dst), "sr": SR}
    assert any(msg.get("progress") == 1.0 for msg in msgs)
    y, sr = sf.read(dst)
    assert sr == SR and y.shape == (SR, 2)


def test_worker_main_reports_errors(tmp_path, monkeypatch, capsys):
    src = tmp_path / "in.wav"
    sf.write(src, _tones(0.5), SR)
    monkeypatch.setattr(models, "ready", lambda key: False)
    assert worker.main(["--model", "apollo", str(src), str(tmp_path / "out.wav")]) == 1
    assert "non scaricato" in json.loads(capsys.readouterr().out.splitlines()[-1])["error"]


def _fake_worker(tmp_path, body):
    script = tmp_path / "fake_worker.py"
    script.write_text("import json, sys, time\nsay = lambda **m: print(json.dumps(m), flush=True)\n" + body)
    return [sys.executable, str(script)]


def test_runner_follows_progress_and_result(tmp_path):
    dst = tmp_path / "out.wav"
    cmd = _fake_worker(tmp_path, f"print('a library warning')\nsay(progress=0.5)\nopen({str(dst)!r}, 'w').write('x')\n"
                                 f"say(done={str(dst)!r}, sr=44100)\n")
    seen = []
    out = runner.run("apollo", "in.wav", str(dst), seen.append, cmd=cmd)
    assert out == {"done": str(dst), "sr": 44100} and seen == [0.5] and dst.exists()


def test_runner_raises_the_worker_error_and_cleans_up(tmp_path):
    dst = tmp_path / "out.wav"
    cmd = _fake_worker(tmp_path, f"open({str(dst)!r}, 'w').write('x')\nsay(error='niente MPS')\nsys.exit(1)\n")
    with pytest.raises(RuntimeError, match="niente MPS"):
        runner.run("apollo", "in.wav", str(dst), cmd=cmd)
    assert not dst.exists()


def test_runner_reports_a_crash(tmp_path):
    cmd = _fake_worker(tmp_path, "raise SystemExit('segfault simulato')\n")
    with pytest.raises(RuntimeError, match="segfault simulato"):
        runner.run("apollo", "in.wav", str(tmp_path / "out.wav"), cmd=cmd)


def test_runner_cancel_kills_the_worker_and_removes_the_partial(tmp_path):
    dst, pid = tmp_path / "out.wav", tmp_path / "pid"
    cmd = _fake_worker(tmp_path, f"import os\nopen({str(pid)!r}, 'w').write(str(os.getpid()))\n"
                                 f"open({str(dst)!r}, 'w').write('x')\nsay(progress=0.1)\ntime.sleep(60)\n")
    with pytest.raises(runner.Cancelled):
        runner.run("apollo", "in.wav", str(dst), cancelled=lambda: dst.exists() and pid.exists(), cmd=cmd)
    assert not dst.exists()
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid.read_text()), 0)


def test_command_runs_the_worker_module_or_the_frozen_app(monkeypatch):
    assert runner.command("apollo", "a", "b")[1:3] == ["-m", "clustersound.enhance.worker"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert runner.command("apollo", "a", "b")[1] == runner.WORKER_FLAG


def test_status_lists_models_without_importing_torch(monkeypatch, tmp_path):
    monkeypatch.setattr(models, "data_dir", lambda: tmp_path)
    st = models.status()
    apollo = next(m for m in st["models"] if m["key"] == "apollo")
    assert st["default"] == "apollo" and apollo["mb"] > 0 and apollo["model_ready"] is False
    with pytest.raises(ValueError):
        models.get("nope")
