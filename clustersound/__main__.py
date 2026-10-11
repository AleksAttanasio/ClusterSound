"""ClusterSound entry point: GUI by default, `--headless DIR --out report.csv` for batch use."""
import argparse
import sys
from collections import Counter


def headless(folder: str, out: str | None) -> int:
    from . import export
    from .library import Library

    import os
    if not os.path.isdir(folder):
        print(f"cartella non trovata: {folder}", file=sys.stderr)
        return 2
    lib = Library()
    lib.scan(folder)
    counts = Counter(it["cls"] for it in lib.items)
    print(f"{len(lib.items)} sample analizzati, {len(lib.errors)} errori "
          f"(head: {lib.stats.get('head_classes')} classi su {lib.stats.get('head_samples')} esempi)")
    for cls, n in counts.most_common():
        print(f"  {cls:14s} {n}")
    for e in lib.errors[:10]:
        print("  ERR", e["path"], e["error"], file=sys.stderr)
    if out:
        export.write(lib.items, out)
        print("report:", out)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="clustersound")
    ap.add_argument("--headless", metavar="DIR", help="analizza DIR senza GUI")
    ap.add_argument("--out", help="file di report .csv o .json (con --headless)")
    ap.add_argument("--debug", action="store_true", help="apre gli strumenti web inspector")
    args, _ = ap.parse_known_args(argv)
    if args.headless:
        return headless(args.headless, args.out)
    from .app import run
    run(debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
