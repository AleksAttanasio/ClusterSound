"""Platform-dependent paths and helpers, checked on any OS by switching the platform flags."""
import os
import subprocess

import pytest

from clustersound import paths


@pytest.fixture
def win(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "IS_WIN", True)
    monkeypatch.setattr(paths, "IS_MAC", False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    return tmp_path


def test_windows_dirs(win):
    assert paths.data_dir_path() == win / "Roaming" / "ClusterSound"
    assert paths.cache_dir() == win / "Local" / "ClusterSound" / "Cache"
    assert paths.data_dir().is_dir()
    assert paths.file_manager() == "Esplora file"


def test_mac_dirs(monkeypatch):
    monkeypatch.setattr(paths, "IS_WIN", False)
    assert str(paths.data_dir_path()).endswith(os.path.join("Library", "Application Support", "ClusterSound"))
    assert str(paths.cache_dir()).endswith(os.path.join("Library", "Caches", "ClusterSound"))
    assert paths.file_manager() == "Finder"


def test_reveal_commands(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    f = tmp_path / "a.wav"
    f.write_bytes(b"")
    monkeypatch.setattr(paths, "IS_WIN", False)
    paths.reveal(str(f))
    paths.reveal(str(tmp_path))
    assert calls == [["open", "-R", str(f)], ["open", str(tmp_path)]]
    calls.clear()
    monkeypatch.setattr(paths, "IS_WIN", True)
    paths.reveal(str(f))
    assert calls == [["explorer", "/select,", os.path.normpath(str(f))]]
    opened = []
    monkeypatch.setattr(os, "startfile", opened.append, raising=False)
    paths.open_folder(str(tmp_path))
    assert opened == [os.path.normpath(str(tmp_path))]


def test_is_inside(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    assert paths.is_inside(str(tmp_path / "a" / "b"), str(tmp_path / "a"))
    assert paths.is_inside(str(tmp_path / "a"), str(tmp_path / "a") + os.sep)
    assert not paths.is_inside(str(tmp_path / "ab"), str(tmp_path / "a"))


@pytest.mark.parametrize("name,expected", [("CON", "_CON"), ("nul.wav", "_nul.wav"), ("com1", "_com1"),
                                           ("Console", "Console"), ("aux kick", "aux kick")])
def test_safe_name_avoids_windows_device_names(name, expected):
    from clustersound.online.downloads import safe_name
    assert safe_name(name) == expected


def test_check_gui_reports_a_broken_backend(monkeypatch, tmp_path):
    import sys
    from clustersound.__main__ import main
    backend = "webview.platforms.winforms" if sys.platform == "win32" else "webview.platforms.cocoa"
    monkeypatch.setitem(sys.modules, backend, None)  # the import fails, as with a blocked Python.Runtime.dll
    log = tmp_path / "gui.log"
    assert main(["--check-gui", str(log)]) == 1
    assert "Traceback" in log.read_text(encoding="utf-8")
