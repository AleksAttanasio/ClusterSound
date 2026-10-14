"""ClusterSound entry point: GUI by default, `--headless DIR --out report.csv` for batch use."""
import argparse
import sys
from collections import Counter


def headless(folder: str, out: str | None) -> int:
    from . import export
    from .library import Library

    import os
    if not os.path.isdir(folder):
        print(f"folder not found: {folder}", file=sys.stderr)
        return 2
    lib = Library()
    lib.scan(folder)
    counts = Counter(it["cls"] for it in lib.items)
    print(f"{len(lib.items)} samples analysed, {len(lib.errors)} errors "
          f"(head: {lib.stats.get('head_classes')} classes on {lib.stats.get('head_samples')} examples)")
    for cls, n in counts.most_common():
        print(f"  {cls:14s} {n}")
    for e in lib.errors[:10]:
        print("  ERR", e["path"], e["error"], file=sys.stderr)
    if out:
        export.write(lib.items, out)
        print("report:", out)
    return 0


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--enhance-worker"]:  # the frozen app re-run as an enhancement job (enhance/runner.py)
        from .enhance import worker
        return worker.main(args[1:])
    ap = argparse.ArgumentParser(prog="clustersound")
    ap.add_argument("--headless", metavar="DIR", help="analyse DIR without the GUI")
    ap.add_argument("--out", help="report file, .csv or .json (with --headless)")
    ap.add_argument("--debug", action="store_true", help="open the web inspector tools")
    args, _ = ap.parse_known_args(argv)
    if args.headless:
        return headless(args.headless, args.out)
    from .app import run
    run(debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
