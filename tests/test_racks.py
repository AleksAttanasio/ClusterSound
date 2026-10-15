import gzip
import json
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import soundfile as sf

from clustersound.racks import ableton, dynamics_match, layouts, select, store

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


@pytest.mark.parametrize("mapping,quads", [("launchpad", "CABD"), ("launchpad", "CDAB"), ("launchpad", "DBCA"), ("rows", "CABD")])
def test_notes_are_unique(mapping, quads):
    notes = [layouts.note_for(p, mapping, quads) for p in range(64)]
    assert sorted(notes) == list(range(36, 100))


def test_launchpad_quadrants():
    # default, as the Launchpad plays them: 36-51 top left, 68-83 top right, 52-67 bottom left, 84-99 bottom right
    n = lambda r, c: layouts.note_for(layouts.pad(r, c))  # noqa: E731
    assert n(4, 0) == 36 and n(4, 3) == 39 and n(7, 0) == 48 and n(7, 3) == 51
    assert n(4, 4) == 68 and n(7, 7) == 83
    assert n(0, 0) == 52 and n(3, 3) == 67
    assert n(0, 4) == 84 and n(3, 7) == 99


def test_live_quadrants():
    n = lambda r, c: layouts.note_for(layouts.pad(r, c), "launchpad", "CDAB")  # noqa: E731
    assert n(0, 0) == 36 and n(0, 4) == 52 and n(4, 0) == 68 and n(7, 7) == 99


def test_quads_are_validated():
    assert layouts.new_rack()["quads"] == "DBCA"
    assert layouts.validate({"quads": "AABB"})["quads"] == "DBCA"
    assert layouts.validate({})["quads"] == "DBCA"
    r = layouts.validate({"quads": "DCBA"})
    assert r["quads"] == "DCBA" and layouts.note_of(r, 0) == 52


def test_group_settings_defaults_and_overrides():
    rack = layouts.new_rack()
    s = layouts.group_settings(rack)
    assert s[3] == {"family": "chat", "choke": 1, "lock": False} and s[0]["choke"] == 0
    rack["groups"] = {"cols8:0": {"family": "808", "choke": 4, "lock": True}}
    assert layouts.group_settings(rack)[0] == {"family": "808", "choke": 4, "lock": True}


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


def test_random_group(emb):
    keys = np.array(["a:1"] * 10 + ["a:2"] * 10 + ["b:1"] * 21, dtype=object)
    ok = np.ones(41, bool)
    ok[20:] = False  # only class "a"
    out = select.random_group(emb, keys, ok, 4, rng_seed=5)
    assert len(out) == 4 and out[0][1] == 1.0
    assert all(i < 20 for i, _ in out)  # inside the allowed classes
    assert out == select.random_group(emb, keys, ok, 4, rng_seed=5)
    seeds = {keys[select.random_group(emb, keys, ok, 1, rng_seed=s)[0][0]] for s in range(20)}
    assert seeds == {"a:1", "a:2"}  # both groups get picked
    assert select.random_group(emb, keys, np.zeros(41, bool), 4) == []


# ---------------------------------------------------------------- dynamics matching
def _env(decay, k=0, attack=0.002):
    """Envelope features of a sound decaying in `decay` s; k: its rank in its class (sets tail and slope)."""
    return {"attack": attack, "decay20": decay, "t60": 3 * decay, "tail_ratio": 0.1 + 0.08 * k, "env_slope": -40 + 3 * k}


@pytest.fixture()
def dyn():
    """Kicks with decays 0.05..0.5 s (0..9), hats 10x shorter (10..19): same spread within each class."""
    decays = np.geomspace(0.05, 0.5, 10)
    feats = [_env(d, k) for k, d in enumerate(decays)] + [_env(d / 10, k) for k, d in enumerate(decays)]
    cls = np.array(["kick"] * 10 + ["hat"] * 10, dtype=object)
    return dynamics_match.dyn_matrix(feats, cls)


def test_dynamics_are_relative_to_the_class(dyn):
    long_kick = dynamics_match.reference(dyn, [9])
    d = dynamics_match.distances(dyn, long_kick)
    assert d[19] < 0.2 < d[0]       # the long hat matches the long kick, a short kick does not
    assert np.argmin(d[10:]) == 9   # the closest hat is the longest one


def test_scores_follow_distance(dyn):
    ref = dynamics_match.reference(dyn, [0, 1])
    sc = dynamics_match.scores(dyn, ref)
    assert np.all((sc >= 0) & (sc <= 1))
    order = np.argsort(dynamics_match.distances(dyn, ref))
    assert np.all(np.diff(sc[order]) <= 1e-6)
    assert np.all(dynamics_match.scores(dyn, None) == 1)
    assert dynamics_match.reference(dyn, []) is None


