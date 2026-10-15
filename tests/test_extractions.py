import os

import numpy as np
import pytest
import soundfile as sf

from clustersound.sampler import export as sampler_export
from clustersound.sampler import extractions
from clustersound.sampler import session as S
from clustersound.sampler import stems

from .synth import SR


def _wav(path, seconds=0.5):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, np.zeros((int(seconds * SR), 2), dtype=np.float32), SR)
    return path


@pytest.fixture
def rec(tmp_path):
    """A recording on disk, opened as a capture session."""
    path = _wav(str(tmp_path / "rec" / "Take 1.wav"), 2.0)
    s = S.load_file(path, origin="capture")
    s.title = "Take 1"
    s.meta = {"device": "Cuffie"}
    return s


def test_scan_finds_stems_and_enhanced(tmp_path, rec):
    root = str(tmp_path / "samples")
    whole = stems.out_folder(rec, "all", root)
    region = stems.out_folder(rec, "region", root)
    _wav(os.path.join(whole, "Take 1 - Drums.wav"))
    _wav(os.path.join(region, "Take 1 0.50-1.50s - Bass.wav"))
    samples = sampler_export.folder_for(rec, root)
    _wav(os.path.join(samples, "Take 1 - 01.wav"))                        # a cut: not an extraction
    _wav(os.path.join(samples, "Take 1 0.50-1.50s (enhanced).wav"))
    _wav(str(tmp_path / "rec" / "Take 1 (migliorato).wav"))               # whole recording, Italian name
    _wav(str(tmp_path / "rec" / "Take 2 (enhanced).wav"))                 # other recordings' results
    _wav(str(tmp_path / "rec" / "Take 10 (enhanced).wav"))
    out = extractions.scan(rec, root)
    assert [i["name"] for i in out["stems"]] == ["Take 1 - Drums", "Take 1 0.50-1.50s - Bass"]
    assert sorted(i["name"] for i in out["enhanced"]) == ["Take 1 (migliorato)", "Take 1 0.50-1.50s (enhanced)"]
    assert all(abs(i["dur"] - 0.5) < 1e-3 and i["sr"] == SR for i in out["stems"] + out["enhanced"])


def test_scan_empty(tmp_path, rec):
    assert extractions.scan(rec, str(tmp_path / "none")) == {"stems": [], "enhanced": []}


def test_copy_to_keeps_notes(tmp_path):
    src = _wav(str(tmp_path / "a" / "x.wav"))
    with open(src + ".source.txt", "w") as f:
        f.write("note")
    dst = str(tmp_path / "out")
    files = extractions.copy_to([src, str(tmp_path / "missing.wav")], dst)
    assert files == [os.path.join(dst, "x.wav"), None]
    assert os.path.isfile(os.path.join(dst, "x.wav.source.txt"))
    again = extractions.copy_to([src], dst)                                # never overwrites
    assert again == [os.path.join(dst, "x (2).wav")]
    assert extractions.copy_to([files[0]], dst) == [files[0]]              # already there


@pytest.fixture
def api(tmp_path, monkeypatch):
    from clustersound.api import Api
    a = object.__new__(Api)
    a._sampler = None
    a._sessions, a._sid_next, a._extr_paths = {}, 0, {}
    a._work = str(tmp_path / "work")
    monkeypatch.setattr(Api, "_settings", lambda self: {"sampler_dir": str(tmp_path / "samples")})
    monkeypatch.setattr(Api, "_inside_library", lambda self, folder: False)
    return a


def test_api_list_open_export(api, tmp_path, rec):
    assert api.sampler_extractions()["stems"] == []
    root = str(tmp_path / "samples")
    stem = _wav(os.path.join(stems.out_folder(rec, "all", root), "Take 1 - Drums.wav"))
    api._add_session(rec)
    out = api.sampler_extractions()
    assert [(i["path"], i["sid"], i["source"]) for i in out["stems"]] == [(stem, rec.sid, "Take 1")]
    assert api.sampler_open_extraction(str(tmp_path / "other.wav"))["error"] == "file not found"
    r = api.sampler_open_extraction(stem)
    assert r["error"] is None and r["session"]["origin"] == "capture" and r["session"]["parent"] == rec.sid
    assert len(r["tabs"]) == 2 and api._sampler.meta["device"] == "Cuffie"
    assert api.sampler_open_extraction(stem)["existing"] and len(api._sessions) == 2  # same tab again
    # the stem's tab counts as its source: the list doesn't change, nor duplicates
    assert [i["path"] for i in api.sampler_extractions()["stems"]] == [stem]
    exp = api.sampler_export_files([stem, "/etc/passwd"])
    assert exp["error"] is None and exp["files"] == [stem, None]  # already saved: it stays where it is
    assert api.sampler_export_files(["/etc/passwd"])["error"] == "file not found"


