"""Matching the dynamics (envelope shape) of samples across buses / pad groups.

Each item gets a small vector of envelope features (attack, decay, t60, tail, envelope slope), z-scored
within its own class: a kick that is short *for a kick* lands near a hat that is short *for a hat*, so a
kit can be kept consistently tight or consistently roomy whatever the instruments.
"""
import numpy as np

# (feature, log scale, weight): decay and tail matter more to the feel of a kit than the attack
COLUMNS = [("attack", True, 0.7), ("decay20", True, 1.2), ("t60", True, 1.2),
           ("tail_ratio", False, 1.0), ("env_slope", False, 0.6)]
MIN_CLASS = 5     # smaller classes use the library-wide statistics
MIN_STD = 0.05
SIGMA = 1.0


def _raw(feats: list[dict]) -> np.ndarray:
    R = np.zeros((len(feats), len(COLUMNS)), np.float32)
    for j, (k, log, _) in enumerate(COLUMNS):
        v = np.array([float(f.get(k, 0.0) or 0.0) for f in feats], np.float32)
        R[:, j] = np.log10(np.maximum(v, 0.0) + 1e-3) if log else v
    R[:, -1] = np.clip(R[:, -1], -200, 50)  # env_slope in dB/s: a few extreme loops would dominate
    return R


def dyn_matrix(feats: list[dict], cls) -> np.ndarray:
    """Weighted, per-class z-scored envelope vectors, one row per item."""
    R = _raw(feats)
    if not len(R):
        return R
    cls = np.asarray(cls, dtype=object)
    D = np.empty_like(R)
    g_mu, g_sd = R.mean(0), np.maximum(R.std(0), MIN_STD)
    for c in set(cls.tolist()):
        m = cls == c
        if m.sum() >= MIN_CLASS:
            mu, sd = R[m].mean(0), np.maximum(R[m].std(0), MIN_STD)
        else:
            mu, sd = g_mu, g_sd
        D[m] = (R[m] - mu) / sd
    return D * np.array([w for *_, w in COLUMNS], np.float32)


def reference(D: np.ndarray, ids) -> np.ndarray | None:
    ids = [int(i) for i in ids or [] if 0 <= int(i) < len(D)]
    return D[ids].mean(0) if ids else None


def distances(D: np.ndarray, ref: np.ndarray) -> np.ndarray:
    return np.sqrt(((D - ref) ** 2).sum(1) / D.shape[1])


def scores(D: np.ndarray, ref: np.ndarray | None) -> np.ndarray:
    """Similarity to the reference in [0, 1] (1 = same envelope)."""
    if ref is None:
        return np.ones(len(D), np.float32)
    d = distances(D, ref)
    return np.exp(-d ** 2 / (2 * SIGMA ** 2))


def margin_mask(D: np.ndarray, ref: np.ndarray | None, ok: np.ndarray, margin: float,
                min_keep: int = 8) -> np.ndarray:
    """Of the allowed items keep the `margin` fraction closest to the reference (at least min_keep)."""
    if ref is None or margin >= 1:
        return ok
    idx = np.flatnonzero(ok)
    keep = max(min_keep, int(np.ceil(max(0.0, margin) * len(idx))))
    if keep >= len(idx):
        return ok
    d = distances(D[idx], ref)
    out = np.zeros_like(ok)
    out[idx[np.argpartition(d, keep - 1)[:keep]]] = True
    return out
