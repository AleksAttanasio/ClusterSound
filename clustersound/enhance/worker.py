"""The child process of an enhancement job: reads a WAV, runs one model over it, writes the result, exits.

Protocol (runner.py): one JSON object per stdout line, {"progress": 0..1} while working, then
{"done": out_path} or {"error": message}. The model is the only thing loaded, and it lives as long as the job.

    python -m clustersound.enhance.worker --model apollo IN.wav OUT.wav
"""
import argparse
import json
import sys
from typing import Callable

import numpy as np
import soundfile as sf
import soxr

from ..paths import torch_device

# Measured with Apollo on MPS, 30 s stereo: 2 s blocks one channel at a time peak at ~1.6 GB (6 s stereo blocks:
# ~6 GB) for ~15% more time; 0.5 s of padding already matches a single pass within -80 dB.
CHUNK_S = 2.0   # processed per block: bounded memory whatever the length
PAD_S = 0.5     # real audio on both sides of a block, run through the model and discarded (its edges are wrong)
XFADE_S = 0.05  # blocks overlap this much and are crossfaded, so the seams don't click


def _say(**msg) -> None:
    print(json.dumps(msg), flush=True)


def process(fn: Callable[[np.ndarray], np.ndarray], x: np.ndarray, sr: int,
            on_progress: Callable[[float], None] | None = None) -> np.ndarray:
    """Run fn over x (frames, channels) at sr in padded, crossfaded blocks; fn takes and returns (channels, n)."""
    n = x.shape[0]
    hop, pad, xf = int(CHUNK_S * sr), int(PAD_S * sr), int(XFADE_S * sr)
    out = np.zeros_like(x, dtype=np.float32)
    tail = None  # the previous block's last xf frames, to crossfade into this one's head
    for s in range(0, n, hop):
        e = min(n, s + hop + xf)
        a, b = max(0, s - pad), min(n, e + pad)
        y = fn(np.ascontiguousarray(x[a:b].T, dtype=np.float32)).T[s - a: e - a]
        if tail is not None:
            k = min(len(tail), len(y))
            fade = np.linspace(0, 1, k, dtype=np.float32)[:, None]
            y[:k] = tail[:k] * (1 - fade) + y[:k] * fade
        last = s + hop >= n
        keep = y.shape[0] if last else hop
        out[s:s + keep] = y[:keep]
        tail = None if last else y[hop:]
        if on_progress:
            on_progress(min(1.0, (s + hop) / n))
    return out


def enhance(fn: Callable[[np.ndarray], np.ndarray], model_sr: int, x: np.ndarray, sr: int,
            on_progress: Callable[[float], None] | None = None) -> tuple[np.ndarray, int]:
    """x (frames, channels) at sr -> (enhanced, rate). Output is at the higher of the two rates: a source below the
    model's rate is upsampled (that's where the new high frequencies go), one above it keeps its own rate."""
    out_sr = max(sr, model_sr)
    y = soxr.resample(x, sr, model_sr, "VHQ") if sr != model_sr else x
    y = process(fn, y.reshape(len(y), -1), model_sr, on_progress)
    if out_sr != model_sr:
        y = soxr.resample(y, model_sr, out_sr, "VHQ")
    want = int(round(x.shape[0] * out_sr / sr))
    y = y[:want] if len(y) >= want else np.pad(y, ((0, want - len(y)), (0, 0)))
    peak = float(np.abs(y).max(initial=0.0))
    if peak > 0.999:  # the model can overshoot: scale down rather than clip
        y = y * (0.999 / peak)
    return y.astype(np.float32), out_sr


class TorchModel:
    """A torch module as fn: (channels, n) float32 -> (channels, n), on the GPU (CUDA or MPS) when it can."""

    def __init__(self, net, sr: int):
        import torch
        self.torch, self.net, self.sr = torch, net, sr
        self.device = torch_device(torch)
        self.net.to(self.device)

    def _run(self, x):
        t = self.torch.from_numpy(x)[None].to(self.device)
        return self.net(t)[0].float().cpu().numpy()

    def _channel(self, x):
        try:
            return self._run(x)
        except Exception:  # an op missing on this GPU: CPU from now on
            if self.device == "cpu":
                raise
            self.device = "cpu"
            self.net.to("cpu")
            return self._run(x)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        with self.torch.inference_mode():  # one channel at a time: half the peak memory of a stereo batch
            out = np.concatenate([self._channel(x[i:i + 1]) for i in range(x.shape[0])])
        if self.device == "mps":
            self.torch.mps.empty_cache()  # MPS keeps every block's buffers cached otherwise
        elif self.device == "cuda":
            self.torch.cuda.empty_cache()
        return out


def load_model(key: str) -> TorchModel:
    from . import models
    m = models.get(key)
    if not models.ready(key):
        raise RuntimeError(f"model {m.label} not downloaded")
    if key == "apollo":
        from . import apollo_net
        return TorchModel(apollo_net.load(models.weights_path(key)), apollo_net.SR)
    raise ValueError(f"unknown model: {key}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="clustersound-enhance")
    ap.add_argument("--model", default="apollo")
    ap.add_argument("src")
    ap.add_argument("dst")
    args = ap.parse_args(argv)
    try:
        x, sr = sf.read(args.src, dtype="float32", always_2d=True)
        if not len(x):
            raise ValueError("empty audio")
        _say(progress=0.0, stage="loading")
        model = load_model(args.model)
        _say(progress=0.0, stage="running", device=model.device)
        y, out_sr = enhance(model, model.sr, x, sr, lambda p: _say(progress=round(p, 3)))
        sf.write(args.dst, y, out_sr, subtype="PCM_24")
    except Exception as e:
        _say(error=str(e) or e.__class__.__name__)
        return 1
    _say(done=args.dst, sr=out_sr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
