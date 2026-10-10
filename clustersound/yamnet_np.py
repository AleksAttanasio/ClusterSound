"""YAMNet (MobileNet v1) forward pass in plain numpy, NHWC layout.

Depthwise 3x3 convolutions are 9 shifted multiply-adds; pointwise 1x1 convolutions are
BLAS matmuls. No deep-learning runtime is needed, which keeps the app small.
"""
import numpy as np


def _same_pad(n: int, stride: int, k: int = 3) -> tuple[int, int, int]:
    """TensorFlow 'SAME' padding: (out, pad_before, pad_after)."""
    out = -(-n // stride)
    total = max((out - 1) * stride + k - n, 0)
    return out, total // 2, total - total // 2


def _conv3x3(x: np.ndarray, w: np.ndarray, b: np.ndarray, stride: int, depthwise: bool) -> np.ndarray:
    """x [N,H,W,C]; w [3,3,C] (depthwise) or [3,3,Cout] (first conv, C=1)."""
    n, h, wd, _ = x.shape
    oh, pt, pb = _same_pad(h, stride)
    ow, pl, pr = _same_pad(wd, stride)
    xp = np.pad(x, ((0, 0), (pt, pb), (pl, pr), (0, 0)))
    taps = [xp[:, dy: dy + stride * oh: stride, dx: dx + stride * ow: stride, :]
            for dy in range(3) for dx in range(3)]
    if not depthwise:
        # single input channel: im2col + one BLAS matmul
        cols = np.concatenate(taps, axis=-1).reshape(-1, 9)
        y = cols @ w.reshape(9, -1) + b
        return np.maximum(y, 0, out=y).reshape(n, oh, ow, -1)
    wf = w.reshape(9, -1)
    y = np.multiply(taps[0], wf[0])
    tmp = np.empty_like(y)
    for k in range(1, 9):
        np.multiply(taps[k], wf[k], out=tmp)
        y += tmp
    y += b
    return np.maximum(y, 0, out=y)


class YAMNet:
    def __init__(self, path: str):
        with np.load(path) as z:
            self.p = {k: z[k].astype(np.float32) if z[k].dtype.kind == "f" else int(z[k])
                      for k in z.files}
        self.n_layers = sum(1 for k in self.p if k.endswith("_stride"))

    def __call__(self, patches: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """[N,96,64] log-mel patches -> (scores [N,521], embeddings [N,1024])."""
        p = self.p
        x = patches[..., None].astype(np.float32)
        for i in range(1, self.n_layers + 1):
            s = p[f"l{i}_stride"]
            if f"l{i}_conv_w" in p:
                x = _conv3x3(x, p[f"l{i}_conv_w"], p[f"l{i}_conv_b"], s, depthwise=False)
            else:
                x = _conv3x3(x, p[f"l{i}_dw_w"], p[f"l{i}_dw_b"], s, depthwise=True)
                n, h, w, c = x.shape
                y = x.reshape(-1, c) @ p[f"l{i}_pw_w"] + p[f"l{i}_pw_b"]
                x = np.maximum(y, 0, out=y).reshape(n, h, w, -1)
        emb = x.mean(axis=(1, 2))
        logits = emb @ p["logits_w"] + p["logits_b"]
        return 1.0 / (1.0 + np.exp(-np.clip(logits, -50, 50))), emb
