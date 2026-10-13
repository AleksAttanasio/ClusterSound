import os
import struct

import pytest

from clustersound.chords import export, harmony, perform, theory, variations
from clustersound.chords.library import DEFAULT_DIR, ChordLibrary
from clustersound.patterns.midi import _track, read_note_spans, read_notes

C_MAJ = {"tonic": 0, "mode": "major"}


def _write_mid(path, chords, ppq=480, bar=1920):
    """chords: list of pitch lists, one bar each."""
    ev = []
    for i, ch in enumerate(chords):
        for p in ch:
            ev.append((i * bar, bytes([0x90, p, 100])))
            ev.append(((i + 1) * bar, bytes([0x80, p, 0])))
    data = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + _track("x", ev, None, len(chords) * bar)
    path.write_bytes(data)


def _pack(tmp_path):
    root = tmp_path / "pack"
    key = root / "01 - C Major - A Minor"
    tri = key / "1 Triads" / "01 - C Major"
    ext = key / "2 Extended Chords" / "01 - C Major"
    bor = key / "3 Borrowed & Modal Chords" / "01 - C Major"
    prog = key / "4 Progressions" / "1 Diatonic Triads" / "Major Progressions"
    for d in (tri, ext, bor, prog):
        d.mkdir(parents=True)
    _write_mid(tri / "I - C Maj.mid", [[48, 55, 60, 64]])
    _write_mid(tri / "IV - F Maj.mid", [[53, 57, 60, 65]])
    _write_mid(tri / "V - G Maj.mid", [[43, 55, 59, 62]])
    _write_mid(tri / "vi - A min.mid", [[45, 57, 60, 64]])
    _write_mid(tri / "ii - D min.mid", [[50, 57, 62, 65]])
    _write_mid(tri / "VII - G;B.mid", [[47, 55, 59, 62]])
    _write_mid(ext / "I - Cmaj9.mid", [[48, 55, 59, 62, 64]])
    _write_mid(ext / "V - G7.mid", [[43, 53, 59, 62]])
    _write_mid(bor / " bVII - Bb9(#11).mid", [[34, 50, 56, 60, 64]])
    _write_mid(bor / "iv - FmAdd9.mid", [[41, 48, 56, 60, 67]])
    _write_mid(prog / "Major Prog 1 (I-V-vi-IV).mid", [[48, 55, 60, 64], [43, 55, 59, 62], [45, 57, 60, 64], [53, 57, 60, 65]])
    return ChordLibrary(str(root))


def _clip(ch, start=0, ln=16, **kw):
    return {"id": f"c{start}", "chordId": ch["id"], "name": ch["name"], "root": ch["root"], "quality": ch["quality"],
            "notes": ch["notes"], "start": start, "len": ln, "vel": 100, **kw}


# ------------------------------------------------------------------ theory / parsing
def test_degree_parsing():
    assert theory.parse_degree("bVII", "major") == (10, False)
    assert theory.parse_degree("iv", "major") == (5, True)
    assert theory.parse_degree("Vsus", "major") == (7, False)
    assert theory.parse_degree("bvii", "minor") == (9, True)
    assert theory.parse_degree("III", "minor") == (3, False)
    assert theory.parse_degree("Prog", "major") is None


def test_names_and_quality():
    assert theory.name_root("Bb9(#11)") == 10
    assert theory.name_root("G;B") == 7
    assert theory.transpose_name("G;B", 2, False) == "A;C#"
    assert theory.transpose_name("Gmaj6Add9", 1, True) == "Abmaj6Add9"  # the A of "Add" is not a note
    assert theory.quality({0, 4, 7}, 0) == "maj"
    assert theory.quality({7, 11, 2, 5}, 7) == "dom"
    assert theory.quality({11, 2, 5, 9}, 11) == "dim"
    assert theory.degree_label(10, "maj", 0, "major") == "bVII"
    assert theory.function(7, "dom", {7, 11, 2, 5}, 0, "major") == "D"
    assert theory.function(8, "maj", {8, 0, 3}, 0, "major") == "C"


def test_library_scan_and_split(tmp_path):
    lib = _pack(tmp_path)
    data = lib.chords_for_key(0, "major")
    names = {c["name"]: c for c in data["chords"]}
    assert {"C Maj", "G/B", "Bb9(#11)", "FmAdd9"} <= set(names)
    assert names["G/B"]["root"] == 7 and names["G/B"]["degree"] == "V"
    assert names["Bb9(#11)"]["category"] == "borrowed" and names["Bb9(#11)"]["func"] == "C"
    prog = data["progressions"][0]
    assert [c["degree"] for c in prog["chords"]] == ["I", "V", "vi", "IV"]
    assert [(c["start"], c["len"]) for c in prog["chords"]] == [(0, 16), (16, 16), (32, 16), (48, 16)]
    big = lib.bigrams("major")
    assert big[((0, False), (7, False))] == 1 and big[((5, False), (0, False))] == .5  # loop back IV -> I


