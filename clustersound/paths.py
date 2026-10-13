"""Resource and data locations, working both from source and inside a PyInstaller bundle, on macOS and Windows."""
import os
import subprocess
import sys
from pathlib import Path

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"


def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "clustersound" / rel
    return p


def _win_dir(var: str, fallback: str) -> Path:
    return Path(os.environ.get(var) or os.path.expanduser(fallback))


def data_dir_path() -> Path:
    """Settings, cache database and models (not created)."""
    if IS_WIN:
        return _win_dir("APPDATA", "~/AppData/Roaming") / "ClusterSound"
    return Path(os.path.expanduser("~/Library/Application Support/ClusterSound"))


def data_dir() -> Path:
    d = data_dir_path()
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    """Disposable files (previews, compiled helpers); not created."""
    if IS_WIN:
        return _win_dir("LOCALAPPDATA", "~/AppData/Local") / "ClusterSound" / "Cache"
    return Path(os.path.expanduser("~/Library/Caches/ClusterSound"))


def file_manager() -> str:
    return "Esplora file" if IS_WIN else "Finder"


def reveal(path: str) -> None:
    """Show a file selected in the Finder / File Explorer (a folder is opened)."""
    if os.path.isdir(path):
        open_folder(path)
    elif IS_WIN:
        subprocess.run(["explorer", "/select,", os.path.normpath(path)], check=False)
    else:
        subprocess.run(["open", "-R", path], check=False)


def open_folder(path: str) -> None:
    if IS_WIN:
        os.startfile(os.path.normpath(path))  # noqa: S606 (Windows only)
    else:
        subprocess.run(["open", path], check=False)


def is_inside(path: str, root: str) -> bool:
    """path is root or below it (resolved; case-insensitive where the filesystem is, as on Windows)."""
    path, root = os.path.normcase(os.path.realpath(path)), os.path.normcase(os.path.realpath(root))
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)
