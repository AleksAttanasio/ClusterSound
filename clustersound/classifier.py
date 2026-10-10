"""Fusion of filename prior, zero-shot AudioSet scores, acoustic rules and two MLP heads:
a base head shipped with the app (models/base_head.npz) and one self-trained per library."""
from dataclasses import dataclass

import numpy as np

from . import taxonomy
from .features import rule_logits
from .paths import resource_path
from .taxonomy import CLASS_IDS, CLASS_INDEX, CLASSES, N_CLASSES

# Weights tuned with tools/evaluate.py (hidden-name cross-validation on a real library).
W_NAME = 2.0
W_AUDIO, W_RULES = 0.25, 0.25          # when at least one head is available
W_AUDIO_ALONE, W_RULES_ALONE = 1.0, 0.8  # zero-shot fallback with no head at all
W_HEAD, W_BASE = 2.0, 1.5
UNSORTED_THRESHOLD = 0.22
FOLDER_WEIGHTS = (0.65, 0.45, 0.3, 0.2)  # parent, grandparent, ...

# AudioSet mapping as a dense [521, K] weight matrix
_MAP = np.zeros((521, N_CLASSES), dtype=np.float32)
for _c in CLASSES:
    for _i, _w in _c.audioset.items():
        _MAP[_i, CLASS_INDEX[_c.id]] = _w


def name_scores(rel_path: str) -> tuple[dict[str, float], bool]:
    """Keyword evidence from file name (full weight) and parent folders (decaying weight)."""
    parts = rel_path.replace("\\", "/").split("/")
    fname, folders = parts[-1], parts[:-1][::-1]
    toks = taxonomy.tokenize(fname)
    scores = taxonomy.keyword_scores(toks)
    loop = taxonomy.is_loop_name(toks)
    for depth, folder in enumerate(folders):
        w = FOLDER_WEIGHTS[min(depth, len(FOLDER_WEIGHTS) - 1)]
        ftoks = taxonomy.tokenize(folder)
        loop = loop or taxonomy.is_loop_name(ftoks)
        for cid, s in taxonomy.keyword_scores(ftoks).items():
            scores[cid] = max(scores.get(cid, 0.0), s * w)
    return scores, loop


def name_logprior(scores: dict[str, float]) -> np.ndarray:
    lp = np.zeros(N_CLASSES, dtype=np.float32)
    if not scores:
        return lp
    v = np.zeros(N_CLASSES, dtype=np.float32)
    for cid, s in scores.items():
        v[CLASS_INDEX[cid]] = s
    strength = float(v.max())
    p = 0.15 / N_CLASSES + 0.85 * (v ** 2) / (v ** 2).sum()
    # weak evidence (e.g. only a folder name) pulls less
    return (np.log(p) - np.log(1.0 / N_CLASSES)) * strength


def audio_logits(scores_max: np.ndarray, scores_mean: np.ndarray) -> np.ndarray:
    s = 0.5 * scores_max.astype(np.float32) + 0.5 * scores_mean.astype(np.float32)
    per_class = (s[:, None] * _MAP).max(axis=0)
    return np.log(per_class + 0.02)


def softmax(z: np.ndarray, axis=-1) -> np.ndarray:
    z = z - z.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


