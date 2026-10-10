"""YAMNet inference (pure numpy, see yamnet_np.py)."""
import csv
import threading

import numpy as np

from . import frontend
from .paths import resource_path
from .yamnet_np import YAMNet

_lock = threading.Lock()
_model: YAMNet | None = None
_class_names: list[str] | None = None


def class_names() -> list[str]:
    global _class_names
    if _class_names is None:
        with open(resource_path("models/yamnet_class_map.csv"), newline="") as f:
            _class_names = [row["display_name"] for row in csv.DictReader(f)]
    return _class_names


def _get_model() -> YAMNet:
    global _model
    with _lock:
        if _model is None:
            _model = YAMNet(str(resource_path("models/yamnet.npz")))
        return _model


def run_patches(p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """[N,96,64] -> (scores [N,521], embeddings [N,1024])."""
    if p.shape[0] == 0:
        return np.zeros((0, 521), np.float32), np.zeros((0, 1024), np.float32)
    model = _get_model()
    out = [model(p[i: i + 16]) for i in range(0, p.shape[0], 16)]
    return np.concatenate([o[0] for o in out]), np.concatenate([o[1] for o in out])


def embed(x16k: np.ndarray) -> dict:
    """Embed a 16 kHz mono waveform. Returns pooled scores/embedding and the log-mel."""
    mel, p = frontend.waveform_to_patches(x16k)
    scores, emb = run_patches(p)
    # Weight patches by their energy so trailing silence in a one-shot doesn't dilute it.
    energy = p.mean(axis=(1, 2))
    wts = np.exp(energy - energy.max())
    wts /= wts.sum()
    return {
        "scores_max": scores.max(axis=0),
        "scores_mean": (scores * wts[:, None]).sum(axis=0),
        "embedding": (emb * wts[:, None]).sum(axis=0).astype(np.float32),
        "mel": mel,
    }


def top_k(scores: np.ndarray, k: int = 5) -> list[tuple[str, float]]:
    names = class_names()
    idx = np.argsort(scores)[::-1][:k]
    return [(names[i], float(scores[i])) for i in idx]
