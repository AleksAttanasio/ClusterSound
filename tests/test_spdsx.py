import pytest

from clustersound.racks import layouts, spdsx

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
