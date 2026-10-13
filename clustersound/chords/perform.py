"""How a chord progression is played: the "Mode" (a rhythm grid + a way of playing every strike) and the
per-chord overrides.

    mode = {"name", "swing": 50..75,
            "rhythm": {"on", "bars", "vel": [0..127 per step], "len": [0 = until the next strike | steps],
                       "dir": ["" | "d" | "u" per step], "preset"},
            "play": {"type": block|strum|arp, "gate", "strum": {…}, "arp": {…}, "velCurve",
                     "humanize": {…}, "alternate": {…}}}
    clip["style"] = None | {"play": {partial play}, "rhythm": "inherit" | "sustain" | grid}

perform() is the single source of truth: the Compose preview plays exactly the events rendered here, and
the MIDI export writes the same ones. Times are ticks at PPQ 480; clip start/len are in sixteenths.
"""
import copy
import math
import zlib

from ..i18n import N_
from ..patterns.model import alt_hash

PPQ = 480
STEP = PPQ // 4
BAR = PPQ * 4
MIN_LEN = 12  # ticks: shorter notes are dropped
RATES = {"1/4": 480, "1/8": 240, "1/16": 120, "1/8t": 160, "1/16t": 80}
STRUM_UNITS = {"ms": None, "1/128": 15, "1/64": 30, "1/32": 60, "1/16t": 80}


def _bar(hits, bars=1):
    """hits: (step, len, vel, dir) -> grid arrays for `bars` bars."""
    n = bars * 16
    g = {"vel": [0] * n, "len": [0] * n, "dir": [""] * n}
    for s, ln, v, d in hits:
        g["vel"][s], g["len"][s], g["dir"][s] = v, ln, d
    return g


# rhythm presets: label, bars, strikes (step, length in steps or 0 = until the next one, velocity, strum dir)
RHYTHM_PRESETS = {
    "quarters": (N_("Quarter notes"), 1, [(0, 0, 100, ""), (4, 0, 80, ""), (8, 0, 92, ""), (12, 0, 80, "")]),
    "eighths": (N_("Eighth notes"), 1, [(i * 2, 0, 100 if i % 2 == 0 else 78, "") for i in range(8)]),
    "offbeat": ("Offbeat / skank", 1, [(2, 2, 95, "u"), (6, 2, 85, "u"), (10, 2, 95, "u"), (14, 2, 85, "u")]),
    "charleston": ("Charleston", 1, [(0, 3, 100, ""), (6, 2, 85, "")]),
    "tresillo": ("Tresillo 3-3-2", 1, [(0, 3, 100, ""), (3, 3, 85, ""), (6, 2, 90, ""), (8, 3, 95, ""), (11, 3, 85, ""), (14, 2, 90, "")]),
    "syncopated": (N_("Syncopated house"), 1, [(0, 3, 100, ""), (3, 3, 82, ""), (6, 4, 90, ""), (10, 2, 80, ""), (12, 4, 88, "")]),
    "half": (N_("Half notes"), 1, [(0, 8, 100, ""), (8, 8, 85, "")]),
    "pulse": ("Pulse 1/16", 1, [(i, 1, 100 if i % 4 == 0 else 70 if i % 2 == 0 else 58, "") for i in range(16)]),
    "pop": (N_("Pop guitar D-DU-UDU"), 1, [(0, 0, 110, "d"), (4, 0, 90, "d"), (6, 0, 75, "u"), (10, 0, 80, "u"), (12, 0, 95, "d"), (14, 0, 75, "u")]),
    "folk": (N_("Folk guitar D-D-DU-DU"), 1, [(0, 0, 110, "d"), (4, 0, 90, "d"), (8, 0, 100, "d"), (10, 0, 72, "u"), (12, 0, 92, "d"), (14, 0, 72, "u")]),
    "reggae": (N_("Reggae (chop on 2 and 4)"), 1, [(4, 1, 105, "u"), (12, 1, 105, "u")]),
    "funk": (N_("Sixteenth-note funk"), 1, [(0, 1, 112, "d"), (1, 1, 40, "u"), (2, 1, 60, "d"), (3, 1, 100, "u"), (5, 1, 90, "u"),
                                      (6, 1, 45, "d"), (8, 1, 110, "d"), (9, 1, 40, "u"), (11, 1, 95, "u"), (12, 1, 60, "d"),
                                      (14, 1, 90, "d"), (15, 1, 45, "u")]),
    "ballad": ("Ballad", 1, [(0, 8, 105, "d"), (8, 4, 85, "d"), (12, 4, 78, "u")]),
    "bossa": (N_("Bossa nova (2 bars)"), 2, [(0, 2, 100, ""), (3, 2, 85, ""), (6, 3, 90, ""), (10, 2, 85, ""), (13, 3, 90, ""),
                                           (18, 3, 85, ""), (22, 2, 90, ""), (24, 2, 95, ""), (28, 3, 85, "")]),
}


