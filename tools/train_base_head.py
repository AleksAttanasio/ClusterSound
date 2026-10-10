"""Dev-only: train the base classifier head shipped with the app (models/base_head.npz).

Every file whose own name carries one strong keyword becomes a training example (the same
rule the in-app self-training uses), so any large, reasonably named sample library works.

    python tools/train_base_head.py ~/Samples/Library [more folders…] \
        [--exclude ~/Samples/TestSet] [--out clustersound/models/base_head.npz]

--exclude drops files that also appear (same name and size) in a held-out folder, so
tools/evaluate.py on that folder stays honest.
"""
import argparse
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clustersound import classifier, taxonomy  # noqa: E402
from clustersound.library import Library, head_features, scan_files  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "clustersound" / "models" / "base_head.npz"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--max-per-class", type=int, default=4000)
    args = ap.parse_args()

    banned = set()
    for ex in args.exclude:
        for p in scan_files(os.path.expanduser(ex)):
            banned.add((os.path.basename(p).lower(), os.path.getsize(p)))
    print(f"{len(banned)} held-out files to exclude")

    X_parts, y_parts = [], []
    for folder in args.folders:
        lib = Library()
        lib.scan_analysis_only(os.path.expanduser(folder))
        keep, ys = [], []
        for i, it in enumerate(lib.items):
            key = (it["name"].lower(), os.path.getsize(it["path"]) if os.path.exists(it["path"]) else -1)
            if key in banned:
                continue
            sc = taxonomy.keyword_scores(taxonomy.tokenize(it["name"]))
            strong = [c for c, s in sc.items() if s >= 0.75]
            if len(strong) == 1:
                keep.append(i)
                ys.append(taxonomy.CLASS_INDEX[strong[0]])
        print(f"{folder}: {len(lib.items)} files, {len(keep)} labelled")
        if keep:
            X = head_features(lib.emb[keep], lib.prof[keep], [lib.items[i]["feats"] for i in keep])
            X_parts.append(X)
            y_parts.append(np.array(ys))
    X = np.vstack(X_parts)
    y = np.concatenate(y_parts)

    # cap very frequent classes so the head file stays small and training balanced
    rng = np.random.default_rng(0)
    sel = []
    for c in np.unique(y):
        idx = np.flatnonzero(y == c)
        if len(idx) > args.max_per_class:
            idx = rng.choice(idx, args.max_per_class, replace=False)
        sel.extend(idx.tolist())
    sel = np.array(sorted(sel))
    X, y = X[sel], y[sel]
    counts = Counter(taxonomy.CLASS_IDS[c] for c in y)
    print("training examples per class:", dict(counts.most_common()))

    head = classifier.train_head(X, y, np.ones(len(y), np.float32), steps=4000, hidden=256,
                                 min_per_class=8)
    head.save(args.out)
    print(f"saved {args.out} ({os.path.getsize(args.out) / 1e6:.2f} MB), "
          f"{len(head.classes)} classes")


if __name__ == "__main__":
    main()
