"""Sub-clusters inside each class (k-means + silhouette) and nearest-neighbour search."""
import numpy as np


def l2norm(X: np.ndarray) -> np.ndarray:
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)


def kmeans(X: np.ndarray, k: int, rng: np.random.Generator, iters: int = 50) -> np.ndarray:
    n = X.shape[0]
    # k-means++ seeding
    centers = [X[rng.integers(n)]]
    d2 = ((X - centers[0]) ** 2).sum(1)
    for _ in range(1, k):
        probs = d2 / d2.sum() if d2.sum() > 0 else np.full(n, 1 / n)
        centers.append(X[rng.choice(n, p=probs)])
        d2 = np.minimum(d2, ((X - centers[-1]) ** 2).sum(1))
    C = np.array(centers)
    labels = np.zeros(n, int)
    for _ in range(iters):
        dist = ((X[:, None, :] - C[None]) ** 2).sum(-1) if n * k * X.shape[1] < 5e7 else \
            (X ** 2).sum(1)[:, None] - 2 * X @ C.T + (C ** 2).sum(1)[None]
        new = dist.argmin(1)
        if (new == labels).all() and _ > 0:
            break
        labels = new
        for j in range(k):
            m = labels == j
            if m.any():
                C[j] = X[m].mean(0)
    return labels


def silhouette(X: np.ndarray, labels: np.ndarray) -> float:
    k = labels.max() + 1
    if k < 2:
        return -1.0
    D = np.sqrt(np.maximum((X ** 2).sum(1)[:, None] - 2 * X @ X.T + (X ** 2).sum(1)[None], 0))
    s = np.zeros(len(X))
    for i in range(len(X)):
        same = labels == labels[i]
        same[i] = False
        if not same.any():
            continue
        a = D[i, same].mean()
        b = min(D[i, labels == j].mean() for j in range(k) if j != labels[i] and (labels == j).any())
        s[i] = (b - a) / max(a, b, 1e-9)
    return float(s.mean())


def subclusters(X: np.ndarray, max_k: int = 8, seed: int = 0) -> np.ndarray:
    """Pick k in [2, max_k] by silhouette (on a sample for big sets). Returns labels."""
    n = X.shape[0]
    if n < 6:
        return np.zeros(n, int)
    rng = np.random.default_rng(seed)
    Xn = l2norm(X)
    sample = rng.choice(n, size=min(n, 800), replace=False)
    best_k, best_s = 1, 0.05  # require some real structure before splitting
    for k in range(2, min(max_k, n // 3) + 1):
        lab = kmeans(Xn[sample], k, rng)
        s = silhouette(Xn[sample], lab)
        if s > best_s:
            best_k, best_s = k, s
    if best_k == 1:
        return np.zeros(n, int)
    lab = kmeans(Xn, best_k, rng)
    # order sub-clusters by size, biggest = 1
    order = np.argsort(-np.bincount(lab, minlength=best_k))
    remap = np.empty(best_k, int)
    remap[order] = np.arange(best_k)
    return remap[lab]


def knn(X: np.ndarray, i: int, k: int = 10, return_sims: bool = False):
    Xn = l2norm(X)
    sims = Xn @ Xn[i]
    sims[i] = -np.inf
    ids = np.argsort(-sims)[:k]
    if return_sims:
        return ids.tolist(), sims[ids].tolist()
    return ids.tolist()
