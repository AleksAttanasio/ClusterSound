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


@pytest.fixture()
def stage(tmp_path):
    lib = tmp_path / "User Library"
    lib.mkdir()
    return payload.Stage.user_library(str(lib))


# ---------------------------------------------------------------- payload
def test_notes_from_events_beats():
    ev = [(0, bytes([0x90, 36, 100])), (12, bytes([0x80, 36, 0])), (96, bytes([0x90, 38, 90])), (120, bytes([0x80, 38, 0]))]
    assert payload.notes_from_events(ev, 96) == [[36, 0.0, 0.125, 100], [38, 1.0, 0.25, 90]]


def test_stage_paths(tmp_path, export_dir):
    lib = payload.Stage.user_library(str(tmp_path / "User Library"))
    p = os.path.join(lib.folder("rack"), "Kit", "Kit Drum Rack.adg")
    assert lib.browser_path(p) == "ClusterSound/rack/Kit/Kit Drum Rack.adg"
    places = payload.Stage.places(export_dir)
    p = os.path.join(places.folder("rack"), "Kit", "Kit Drum Rack.adg")
    assert places.browser_path(p) == "ClusterSound Patterns/Live Import/rack/Kit/Kit Drum Rack.adg"
    assert places.browser_path(None) is None
    assert payload.Stage.default(export_dir, str(tmp_path / "missing")).root == "places"
    assert payload.Stage.default(export_dir, str(tmp_path / "User Library")).root == "user_library"


def test_pattern_payload_matches_drum_rack(stage, samples):
    p = genres.build("house", 0)
    p["buses"]["kick"]["layers"] = [model.new_layer(samples["kick"], "kick")]
    p["buses"]["snare"]["layers"] = [model.new_layer(samples["snare"], "snare")]
    p["buses"]["chat"]["layers"] = [model.new_layer(samples["chat"], "chat")]
    p["buses"]["bass"]["layers"] = [model.new_layer(samples["sub"], "sub")]
    out = payload.pattern(p, stage, _resolve, lambda r: None, "House Test")
    assert out["kind"] == "pattern" and out["bpm"] == p["bpm"]
    drums, bass = out["tracks"]
    assert os.path.isfile(drums["adg"]) and drums["adg_root"] == "user_library"
    assert drums["adg_path"].startswith("ClusterSound/pattern/") and (drums["role"], bass["role"]) == ("drums", "bass")
    clip = drums["clips"][0]
    assert clip["length"] == p["bars"] * 4
    loaded = {b for b in ("kick", "snare", "chat") if any(p["buses"][b]["steps"])}
    layout = midi.drum_layout(p, "drumrack", include=loaded)
    assert {n[0] for n in clip["notes"]} == {n for notes in layout.values() for n in notes}
    assert all(0 <= n[1] < clip["length"] for n in clip["notes"])
    assert {(b["id"], b["note"]) for b in drums["buses"]} == {(b, notes[0]) for b, notes in layout.items()}
    assert drums["buses"][0]["label"] == model.BUS_BY_ID[drums["buses"][0]["id"]][1]
    if p["buses"]["bass"]["notes"]:
        assert bass["name"] == "Bass" and os.path.isfile(bass["adg"]) and bass["clips"][0]["notes"]


def test_pattern_without_samples_has_clip_only(stage):
    p = genres.build("house", 0)
    out = payload.pattern(p, stage, _resolve, lambda r: None, "No Kit")
    drums = out["tracks"][0]
    assert drums["adg"] is None and drums["adg_path"] is None and drums["clips"][0]["notes"]
    assert [b["id"] for b in drums["buses"]] == list(midi.drum_layout(p, "drumrack"))  # every bus that plays


def test_rack_payload(stage, samples):
    r = layouts.new_rack("Kit")
    r["pads"][0] = samples["kick"]
    out = payload.rack(r, stage, _resolve, lambda r: None)
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
    assert out["tracks"][0]["role"] == "chords"
    ev = perform.render({**seq, "bpm": 90, "mode": perform.DEFAULT_MODE})
    assert len(a["notes"]) == len(ev)
    assert sorted(n[1] for n in a["notes"]) == sorted(round(s / perform.PPQ, 6) for s, *_ in ev)
    single = payload.compose({**seq, "name": "S", "bpm": 100})
    assert single["tracks"][0]["clips"][0]["name"] == "S"