def preset_grid(pid: str) -> dict:
    label, bars, hits = RHYTHM_PRESETS.get(pid, RHYTHM_PRESETS["quarters"])
    return {"on": True, "bars": bars, "preset": pid, **_bar(hits, bars)}


PLAY_TYPES = [("block", "Block"), ("strum", "Strum"), ("arp", "Arpeggio")]
TOKENS = [("block", "Block"), ("strum_up", N_("Strum from the bottom")), ("strum_down", N_("Strum from the top")), ("arp", "Arp")]
DEFAULT_PLAY = {
    "type": "block",
    "gate": 1.0,
    # dir: up = from the lowest note (a guitar downstroke), down = from the top; guitar = downstrokes on the
    # beat, upstrokes in between; grid = the arrows of the rhythm grid; alt = alternate on every strike
    "strum": {"dir": "guitar", "spread": 25, "unit": "ms", "curve": "linear", "upNotes": 0, "velTilt": 0, "upSoft": 0},
    "arp": {"mode": "up", "rate": "1/8", "octaves": 1},
    "velCurve": "flat",
    "humanize": {"timing": 0, "spread": 0, "feel": 0, "drift": 0, "vel": 0, "len": 0, "accent": 0, "seed": 1},
    "alternate": {"every": "off", "tokens": []},
}
DEFAULT_RHYTHM = {"on": False, "bars": 1, "preset": None, **_bar([], 1)}
DEFAULT_MODE = {"name": N_("Mode 1"), "swing": 50, "rhythm": DEFAULT_RHYTHM, "play": DEFAULT_PLAY}


def meta() -> dict:
    return {"types": PLAY_TYPES, "tokens": TOKENS, "rates": list(RATES), "strumUnits": list(STRUM_UNITS),
            "presets": [(k, v[0], v[1]) for k, v in RHYTHM_PRESETS.items()],
            "presetGrids": {k: preset_grid(k) for k in RHYTHM_PRESETS},
            "arpModes": [("up", N_("Up")), ("down", N_("Down")), ("updown", N_("Up-down")), ("random", N_("Random"))],
            "strumDirs": [("guitar", N_("Guitar (down on the beat, up off the beat)")), ("grid", N_("Rhythm grid arrows")),
                          ("up", N_("Always from the bottom")), ("down", N_("Always from the top")), ("alt", N_("Alternate"))],
            "strumCurves": [("linear", N_("Even")), ("accel", N_("Speeds up")), ("decel", N_("Slows down"))],
            "velCurves": [("flat", N_("Flat")), ("cresc", "Crescendo"), ("decresc", "Decrescendo"), ("bass", N_("Bass accent"))],
            "defaultMode": DEFAULT_MODE, "defaultPlay": DEFAULT_PLAY}


def _merge(base: dict, over: dict | None) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        elif v is not None:
            out[k] = copy.deepcopy(v)
    return out


