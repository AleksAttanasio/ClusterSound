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


# ---------------------------------------------------------------- HTTP bridge
@pytest.fixture()
def bridge(tmp_path, export_dir, monkeypatch):
    from clustersound.patterns import store as pat_store
    from clustersound.racks import store as rack_store
    monkeypatch.setattr(pat_store, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(rack_store, "data_dir", lambda: tmp_path)
    from clustersound.live import server
    b = server.Bridge(export_dir, _resolve, lambda r: None)
    assert b.start(0)
    yield b
    b.stop()


def _get(b, path):
    import json
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{b.port}{path}") as r:
            body = r.read()
            return r.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_bridge_catalog_and_payload(bridge):
    from clustersound.patterns import store as pat_store
    seq = {"bars": 1, "clips": [{"id": "a", "notes": CMAJ, "start": 0, "len": 16}]}
    prog = pat_store.save_progression({"name": "P", "bpm": 100, "order": ["A"], "versions": {"A": seq}})
    status, cat = _get(bridge, "/live/catalog")
    assert status == 200 and cat["compose"] == [{"id": prog["id"], "name": "P"}]
    assert any(g["id"] == "house:0" for g in cat["genre"])
    status, out = _get(bridge, f"/live/payload?kind=compose&id={prog['id']}")
    assert status == 200 and out["tracks"][0]["clips"][0]["notes"]
    status, out = _get(bridge, "/live/payload?kind=genre&id=house:0")
    assert status == 200 and out["tracks"][0]["name"] == "Drums"
    assert _get(bridge, "/live/payload?kind=rack&id=rack:nope")[0] == 404


def test_bridge_push_queue_and_routes(bridge):
    assert _get(bridge, "/live/next") == (204, None)
    bridge.push({"kind": "compose", "name": "x"})
    assert _get(bridge, "/live/ping")[1]["pending"] == 1
    assert _get(bridge, "/live/next") == (200, {"kind": "compose", "name": "x"})
    assert _get(bridge, "/live/next")[0] == 204
    assert _get(bridge, "/api/init")[0] == 404


# ---------------------------------------------------------------- Remote Script protocol
def _protocol():
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), "..", "remote_script", "ClusterSoundBridge", "protocol.py")
    spec = importlib.util.spec_from_file_location("cs_protocol", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_osc_roundtrip_and_padding():
    proto = _protocol()
    msg = {"id": 3, "cmd": "load", "track": 2, "place": "ClusterSound Patterns/_Live/rack/Kit – è/Kit Drum Rack.adg"}
    data = proto.osc_encode(msg)
    assert len(data) % 4 == 0 and data.startswith(b"/clustersound\0\0\0,s\0\0")
    assert proto.parse(data) == msg
    assert proto.parse(proto.osc_encode({"x": 1})) is None        # no cmd
    assert proto.parse(proto.osc_encode({"cmd": "ping"}, "/other")) is None
    assert proto.parse(b"garbage") is None


def test_find_item_in_places():
    proto = _protocol()

    class Item:
        def __init__(self, name, *children):
            self.name, self.children = name, list(children)

    adg = Item("Kit Drum Rack.adg")
    places = [Item("Samples"), Item("ClusterSound Patterns", Item("_Live", Item("rack", Item("Kit", Item("Samples"), adg))))]
    assert proto.find_item(places, "ClusterSound Patterns/_Live/rack/Kit/Kit Drum Rack.adg") is adg
    adg.name = "Kit Drum Rack"  # the browser may hide the extension
    assert proto.find_item(places, "ClusterSound Patterns/_Live/rack/Kit/Kit Drum Rack.adg") is adg
    assert proto.find_item(places, "ClusterSound Patterns/_Live/rack/Other/x.adg") is None
    assert proto.find_item(places, "") is None


# ---------------------------------------------------------------- device build
def test_build_amxd(tmp_path):
    import importlib.util
    import json
    import struct
    spec = importlib.util.spec_from_file_location("build_amxd", os.path.join(os.path.dirname(__file__), "..", "tools", "build_amxd.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = mod.build(tmp_path).read_bytes()
    assert data[:12] == b"ampf\x04\x00\x00\x00mmmm" and data[12:24] == b"meta\x04\x00\x00\x00\x00\x00\x00\x00"
    assert data[24:28] == b"ptch"
    n = struct.unpack("<I", data[28:32])[0]
    assert len(data) == 32 + n and data.endswith(b"\0")
    patcher = json.loads(data[32:-1])["patcher"]
    texts = {b["box"].get("text") for b in patcher["boxes"]}
    assert {"js ClusterSound.js", "udpsend 127.0.0.1 9101", "udpreceive 9102", "live.thisdevice"} <= texts
    ids = {b["box"]["id"] for b in patcher["boxes"]}
    assert all(ln["patchline"]["source"][0] in ids and ln["patchline"]["destination"][0] in ids for ln in patcher["lines"])
    assert (tmp_path / "ClusterSound.js").is_file()
