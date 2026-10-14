import gzip
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import soundfile as sf

from clustersound.online import cache
from clustersound.patterns import ableton, genres, midi, model, render, store

from . import synth

SR = synth.SR


@pytest.fixture()
def samples(tmp_path):
    rng = np.random.default_rng(3)
    out = {}
    for name, gen in [("kick", synth.kick), ("snare", synth.snare), ("clap", synth.clap),
                      ("chat", synth.closed_hat), ("ohat", synth.open_hat), ("sub", synth.sub808)]:
        p = tmp_path / f"{name}.wav"
        sf.write(p, gen(rng), SR)
        out[name] = {"kind": "file", "path": str(p), "name": p.name}
    return out


def with_samples(p, s, layers=None):
    layers = layers or {"kick": ["kick"], "snare": ["snare", "clap"], "chat": ["chat"], "ohat": ["ohat"], "bass": ["sub"]}
    for bus, names in layers.items():
        p["buses"][bus]["layers"] = [model.new_layer(s[n], n) for n in names]
    if p["buses"]["bass"]["layers"]:
        p["buses"]["bass"]["layers"][0]["root"] = 33
    return p


# ---------------------------------------------------------------- genre library
def test_every_genre_is_valid():
    assert len(genres.GENRES) >= 40
    groups = {g["group"] for g in genres.GENRES}
    assert groups == set(genres.GROUPS)
    for g in genres.GENRES:
        lo, hi = g["bpm_range"]
        assert lo <= g["bpm"] <= hi, g["id"]
        vs = genres.variants(g["id"])
        assert len(vs) >= 3, g["id"]
        for i, v in enumerate(vs):
            bars = v.get("bars", 1)
            for bus, text in v["drums"].items():
                assert bus in model.DRUM_IDS, (g["id"], bus)
                parts = text.split("|")
                assert all(len(x) == 16 for x in parts) and len(parts) in (1, bars), (g["id"], v["name"], bus)
                assert not set(text) - set(".xXo234|")
            p = genres.build(g["id"], i)
            assert len(p["buses"]["kick"]["steps"]) == bars * 16
            for nt in p["buses"]["bass"]["notes"]:
                assert nt["step"] + nt["len"] <= bars * 16, (g["id"], v["name"])


def test_bass_music_is_covered():
    names = " ".join(g["name"].lower() for g in genres.GENRES)
    for word in ("garage", "2-step", "dubstep", "drum", "jungle", "grime", "bassline", "riddim", "drill",
                 "footwork", "halftime", "breaks", "neurofunk", "jump-up", "liquid"):
        assert word in names, word


def test_canonical_grooves():
    dnb = genres.build("dnb_rollers", 0)["buses"]
    assert [i for i, v in enumerate(dnb["snare"]["steps"]) if v] == [4, 12]  # 2 and 4
    assert dnb["kick"]["steps"][0] and dnb["kick"]["steps"][10]
    dub = genres.build("dubstep", 0)["buses"]
    assert [i for i, v in enumerate(dub["snare"]["steps"]) if v] == [8]  # half time: snare on 3
    house = genres.build("house", 0)["buses"]
    assert [i for i, v in enumerate(house["kick"]["steps"]) if v] == [0, 4, 8, 12]
    trap = genres.build("trap", 0)["buses"]
    assert any(r > 1 for r in trap["chat"]["ratchet"])  # hat rolls
    assert genres.build("ukg2step", 0)["swing"] > 55


def test_fill_and_breakdown_are_derived():
    names = genres.catalog()[0]["variants"]
    assert "Fill" in names and "Breakdown" in names
    i = names.index("Breakdown")
    brk = genres.build(genres.GENRES[0]["id"], i)
    assert not any(brk["buses"]["kick"]["steps"]) and not brk["buses"]["bass"]["notes"]


def test_notation():
    vel, rat = model.parse_steps("X.x.o.3.|", 16)
    assert vel[:8] == [127, 0, 100, 0, 55, 0, 100, 0] and rat[6] == 3 and len(vel) == 16
    notes = model.parse_bass("0:4:0 6:2:-2g 10:3:5!")
    assert notes[1]["glide"] and notes[1]["semi"] == -2 and notes[2]["vel"] == 120


