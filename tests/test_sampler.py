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
def test_ring_buffer_wraps_and_keeps_latest():
    rb = capture.RingBuffer(seconds=1.0, sr=10, channels=2)
    rb.write(np.arange(7, dtype=np.float32))  # mono -> both channels
    rb.write(np.arange(7, 14, dtype=np.float32))
    assert rb.filled == 10 and rb.seconds == 1.0
    assert rb.latest()[:, 0].tolist() == list(range(4, 14))
    assert rb.latest(0.3)[:, 1].tolist() == [11, 12, 13]
    rb.write(np.arange(100, 125, dtype=np.float32))  # bigger than the buffer
    assert rb.latest()[:, 0].tolist() == list(range(115, 125))


def test_capture_grab_uses_ring(monkeypatch):
    class Fake:
        sr, channels = 100, 2

        def __init__(self, on_block):
            self.on_block = on_block

        def start(self):
            self.on_block(np.full((250, 2), 0.5, dtype=np.float32))

        def stop(self):
            pass

    monkeypatch.setattr(capture, "SystemAudioBackend", Fake)
    c = capture.SystemCapture(seconds=2)
    st = c.start()
    assert st["running"] and st["seconds"] == 2.0 and st["level"] == 0.5
    s = c.grab(0.5)
    assert s.origin == "capture" and s.audio.shape == (50, 2) and s.meta["device"] == "audio di sistema"
    assert not c.stop()["running"]


def test_capture_grab_empty():
    with pytest.raises(capture.CaptureError):
        capture.SystemCapture().grab()


def test_hit_at_time_zero_is_found():
    x, starts = _hits()
    x = x[int(starts[0] * SR):]  # the first hit starts at sample 0
    assert len(slicing.auto_slices(S.from_array(x, SR))) == len(starts)