def test_margin_mask(dyn):
    ok = np.zeros(20, bool)
    ok[10:] = True
    ref = dynamics_match.reference(dyn, [0])  # the shortest kick
    m = dynamics_match.margin_mask(dyn, ref, ok, 0.3, min_keep=2)
    assert set(np.flatnonzero(m)) == {10, 11, 12}  # the 3 shortest hats
    assert dynamics_match.margin_mask(dyn, ref, ok, 0.1, min_keep=4).sum() == 4
    assert dynamics_match.margin_mask(dyn, ref, ok, 1.0) is ok
    assert dynamics_match.margin_mask(dyn, None, ok, 0.1) is ok


def test_random_group_with_dynamics_mask(emb):
    keys = np.array(["a:1"] * 20 + ["b:1"] * 21, dtype=object)
    feats = [_env(d, k % 10) for k, d in enumerate(np.geomspace(0.05, 0.5, 41))]
    D = dynamics_match.dyn_matrix(feats, keys)
    ok = dynamics_match.margin_mask(D, dynamics_match.reference(D, [0]), np.ones(41, bool), 0.2)
    out = select.random_group(emb, keys, ok, 3, rng_seed=2)
    assert out and all(ok[i] for i, _ in out)
    assert out == select.random_group(emb, keys, ok, 3, rng_seed=2)


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
    rack["pads"][0] = kick                      # col 0 (kick group), note 52
    rack["pads"][layouts.pad(1, 0)] = kick      # same file on another pad, note 56
    rack["pads"][1] = snare                     # col 1, note 53
    rack["pads"][layouts.pad(7, 3)] = chat      # col 3 (closed hat, choke 1), note 51
    rack["pads"][layouts.pad(0, 4)] = ohat      # col 4 (open hat, choke 1), note 84
    rack["pads"][5] = {"kind": "file", "path": str(tmp_path / "missing.wav"), "name": "missing.wav"}
    out = tmp_path / "out"
    out.mkdir()
    folder = ableton.export_rack(rack, str(out), lambda r: r["path"] if os.path.isfile(r["path"]) else None,
                                 lambda r: None)
    doc = ET.fromstring(gzip.open(os.path.join(folder, "Test Kit Drum Rack.adg")).read())
    branches = doc.findall(".//DrumBranchPreset")
    notes = sorted(128 - int(b.find("ZoneSettings/ReceivingNote").get("Value")) for b in branches)
    assert notes == [51, 52, 53, 56, 84]
    chokes = {128 - int(b.find("ZoneSettings/ReceivingNote").get("Value")): int(b.find("ZoneSettings/ChokeGroup").get("Value"))
              for b in branches}
    assert chokes[51] == 1 and chokes[84] == 1 and chokes[52] == 0
    for b in branches:
        fr = b.find(".//SampleRef/FileRef")
        rel = [e.get("Dir") for e in fr.find("RelativePath")]
        assert os.path.isfile(os.path.join(folder, *rel, fr.find("Name").get("Value")))
    wavs = [f for _, _, fs in os.walk(os.path.join(folder, "Samples")) for f in fs if f.endswith(".wav")]
    assert len(wavs) == 5
    text = open(os.path.join(folder, "README.txt"), encoding="utf-8").read()
    assert "PAD MAP" in text and "C1" in text and "Active choke groups: 1" in text
    assert "36-51 top left, 68-83 top right, 52-67 bottom left, 84-99 bottom right" in text


def test_export_follows_the_kits_quads(tmp_path, samples):
    rack = layouts.new_rack("Live Kit")
    rack["quads"] = "CDAB"
    rack["pads"][layouts.pad(0, 4)] = samples[0]
    folder = ableton.export_rack(rack, str(tmp_path), lambda r: r["path"], lambda r: None)
    doc = ET.fromstring(gzip.open(os.path.join(folder, "Live Kit Drum Rack.adg")).read())
    assert [128 - int(b.find("ZoneSettings/ReceivingNote").get("Value")) for b in doc.findall(".//DrumBranchPreset")] == [52]
    assert "E2" in open(os.path.join(folder, "README.txt"), encoding="utf-8").read()


def test_export_empty_rack_fails(tmp_path):
    with pytest.raises(ValueError):
        ableton.export_rack(layouts.new_rack(), str(tmp_path), lambda r: None, lambda r: None)


def test_store_lists_old_racks_with_quads(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    old = {k: v for k, v in layouts.new_rack("Old").items() if k != "quads"}
    old["id"] = "rack:old"
    (tmp_path / "racks.json").write_text(json.dumps({"version": 1, "racks": [old]}), encoding="utf-8")
    assert store.list_racks()[0]["quads"] == layouts.DEFAULT_QUADS and store.list_racks()[0]["id"] == "rack:old"


def test_store_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    r = store.save(layouts.new_rack("A"))
    assert r["id"].startswith("rack:") and len(r["pads"]) == 64
    r["name"] = "B"
    store.save(r)
    assert [x["name"] for x in store.list_racks()] == ["B"]
    assert store.delete(r["id"]) and store.list_racks() == []