def _grid(r: dict | None) -> dict:
    """Normalised grid: arrays exactly bars*16 long."""
    g = _merge(DEFAULT_RHYTHM, r)
    g["bars"] = max(1, min(8, int(g.get("bars") or 1)))
    n = g["bars"] * 16
    for k, fill in (("vel", 0), ("len", 0), ("dir", "")):
        a = list(g.get(k) or [])
        g[k] = (a + [fill] * n)[:n]
    g["vel"] = [max(0, min(127, int(v or 0))) for v in g["vel"]]
    g["len"] = [max(0, int(v or 0)) for v in g["len"]]
    return g


# ------------------------------------------------------------------ legacy (Compose v1) styles
def _legacy_style(st: dict) -> tuple[dict, dict | str]:
    """v1 style {type: block|strum|arp|rhythm, rhythm: {pattern, hit}, …} -> (play, rhythm)."""
    play = {k: copy.deepcopy(v) for k, v in st.items() if k in DEFAULT_PLAY and k != "type"}
    play["type"] = st.get("type", "block")
    rhythm: dict | str = "sustain"
    if play["type"] == "rhythm":
        r = st.get("rhythm") or {}
        rhythm = preset_grid(r.get("pattern", "quarters"))
        play["type"] = "strum" if r.get("hit") == "strum" else "block"
    if play["type"] == "strum" or (st.get("rhythm") or {}).get("hit") == "strum":
        play["strum"] = {"dir": "up", **(play.get("strum") or {})}  # v1 default: from the lowest note
    alt = play.get("alternate") or {}
    if alt.get("tokens"):
        alt["tokens"] = ["block" if t == "rhythm" else t for t in alt["tokens"]]
    return play, rhythm


def mode_of(seq: dict) -> dict:
    """The Mode of a sequence (v1 sequences: built from defaultStyle)."""
    if seq.get("mode"):
        m = _merge(DEFAULT_MODE, seq["mode"])
    else:
        m = copy.deepcopy(DEFAULT_MODE)
        if seq.get("defaultStyle"):
            play, rhythm = _legacy_style(seq["defaultStyle"])
            m["play"] = _merge(DEFAULT_PLAY, play)
            if isinstance(rhythm, dict):
                m["rhythm"] = rhythm
    m["rhythm"] = _grid(m["rhythm"])
    m["swing"] = max(50, min(75, float(m.get("swing", 50) or 50)))
    return m


def clip_override(clip: dict) -> dict | None:
    """{play, rhythm} override of a clip (v1 clip styles converted: they keep sounding as before)."""
    st = clip.get("style")
    if not st:
        return None
    if "type" in st and "play" not in st:
        play, rhythm = _legacy_style(st)
        return {"play": play, "rhythm": rhythm}
    return {"play": st.get("play"), "rhythm": st.get("rhythm", "inherit")}


def effective(clip: dict, seq: dict, mode: dict | None = None) -> tuple[dict, dict | None]:
    """(play, grid or None for a sustained chord) of a clip."""
    mode = mode or mode_of(seq)
    ov = clip_override(clip) or {}
    play = _merge(mode["play"], ov.get("play"))
    r = ov.get("rhythm", "inherit")
    if r == "sustain":
        grid = None
    elif isinstance(r, dict):
        grid = _grid(r) if r.get("on", True) else None
    else:
        grid = mode["rhythm"] if mode["rhythm"]["on"] and any(mode["rhythm"]["vel"]) else None
    return play, grid


