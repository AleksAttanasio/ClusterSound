"""3D layout of the library: PCA (instant) and an exact t-SNE in numpy (landmarks for big sets)."""
import numpy as np

MAX_TSNE = 2500
SCALE = 50.0


def pca(X: np.ndarray, dims: int) -> np.ndarray:
    Xc = X - X.mean(0)
    if Xc.shape[0] < 2:
        return np.zeros((Xc.shape[0], dims), np.float32)
    U, S, _ = np.linalg.svd(Xc, full_matrices=False)
    Z = U[:, :dims] * S[:dims]
    if Z.shape[1] < dims:
        Z = np.pad(Z, ((0, 0), (0, dims - Z.shape[1])))
    return Z.astype(np.float32)


def _sqdist(X: np.ndarray) -> np.ndarray:
    s = (X ** 2).sum(1)
    return np.maximum(s[:, None] - 2 * X @ X.T + s[None], 0)


def _joint_p(X: np.ndarray, perplexity: float) -> np.ndarray:
    n = X.shape[0]
    D = _sqdist(X).astype(np.float64)
    target = np.log(perplexity)
    np.fill_diagonal(D, np.inf)
    D = D - D.min(1, keepdims=True)  # shift per row: doesn't change the conditional P
    D = D / (np.median(D[np.isfinite(D)]) + 1e-12)
    Dfin = np.where(np.isinf(D), 0, D)
    beta = np.ones(n)
    lo, hi = np.zeros(n), np.full(n, np.inf)
    for _ in range(64):
        Pm = np.exp(-D * beta[:, None])
        sumP = Pm.sum(1) + 1e-300
        Pn = Pm / sumP[:, None]
        H = np.log(sumP) + beta * (Dfin * Pn).sum(1)
        diff = H - target
        if np.abs(diff).max() < 1e-4:
            break
        up = diff > 0  # entropy too high -> sharper kernel (bigger beta)
        lo = np.where(up, beta, lo)
        hi = np.where(up, hi, beta)
        beta = np.where(up, np.where(np.isinf(hi), beta * 2, (lo + hi) / 2), (lo + hi) / 2)
    P = (Pn + Pn.T) / (2 * n)
    return np.maximum(P, 1e-12).astype(np.float32)


def tsne(X: np.ndarray, dims: int = 3, perplexity: float = 30.0, iters: int = 600,
         seed: int = 0, progress=None) -> np.ndarray:
    n = X.shape[0]
    if n < 5:
        return pca(X, dims)
    perplexity = min(perplexity, max(2.0, (n - 1) / 3))
    P = _joint_p(X, perplexity)
    init = pca(X, dims)
    Y = (init / (init[:, 0].std() + 1e-9) * 1e-2).astype(np.float32)
    rng = np.random.default_rng(seed)
    Y += rng.normal(0, 1e-4, Y.shape).astype(np.float32)
    lr = max(n / 12.0, 50.0)
    vel = np.zeros_like(Y)
    gains = np.ones_like(Y)
    exag_iters = 250
    for it in range(iters):
        exag = 12.0 if it < exag_iters else 1.0
        mom = 0.5 if it < exag_iters else 0.8
        num = 1.0 / (1.0 + _sqdist(Y))
        np.fill_diagonal(num, 0)
        Q = np.maximum(num / num.sum(), 1e-12)
        Wm = (exag * P - Q) * num
        grad = 4.0 * (Wm.sum(1)[:, None] * Y - Wm @ Y)
        inc = np.sign(grad) != np.sign(vel)
        gains = np.where(inc, gains + 0.2, gains * 0.8)
        np.maximum(gains, 0.01, out=gains)
        vel = mom * vel - lr * gains * grad
        Y += vel
        Y -= Y.mean(0)
        if progress and it % 25 == 0:
            progress(it / iters)
    return Y


def layout(X: np.ndarray, progress=None, seed: int = 0) -> np.ndarray:
    """Full 3D layout: t-SNE on up to MAX_TSNE landmarks, k-NN placement for the rest."""
    n = X.shape[0]
    if n == 0:
        return np.zeros((0, 3), np.float32)
    Z = pca(X, min(30, max(1, X.shape[1])))
    rng = np.random.default_rng(seed)
    if n <= MAX_TSNE:
        Y = tsne(Z, progress=progress, seed=seed)
    else:
        land = np.sort(rng.choice(n, MAX_TSNE, replace=False))
        Yl = tsne(Z[land], progress=progress, seed=seed)
        Y = np.zeros((n, 3), np.float32)
        Y[land] = Yl
        rest = np.setdiff1d(np.arange(n), land)
        Zl = Z[land]
        sl = (Zl ** 2).sum(1)
        for start in range(0, len(rest), 2000):
            chunk = rest[start:start + 2000]
            d = (Z[chunk] ** 2).sum(1)[:, None] - 2 * Z[chunk] @ Zl.T + sl[None]
            nn = np.argpartition(d, 5, axis=1)[:, :5]
            dn = np.take_along_axis(d, nn, 1)
            w = 1.0 / (np.sqrt(np.maximum(dn, 0)) + 1e-6)
            w /= w.sum(1, keepdims=True)
            Y[chunk] = (Yl[nn] * w[..., None]).sum(1)
        spread = Yl.std() * 0.02
        Y[rest] += rng.normal(0, spread, (len(rest), 3)).astype(np.float32)
    return normalize(Y)


def quick_layout(X: np.ndarray) -> np.ndarray:
    return normalize(pca(X, 3)) if X.shape[0] else np.zeros((0, 3), np.float32)


def normalize(Y: np.ndarray) -> np.ndarray:
    Y = Y - np.median(Y, axis=0)
    r = np.percentile(np.abs(Y), 98) + 1e-9
    return (Y / r * SCALE).astype(np.float32)
