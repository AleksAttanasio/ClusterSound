import os

import numpy as np
import pytest
import soundfile as sf

from clustersound.chords import perform
from clustersound.live import payload
from clustersound.patterns import genres, midi, model
from clustersound.racks import layouts

from . import synth

CMAJ = [[48, 100], [52, 100], [55, 100], [60, 100]]


def _resolve(r):
    return r["path"] if r and os.path.isfile(r.get("path", "")) else None


@pytest.fixture()
def samples(tmp_path):
    rng = np.random.default_rng(3)
    out = {}
    for name, gen in [("kick", synth.kick), ("snare", synth.snare), ("chat", synth.closed_hat), ("sub", synth.sub808)]:
        p = tmp_path / f"{name}.wav"
        sf.write(p, gen(rng), synth.SR)
        out[name] = {"kind": "file", "path": str(p), "name": p.name}
    return out


@pytest.fixture()
def export_dir(tmp_path):
    d = tmp_path / "ClusterSound Patterns"
    d.mkdir()
    return str(d)


# ---------------------------------------------------------------- payload
def test_notes_from_events_beats():
    ev = [(0, bytes([0x90, 36, 100])), (12, bytes([0x80, 36, 0])), (96, bytes([0x90, 38, 90])), (120, bytes([0x80, 38, 0]))]
    assert payload.notes_from_events(ev, 96) == [[36, 0.0, 0.125, 100], [38, 1.0, 0.25, 90]]


def test_place_path(export_dir):
    p = os.path.join(export_dir, "_Live", "rack", "Kit", "Kit Drum Rack.adg")
    assert payload.place_path(export_dir, p) == "ClusterSound Patterns/_Live/rack/Kit/Kit Drum Rack.adg"
    assert payload.place_path(export_dir, None) is None


def test_pattern_payload_matches_drum_rack(export_dir, samples):
    p = genres.build("house", 0)
    p["buses"]["kick"]["layers"] = [model.new_layer(samples["kick"], "kick")]
    p["buses"]["snare"]["layers"] = [model.new_layer(samples["snare"], "snare")]
    p["buses"]["chat"]["layers"] = [model.new_layer(samples["chat"], "chat")]
    p["buses"]["bass"]["layers"] = [model.new_layer(samples["sub"], "sub")]
    out = payload.pattern(p, export_dir, _resolve, lambda r: None, "House Test")
    assert out["kind"] == "pattern" and out["bpm"] == p["bpm"]
    drums, bass = out["tracks"]
    assert os.path.isfile(drums["adg"]) and drums["adg_place"].startswith("ClusterSound Patterns/_Live/pattern/")
    clip = drums["clips"][0]
    assert clip["length"] == p["bars"] * 4
    loaded = {b for b in ("kick", "snare", "chat") if any(p["buses"][b]["steps"])}
    layout = midi.drum_layout(p, "drumrack", include=loaded)
    assert {n[0] for n in clip["notes"]} == {n for notes in layout.values() for n in notes}
    assert all(0 <= n[1] < clip["length"] for n in clip["notes"])
    if p["buses"]["bass"]["notes"]:
        assert bass["name"] == "Bass" and os.path.isfile(bass["adg"]) and bass["clips"][0]["notes"]


def test_pattern_without_samples_has_clip_only(export_dir):
    p = genres.build("house", 0)
    out = payload.pattern(p, export_dir, _resolve, lambda r: None, "No Kit")
    drums = out["tracks"][0]
    assert drums["adg"] is None and drums["clips"][0]["notes"]


def test_rack_payload(export_dir, samples):
    r = layouts.new_rack("Kit")
    r["pads"][0] = samples["kick"]
    out = payload.rack(r, export_dir, _resolve, lambda r: None)
    (track,) = out["tracks"]
    assert track["name"] == "Kit" and os.path.isfile(track["adg"]) and track["clips"] == []


def test_compose_payload_matches_render():
    seq = {"bars": 2, "clips": [{"id": "a", "notes": CMAJ, "start": 0, "len": 16},
                                {"id": "b", "notes": CMAJ, "start": 16, "len": 16, "transpose": 5}]}
    proj = {"name": "Prog", "bpm": 90, "order": ["A", "B"], "versions": {"A": seq, "B": {**seq, "bars": 1}},
            "modes": {"1": perform.DEFAULT_MODE}, "modeActive": "1"}
    out = payload.compose(proj)
    assert out["bpm"] == 90
    a, b = out["tracks"][0]["clips"]
    assert (a["name"], a["length"], b["length"]) == ("Prog A", 8.0, 4.0)
    ev = perform.render({**seq, "bpm": 90, "mode": perform.DEFAULT_MODE})
    assert len(a["notes"]) == len(ev)
    assert sorted(n[1] for n in a["notes"]) == sorted(round(s / perform.PPQ, 6) for s, *_ in ev)
    single = payload.compose({**seq, "name": "S", "bpm": 100})
    assert single["tracks"][0]["clips"][0]["name"] == "S"