def test_swing_timing():
    assert model.step_tick(1, 50) == model.TICKS_PER_STEP
    assert model.step_tick(1, 75) == model.TICKS_PER_STEP + model.TICKS_PER_STEP // 2
    assert model.step_tick(2, 75) == 2 * model.TICKS_PER_STEP


# ---------------------------------------------------------------- MIDI
def test_midi_drum_rack_mapping(tmp_path, samples):
    p = with_samples(genres.build("dnb_rollers", 0), samples)
    path = tmp_path / "d.mid"
    midi.write(str(path), p, "drums", "drumrack")
    notes = midi.read_notes(str(path))
    by_note = {}
    for _, tick, note, vel in notes:
        by_note.setdefault(note, []).append((tick, vel))
    mapping = midi.drum_notes(p, "drumrack")
    assert list(mapping.values()) == list(range(36, 36 + len(mapping)))
    assert [t for t, _ in by_note[mapping["snare"]]] == [4 * 24, 12 * 24]
    assert by_note[mapping["kick"]][0] == (0, 127)


def test_midi_gm_ratchet_and_swing(tmp_path):
    p = genres.build("trap", 0)
    p["swing"] = 75
    path = tmp_path / "t.mid"
    midi.write(str(path), p, "drums", "gm")
    hats = sorted(t for _, t, n, _ in midi.read_notes(str(path)) if n == 42)
    roll_step = p["buses"]["chat"]["ratchet"].index(3)
    base = model.step_tick(roll_step, 75)
    assert {base, base + 8, base + 16} <= set(hats)  # 3 hits inside one 16th
    assert model.step_tick(1, 75) in hats or model.step_tick(1, 75) not in [t for t in hats if t % 24 == 0]


def test_midi_bass_and_type1(tmp_path):
    p = genres.build("ukdrill", 0)
    path = tmp_path / "b.mid"
    midi.write(str(path), p, "both", "gm")
    notes = midi.read_notes(str(path))
    tracks = {t for t, *_ in notes}
    assert tracks == {1, 2}
    bass = [n for t, _, n, _ in notes if t == 2]
    root = model.bass_root_midi(p)
    assert bass[0] == root and len(bass) == len(p["buses"]["bass"]["notes"])


# ---------------------------------------------------------------- render
def test_render_length_and_layers(samples):
    p = with_samples(genres.build("dnb_rollers", 0), samples)
    one = render.render(p, lambda r: r.get("path"))
    assert len(one) == round(16 * 24 * (60 / p["bpm"] / model.PPQ) * render.SR)
    assert np.max(np.abs(one)) > 0.05
    p2 = with_samples(genres.build("dnb_rollers", 0), samples, {"snare": ["snare"]})
    p3 = with_samples(genres.build("dnb_rollers", 0), samples, {"snare": ["snare", "clap"]})
    e2 = float(np.sum(render.render(p2, lambda r: r.get("path")) ** 2))
    e3 = float(np.sum(render.render(p3, lambda r: r.get("path")) ** 2))
    assert e3 > e2  # the clap layer adds energy on the snare bus
    p3["buses"]["snare"]["mute"] = True
    assert float(np.sum(render.render(p3, lambda r: r.get("path")) ** 2)) < e2


def test_bass_repitch():
    p = genres.build("dubstep", 0)
    layer = model.new_layer({"kind": "file", "path": "x"}, root=model.bass_root_midi(p) - 2)
    assert render.bass_semitones(p, layer, 0) == 2
    assert render.bass_semitones(p, layer, 5) == 7


