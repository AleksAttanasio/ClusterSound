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
    assert exp["error"] is None and exp["files"] == [os.path.join(sampler_export.folder_for(rec, root), "Take 1 - Drums.wav")]
    assert api.sampler_export_files(["/etc/passwd"])["error"] == "file not found"


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
