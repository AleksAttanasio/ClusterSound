import gzip
import os
import threading
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import soundfile as sf

from clustersound.racks import ableton, layouts, spdsx

from . import synth

TRIGGERS = [{"trig1": a, "trig2": b} for a in (True, False) for b in (True, False)]


def _rack(geometry="spd_kit", triggers=None, **kw):
    r = spdsx.new_rack()
    r.update(geometry=geometry, **kw)
    if triggers is not None:
        r["triggers"] = triggers
    return r


# ---------------------------------------------------------------- layout
@pytest.mark.parametrize("geometry", spdsx.GEOMETRIES)
@pytest.mark.parametrize("triggers", TRIGGERS)
def test_config_covers_active_pads_once(geometry, triggers):
    gs = spdsx.groups(geometry, triggers)
    flat = [p for g in gs for p in g]
    expected = list(range(9)) + [spdsx.TRIG1] * triggers["trig1"] + [spdsx.TRIG2] * triggers["trig2"]
    assert sorted(flat) == sorted(expected)
    assert len(spdsx.group_keys(geometry, triggers)) == len(set(spdsx.group_keys(geometry, triggers))) == len(gs)


def test_pedal_off_moves_kick_to_pad_8():
    on = dict(zip(spdsx.group_keys("spd_kit"), spdsx.groups("spd_kit")))
    assert on["t1"] == [spdsx.TRIG1] and spdsx.KICK_PAD in on["2"]
    off = {"trig1": False, "trig2": False}
    lay = {k: (pads, fam) for k, pads, fam in spdsx.layout("spd_kit", off)}
    assert lay["k"] == ([spdsx.KICK_PAD], "kick") and "t1" not in lay
    assert spdsx.KICK_PAD not in lay["2"][0]


def test_notes_are_spdsx_defaults():
    assert spdsx.NOTES == list(range(60, 71))
    r = _rack()
    assert [layouts.note_of(r, p) for p in range(spdsx.PADS)] == list(range(60, 71))
    assert layouts.note_of(layouts.new_rack(), 0) == 36


def test_validate_and_dispatch():
    r = layouts.validate({"device": "spdsx", "pads": [{"path": "/x.wav"}] * 20, "geometry": "nope"})
    assert len(r["pads"]) == 11 and r["geometry"] == "spd_kit" and r["triggers"] == {"trig1": True, "trig2": False}
    old = layouts.validate({"pads": [None] * 64})  # a kit saved before devices existed
    assert "device" not in old and len(old["pads"]) == 64 and old["geometry"] == "cols8"
    assert layouts.pad_count(r) == 11 and layouts.pad_count(old) == 64
    assert layouts.groups_of(old) == layouts.groups("cols8")


def test_group_settings_use_group_keys():
    r = _rack(groups={"spd_kit:t1": {"family": "808"}, "spd_kit:0": {"lock": True}})
    s = layouts.group_settings(r)
    keys = spdsx.group_keys("spd_kit")
    assert s[keys.index("t1")]["family"] == "808"
    assert s[0] == {"family": "hatscym", "choke": 0, "lock": True}


# ---------------------------------------------------------------- playability
@pytest.mark.parametrize("geometry", spdsx.GEOMETRIES)
@pytest.mark.parametrize("triggers", TRIGGERS)
def test_default_configs_are_playable(geometry, triggers):
    assert spdsx.playability(_rack(geometry, triggers)) == []


def test_random_configs_are_playable():
    for seed in range(200):
        t = TRIGGERS[seed % 4]
        cfg = spdsx.random_config(seed, t)
        r = _rack(cfg["geometry"], t, groups=cfg["groups"])
        assert spdsx.playability(r) == [], cfg
        fams = dict(zip(spdsx.group_keys(cfg["geometry"], t), [s["family"] for s in layouts.group_settings(r)]))
        assert fams.get("t1", "kick") == "kick" and fams.get("k", "kick") == "kick"
    assert spdsx.random_config(7) == spdsx.random_config(7)


def test_free_config_warns_on_too_many_kicks():
    kick = {"kind": "file", "path": "/k.wav", "name": "k", "cls": "kick"}
    r = _rack("spd_free", pads=[kick, kick] + [None] * 9)
    assert spdsx.playability(r) and "kick" in spdsx.playability(r)[0]   # 2 pads + the pedal
    r["triggers"] = {"trig1": False, "trig2": False}
    assert spdsx.playability(r) == []


def test_allowed_families():
    r = _rack("spd_kit")
    allowed = spdsx.allowed_families(r)
    keys = spdsx.group_keys("spd_kit")
    toms = allowed[keys.index("2")]      # 3 pads: a kick family would make 4 kicks with the pedal
    assert "kick" not in toms and "perc" in toms and "tom" in toms
    assert "snareclap" not in toms       # 6 snares
    t1 = allowed[keys.index("t1")]
    assert "kick" in t1 and "808" in t1


# ---------------------------------------------------------------- API
class _FakeLib:
    """Library stub: every class used by the SPD-SX families, two sub-clusters each, 6 one-shots per sub."""

    CLASSES = ["kick", "sub808", "snare", "clap", "snap", "rimshot", "closed_hat", "open_hat", "ride", "crash",
               "tom", "shaker", "tambourine", "perc_other", "cowbell", "hand_drum", "woodblock", "impact"]

    def __init__(self):
        rng = np.random.default_rng(0)
        self.items, rows = [], []
        for c, cls in enumerate(self.CLASSES):
            for sub in (1, 2):
                centre = rng.normal(size=16)
                for k in range(6):
                    i = len(self.items)
                    self.items.append({"id": i, "path": f"/lib/{cls}{sub}_{k}.wav", "rel": f"{cls}/{cls}{sub}_{k}.wav",
                                       "name": f"{cls}{sub}_{k}.wav", "cls": cls, "sub": sub, "conf": 0.9,
                                       "feats": {"type": "One-shot", "decay20": 0.1 + k / 50}, "info": {"duration": 0.3}})
                    rows.append(centre + 0.3 * rng.normal(size=16))
        self.emb = np.array(rows, np.float32)
        self.version = 1