# ---------------------------------------------------------------- Ableton package
def test_ableton_package(tmp_path, samples):
    p = with_samples(genres.build("dnb_rollers", 0), samples)
    folder = ableton.export_package(p, str(tmp_path), lambda r: r.get("path"), lambda r: None, "Test DnB")
    files = os.listdir(folder)
    for f in ("Drums.mid", "Bass.mid", "Loop.wav", "README.txt", "Test DnB Drum Rack.adg", "Test DnB Bass.adg"):
        assert f in files, f
    doc = ET.fromstring(gzip.open(os.path.join(folder, "Test DnB Drum Rack.adg")).read())
    assert doc.tag == "Ableton" and doc.get("MajorVersion") == "5"
    pads = doc.find("GroupDevicePreset/BranchPresets")
    notes = [128 - int(b.find("ZoneSettings/ReceivingNote").get("Value")) for b in pads]
    assert notes == list(range(36, 36 + len(notes)))
    midi_notes = {n for _, _, n, _ in midi.read_notes(os.path.join(folder, "Drums.mid"))}
    assert midi_notes <= set(notes)  # every MIDI note lands on a pad
    names = [b.find("Name").get("Value") for b in pads]
    snare = pads[names.index("Snare")]
    assert snare.find("DevicePresets/GroupDevicePreset/Device/InstrumentGroupDevice") is not None  # 2 layers
    assert len(snare.find("DevicePresets/GroupDevicePreset/BranchPresets")) == 2
    hats = [b for b in pads if b.find("Name").get("Value") in ("Closed Hat", "Open Hat")]
    assert all(b.find("ZoneSettings/ChokeGroup").get("Value") == "1" for b in hats)
    for fr in (sr.find("FileRef") for sr in doc.iter("SampleRef")):
        rel = [e.get("Dir") for e in fr.find("RelativePath")]
        assert fr.find("RelativePathType").get("Value") == "1"
        assert os.path.exists(os.path.join(folder, *rel, fr.find("Name").get("Value")))
    for s in doc.iter("OriginalSimpler"):
        assert s.find("Globals/PlaybackMode").get("Value") == "1"  # one-shot drums
    bass = ET.fromstring(gzip.open(os.path.join(folder, "Test DnB Bass.adg")).read())
    assert [k.get("Value") for k in bass.iter("RootKey")] == ["33"]
    assert sf.info(os.path.join(folder, "Loop.wav")).duration == pytest.approx(16 * 60 / p["bpm"] / 4, abs=1e-3)


# ---------------------------------------------------------------- layer alternation
HASH_VECTOR = [((0, 0), 0), ((1, 0), 1667036862), ((7, 15), 1636717729), ((123456, 63), 3070290591),
               ((4294967295, 1000), 3072357879)]  # also checked against altHash() in ui/sequencer.js


def test_alt_hash_vector():
    assert [model.alt_hash(*args) for args, _ in HASH_VECTOR] == [v for _, v in HASH_VECTOR]


def _alt(p, bus, mode, seed=3):
    p["buses"][bus]["alt"] = {"mode": mode, "seed": seed}
    return model.validate(p)


def test_bus_hits_alternation(samples):
    base = with_samples(genres.build("dnb_rollers", 0), samples,
                        {"chat": ["chat", "ohat", "clap"], "snare": ["snare", "clap"]})
    n_hits = len(model.drum_hits(base, "chat"))
    together = model.bus_hits(base, "chat")
    assert len(together) == 3 * n_hits  # off: every layer on every hit
    for mode in ("cycle", "random", "random_pass"):
        p = _alt(base, "chat", mode)
        hits = model.bus_hits(p, "chat")
        assert len(hits) == n_hits and {t for _, t, _ in hits} == {t for t, _ in model.drum_hits(p, "chat")}
        assert len({j for j, _, _ in hits}) > 1
    cyc = _alt(base, "chat", "cycle")
    steps = [i for i, v in enumerate(cyc["buses"]["chat"]["steps"]) if v]
    first = [j for j, t, _ in model.bus_hits(cyc, "chat") if t in {model.tick(cyc, i) for i in steps}]
    assert first[:3] == [0, 1, 2]
    # random: seed decides; random_pass renders/exports its first loop, i.e. the same picks
    assert model.bus_hits(_alt(base, "chat", "random", 1), "chat") != model.bus_hits(_alt(base, "chat", "random", 2), "chat")
    bus = _alt(base, "chat", "random_pass")["buses"]["chat"]
    assert [model.alt_pick(bus, 3, i, 0, 16, loop=0) for i in range(16)] != [model.alt_pick(bus, 3, i, 0, 16, loop=1) for i in range(16)]
    # muted layers drop out; a single remaining layer means no alternation
    p = _alt(base, "chat", "random")
    p["buses"]["chat"]["layers"][1]["mute"] = p["buses"]["chat"]["layers"][2]["mute"] = True
    assert not model.alternating(p["buses"]["chat"]) and {j for j, _, _ in model.bus_hits(p, "chat")} == {0}
    # a layer with its own steps keeps them
    p = _alt(base, "chat", "random")
    own = [0] * 16
    own[3] = 100
    p["buses"]["chat"]["layers"][2]["steps"] = own
    hits = model.bus_hits(p, "chat")
    assert [t for j, t, _ in hits if j == 2] == [model.tick(p, 3)]
    assert {j for j, _, _ in hits if j != 2} <= {0, 1}


