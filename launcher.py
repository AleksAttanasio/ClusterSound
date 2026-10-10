"""Entry point for the frozen app (PyInstaller)."""
import sys

from clustersound.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