def test_missing_key_is_transposed(tmp_path):
    lib = _pack(tmp_path)
    d = lib.chords_for_key(2, "major")  # D major is not in the pack
    assert d["transposed"] == 2
    c = next(x for x in d["chords"] if x["degree"] == "I" and len(x["notes"]) == 4)
    assert c["name"] == "D Maj" and [n for n, _ in c["notes"]] == [50, 57, 62, 66]


# ------------------------------------------------------------------ suggestions
def test_suggest_after_dominant(tmp_path):
    lib = _pack(tmp_path)
    pool = lib.chords_for_key(0, "major")["chords"]
    g = next(c for c in pool if c["name"] == "G Maj")
    out = harmony.suggest([_clip(g)], pool, C_MAJ, lib.bigrams("major"))
    assert out[0]["degree"] in ("I", "vi")
    assert any("cadence" in r for r in out[0]["reasons"])
    assert out[0]["score"] == 1.0 and all(0 < r["score"] <= 1 for r in out)
    assert len({(r["chord"]["root"], r["degree"]) for r in out}) == len(out)  # one entry per chord


def test_voice_leading_rewards_common_tones():
    c = [48, 55, 60, 64]
    assert harmony.voice_distance(c, [45, 57, 60, 64]) < harmony.voice_distance(c, [42, 54, 61, 66])


# ------------------------------------------------------------------ performance
SEQ = {"bpm": 120, "bars": 1}
CMAJ = [[48, 100], [55, 100], [60, 100], [64, 100]]


def _perf(style, ln=16, **kw):
    clip = {"id": "x", "notes": CMAJ, "start": 0, "len": ln, "style": style, **kw}
    return perform.perform(clip, SEQ)


def test_block_and_voicing():
    ev = _perf(None)
    assert [(s, e) for s, e, _, _ in ev] == [(0, 1920)] * 4
    assert [p for p, _ in perform.voicing({"notes": CMAJ, "inversion": 1})] == [55, 60, 64, 72]
    assert [p for p, _ in perform.voicing({"notes": CMAJ, "inversion": -1, "transpose": 2})] == [42, 50, 57, 62]


def test_strum_order_and_spread():
    ev = _perf({"type": "strum", "strum": {"dir": "up", "spread": 20}})
    tpm = 480 * 120 / 60000
    starts = sorted((s, p) for s, _, p, _ in ev)
    assert [p for _, p in starts] == [48, 55, 60, 64]
    assert starts[1][0] - starts[0][0] == round(20 * tpm)
    down = _perf({"type": "strum", "strum": {"dir": "down", "spread": 20}})
    assert min(down)[2] == 64


def test_arpeggio_eighths():
    ev = _perf({"type": "arp", "arp": {"mode": "up", "rate": "1/8", "octaves": 1}})
    assert len(ev) == 8 and [s for s, *_ in ev] == list(range(0, 1920, 240))
    assert [p for _, _, p, _ in ev[:5]] == [48, 55, 60, 64, 48]


def test_rhythm_offbeat_and_end():
    ev = _perf({"type": "rhythm", "rhythm": {"pattern": "offbeat", "hit": "block"}})
    assert sorted({s for s, *_ in ev}) == [240, 720, 1200, 1680]
    assert max(e for _, e, _, _ in ev) <= 1920


def test_humanize_deterministic_and_bounded():
    st = {"type": "rhythm", "rhythm": {"pattern": "eighths"}, "humanize": {"timing": 15, "vel": 12, "seed": 9}}
    a, b = _perf(st), _perf(st)
    assert a == b
    assert a != _perf({**st, "humanize": {"timing": 15, "vel": 12, "seed": 10}})
    tpm = 480 * 120 / 60000
    plain = _perf({**st, "humanize": {"timing": 0, "vel": 0}})
    assert len(a) == len(plain)
    for (s, _, _, v), (s0, _, _, v0) in zip(sorted(a, key=lambda e: (e[2], e[0])), sorted(plain, key=lambda e: (e[2], e[0]))):
        assert abs(s - s0) <= 15 * tpm + 1 and abs(v - v0) <= 12 + 1
    assert all(0 <= s and e <= 1920 for s, e, _, _ in a)


def test_alternate_styles_per_bar():
    ev = _perf({"type": "block", "alternate": {"every": "bar", "tokens": ["block", "arp"]}}, ln=32)
    bar1 = [e for e in ev if e[0] < 1920]
    bar2 = [e for e in ev if e[0] >= 1920]
    assert len({s for s, *_ in bar1}) == 1 and len({s for s, *_ in bar2}) == 8


def test_clip_never_spills():
    clip = {"id": "y", "notes": CMAJ, "start": 4, "len": 6, "style": {"type": "arp", "arp": {"rate": "1/16"}, "humanize": {"timing": 30, "seed": 3}}}
    ev = perform.perform(clip, SEQ)
    assert all(480 <= s < e <= 1200 for s, e, _, _ in ev)