def test_api_temporary_save_delete(api, tmp_path, rec, monkeypatch):
    root, work = str(tmp_path / "samples"), api._work
    api._add_session(rec)
    tmp_stem = _wav(os.path.join(extractions.stem_folder(rec, work), "Take 1 - Bass.wav"))
    with open(tmp_stem + ".source.txt", "w") as f:
        f.write("note")
    tmp_enh = _wav(os.path.join(sampler_export.folder_for(rec, work), "Take 1 (enhanced).wav"))
    out = api.sampler_extractions()
    assert [(i["path"], i["saved"]) for i in out["stems"]] == [(tmp_stem, False)]
    assert [(i["path"], i["saved"]) for i in out["enhanced"]] == [(tmp_enh, False)]
    # «Export all»: into the export folder, same layout, with the note
    exp = api.sampler_export_files([tmp_stem])
    saved = os.path.join(root, os.path.relpath(tmp_stem, work))
    assert exp["files"] == [saved] and os.path.isfile(saved + ".source.txt") and not os.path.exists(tmp_stem)
    assert [(i["path"], i["saved"]) for i in api.sampler_extractions()["stems"]] == [(saved, True)]
    # delete: a temporary file is removed, a saved one goes to the Trash
    trashed = []
    monkeypatch.setattr("clustersound.api.trash", lambda p: (trashed.append(p), os.remove(p)))
    assert api.sampler_delete_extraction(tmp_enh)["error"] is None and not os.path.exists(tmp_enh) and not trashed
    assert api.sampler_delete_extraction(saved)["error"] is None and trashed == [saved, saved + ".source.txt"]
    assert api.sampler_delete_extraction(saved)["error"] == "file not found"
    api._drop_work()
    assert not os.path.exists(work)


def test_api_send_to_library(api, tmp_path, rec, monkeypatch):
    api._add_session(rec)
    lib_a, lib_b = str(tmp_path / "libA"), str(tmp_path / "libB")
    api._lib = type("L", (), {"roots": []})()
    monkeypatch.setattr(type(api), "_schedule_rescan", lambda self: None)
    stem = _wav(os.path.join(extractions.stem_folder(rec, api._work), "Take 1 - Bass.wav"))
    api.sampler_extractions()
    assert api.sampler_send_to_library([{"path": stem}])["error"].startswith("no library open")
    api._lib.roots = [lib_a, lib_b]
    assert api.sampler_send_to_library([{"path": stem}])["choose"] == [lib_a, lib_b]
    cut = _wav(os.path.join(sampler_export.folder_for(rec, api._work), "Take 1 - 01.wav"))
    r = api.sampler_send_to_library([{"path": stem}, {"path": cut, "sid": rec.sid}, {"path": "/etc/passwd"}], lib_b)
    folder = os.path.join(lib_b, "ClusterSound Recorder", "Take 1")
    assert r["error"] is None and sorted(r["files"]) == [os.path.join(folder, "Take 1 - 01.wav"), os.path.join(folder, "Take 1 - Bass.wav")]
    assert r["copies"][stem] == os.path.join(folder, "Take 1 - Bass.wav")
    assert os.path.isfile(stem)  # a copy: the temporary file stays temporary


def test_api_tabs(api, tmp_path):
    a = _wav(str(tmp_path / "a.wav"))
    b = _wav(str(tmp_path / "b.wav"), 1.0)
    ra = api.sampler_open_file(a)
    rb = api.sampler_open_file(b)
    assert [t["title"] for t in rb["tabs"]] == ["a", "b"] and rb["session"]["title"] == "b"
    sa, sb = ra["session"]["sid"], rb["session"]["sid"]
    assert api.sampler_open_file(a)["session"]["sid"] == sa  # already open: its tab is shown
    assert api.sampler_audio(0, 0.5, None, sb) and api._sampler.sid == sa  # another tab, without showing it
    assert api.sampler_select(sb)["session"]["sid"] == sb
    r = api.sampler_close(sb)
    assert r["session"]["sid"] == sa and [t["sid"] for t in r["tabs"]] == [sa]
    assert api.sampler_close(sa)["session"] is None
