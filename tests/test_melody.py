from clustersound.chords import export, melody, perform
from clustersound.live import payload
from clustersound.patterns.midi import read_note_spans

from .test_chords import C_MAJ, _clip, _pack


def _mel(*notes):
    """notes: (start, len, pitch) in sixteenths."""
    return {"notes": [{"id": f"n{i}", "start": s, "len": ln, "pitch": p, "vel": 100} for i, (s, ln, p) in enumerate(notes)]}


def _by_name(lib):
    return {c["name"]: c for c in lib.chords_for_key(0, "major")["chords"]}


def test_render_applies_swing_and_cuts_at_the_end():
    seq = {"bars": 1, "melody": _mel((0, 2, 72), (1, 1, 74), (14, 8, 76)),
           "mode": {"swing": 75, "rhythm": {}, "play": {}}}
    ev = melody.render(seq)
    assert ev[0] == (0, 240, 72, 100)
    assert ev[1][0] > perform.STEP  # odd sixteenth delayed
    assert ev[2][1] == perform.BAR  # cut at the sequence length


def test_from_spans_quantises_and_keeps_the_top_line():
    ppq = 96
    spans = [(1922 * ppq // 480, 2400 * ppq // 480, 60, 90), (1920 * ppq // 480, 2400 * ppq // 480, 67, 100),
             (2390 * ppq // 480, 2880 * ppq // 480, 65, 80)]
    out = melody.from_spans(spans, ppq)
    assert [(n["start"], n["len"], n["pitch"]) for n in out] == [(0, 4, 67), (4, 4, 65)]  # moved to bar 1


def test_detect_key():
    notes = _mel((0, 4, 69), (4, 4, 72), (8, 4, 76), (12, 4, 74), (16, 4, 71), (20, 4, 68), (24, 8, 69))["notes"]
    assert melody.detect_key(notes) == {"tonic": 9, "mode": "minor"}
    notes = _mel((0, 4, 60), (4, 4, 64), (8, 4, 67), (12, 4, 65), (16, 4, 62), (20, 4, 59), (24, 8, 60))["notes"]
    assert melody.detect_key(notes) == {"tonic": 0, "mode": "major"}


def test_harmonize_c_major_melody(tmp_path):
    lib = _pack(tmp_path)
    pool = lib.chords_for_key(0, "major")["chords"]
    seq = {"bars": 4, "key": C_MAJ, "clips": [],
           "melody": _mel((0, 4, 72), (4, 4, 76), (8, 8, 79),      # C E G
                          (16, 8, 77), (24, 8, 81),                # F A
                          (32, 4, 79), (36, 4, 83), (40, 8, 74),   # G B D
                          (48, 16, 72))}                           # C
    out = melody.harmonize(seq, pool, C_MAJ, lib.bigrams("major"), {"rate": "bar"}, seed=3)
    assert out
    first = out[0]["seq"]["clips"]
    assert [c["degree"] for c in first] == ["I", "IV", "V", "I"]
    for c in first:  # the chord holds the melody note on its downbeat, below the melody
        down = next(n for n in seq["melody"]["notes"] if n["start"] == c["start"])
        assert down["pitch"] % 12 in {p % 12 for p, _ in c["notes"]}
        assert max(p for p, _ in c["notes"]) <= down["pitch"]
    assert len({tuple(c["degree"] for c in o["seq"]["clips"]) for o in out}) == len(out)
    assert out[0]["seq"]["melody"] == seq["melody"]


def test_harmonize_merges_repeated_chords(tmp_path):
    lib = _pack(tmp_path)
    pool = lib.chords_for_key(0, "major")["chords"]
    seq = {"bars": 2, "key": C_MAJ, "clips": [], "melody": _mel((0, 16, 72), (16, 16, 76))}
    clips = melody.harmonize(seq, pool, C_MAJ, lib.bigrams("major"), {"rate": "half"}, seed=1)[0]["seq"]["clips"]
    assert sum(c["len"] for c in clips) == 32
    assert all(a["start"] + a["len"] == b["start"] for a, b in zip(clips, clips[1:]))


def test_generate_follows_the_chords(tmp_path):
    ch = _by_name(_pack(tmp_path))
    seq = {"bars": 4, "key": C_MAJ, "clips": [_clip(ch["C Maj"], 0), _clip(ch["F Maj"], 16), _clip(ch["G Maj"], 32),
                                               _clip(ch["C Maj"], 48)]}
    cmap = melody._chord_map(seq)
    a = melody.generate(seq, C_MAJ, {"density": "mid", "contour": "arch", "lo": 60, "hi": 84}, seed=7)
    b = melody.generate(seq, C_MAJ, {"density": "mid", "contour": "arch", "lo": 60, "hi": 84}, seed=7)
    assert a == [] or [x["melody"]["notes"][0]["pitch"] for x in a] == [x["melody"]["notes"][0]["pitch"] for x in b]
    assert len(a) == 4
    for item in a:
        notes = item["melody"]["notes"]
        assert all(60 <= n["pitch"] <= 84 for n in notes)
        assert all(x["start"] + x["len"] <= y["start"] for x, y in zip(notes, notes[1:]))  # one voice
        for n in notes:
            if n["start"] % 4 == 0:
                assert n["pitch"] % 12 in cmap[n["start"]]["pcs"]


def test_generate_keeps_notes_outside_the_range(tmp_path):
    ch = _by_name(_pack(tmp_path))
    seq = {"bars": 2, "key": C_MAJ, "clips": [_clip(ch["C Maj"], 0), _clip(ch["G Maj"], 16)],
           "melody": _mel((0, 16, 72))}
    out = melody.generate(seq, C_MAJ, {"fromBar": 1, "toBar": 2}, seed=2)
    for item in out:
        notes = item["melody"]["notes"]
        assert notes[0] == seq["melody"]["notes"][0]
        assert all(n["start"] >= 16 for n in notes[1:])


def test_export_two_tracks(tmp_path):
    seq = {"bars": 1, "bpm": 100, "clips": [{"id": "a", "notes": [[60, 100], [64, 100]], "root": 0, "start": 0, "len": 16}],
           "melody": _mel((0, 4, 72), (4, 4, 74))}
    path = tmp_path / "x.mid"
    export.write(str(path), seq)
    data = path.read_bytes()
    assert data[8:10] == b"\x00\x01" and data.count(b"MTrk") == 2
    _, spans = read_note_spans(str(path))
    assert {p for _, _, p, _ in spans} == {60, 64, 72, 74}
    export.write(str(path), seq, parts="melody")
    data = path.read_bytes()
    assert data[8:10] == b"\x00\x00" and data.count(b"MTrk") == 1
    assert {p for _, _, p, _ in read_note_spans(str(path))[1]} == {72, 74}
    export.write(str(path), {**seq, "melody": {"notes": []}})
    assert path.read_bytes().count(b"MTrk") == 1


def test_live_payload_melody_track():
    a = {"bars": 1, "clips": [{"id": "a", "notes": [[60, 100]], "root": 0, "start": 0, "len": 16}],
         "melody": _mel((0, 4, 72))}
    b = {"bars": 1, "clips": a["clips"], "melody": {"notes": []}}
    out = payload.compose({"name": "P", "bpm": 90, "order": ["A", "B"], "versions": {"A": a, "B": b}})
    assert [t["role"] for t in out["tracks"]] == ["chords", "melody"]
    mel = out["tracks"][1]["clips"]
    assert mel[0]["notes"] == [[72, 0.0, 1.0, 100]] and mel[1]["notes"] == []
    out = payload.compose({"name": "P", "bpm": 90, "order": ["B"], "versions": {"B": b}})
    assert len(out["tracks"]) == 1


def test_recorder_feed_and_ticks():
    from clustersound.chords import midi_in
    r = midi_in.Recorder()
    r.feed([0x90, 72, 100], 1.0)
    r.feed([0x90, 76, 90], 1.5)
    r.feed([0x80, 72, 0], 1.5)
    r.feed([0x90, 76, 0], 2.0)
    r.feed([0x90, 79, 80], 2.9)  # held when stopped
    notes = r.stop()
    assert notes[:2] == [(1.0, 1.5, 72, 100), (1.5, 2.0, 76, 90)] and notes[2][2] == 79
    # 120 bpm: one beat = .5 s; the transport started 1 s after the recorder
    ticks = midi_in.to_ticks(notes[:2], 1.0, 120, 480)
    assert ticks == [(0, 480, 72, 100), (480, 960, 76, 90)]
    out = melody.from_spans(ticks + [(1920 * 2, 1920 * 2 + 480, 74, 80)], 480, keep=True)
    assert [(n["start"], n["len"], n["pitch"]) for n in out] == [(0, 4, 72), (4, 4, 76), (32, 4, 74)]
    looped = midi_in.to_ticks([(1.0 + 2.0, 1.5 + 2.0, 72, 100)], 1.0, 120, 480, length_ticks=1920)
    assert looped == [(0, 480, 72, 100)]