# ------------------------------------------------------------------ helpers
def voicing(clip: dict) -> list[list[int]]:
    """[[pitch, vel]] after inversion, octave and transposition (applied before the playing style)."""
    notes = sorted([int(n), int(v)] for n, v in clip.get("notes", []))
    if not notes:
        return []
    inv = int(clip.get("inversion", 0) or 0)
    for _ in range(min(abs(inv), 12)):  # rotate: the lowest note goes above the top one (or vice versa)
        if inv > 0:
            n = notes.pop(0)
            top = notes[-1][0] if notes else n[0]
            notes.append([n[0] + 12 * max(1, (top - n[0]) // 12 + 1), n[1]])
        else:
            n = notes.pop()
            low = notes[0][0] if notes else n[0]
            notes.insert(0, [n[0] - 12 * max(1, (n[0] - low) // 12 + 1), n[1]])
    shift = int(clip.get("transpose", 0) or 0) + 12 * int(clip.get("octave", 0) or 0)
    out: dict[int, int] = {}
    for p, v in notes:  # inversions can land on a pitch already there
        q = max(0, min(127, p + shift))
        out[q] = max(v, out.get(q, 0))
    return sorted([p, v] for p, v in out.items())


def _rand(seed: int, i: int) -> float:
    """Deterministic value in [-1, 1)."""
    return alt_hash(seed & 0xFFFFFFFF, i & 0xFFFFFFFF) / 2 ** 31 - 1.0


def _smooth(seed: int, t: float, period: float) -> float:
    """Smooth value noise in [-1, 1]: cosine interpolation of random points every `period` ticks."""
    x = t / period
    i = math.floor(x)
    f = (1 - math.cos((x - i) * math.pi)) / 2
    return _rand(seed, i * 2 + 7) * (1 - f) + _rand(seed, i * 2 + 9) * f


def _swing(t: int, swing: float) -> int:
    """Delay strikes on odd sixteenths, like the step sequencer (50 = straight, 75 = hard shuffle)."""
    if swing <= 50 or t % STEP or (t // STEP) % 2 == 0:
        return t
    return t + round((swing / 50 - 1) * STEP)


# ------------------------------------------------------------------ strikes
def _strikes(c0: int, c1: int, grid: dict | None) -> list[dict]:
    """Where the chord is struck inside [c0, c1): grid repeated on the absolute timeline."""
    if grid is None:
        return [{"t": c0, "dur": c1 - c0, "vel": 1.0, "dir": "", "step": c0 // STEP, "len0": False}]
    n = len(grid["vel"])
    on = [j for j in range(n) if grid["vel"][j]]
    out = []
    for s in range(c0 // STEP, -(-c1 // STEP)):
        j = s % n
        if not grid["vel"][j]:
            continue
        t = s * STEP
        if grid["len"][j]:
            ln, len0 = grid["len"][j], False
        else:  # until the next strike (wrapping around the grid)
            nxt = next((k for k in on if k > j), None)
            ln, len0 = ((nxt - j) if nxt is not None else (n - j + on[0])), True
        out.append({"t": t, "dur": min(ln * STEP, c1 - t), "vel": grid["vel"][j] / 100, "dir": grid["dir"][j],
                    "step": s, "len0": len0})
    if not out or (out[0]["t"] > c0 and c0 % PPQ):  # off-beat start (a "push"): strike it there
        first = out[0]["t"] if out else c1
        out.insert(0, {"t": c0, "dur": first - c0, "vel": .92, "dir": "", "step": c0 // STEP, "len0": True})
    return out


def _strum_dir(play: dict, strike: dict, k: int, sixteenth_feel: bool) -> str:
    """'up' (from the lowest note, a guitar downstroke) or 'down' (from the top, an upstroke)."""
    mode = play["strum"].get("dir", "guitar")
    if mode in ("up", "down"):
        return mode
    if mode == "alt":
        return "up" if k % 2 == 0 else "down"
    if mode == "grid" and strike["dir"] in ("d", "u"):
        return "up" if strike["dir"] == "d" else "down"
    s = strike["step"]
    downstroke = s % 2 == 0 if sixteenth_feel else s % 4 == 0
    return "up" if downstroke else "down"


def _strum(notes, t, dur, how, play, tpm):
    """[(start, end, pitch, vel factor)] of one strummed strike."""
    st = play["strum"]
    order = list(notes) if how == "up" else list(reversed(notes))
    up_n = int(st.get("upNotes", 0) or 0)
    if how == "down" and 0 < up_n < len(order):
        order = order[:up_n]  # an upstroke only catches the top strings
    unit = STRUM_UNITS.get(st.get("unit", "ms"))
    gap = unit if unit else float(st.get("spread", 25)) * tpm
    m = len(order)
    span = min(gap * (m - 1), dur * .5) if m > 1 else 0
    curve = st.get("curve", "linear")
    tilt = float(st.get("velTilt", 0) or 0) / 100
    soft = 1 - float(st.get("upSoft", 0) or 0) / 100 if how == "down" else 1.0
    out = []
    for i, (p, v) in enumerate(order):
        x = i / (m - 1) if m > 1 else 0
        f = 1 - (1 - x) ** 2 if curve == "accel" else x * x if curve == "decel" else x
        out.append((t + round(span * f), t + dur, p, v * soft * (1 + tilt * (2 * x - 1))))
    return out


def _arp(notes, t, dur, play, seed, swing):
    a = play["arp"]
    rate = RATES.get(a.get("rate"), 240)
    pool = list(notes)
    for o in range(1, max(1, min(3, int(a.get("octaves", 1))))):
        pool += [(p + 12 * o, v) for p, v in notes]
    mode = a.get("mode", "up")
    if mode == "down":
        order = list(reversed(pool))
    elif mode == "updown":
        order = pool + list(reversed(pool))[1:-1]
    else:
        order = pool
    gate = max(.05, min(1.0, float(play.get("gate", 1.0))))
    out, k = [], 0
    while t + k * rate < t + dur:
        s = _swing(t + k * rate, swing)
        p, v = pool[int((_rand(seed * 7919, s // 10) + 1) / 2 * len(pool)) % len(pool)] if mode == "random" else order[k % len(order)]
        out.append((s, min(t + dur, s + max(MIN_LEN, round(rate * gate))), p, v * (1.0 if s % PPQ == 0 else .86), True))
        k += 1
    return out


def _token_play(play: dict, token: str) -> tuple[dict, str | None]:
    """Play settings for an alternation token, plus a forced strum direction."""
    p = copy.deepcopy(play)
    if token in ("strum_up", "strum_down"):
        p["type"] = "strum"
        return p, "up" if token == "strum_up" else "down"
    if token in ("block", "arp"):
        p["type"] = token
    return p, None


def _fix_overlaps(events):
    """Same pitch never overlaps itself (a note-off would cut the next note-on)."""
    out = []
    by_pitch: dict[int, list] = {}
    for e in sorted(events):
        by_pitch.setdefault(e[2], []).append(list(e))
    for evs in by_pitch.values():
        for a, b in zip(evs, evs[1:]):
            if a[1] > b[0]:
                a[1] = b[0]
        out += [tuple(e) for e in evs if e[1] - e[0] >= MIN_LEN]
    return sorted(out)


def perform(clip: dict, seq: dict, pure: bool = False, mode: dict | None = None) -> list[tuple[int, int, int, int]]:
    """[(start tick, end tick, pitch, velocity)] of one clip, never outside the clip."""
    notes = voicing(clip)
    if not notes:
        return []
    c0 = int(clip["start"]) * STEP
    c1 = c0 + max(1, int(clip["len"])) * STEP
    if pure:
        return [(c0, c1, p, v) for p, v in notes]
    mode = mode or mode_of(seq)
    play, grid = effective(clip, seq, mode)
    tpm = PPQ * float(seq.get("bpm", 120)) / 60000.0  # ticks per millisecond
    hz = play.get("humanize") or {}
    seed = int(hz.get("seed", 1) or 1) ^ zlib.crc32(str(clip.get("id", "")).encode())
    gate = max(.05, min(1.0, float(play.get("gate", 1.0))))
    alt = play.get("alternate") or {}
    tokens = [t for t in alt.get("tokens", []) if t in dict(TOKENS)]
    every = alt.get("every", "off") if tokens else "off"
    sixteenth = bool(grid) and any(v and j % 2 for j, v in enumerate(grid["vel"]))
    strikes = _strikes(c0, c1, grid)
    if grid is None and every == "bar":  # a sustained chord still changes style on every bar
        strikes = []
        s = c0
        while s < c1:
            e = min(c1, (s // BAR + 1) * BAR)
            strikes.append({"t": s, "dur": e - s, "vel": 1.0, "dir": "", "step": s // STEP, "len0": True})
            s = e
    accent = float(hz.get("accent", 0) or 0) / 100
    events = []  # (start, end, pitch, vel, is_arp, strike index)
    for k, sk in enumerate(strikes):
        p_play, forced = play, None
        if every == "hit":
            p_play, forced = _token_play(play, tokens[k % len(tokens)])
        elif every == "bar":
            p_play, forced = _token_play(play, tokens[((sk["t"] - c0) // BAR) % len(tokens)])
        t = _swing(sk["t"], float(mode.get("swing", 50)))
        full = max(MIN_LEN, sk["dur"] - (t - sk["t"]))
        dur = max(MIN_LEN, round(full * gate))
        vel = sk["vel"]
        if accent:
            s = sk["step"] % 16
            vel *= 1 + accent if s == 0 else 1 + accent * .5 if s % 4 == 0 else 1 - accent * .35
        typ = p_play.get("type", "block")
        if typ == "arp":
            evs = _arp(notes, t, full, p_play, seed, float(mode.get("swing", 50)))
        elif typ == "strum":
            evs = [e + (False,) for e in _strum(notes, t, dur, forced or _strum_dir(p_play, sk, k, sixteenth), p_play, tpm)]
        else:
            evs = [(t, t + dur, p, v, False) for p, v in notes]
        events += [(s, e, p, v * vel, arp, k) for s, e, p, v, arp in evs]

    # dynamics and humanize
    curve = play.get("velCurve", "flat")
    low = notes[0][0]
    scale = float(clip.get("vel", 100) or 100) / 100.0
    h_t = float(hz.get("timing", 0) or 0) * tpm
    h_s = float(hz.get("spread", 0) or 0) * tpm
    feel = float(hz.get("feel", 0) or 0) * tpm
    drift = max(0.0, min(1.0, float(hz.get("drift", 0) or 0) / 100))
    h_v = float(hz.get("vel", 0) or 0)
    h_l = float(hz.get("len", 0) or 0) / 100
    out = []
    for i, (s, e, p, v, arp, k) in enumerate(sorted(events)):
        frac = (s - c0) / (c1 - c0)
        f = {"cresc": .72 + .42 * frac, "decresc": 1.14 - .42 * frac, "bass": 1.12 if p == low else .9}.get(curve, 1.0)
        vel = v * scale * f
        dt = feel
        if h_t:  # the whole strike moves together (an arpeggio note is its own strike)
            key = i if arp else k
            rnd = _rand(seed, 3 * key) * (1 - drift) + _smooth(seed, s, PPQ * 2) * drift
            dt += rnd * h_t
        if h_s and not arp:
            dt += _rand(seed, 3 * i + 1) * h_s
        dt = round(dt)
        ln = e - s
        if h_l:
            ln = round(ln * (1 + _rand(seed, 3 * i + 2) * h_l))
        if h_v:
            vel += _rand(seed, 5 * i + 3) * h_v
        s, e = max(c0, s + dt), min(c1, s + dt + ln)
        if e - s >= MIN_LEN:
            out.append((s, e, p, int(max(1, min(127, round(vel))))))
    return _fix_overlaps(out)


def render(seq: dict, pure: bool = False) -> list[tuple[int, int, int, int, int]]:
    """Every clip of a sequence: (start, end, pitch, velocity, clip index), cut at the sequence length."""
    length = int(seq.get("bars", 4)) * BAR
    mode = mode_of(seq)
    out = []
    for i, clip in enumerate(seq.get("clips", [])):
        for s, e, p, v in perform(clip, seq, pure, mode):
            if s < length:
                out.append((s, min(e, length), p, v, i))
    return sorted(out)