@dataclass
class Head:
    """One-hidden-layer MLP over the trained subset of classes."""
    classes: list[int]
    mean: np.ndarray
    std: np.ndarray
    W1: np.ndarray
    b1: np.ndarray
    W2: np.ndarray
    b2: np.ndarray

    def save(self, path: str) -> None:
        np.savez_compressed(path, classes=np.array([CLASS_IDS[c] for c in self.classes]),
                            mean=self.mean, std=self.std, W1=self.W1.astype(np.float16),
                            b1=self.b1, W2=self.W2.astype(np.float16), b2=self.b2)

    @classmethod
    def load(cls, path: str) -> "Head":
        with np.load(path, allow_pickle=False) as z:
            classes = [CLASS_INDEX[c] for c in z["classes"].tolist() if c in CLASS_INDEX]
            if len(classes) != len(z["classes"]):
                raise ValueError("base head trained on a different taxonomy")
            return cls(classes, z["mean"], z["std"], z["W1"].astype(np.float32), z["b1"],
                       z["W2"].astype(np.float32), z["b2"])

    def proba(self, X: np.ndarray) -> np.ndarray:
        H = np.maximum(((X - self.mean) / self.std) @ self.W1 + self.b1, 0)
        return softmax(H @ self.W2 + self.b2)

    def predict_log(self, X: np.ndarray) -> np.ndarray:
        """Additive log-evidence per class: log(p * k) for trained classes, clipped so the
        head can't overrule everything else; 0 (neutral) for classes it never saw."""
        p_sub = self.proba(X)
        out = np.zeros((X.shape[0], N_CLASSES), dtype=np.float32)
        out[:, self.classes] = np.clip(np.log(p_sub * len(self.classes) + 1e-9), -3.0, 2.0)
        return out


def train_head(X: np.ndarray, y: np.ndarray, weights: np.ndarray, min_per_class: int = 4,
               steps: int = 1500, batch: int = 256, hidden: int = 256, wd: float = 1e-3,
               dropout: float = 0.2, lr: float = 3e-3, seed: int = 0) -> Head | None:
    """Mini-batch Adam with class-balanced sampling: cost doesn't grow with library size."""
    classes = [int(c) for c in np.unique(y) if (y == c).sum() >= min_per_class]
    if len(classes) < 2:
        return None
    keep = np.isin(y, classes)
    X, y, weights = X[keep], y[keep], weights[keep]
    remap = {c: i for i, c in enumerate(classes)}
    yi = np.array([remap[c] for c in y])
    mean, std = X.mean(0), X.std(0) + 1e-6
    Xs = ((X - mean) / std).astype(np.float32)
    n, d = Xs.shape
    k = len(classes)
    counts = np.bincount(yi, minlength=k).astype(np.float64)
    p_sample = weights / counts[yi]
    p_sample /= p_sample.sum()
    rng = np.random.default_rng(seed)
    W1 = rng.normal(0, np.sqrt(2 / d), (d, hidden)).astype(np.float32)
    b1 = np.zeros(hidden, np.float32)
    W2 = rng.normal(0, np.sqrt(1 / hidden), (hidden, k)).astype(np.float32)
    b2 = np.zeros(k, np.float32)
    params = [W1, b1, W2, b2]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    eye = np.eye(k, dtype=np.float32)
    for t in range(1, steps + 1):
        bi = rng.choice(n, size=min(batch, n), p=p_sample)
        xb, yb = Xs[bi], eye[yi[bi]]
        H = xb @ W1 + b1
        A = np.maximum(H, 0)
        mask = (rng.random(A.shape) > dropout) / (1 - dropout)
        Ad = A * mask
        G = (softmax(Ad @ W2 + b2) - yb) / len(bi)
        dA = (G @ W2.T) * mask * (H > 0)
        grads = [xb.T @ dA + wd * W1, dA.sum(0), Ad.T @ G + wd * W2, G.sum(0)]
        step_lr = lr * min(1.0, 2.0 * (1 - t / steps) + 0.05)  # linear decay in the second half
        for i, (p, g) in enumerate(zip(params, grads)):
            m[i] = 0.9 * m[i] + 0.1 * g
            v[i] = 0.999 * v[i] + 0.001 * g * g
            p -= step_lr * (m[i] / (1 - 0.9 ** t)) / (np.sqrt(v[i] / (1 - 0.999 ** t)) + 1e-8)
    return Head(classes, mean, std, W1, b1, W2, b2)


