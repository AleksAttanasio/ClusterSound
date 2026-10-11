import gzip
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import soundfile as sf

from clustersound.racks import ableton, layouts, select, store

from . import synth


# ---------------------------------------------------------------- layouts
@pytest.mark.parametrize("geometry", layouts.GEOMETRIES)
def test_geometry_covers_every_pad_once(geometry):
    gs = layouts.groups(geometry)
    flat = [p for g in gs for p in g]
    assert sorted(flat) == list(range(64))
    assert len(layouts.default_families(geometry)) == len(gs)
    sizes = {"cols8": 8, "blocks2": 4, "blocks4": 16, "quadcols": 4, "free": 1}[geometry]
    assert all(len(g) == sizes for g in gs)


def test_group_shapes():
    assert layouts.groups("cols8")[0] == [layouts.pad(r, 0) for r in range(8)]  # first column, bottom up
    assert layouts.groups("blocks2")[0] == [0, 1, 8, 9]
    assert layouts.groups("quadcols")[4] == [4, 12, 20, 28]  # first column of the bottom-right quadrant


@pytest.mark.parametrize("mapping", ["launchpad", "rows"])
def test_notes_are_unique(mapping):
    notes = [layouts.note_for(p, mapping) for p in range(64)]
    assert sorted(notes) == list(range(36, 100))


def test_launchpad_quadrants():
    n = lambda r, c: layouts.note_for(layouts.pad(r, c))  # noqa: E731
    assert n(0, 0) == 36 and n(0, 3) == 39 and n(3, 3) == 51
    assert n(0, 4) == 52 and n(0, 7) == 55
    assert n(4, 0) == 68 and n(7, 0) == 80
    assert n(7, 7) == 99


def test_group_settings_defaults_and_overrides():
    rack = layouts.new_rack()
    s = layouts.group_settings(rack)
    assert s[3] == {"family": "chat", "choke": 1} and s[0]["choke"] == 0
    rack["groups"] = {"cols8:0": {"family": "808", "choke": 4}}
    assert layouts.group_settings(rack)[0] == {"family": "808", "choke": 4}


# ---------------------------------------------------------------- similarity picks
@pytest.fixture()
def emb():
    """Two families of points: 0..19 near axis 0, 20..39 near axis 1; 40 duplicates 1."""
    rng = np.random.default_rng(0)
    X = np.zeros((41, 8), np.float32)
    X[:20, 0] = 1
    X[20:40, 1] = 1
    X[:40] += rng.normal(0, 0.15, (40, 8))
    X[:20, 0] += np.linspace(0, 1, 20)  # a gradient of similarity around item 19
    X[40] = X[1] * 1.0001
    return select.l2norm(X)


def test_nearest_is_sorted_and_same_family(emb):
    out = select.pick(emb, 0, 5, "nearest")
    sims = [s for _, s in out]
    assert sims == sorted(sims, reverse=True)
    assert all(i < 20 or i == 40 for i, _ in out)


def test_duplicates_are_skipped(emb):
    ids = [i for i, _ in select.neighbours(emb, 1, 30)]
    assert 40 not in ids


def test_mask_and_exclude(emb):
    ok = np.zeros(41, bool)
    ok[20:40] = True
    out = select.pick(emb, 0, 4, "nearest", ok=ok, exclude={20, 21})
    assert all(22 <= i < 40 for i, _ in out) and len(out) == 4


def test_random_is_reproducible_and_varies(emb):
    a = select.pick(emb, 5, 4, "random", variation=1.0, rng_seed=1)
    assert a == select.pick(emb, 5, 4, "random", variation=1.0, rng_seed=1)
    pool = {i for i, _ in select.neighbours(emb, 5, 4 + 20)}
    assert {i for i, _ in a} <= pool
    draws = {tuple(sorted(i for i, _ in select.pick(emb, 5, 4, "random", variation=1.0, rng_seed=s))) for s in range(10)}
    assert len(draws) > 1


def test_trail_cut_and_topped_up(emb):
    out = select.trail(emb, [3, 7, 3, 9], 2)
    assert [i for i, _ in out] == [3, 7]
    out = select.trail(emb, [3, 7, 3, 9], 6)
    ids = [i for i, _ in out]
    assert ids[:3] == [3, 7, 9] and len(ids) == 6 and len(set(ids)) == 6
    ids = [i for i, _ in select.trail(emb, [3, 7], 4, exclude={7, 2})]
    assert ids[:2] == [3, 7] and 2 not in ids  # stops kept, exclusion only for the top-up


# ---------------------------------------------------------------- export
@pytest.fixture()
def samples(tmp_path):
    rng = np.random.default_rng(3)
    refs = []
    for name, gen in [("kick", synth.kick), ("snare", synth.snare), ("chat", synth.closed_hat), ("ohat", synth.open_hat)]:
        p = tmp_path / f"{name}.wav"
        sf.write(p, gen(rng), synth.SR)
        refs.append({"kind": "file", "path": str(p), "name": p.name})
    return refs


def test_export_rack(tmp_path, samples):
    rack = layouts.new_rack("Test Kit")
    kick, snare, chat, ohat = samples
    rack["pads"][0] = kick                      # col 0 (kick group), note 36
    rack["pads"][layouts.pad(1, 0)] = kick      # same file on another pad, note 40
    rack["pads"][1] = snare                     # col 1, note 37
    rack["pads"][layouts.pad(7, 3)] = chat      # col 3 (closed hat, choke 1), note 83
    rack["pads"][layouts.pad(0, 4)] = ohat      # col 4 (open hat, choke 1), note 52
    rack["pads"][5] = {"kind": "file", "path": str(tmp_path / "missing.wav"), "name": "missing.wav"}
    out = tmp_path / "out"
    out.mkdir()
    folder = ableton.export_rack(rack, str(out), lambda r: r["path"] if os.path.isfile(r["path"]) else None,
                                 lambda r: None)
    doc = ET.fromstring(gzip.open(os.path.join(folder, "Test Kit Drum Rack.adg")).read())
    branches = doc.findall(".//DrumBranchPreset")
    notes = sorted(128 - int(b.find("ZoneSettings/ReceivingNote").get("Value")) for b in branches)
    assert notes == [36, 37, 40, 52, 83]
    chokes = {128 - int(b.find("ZoneSettings/ReceivingNote").get("Value")): int(b.find("ZoneSettings/ChokeGroup").get("Value"))
              for b in branches}
    assert chokes[83] == 1 and chokes[52] == 1 and chokes[36] == 0
    for b in branches:
        fr = b.find(".//SampleRef/FileRef")
        rel = [e.get("Dir") for e in fr.find("RelativePath")]
        assert os.path.isfile(os.path.join(folder, *rel, fr.find("Name").get("Value")))
    wavs = [f for _, _, fs in os.walk(os.path.join(folder, "Samples")) for f in fs if f.endswith(".wav")]
    assert len(wavs) == 5
    text = open(os.path.join(folder, "LEGGIMI.txt"), encoding="utf-8").read()
    assert "MAPPA DEI PAD" in text and "C1" in text and "Choke group attivi: 1" in text


def test_export_empty_rack_fails(tmp_path):
    with pytest.raises(ValueError):
        ableton.export_rack(layouts.new_rack(), str(tmp_path), lambda r: None, lambda r: None)


def test_store_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    r = store.save(layouts.new_rack("A"))
    assert r["id"].startswith("rack:") and len(r["pads"]) == 64
    r["name"] = "B"
    store.save(r)
    assert [x["name"] for x in store.list_racks()] == ["B"]
    assert store.delete(r["id"]) and store.list_racks() == []
