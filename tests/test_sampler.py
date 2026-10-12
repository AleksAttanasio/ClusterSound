import json
import os
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from clustersound.online import archive, downloads
from clustersound.online.base import OnlineResult, SourceError
from clustersound.sampler import capture
from clustersound.sampler import export as sampler_export
from clustersound.sampler import links
from clustersound.sampler import session as S
from clustersound.sampler import slicing

from .synth import SR

FIX = Path(__file__).parent / "fixtures" / "online"


# ---------------------------------------------------------------- session
def test_load_file_and_peaks(tmp_path):
    t = np.arange(SR * 2) / SR
    x = np.stack([np.sin(2 * np.pi * 220 * t), np.zeros_like(t)], axis=1).astype(np.float32) * 0.5
    p = tmp_path / "tone.wav"
    sf.write(p, x, SR)
    s = S.load_file(str(p))
    assert s.title == "tone" and s.origin == "file" and s.audio.shape == (SR * 2, 2)
    assert abs(s.duration - 2.0) < 1e-6 and not s.truncated
    pk = s.peaks(0.5, 1.5, cols=100)
    assert len(pk["wave_min"]) == len(pk["wave_max"]) == 100
    assert max(pk["wave_max"]) <= 0.25 + 1e-3 and min(pk["wave_min"]) >= -0.25 - 1e-3  # mono mix halves it
    assert s.clip(1.0, 0.5).shape[0] == SR // 2  # reversed bounds are swapped


def test_load_file_truncates(tmp_path):
    p = tmp_path / "long.wav"
    sf.write(p, np.zeros(SR * 3, dtype=np.float32), SR)
    s = S.load_file(str(p), max_seconds=1)
    assert s.truncated and s.frames == SR


def test_from_array_keeps_two_channels():
    s = S.from_array(np.zeros((10, 4)), SR)
    assert s.audio.shape == (10, 2) and s.audio.dtype == np.float32
    assert S.from_array(np.zeros(10), SR).audio.shape == (10, 1)


# ---------------------------------------------------------------- slicing
def _hits(n=6, gap=0.5, seed=0):
    rng = np.random.default_rng(seed)
    from . import synth
    x = np.zeros(int(SR * (n * gap + 0.5)), dtype=np.float32)
    starts = []
    for i in range(n):
        h = (synth.kick if i % 2 == 0 else synth.snare)(rng)[: int(gap * SR * 0.8)]
        a = int((0.25 + i * gap) * SR)
        x[a:a + h.size] += h
        starts.append(a / SR)
    return x, starts


def test_auto_slices_one_region_per_hit():
    x, starts = _hits()
    s = S.from_array(x, SR)
    regions = slicing.auto_slices(s, sensitivity=0.5)
    assert len(regions) == len(starts)
    assert all(type(v) is float for r in regions for v in r.values())  # JSON-serialisable for the js bridge
    for r, t in zip(regions, starts):
        assert abs(r["start"] - t) < 0.03
        assert r["end"] <= t + 0.5  # cut before the next hit (silent tail trimmed)


def test_auto_slices_respects_max_and_window():
    x, starts = _hits()
    s = S.from_array(x, SR)
    regions = slicing.auto_slices(s, max_s=0.1)
    assert all(r["end"] - r["start"] <= 0.1 + 1e-6 for r in regions)
    inner = slicing.auto_slices(s, start=1.0, end=2.0)
    assert inner and all(1.0 <= r["start"] < 2.0 for r in inner)


def test_onsets_across_chunks(monkeypatch):
    monkeypatch.setattr(slicing, "CHUNK_S", 1.0)  # force several chunks with overlap
    x, starts = _hits(n=8)
    t = slicing.onset_times(x, SR)
    assert len(t) == len(starts)


