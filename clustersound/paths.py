"""Resource and data locations, working both from source and inside a PyInstaller bundle."""
import os
import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "clustersound" / rel
    return p


def data_dir() -> Path:
    d = Path(os.path.expanduser("~/Library/Application Support/ClusterSound"))
    d.mkdir(parents=True, exist_ok=True)
    return d