def test_alternation_render_midi_and_package(tmp_path, samples):
    p = _alt(with_samples(genres.build("dnb_rollers", 0), samples, {"chat": ["chat", "ohat"], "snare": ["snare", "clap"]}),
             "chat", "random")
    layout = midi.drum_layout(p, "drumrack")
    assert len(layout["chat"]) == 2 and len(layout["snare"]) == 1 and len(midi.drum_layout(p, "gm")["chat"]) == 1
    flat = [n for ns in layout.values() for n in ns]
    assert flat == list(range(36, 36 + len(flat)))
    path = tmp_path / "a.mid"
    midi.write(str(path), p, "drums", "drumrack")
    got = sorted((t, n) for _, t, n, _ in midi.read_notes(str(path)) if n in layout["chat"])
    assert got == sorted((t, layout["chat"][j]) for j, t, _ in model.bus_hits(p, "chat"))
    # rendering alternated hats has less energy than both layers on every hit
    off = model.validate({**p, "buses": {**p["buses"], "chat": {**p["buses"]["chat"], "alt": {"mode": "off", "seed": 0}}}})
    e = lambda q: float(np.sum(render.render(q, lambda r: r.get("path")) ** 2))  # noqa: E731
    assert e(p) < e(off)
    folder = ableton.export_package(p, str(tmp_path), lambda r: r.get("path"), lambda r: None, "Alt")
    doc = ET.fromstring(gzip.open(os.path.join(folder, "Alt Drum Rack.adg")).read())
    names = {b.find("Name").get("Value"): 128 - int(b.find("ZoneSettings/ReceivingNote").get("Value"))
             for b in doc.find("GroupDevicePreset/BranchPresets")}
    filled = midi.drum_layout(p, "drumrack", include={b for b in model.DRUM_IDS if model.active_layers(p["buses"][b])})
    assert names["Closed Hat 1"] == filled["chat"][0] and names["Closed Hat 2"] == filled["chat"][1]
    midi_notes = {n for _, _, n, _ in midi.read_notes(os.path.join(folder, "Drums.mid"))}
    assert midi_notes <= set(names.values())
    assert "the samples alternate" in open(os.path.join(folder, "README.txt"), encoding="utf-8").read()


# ---------------------------------------------------------------- user patterns + cache
def test_user_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    p = genres.build("house", 1)
    saved = store.save({**p, "name": "Mia"})
    assert saved["id"].startswith("user:") and store.list_user()[0]["name"] == "Mia"
    saved["bpm"] = 126
    store.save(saved)
    assert len(store.list_user()) == 1 and store.list_user()[0]["bpm"] == 126
    assert store.delete(saved["id"]) and store.list_user() == []


def test_cache_prune_respects_protected(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path))
    paths = []
    for i in range(5):
        pth = tmp_path / f"{i}.mp3"
        pth.write_bytes(b"x" * (400 << 10))
        os.utime(pth, (1000 + i, 1000 + i))
        paths.append(str(pth))
    cache.protect([paths[0]])  # oldest, but used by the open pattern
    cache.prune(max_mb=1)
    left = sorted(os.listdir(tmp_path))
    assert "0.mp3" in left and cache.size() <= (1 << 20) + (400 << 10)
    assert "1.mp3" not in left  # least recently used unprotected file went first
    cache.protect([])
    cache.clear()
    assert os.listdir(tmp_path) == []