def test_clamp_and_render():
    assert slicing.clamp(5, 1, max_s=2) == (1.0, 3.0)
    assert slicing.clamp(-1, 100, max_s=30, total=10) == (0.0, 10.0)
    s = S.from_array(np.full(SR, 0.25, dtype=np.float32), SR)
    y = slicing.render(s, 0.0, 0.5, fade_in_ms=10, fade_out_ms=10, normalize=True)
    assert y.shape == (SR // 2, 1)
    assert y[0, 0] == 0 and y[-1, 0] == 0
    assert abs(np.abs(y).max() - 10 ** (-0.3 / 20)) < 1e-4
    assert slicing.render(s, 0, 10, max_s=0.2).shape[0] == int(0.2 * SR)


# ---------------------------------------------------------------- export
def test_export_file_origin(tmp_path):
    x, _ = _hits()
    s = S.from_array(x, SR, title="Break", origin="file")
    paths = sampler_export.export(s, [{"start": 0.2, "end": 0.6}, {"start": 0.7, "end": 1.1, "name": "snare/1"}],
                                  root=str(tmp_path))
    assert [os.path.basename(p) for p in paths] == ["Break - 01.wav", "snare 1.wav"]
    assert all(os.path.dirname(p) == str(tmp_path / "Da file" / "Break") for p in paths)
    info = sf.info(paths[0])
    assert info.subtype == "PCM_24" and abs(info.duration - 0.4) < 0.01
    assert not os.path.exists(paths[0] + ".license.txt")
    again = sampler_export.export(s, [{"start": 0.2, "end": 0.6}], root=str(tmp_path))
    assert os.path.basename(again[0]) == "Break - 01 (2).wav"


def test_export_link_and_capture_sidecars(tmp_path):
    x, _ = _hits()
    r = OnlineResult(uid="archive:x", source="archive", source_label="Internet Archive", title="Old Tape",
                     author="Someone", license="by", page_url="https://archive.org/details/x",
                     download_url="https://archive.org/download/x/a.flac")
    link = S.from_array(x, SR, origin="link", title="Old Tape", result=r)
    p = sampler_export.export(link, [{"start": 0, "end": 99}], root=str(tmp_path), max_s=1.0)[0]
    assert sf.info(p).duration <= 1.0 + 1e-3
    lic = open(p + ".license.txt").read()
    assert "CC BY" in lic and "Attribuzione richiesta" in lic and "Regione: 0.000–1.000 s" in lic
    assert "Internet Archive" in p
    cap = S.from_array(x, SR, origin="capture", title="Cattura", meta={"captured_at": "2026-10-12 10:00"})
    p = sampler_export.export(cap, [{"start": 0, "end": 1}], root=str(tmp_path))[0]
    assert "uso personale" in open(p + ".source.txt").read()


# ---------------------------------------------------------------- links
@pytest.mark.parametrize("url,expected", [
    ("https://freesound.org/people/producer/sounds/2086/", ("freesound", "2086")),
    ("freesound.org/s/2086", ("freesound", "2086")),
    ("https://archive.org/details/DR660Samples", ("archive", "DR660Samples")),
    ("https://archive.org/download/DR660Samples/Kick%2001.wav", ("archive", "DR660Samples/Kick 01.wav")),
    ("https://ccmixter.org/files/bblohowiak/71265", ("ccmixter", "71265")),
    ("https://openverse.org/audio/e43d1972-6c6c-44be-a6f7-1eea6cda842f",
     ("openverse", "e43d1972-6c6c-44be-a6f7-1eea6cda842f")),
    ("https://commons.wikimedia.org/wiki/File:Snare_drum.ogg", ("commons", "File:Snare_drum.ogg")),
    ("https://upload.wikimedia.org/wikipedia/commons/a/ab/Snare_drum.ogg", ("commons", "File:Snare_drum.ogg")),
])
def test_classify_supported(url, expected):
    assert links.classify(url) == expected


@pytest.mark.parametrize("url,name", [
    ("https://www.youtube.com/watch?v=abc", "YouTube"), ("https://youtu.be/abc", "YouTube"),
    ("https://m.youtube.com/watch?v=abc", "YouTube"), ("https://open.spotify.com/track/x", "Spotify"),
    ("https://listen.tidal.com/track/1", "Tidal"), ("https://music.apple.com/it/album/x", "Apple Music"),
    ("https://soundcloud.com/a/b", "SoundCloud"),
])
def test_classify_refuses_streaming(url, name):
    with pytest.raises(SourceError, match=name + " non consente"):
        links.classify(url)


def test_classify_unknown():
    with pytest.raises(SourceError, match="non riconosciuto"):
        links.classify("https://example.com/a.wav")
    with pytest.raises(SourceError):
        links.classify("https://freesound.org/browse/")


def test_resolve_archive_item_and_file(monkeypatch):
    meta = json.loads((FIX / "archive_metadata.json").read_text())
    listing = (FIX / "archive_zip_listing.html").read_text()
    monkeypatch.setattr(archive, "http_get", lambda url, *a, **k: listing if url.endswith("/") else meta)
    monkeypatch.setattr(links, "http_get", lambda url, *a, **k: meta)
    files = links.resolve("https://archive.org/details/DR660Samples", {})
    assert len(files) > 1 and all(f.license == "by" and f.author == "Shpitz Audio" for f in files)
    one = links.resolve(f"https://archive.org/download/DR660Samples/{files[0].path}", {})
    assert [f.path for f in one] == [files[0].path]


def test_resolve_openverse_and_ccmixter(monkeypatch):
    ov = json.loads((FIX / "openverse_snare.json").read_text())["results"][0]
    cc = json.loads((FIX / "ccmixter_drums.json").read_text())
    monkeypatch.setattr(links, "http_get", lambda url, *a, **k: ov if "openverse" in url else cc[:1])
    r = links.resolve(f"https://openverse.org/audio/{ov['id']}", {})[0]
    assert r.download_url == ov["url"] and r.license != "unknown"
    r = links.resolve(cc[0]["file_page_url"], {})[0]
    assert r.download_url and not r.download_url.endswith(".zip")


def test_parse_commons():
    data = {"query": {"pages": {"1": {"pageid": 1, "title": "File:Snare drum.ogg", "imageinfo": [{
        "url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Snare_drum.ogg", "mediatype": "AUDIO",
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Snare_drum.ogg", "size": 1234,
        "extmetadata": {"Artist": {"value": '<a href="x">Jane &amp; Co</a>'},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
                        "LicenseShortName": {"value": "CC BY-SA 4.0"}, "Duration": {"value": 1.5}}}]}}}}
    r = links.parse_commons(data)[0]
    assert (r.title, r.author, r.license, r.format) == ("Snare drum", "Jane & Co", "by-sa", "ogg")
    assert downloads.host_allowed(r.download_url)


# ---------------------------------------------------------------- capture
def test_system_backend_can_be_created_twice():
    """The Objective-C output class must be registered once, or the second capture fails."""
    pytest.importorskip("ScreenCaptureKit")
    a = capture.SystemAudioBackend(lambda b: None)
    b = capture.SystemAudioBackend(lambda b: None)
    assert type(a._output) is type(b._output)


def test_export_keeps_regions_aligned(tmp_path):
    x, _ = _hits()
    s = S.from_array(x, SR, title="Break")
    out = sampler_export.export(s, [{"start": 0.2, "end": 0.6}, {"start": 99, "end": 100}, {"start": 1, "end": 1.2}],
                                root=str(tmp_path))
    assert out[1] is None and os.path.basename(out[2]) == "Break - 03.wav"


# ---------------------------------------------------------------- open from the library / Finder
@pytest.fixture
def lib_api(tmp_path):
    from clustersound.api import Api
    rels = ["Pack A/Loops/loop 1.wav", "Pack A/Loops/loop 2.wav", "Pack A/kick.wav", "Pack B/Snare.wav", "top.wav"]
    items = []
    for i, rel in enumerate(rels):
        p = tmp_path / "lib" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        sf.write(p, np.zeros(SR // 2, dtype=np.float32), SR)
        items.append({"id": i, "path": str(p), "rel": rel, "name": os.path.basename(rel), "cls": 0,
                      "info": {"duration": 0.5}})

    class Lib:
        root = str(tmp_path / "lib")
    a = object.__new__(Api)
    a._lib = Lib()
    a._lib.items = items
    a._sampler = None
    a._sampler_max = lambda: 30.0
    return a


def test_library_browse_folders_files_search(lib_api):
    top = lib_api.sampler_library_browse()
    assert [(f["name"], f["count"]) for f in top["folders"]] == [("Pack A", 3), ("Pack B", 1)]
    assert [f["name"] for f in top["files"]] == ["top.wav"] and top["crumbs"] == [{"name": "lib", "path": ""}]
    a = lib_api.sampler_library_browse("Pack A")
    assert [f["path"] for f in a["folders"]] == ["Pack A/Loops"] and [f["name"] for f in a["files"]] == ["kick.wav"]
    b = lib_api.sampler_library_browse("../Pack B")  # ".." is dropped: never above the library root
    assert b["folder"] == "Pack B" and [f["name"] for f in b["files"]] == ["Snare.wav"]
    assert [c["name"] for c in b["crumbs"]] == ["lib", "Pack B"]
    hits = lib_api.sampler_library_browse("", "LOOP")
    assert [f["rel"] for f in hits["files"]] == ["Pack A/Loops/loop 1.wav", "Pack A/Loops/loop 2.wav"]
    assert lib_api.sampler_library_browse("", "l")["folders"]  # 1 character: browse, not search
    lib_api._lib.root = None
    assert lib_api.sampler_library_browse()["error"]


def test_open_library_item(lib_api):
    r = lib_api.sampler_open_library(3)
    assert r["error"] is None and r["session"]["title"] == "Snare" and r["session"]["origin"] == "file"
    assert lib_api.sampler_open_library(99)["error"] == "sample non trovato"


def test_drop_from_finder(lib_api, tmp_path):
    calls = []

    class Win:
        def evaluate_js(self, js):
            calls.append(js)
    lib_api._window = Win()
    wav = lib_api._lib.items[0]["path"]
    lib_api._on_drop({"dataTransfer": {"files": [{"name": "loop 1.wav", "pywebviewFullPath": wav}]}})
    assert lib_api._sampler.path == wav and '"title": "loop 1"' in calls[-1]
    txt = tmp_path / "notes.txt"
    txt.write_text("x")
    lib_api._on_drop({"dataTransfer": {"files": [{"name": "notes.txt", "pywebviewFullPath": str(txt)}]}})
    assert "trascina un file audio" in calls[-1] and lib_api._sampler.path == wav