@pytest.fixture()
def api():
    from clustersound.api import Api
    a = object.__new__(Api)
    a._lib = _FakeLib()
    a._rack_cache = {}
    a._rack_lock = threading.Lock()
    return a


def _sub(ref):
    return ref["cls"], ref["path"].rsplit("/", 1)[1][len(ref["cls"])]


@pytest.mark.parametrize("triggers", TRIGGERS)
def test_rack_generate(api, triggers):
    for seed in range(10):
        r = api.rack_generate(_rack(triggers=triggers), {"rng_seed": seed})
        assert r["device"] == "spdsx" and r["geometry"] in spdsx.GEOMETRIES
        assert spdsx.playability(r) == []
        active = spdsx.active_pads(r)
        assert all(r["pads"][p] for p in active)
        ids = [r["pads"][p]["id"] for p in active]
        assert len(ids) == len(set(ids))
        if triggers["trig1"]:
            assert r["pads"][spdsx.TRIG1]["cls"] == "kick"
        # every pad group is seeded from its own sample group (class + sub-cluster)
        seeds = [_sub(r["pads"][pads[0]]) for pads in layouts.groups_of(r)]
        assert len(seeds) == len(set(seeds))


def test_rack_generate_keeps_config_with_locked_group(api):
    r = _rack("spd_cols", groups={"spd_cols:1": {"lock": True}})
    out = api.rack_generate(r, {"rng_seed": 1})
    assert out["geometry"] == "spd_cols" and not any(out["pads"][p] for p in spdsx.groups("spd_cols")[1])


def test_rack_check(api):
    chk = api.rack_check(_rack())
    assert chk["warnings"] == [] and len(chk["allowed"]) == len(spdsx.groups("spd_kit"))
    assert api.rack_check(layouts.new_rack()) == {"warnings": [], "allowed": None}


def test_autofill_spd(api):
    r = api.rack_autofill(_rack("spd_rows", {"trig1": True, "trig2": True}))
    assert all(r["pads"][p] for p in range(spdsx.PADS))
    assert r["pads"][spdsx.TRIG1]["cls"] == "kick" and r["pads"][spdsx.TRIG2]["cls"] in ("ride", "crash")


# ---------------------------------------------------------------- export
def test_export_spdsx(tmp_path):
    rng = np.random.default_rng(3)
    refs = []
    for name, gen in [("kick", synth.kick), ("snare", synth.snare), ("chat", synth.closed_hat)]:
        p = tmp_path / f"{name}.wav"
        sf.write(p, gen(rng), 48000)
        refs.append({"kind": "file", "path": str(p), "name": p.name})
    kick, snare, chat = refs
    r = _rack("spd_kit", {"trig1": True, "trig2": False})
    r["name"] = "SPD Kit"
    r["pads"][spdsx.TRIG1] = kick
    r["pads"][4] = snare          # pad 5
    r["pads"][0] = chat           # pad 1
    r["pads"][spdsx.TRIG2] = snare  # trigger 2 is off: not exported
    out = tmp_path / "out"
    out.mkdir()
    folder = ableton.export_rack(r, str(out), lambda x: x["path"], lambda x: None)
    doc = ET.fromstring(gzip.open(os.path.join(folder, "SPD Kit SPD-SX Drum Rack.adg")).read())
    notes = sorted(128 - int(b.find("ZoneSettings/ReceivingNote").get("Value")) for b in doc.findall(".//DrumBranchPreset"))
    assert notes == [60, 64, 69]
    spd = sorted(os.listdir(os.path.join(folder, "SPD-SX")))
    assert spd == ["P1 - chat.wav", "P5 - snare.wav", "T1 Pedale - kick.wav"]
    for f in spd:
        info = sf.info(os.path.join(folder, "SPD-SX", f))
        assert info.samplerate == 44100 and info.subtype == "PCM_16"
    text = open(os.path.join(folder, "LEGGIMI.txt"), encoding="utf-8").read()
    assert "Wave Manager" in text and "Pedale (Trig 1) · A3: kick" in text and "Trig 2 · A#3: non collegato" in text


def test_rimshots_in_a_rim_group_are_not_snares():
    rim = {"kind": "file", "path": "/r.wav", "name": "r", "cls": "rimshot"}
    r = _rack("spd_cross", groups={"spd_cross:1": {"family": "rim"}})
    for p in spdsx.groups("spd_cross")[1]:
        r["pads"][p] = rim
    assert spdsx.playability(r) == []


def test_allowed_families_on_a_kit_over_the_caps():
    snare = {"kind": "file", "path": "/s.wav", "name": "s", "cls": "snare"}
    r = _rack("spd_free", pads=[snare] * 4 + [None] * 7)   # 4 snares: over the cap
    allowed = spdsx.allowed_families(r)
    assert "tom" in allowed[5] and "snare" not in allowed[5]   # an empty pad may not add a 5th snare
    assert "snare" in allowed[0]                              # a snare pad may stay a snare
