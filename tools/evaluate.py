"""Dev tool: estimate how well ClusterSound classifies samples *without* telling names.

Files whose file name carries a single strong keyword get that keyword as ground truth.
In K folds, the names (and folders) of the test fold are hidden and the full pipeline is run;
accuracy is measured on the hidden fold.

    python tools/evaluate.py ~/Samples/SomePack [--folds 5]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clustersound import classifier, taxonomy  # noqa: E402
from clustersound.library import Library  # noqa: E402


def truth_label(rel: str) -> str | None:
    toks = taxonomy.tokenize(rel.split("/")[-1])
    sc = taxonomy.keyword_scores(toks)
    strong = {c: s for c, s in sc.items() if s >= 0.75}
    if len(strong) != 1:
        return None
    return next(iter(strong))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--oneshots", action="store_true", help="only score one-shot samples")
    ap.add_argument("--no-base", action="store_true", help="ignore models/base_head.npz")
    ap.add_argument("--all-hidden", action="store_true",
                    help="hide every name at once (library with no meaningful names)")
    args = ap.parse_args()

    if args.no_base:
        classifier._BASE_HEAD = None
    lib = Library()
    lib.scan_analysis_only(args.folder)
    items = lib.items
    truth = [truth_label(it["rel"]) for it in items]
    if args.oneshots:
        truth = [t if it["feats"].get("type") == "One-shot" and not classifier.name_scores(it["rel"])[1]
                 else None for t, it in zip(truth, items)]
    idx = np.array([i for i, t in enumerate(truth) if t])
    print(f"{len(items)} files, {len(idx)} with a ground-truth label from the file name")
    rng = np.random.default_rng(0)
    rng.shuffle(idx)
    folds = [idx] if args.all_hidden else np.array_split(idx, args.folds)
    correct, total = Counter(), Counter()
    confusion = Counter()
    for k, test in enumerate(folds):
        test_set = set(test.tolist())
        trial = []
        for i, it in enumerate(items):
            c = dict(it)
            if i in test_set or args.all_hidden:
                c["rel"] = f"hidden/sample_{i}.wav"
            trial.append(c)
        classifier.classify(trial, lib.X, {})
        for i in test:
            t, p = truth[i], trial[i]["cls"]
            total[t] += 1
            correct[t] += p == t
            if p != t:
                confusion[(t, p)] += 1
        print(f"fold {k + 1}: {sum(trial[i]['cls'] == truth[i] for i in test)}/{len(test)}")
    n = sum(total.values())
    print(f"\naccuracy with hidden names: {sum(correct.values())}/{n} = {sum(correct.values()) / max(n, 1):.1%}")
    for c in sorted(total, key=lambda c: -total[c]):
        print(f"  {c:14s} {correct[c]:4d}/{total[c]:<4d} {correct[c] / total[c]:.0%}")
    print("most common confusions:")
    for (t, p), v in confusion.most_common(15):
        print(f"  {t:14s} -> {p:14s} {v}")


if __name__ == "__main__":
    main()
