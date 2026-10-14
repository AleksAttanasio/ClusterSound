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


def check_gui(log: str | None) -> int:
    """Load the web view backend (Cocoa, or WinForms + WebView2 through pythonnet) without opening a window.
    A windowed exe has no console: the traceback goes to LOG, if given."""
    try:
        if sys.platform == "win32":
            import webview.platforms.winforms  # noqa: F401  (loads Python.Runtime.dll and the WebView2 assemblies)
        else:
            import webview.platforms.cocoa  # noqa: F401
    except Exception:
        import traceback
        if log:
            with open(log, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        traceback.print_exc()
        return 1
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
    ap.add_argument("--check-gui", nargs="?", const="", metavar="LOG",
                    help="load the GUI backend without opening a window (exit code 1 if it fails)")
    args, _ = ap.parse_known_args(argv)
    if args.check_gui is not None:
        return check_gui(args.check_gui or None)
    if args.headless:
        return headless(args.headless, args.out)
    from .app import run
    run(debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