def components(items: list[dict]) -> dict:
    """Per-item evidence that doesn't depend on training: name prior, zero-shot audio, rules."""
    n = len(items)
    name_lp = np.zeros((n, N_CLASSES), np.float32)
    audio_lp = np.zeros((n, N_CLASSES), np.float32)
    rules = np.zeros((n, N_CLASSES), np.float32)
    file_strength = np.zeros(n, np.float32)
    file_hit: list[str | None] = [None] * n
    for i, it in enumerate(items):
        sc, loop = name_scores(it["rel"])
        it["name_loop"] = loop
        fname_scores = taxonomy.keyword_scores(taxonomy.tokenize(it["rel"].split("/")[-1]))
        if fname_scores:
            file_hit[i] = max(fname_scores, key=fname_scores.get)
            file_strength[i] = fname_scores[file_hit[i]]
        name_lp[i] = name_logprior(sc)
        audio_lp[i] = audio_logits(it["scores_max"], it["scores_mean"])
        rules[i] = rule_logits(it["feats"])
    return {"name": name_lp, "audio": audio_lp, "rules": rules,
            "file_strength": file_strength, "file_hit": file_hit}


def training_set(items: list[dict], comp: dict, user_labels: dict[str, str]):
    """Self-training set: user labels, plus files whose own name carries a strong keyword."""
    ys, idx, wts = [], [], []
    for i, it in enumerate(items):
        lab = user_labels.get(it["path"])
        if lab in CLASS_INDEX:
            ys.append(CLASS_INDEX[lab]); idx.append(i); wts.append(3.0)
        elif comp["file_strength"][i] >= 0.75 and comp["file_hit"][i]:
            ys.append(CLASS_INDEX[comp["file_hit"][i]]); idx.append(i); wts.append(1.0)
    return np.array(idx, int), np.array(ys, int), np.array(wts, np.float32)


_BASE_HEAD: "Head | None | bool" = False


def base_head() -> "Head | None":
    global _BASE_HEAD
    if _BASE_HEAD is False:
        path = resource_path("models/base_head.npz")
        _BASE_HEAD = Head.load(str(path)) if path.exists() else None
    return _BASE_HEAD


def fuse(comp: dict, head_log: np.ndarray | None, base_log: np.ndarray | None = None) -> np.ndarray:
    if head_log is None and base_log is None:
        total = W_AUDIO_ALONE * comp["audio"] + W_RULES_ALONE * comp["rules"]
    else:
        total = W_AUDIO * comp["audio"] + W_RULES * comp["rules"]
    total = total + W_NAME * comp["name"]
    if head_log is not None:
        total = total + W_HEAD * head_log
    if base_log is not None:
        total = total + W_BASE * base_log
    return softmax(total)


def classify(items: list[dict], X: np.ndarray, user_labels: dict[str, str]) -> dict:
    """Classify all items in place. X = audio feature matrix used by the head.

    Each item needs: rel, path, scores_max, scores_mean, feats.
    Sets: cls, conf, alts, user; returns training stats.
    """
    n = len(items)
    if n == 0:
        return {"head_classes": 0, "head_samples": 0}
    comp = components(items)
    idx, ys, wts = training_set(items, comp, user_labels)
    head = train_head(X[idx], ys, wts) if len(idx) else None
    base = base_head()
    P = fuse(comp, head.predict_log(X) if head is not None else None,
             base.predict_log(X) if base is not None else None)

    for i, it in enumerate(items):
        order = np.argsort(-P[i])
        it["alts"] = [{"cls": CLASS_IDS[j], "p": round(float(P[i, j]), 3)} for j in order[:4]]
        lab = user_labels.get(it["path"])
        if lab:
            it["cls"], it["conf"], it["user"] = lab, 1.0, True
        else:
            best = order[0]
            it["user"] = False
            it["conf"] = round(float(P[i, best]), 3)
            it["cls"] = CLASS_IDS[best] if P[i, best] >= UNSORTED_THRESHOLD else "unsorted"
    return {"head_classes": len(head.classes) if head else 0, "head_samples": len(idx),
            "probs": P}
