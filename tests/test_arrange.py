import gzip
import os

import numpy as np
import pytest
import soundfile as sf

from clustersound.patterns import ableton, arrange, genres, midi, model, render, store

from . import synth


@pytest.fixture()
def kit(tmp_path):
    rng = np.random.default_rng(5)
    p = genres.build("dnb_rollers", 0)
    for bus, gen in [("kick", synth.kick), ("snare", synth.snare), ("chat", synth.closed_hat), ("bass", synth.sub808)]:
        f = tmp_path / f"{bus}.wav"
        sf.write(f, gen(rng), synth.SR)
        p["buses"][bus]["layers"] = [model.new_layer({"kind": "file", "path": str(f)}, bus)]
    p["buses"]["bass"]["layers"][0]["root"] = 29
    return p


def block(genre, variant, repeat=1, label=None):
    p = genres.build(genre, variant)
    return {"id": f"{genre}{variant}", "label": label or f"{genre} {p['name']}", "repeat": repeat,
            "source": {"genre": genre, "variant": variant}, "groove": arrange.groove_of(p)}


def seq():
    # different genres, lengths and swing: DnB 1 bar ×2, jungle 2 bars, UK garage 1 bar (swing 62)
    return {"name": "Test", "blocks": [block("dnb_rollers", 0, 2), block("jungle", 0), block("ukg2step", 0)]}


def test_flatten_lengths_and_sections(kit):
    flat = arrange.flatten(kit, seq())
    assert flat["bars"] == 2 + 2 + 1 == arrange.total_bars(seq())
    assert len(flat["buses"]["kick"]["steps"]) == flat["bars"] * 16
    assert [(s["start_bar"], s["bars"], s["repeat"]) for s in flat["sections"]] == [(0, 2, 2), (2, 2, 1), (4, 1, 1)]
    assert flat["swing_bars"] == [50, 50, 50, 50, 62]
    # samples/mix come from the kit
    assert flat["buses"]["kick"]["layers"][0]["name"] == "kick" and flat["bpm"] == kit["bpm"]


def test_flatten_offsets(kit):
    s = seq()
    flat = arrange.flatten(kit, s)
    dnb = s["blocks"][0]["groove"]
    jungle = s["blocks"][1]["groove"]
    k = flat["buses"]["kick"]["steps"]
    assert k[:16] == dnb["buses"]["kick"]["steps"] and k[16:32] == dnb["buses"]["kick"]["steps"]
    assert k[32:64] == jungle["buses"]["kick"]["steps"]
    first_jungle_note = min(n["step"] for n in jungle["bass"]["notes"])
    assert any(n["step"] == 32 + first_jungle_note for n in flat["buses"]["bass"]["notes"])
    assert all(n["step"] + n["len"] <= flat["bars"] * 16 for n in flat["buses"]["bass"]["notes"])


def test_sequence_midi_and_swing(kit, tmp_path):
    flat = arrange.flatten(kit, seq())
    path = tmp_path / "s.mid"
    midi.write(str(path), flat, "drums", "drumrack")
    notes = midi.read_notes(str(path))
    kick_note = midi.drum_notes(flat, "drumrack")["kick"]
    kicks = sorted(t for _, t, n, _ in notes if n == kick_note)
    assert kicks[0] == 0 and 16 * 2 * 24 * 2 in kicks  # first kick of the jungle block at bar 3
    # garage bar (bar 5) is swung, the DnB bars are straight
    assert model.tick(flat, 1) == 24
    assert model.tick(flat, 4 * 16 + 1) == model.step_tick(1, 62) + 4 * 16 * 24
    assert max(t for *_, t, _, _ in [(0, *x[1:]) for x in notes]) < flat["bars"] * 16 * 24


def test_sequence_render_length(kit):
    flat = arrange.flatten(kit, seq())
    x = render.render(flat, lambda r: r.get("path"))
    assert len(x) == pytest.approx(flat["bars"] * 4 * 60 / flat["bpm"] * render.SR, abs=2)
    assert np.max(np.abs(x)) > 0.05


def test_sequence_ableton_package(kit, tmp_path):
    flat = arrange.flatten(kit, seq())
    folder = ableton.export_package(flat, str(tmp_path), lambda r: r.get("path"), lambda r: None, "Seq")
    files = os.listdir(folder)
    assert "Sequence.wav" in files and "Loop.wav" not in files
    readme = open(os.path.join(folder, "README.txt"), encoding="utf-8").read()
    assert "RUNNING ORDER" in readme and "bars 1-2" in readme and "×2" in readme and "bars 5-5" in readme
    last = max(t for _, t, _, _ in midi.read_notes(os.path.join(folder, "Drums.mid")))
    assert last > 4 * 16 * 24  # the drums MIDI covers the whole sequence
    assert gzip.open(os.path.join(folder, "Seq Drum Rack.adg")).read(5) == b"<?xml"


def test_empty_and_cap(kit):
    with pytest.raises(ValueError):
        arrange.flatten(kit, {"blocks": []})
    long = {"blocks": [block("house", 0, repeat=32)] * 10}
    assert arrange.flatten(kit, long)["bars"] == arrange.MAX_BARS


def test_layer_own_steps_are_tiled(kit):
    kit["buses"]["kick"]["layers"][0]["steps"] = [100] + [0] * 15
    flat = arrange.flatten(kit, seq())
    own = flat["buses"]["kick"]["layers"][0]["steps"]
    assert len(own) == flat["bars"] * 16 and own[16] == 100 and own[17] == 0


def test_store_sequences(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    store.save(genres.build("house", 0))  # patterns and sequences live side by side
    s = store.save_sequence(seq())
    assert s["id"].startswith("seq:") and store.list_sequences()[0]["name"] == "Test"
    assert len(store.list_user()) == 1
    assert store.delete_sequence(s["id"]) and store.list_sequences() == [] and len(store.list_user()) == 1