# ---------------------------------------------------------------- HTTP bridge
@pytest.fixture()
def bridge(tmp_path, stage, monkeypatch):
    from clustersound.patterns import store as pat_store
    from clustersound.racks import store as rack_store
    monkeypatch.setattr(pat_store, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(rack_store, "data_dir", lambda: tmp_path)
    from clustersound.live import server
    monkeypatch.setattr(server, "data_dir", lambda: tmp_path)
    b = server.Bridge(stage, _resolve, lambda r: None)
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
    assert "genre" not in cat and cat["sequence"] == []
    status, out = _get(bridge, f"/live/payload?kind=compose&id={prog['id']}")
    assert status == 200 and out["tracks"][0]["clips"][0]["notes"]
    assert _get(bridge, "/live/payload?kind=rack&id=rack:nope")[0] == 404


def _sequence(kit=None, source=None):
    from clustersound.patterns import arrange
    a, b = genres.build("house", 0), genres.build("house", 1)
    seq = {"name": "Seq", "blocks": [
        {"id": "b1", "label": "A", "source": source or {}, "repeat": 2, "groove": arrange.groove_of(a)},
        {"id": "b2", "label": "B", "source": {}, "repeat": 1, "groove": arrange.groove_of(b)}]}
    if kit:
        seq["kit"] = kit
    return seq


def test_bridge_sequences(bridge, samples):
    from clustersound.patterns import arrange
    from clustersound.patterns import store as pat_store
    kit = genres.build("house", 0)
    kit["buses"]["kick"]["layers"] = [model.new_layer(samples["kick"], "kick")]
    kit["buses"]["bass"]["layers"] = [model.new_layer(samples["sub"], "sub")]
    with_kit = pat_store.save_sequence(_sequence(kit))
    user = pat_store.save(kit)
    from_user = pat_store.save_sequence({**_sequence(source={"genre": "house", "user": user["id"]}), "name": "U"})
    midi_only = pat_store.save_sequence({**_sequence(source={"genre": "house", "variant": 0}), "name": "G"})
    orphan = pat_store.save_sequence({**_sequence(), "name": "X"})

    names = {s["id"]: s["name"] for s in _get(bridge, "/live/catalog")[1]["sequence"]}
    assert names[with_kit["id"]] == "Seq" and names[from_user["id"]] == "U" and names[midi_only["id"]] == "G (MIDI only)"

    status, out = _get(bridge, f"/live/payload?kind=sequence&id={with_kit['id']}")
    assert status == 200 and out["kind"] == "pattern"
    drums = out["tracks"][0]
    assert drums["adg"] and drums["clips"][0]["length"] == arrange.total_bars(with_kit) * 4
    assert max(n[1] for n in drums["clips"][0]["notes"]) >= 4 * arrange.total_bars(with_kit) - 4  # notes up to the last bar
    assert _get(bridge, f"/live/payload?kind=sequence&id={from_user['id']}")[1]["tracks"][0]["adg"]
    status, out = _get(bridge, f"/live/payload?kind=sequence&id={midi_only['id']}")
    assert status == 200 and out["tracks"][0]["adg"] is None and out["tracks"][0]["clips"][0]["notes"]
    status, out = _get(bridge, f"/live/payload?kind=sequence&id={orphan['id']}")
    assert status == 500 and "without a kit" in out["error"]

    from clustersound.live import server
    server.save_current_kit(kit)  # the Sequencer's kit fills in for sequences saved without one
    names = {s["id"]: s["name"] for s in _get(bridge, "/live/catalog")[1]["sequence"]}
    assert names[midi_only["id"]] == "G (current kit)" and names[orphan["id"]] == "X (current kit)"
    assert _get(bridge, f"/live/payload?kind=sequence&id={orphan['id']}")[1]["tracks"][0]["adg"]


def test_bridge_push_queue_and_routes(bridge):
    assert _get(bridge, "/live/next") == (204, None)
    bridge.push({"kind": "compose", "name": "x"})
    assert _get(bridge, "/live/ping")[1]["pending"] == 1
    assert _get(bridge, "/live/next") == (200, {"kind": "compose", "name": "x"})
    assert _get(bridge, "/live/next")[0] == 204
    assert _get(bridge, "/api/init")[0] == 404


# ---------------------------------------------------------------- Recorder audio
def test_audio_payload_whole_and_region(stage):
    from clustersound.sampler import session as S
    x = (0.3 * np.sin(np.arange(synth.SR * 2) / synth.SR * 2 * np.pi * 220)).astype(np.float32)
    s = S.from_array(np.stack([x, x], 1), synth.SR, origin="capture", title="Rec",
                     meta={"captured_at": "2026-10-12 10:00"})
    whole = payload.audio(s, stage)
    t = whole["tracks"][0]
    assert whole["kind"] == "audio" and t["role"] == "audio" and t["clips"] == [] and t["name"] == "Rec"
    assert t["audio_root"] == "user_library" and t["audio_path"] == "ClusterSound/Audio/Rec.wav"
    assert sf.info(t["audio_file"]).frames == synth.SR * 2 and t["seconds"] == 2.0
    assert "personal use" in open(t["audio_file"] + ".source.txt").read()

    region = payload.audio(s, stage, 1.5, 0.5, {"fade_in_ms": 0, "fade_out_ms": 0})
    r = region["tracks"][0]
    assert r["name"] == "Rec 0.50-1.50s" and abs(r["seconds"] - 1.0) < 1e-3
    assert payload.audio(s, stage)["tracks"][0]["name"] == "Rec (2)"  # never overwrites
    with pytest.raises(ValueError):
        payload.audio(s, stage, 3.0, 4.0)


def test_send_to_live_api(stage):

    from clustersound.api import Api
    from clustersound.live import server
    from clustersound.sampler import session as S
    a = object.__new__(Api)
    a._sampler = None
    a._live = server.Bridge(stage, _resolve, lambda r: None)
    a._settings = lambda: {}
    assert a.sampler_send_to_live()["error"] == "no audio open"
    a._sampler = S.from_array(np.zeros((synth.SR, 1), np.float32) + .1, synth.SR, title="Stem · Voce")
    r = a.sampler_send_to_live(0.2, 0.7)
    assert r["queued"] == 1 and r["tracks"] == ["Stem · Voce 0.20-0.70s"] and os.path.isfile(r["file"])
    item = a._live.next()
    assert item["kind"] == "audio" and item["tracks"][0]["audio_file"] == r["file"]


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
    lib_adg = Item("Kit Drum Rack.adg")
    library = [Item("Presets"), Item("ClusterSound", Item("rack", Item("Kit", lib_adg)))]  # User Library top folders
    assert proto.find_item(library + places, "ClusterSound/rack/Kit/Kit Drum Rack.adg") is lib_adg
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


def test_instrument_types_and_pools():
    proto = _protocol()

    class Item:
        def __init__(self, name, *children, folder=False, device=False, loadable=True):
            self.name, self.children = name, list(children)
            self.is_folder, self.is_device, self.is_loadable = folder, device, loadable and not folder

    bass = Item("Bass", *[Item(f"Bass {i:02d}.adg") for i in range(150)], folder=True)
    keys = Item("Piano & Keys", Item("Grand.adv"), Item("Sub", Item("Rhodes.adg"), folder=True), folder=True)
    pad = Item("Pad", Item("Warm Pad.adg"), Item("pad.wav"), folder=True)

    class Browser:
        sounds = Item("Sounds", bass, keys, pad, folder=True)
        drums = Item("Drums", Item("Kit-Core 909.adg"), Item("Kick Punchy.adv"),
                     Item("Drum Hits", Item("kick.wav"), folder=True), folder=True)
        instruments = Item("Instruments", Item("Operator", Item("Init.adv"), Item("Bell.adv"), device=True), folder=True)

    b = Browser()
    cats = proto.categories(b)
    assert cats == [("sounds:Bass", "Bass"), ("sounds:Piano & Keys", "Piano & Keys"), ("sounds:Pad", "Pad"),
                    (proto.DRUM_KITS, "Kit di batteria"), ("instruments:Operator", "Preset di Operator")]
    d = proto.defaults([k for k, _ in cats])
    assert d == {"chords": "sounds:Piano & Keys", "melody": "sounds:Piano & Keys", "bass": "sounds:Bass", "drums": proto.DRUM_KITS}
    assert proto.defaults(["sounds:Pad"])["chords"] == "sounds:Pad" and proto.defaults([])["bass"] is None
    assert len(proto.category_pool(b, "sounds:Bass")) == 150                       # every preset of the type
    assert [i.name for i, _ in proto.category_pool(b, "sounds:Piano & Keys")] == ["Grand.adv", "Rhodes.adg"]
    assert [i.name for i, _ in proto.category_pool(b, "sounds:Pad")] == ["Warm Pad.adg"]   # no audio
    assert [i.name for i, _ in proto.category_pool(b, proto.DRUM_KITS)] == ["Kit-Core 909.adg"]
    assert [i.name for i, _ in proto.category_pool(b, "instruments:Operator")] == ["Bell.adv", "Init.adv", "Operator"]
    assert proto.category_pool(b, "sounds:Nope") == [] and proto.category_pool(b, "bogus") == []
    assert proto.display_name("Warm Pad.adg") == "Warm Pad"


def test_bus_suggestions():
    proto = _protocol()

    class Item:
        def __init__(self, name, *children, folder=False):
            self.name, self.children, self.is_folder, self.is_device = name, list(children), folder, False
            self.is_loadable = not folder

    drums = [Item("909 Kit.adg"),
             Item("Drum Hits", Item("Kick", Item("Kick 808.wav"), Item("Deep.aif"), folder=True),
                  Item("Snare", Item("Snare Tight.wav"), folder=True),
                  Item("Hihat", Item("Closed Hat 1.wav"), Item("Open Hat 2.wav"), folder=True), folder=True),
             Item("Kick Punchy.adv")]
    names = lambda bus: sorted(i.name for i, _ in proto.collect_bus(drums, proto.BUS_WORDS[bus]))
    assert names("kick") == ["Deep.aif", "Kick 808.wav", "Kick Punchy.adv"]  # folder or own name; no kits
    assert names("snare") == ["Snare Tight.wav"]
    assert "Open Hat 2.wav" in names("ohat") and names("tom") == []
    assert proto.bus_of("bus:kick") == "kick" and proto.bus_of("bass") is None and proto.bus_of("bus:nope") is None


def _post(b, path, body):
    import json
    import urllib.error
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{b.port}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_bridge_receives_a_clip(bridge):
    assert bridge.last_clip() is None
    status, out = _post(bridge, "/live/clip", {"name": "Lead", "length": 4,
                                               "notes": [[72, 0, 1, 100], [74, 1, .5, 90], [300, 0, 1, 1], [60, 2, 0, 1]]})
    assert status == 200 and out == {"ok": True, "notes": 2}
    clip = bridge.last_clip()
    assert clip["name"] == "Lead" and clip["notes"] == [[72, 0.0, 1.0, 100], [74, 1.0, 0.5, 90]]
    assert _post(bridge, "/live/clip", {"notes": []})[0] == 400
    assert _post(bridge, "/live/nope", {})[0] == 404


def test_bridge_receives_a_clip_by_get(bridge):
    import json
    import urllib.parse
    data = urllib.parse.quote(json.dumps({"name": "Lead", "length": 4, "notes": [[72, 0, 1, 100]]}))
    assert _get(bridge, f"/live/clip?data={data}") == (200, {"ok": True, "notes": 1})
    assert bridge.last_clip()["notes"] == [[72, 0.0, 1.0, 100]]
    assert _get(bridge, "/live/clip?data=%7B%7D")[0] == 400