# ------------------------------------------------------------------ variations
def _seq(lib):
    pool = lib.chords_for_key(0, "major")["chords"]
    by = {c["name"]: c for c in pool}
    clips = [_clip(by[n], i * 16) for i, n in enumerate(["C Maj", "A min", "F Maj", "G Maj"])]
    return {"bpm": 100, "bars": 4, "key": C_MAJ, "clips": clips}, pool


def test_clip_variations(tmp_path):
    lib = _pack(tmp_path)
    seq, pool = _seq(lib)
    kinds = [k for k, _ in variations.CLIP_KINDS]  # playing style lives in the Modalità: see test_mode_variations
    a = variations.vary_clip(seq, "c16", kinds, 4, pool, C_MAJ, lib.bigrams("major"))
    assert a == variations.vary_clip(seq, "c16", kinds, 4, pool, C_MAJ, lib.bigrams("major"))
    assert {"voicing", "substitute"} <= {v["kind"] for v in a} <= set(kinds)
    ids = {c["id"] for c in pool}
    for v in a:
        assert v["clip"]["start"] == 16 and v["clip"]["len"] == 16
        if v["kind"] == "substitute":
            assert v["clip"]["chordId"] in ids and v["clip"]["root"] != 9


def test_mode_variations():
    base = perform.mode_of({"mode": perform.DEFAULT_MODE})
    kinds = [k for k, _ in variations.MODE_KINDS]
    a = variations.vary_mode(base, kinds, 0.5, 3)
    assert a == variations.vary_mode(base, kinds, 0.5, 3)
    assert 0 < len(a) <= 4 and all(v["kind"] in kinds for v in a)
    assert all(v["mode"] != base for v in a) and len({repr(v["mode"]) for v in a}) == len(a)


def test_progression_variations(tmp_path):
    lib = _pack(tmp_path)
    seq, pool = _seq(lib)
    big = lib.bigrams("major")
    kinds = ["reharm", "rhythm", "voicing", "richer", "performance", "ending"]
    out = variations.vary_progression(seq, kinds, .5, 11, pool, C_MAJ, big, count=6)
    assert out and out == variations.vary_progression(seq, kinds, .5, 11, pool, C_MAJ, big, count=6)
    ids = {c["id"] for c in pool}
    for v in out:
        clips = sorted(v["seq"]["clips"], key=lambda c: c["start"])
        assert v["label"]
        assert clips[0]["start"] == 0 and clips[-1]["start"] + clips[-1]["len"] == 64  # same total length
        for a, b in zip(clips, clips[1:]):
            assert a["start"] + a["len"] == b["start"]  # no gaps, no overlaps
        if v["kind"] == "reharm":
            assert clips[0]["chordId"] == seq["clips"][0]["chordId"] and clips[-1]["chordId"] == seq["clips"][-1]["chordId"]
        assert all(c["chordId"] in ids for c in clips)


def test_revoice_does_not_move_more(tmp_path):
    lib = _pack(tmp_path)
    seq, pool = _seq(lib)
    out = variations.vary_progression(seq, ["voicing"], .5, 1, pool, C_MAJ, lib.bigrams("major"), count=1)

    def moves(clips):
        ps = [[p for p, _ in perform.voicing(c)] for c in sorted(clips, key=lambda c: c["start"])]
        return sum(harmony.voice_distance(a, b) for a, b in zip(ps, ps[1:]))

    if out:
        assert moves(out[0]["seq"]["clips"]) <= moves(seq["clips"]) + 1e-9


# ------------------------------------------------------------------ export
def test_export_roundtrip(tmp_path):
    seq = {"name": "Test", "bpm": 90, "bars": 3, "clips": [
        {"id": "a", "notes": CMAJ, "start": 0, "len": 16, "transpose": 2},
        {"id": "b", "notes": CMAJ, "start": 16, "len": 8, "style": {"type": "arp", "arp": {"rate": "1/4"}}},
    ]}
    path = tmp_path / "p.mid"
    export.write(str(path), seq)
    ppq, spans = read_note_spans(str(path))
    assert ppq == 480
    first = [s for s in spans if s[0] == 0]
    assert sorted(p for _, _, p, _ in first) == [50, 57, 62, 66] and all(e == 1920 for _, e, _, _ in first)
    arp = [s for s in spans if s[0] >= 1920]
    assert [s for s, *_ in arp] == [1920, 2400]
    data = path.read_bytes()
    assert b"\xff\x51\x03" + int(round(60_000_000 / 90)).to_bytes(3, "big") in data
    pure = tmp_path / "pure.mid"
    export.write(str(pure), seq, pure=True)
    assert len(read_notes(str(pure))) == 8


@pytest.mark.skipif(not os.path.isdir(DEFAULT_DIR), reason="Unison MIDI Chord Pack not installed")
def test_real_pack():
    lib = ChordLibrary()
    keys = lib.available_keys()
    assert len(keys) >= 10
    for tonic in range(12):
        d = lib.chords_for_key(tonic, "major")
        assert d["chords"] and d["progressions"]
        assert any(c["degree"] == "I" for c in d["chords"])
