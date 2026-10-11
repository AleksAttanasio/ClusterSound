"""Choosing the samples that go with a seed on a group of pads.

Everything works on L2-normalised embeddings (Xn) and a boolean mask of allowed items, so it can be
tested without a Library. Results are lists of (item id, cosine similarity to the seed), most similar first.
"""
import numpy as np

from ..clustering import l2norm  # noqa: F401  (callers normalise once with it)

POOL = 400        # nearest neighbours considered
DUPLICATE = 0.995  # above this two samples are the same sound (copies, renamed files)
TEMPERATURE = 0.05


def _ranked(Xn: np.ndarray, seed: int, ok: np.ndarray | None, exclude) -> tuple[np.ndarray, np.ndarray]:
    sims = Xn @ Xn[seed]
    allowed = np.ones(len(Xn), bool) if ok is None else ok.copy()
    allowed[seed] = False
    allowed[list(exclude)] = False
    idx = np.flatnonzero(allowed)
    if not len(idx):
        return idx, sims[idx]
    k = min(POOL, len(idx))
    top = idx[np.argpartition(-sims[idx], k - 1)[:k]]
    top = top[np.argsort(-sims[top], kind="stable")]
    return top, sims[top]


def _distinct(Xn: np.ndarray, chosen: list[int], cand: int) -> bool:
    return not chosen or float(np.max(Xn[chosen] @ Xn[cand])) < DUPLICATE


def neighbours(Xn, seed, k, ok=None, exclude=()) -> list[tuple[int, float]]:
    """The k most similar allowed items, skipping duplicates of the seed or of each other."""
    ids, sims = _ranked(Xn, seed, ok, exclude)
    chosen, out = [seed], []
    for i, s in zip(ids.tolist(), sims.tolist()):
        if len(out) >= k:
            break
        if _distinct(Xn, chosen, i):
            chosen.append(i)
            out.append((i, s))
    return out


def pick(Xn, seed, count, mode="nearest", ok=None, variation=0.3, exclude=(), rng_seed=None) -> list[tuple[int, float]]:
    """`count` companions for `seed`. 'nearest': the most similar ones. 'random': a similarity-weighted
    draw from the closest count + variation·5·count, so each call gives a slightly different set."""
    if count <= 0:
        return []
    if mode != "random":
        return neighbours(Xn, seed, count, ok, exclude)
    width = count + int(round(max(0.0, min(1.0, variation)) * 5 * count))
    pool = neighbours(Xn, seed, max(width, count), ok, exclude)
    if len(pool) <= count:
        return pool
    rng = np.random.default_rng(rng_seed)
    sims = np.array([s for _, s in pool])
    w = np.exp((sims - sims.max()) / TEMPERATURE)
    picked = rng.choice(len(pool), size=count, replace=False, p=w / w.sum())
    return sorted((pool[j] for j in picked), key=lambda t: -t[1])


def trail(Xn, ids, size, ok=None, exclude=()) -> list[tuple[int, float]]:
    """A similar-samples navigation trail on `size` pads: its stops in order (revisits once), cut to
    size; if it is shorter, topped up with the nearest neighbours of its last stop. The stops were picked
    by hand, so `ok` and `exclude` only apply to the top-up."""
    stops = []
    for i in ids:
        if int(i) not in stops:
            stops.append(int(i))
    stops = stops[:size]
    if not stops:
        return []
    first = Xn[stops[0]]
    out = [(i, float(Xn[i] @ first)) for i in stops]
    if len(out) < size:
        out += neighbours(Xn, stops[-1], size - len(out), ok, set(exclude) | set(stops))
    return out
