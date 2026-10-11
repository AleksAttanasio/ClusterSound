"""How a chord clip is played: block, strum, arpeggio, rhythmic patterns, velocity curves and humanize.

perform() is the single source of truth: the Compose preview plays exactly the events rendered here, and
the MIDI export writes the same ones. Times are ticks at PPQ 480; clip start/len are in sixteenths.
"""
import copy
import zlib

from ..patterns.model import alt_hash

PPQ = 480
STEP = PPQ // 4
BAR = PPQ * 4
MIN_LEN = 12  # ticks: shorter notes are dropped
RATES = {"1/4": 480, "1/8": 240, "1/16": 120, "1/8t": 160, "1/16t": 80}
# per-bar patterns: (position in sixteenths, length in sixteenths, accent)
RHYTHMS = {
    "quarters": ("Semiminime", [(0, 4, 1.0), (4, 4, .8), (8, 4, .92), (12, 4, .8)]),
    "eighths": ("Ottavi", [(i * 2, 2, 1.0 if i % 2 == 0 else .78) for i in range(8)]),
    "offbeat": ("Offbeat / skank", [(2, 2, .95), (6, 2, .85), (10, 2, .95), (14, 2, .85)]),
    "charleston": ("Charleston", [(0, 3, 1.0), (6, 2, .85)]),
    "tresillo": ("Tresillo 3-3-2", [(0, 3, 1.0), (3, 3, .85), (6, 2, .9), (8, 3, .95), (11, 3, .85), (14, 2, .9)]),
    "syncopated": ("Sincopato house", [(0, 3, 1.0), (3, 3, .82), (6, 4, .9), (10, 2, .8), (12, 4, .88)]),
    "half": ("Minime", [(0, 8, 1.0), (8, 8, .85)]),
    "pulse": ("Pulse 1/16", [(i, 1, 1.0 if i % 4 == 0 else .7 if i % 2 == 0 else .58) for i in range(16)]),
}
STYLE_TYPES = [("block", "Block"), ("strum", "Strum"), ("arp", "Arpeggio"), ("rhythm", "Ritmo")]
TOKENS = [("block", "Block"), ("strum_up", "Strum ↑"), ("strum_down", "Strum ↓"), ("arp", "Arp"), ("rhythm", "Ritmo")]
DEFAULT_STYLE = {
    "type": "block",
    "gate": 1.0,
    "strum": {"dir": "up", "spread": 25},
    "arp": {"mode": "up", "rate": "1/8", "octaves": 1},
    "rhythm": {"pattern": "quarters", "hit": "block"},
    "velCurve": "flat",
    "humanize": {"timing": 0, "vel": 0, "seed": 1},
    "alternate": {"every": "off", "tokens": []},
}


def meta() -> dict:
    return {"types": STYLE_TYPES, "tokens": TOKENS, "rates": list(RATES),
            "rhythms": [(k, v[0]) for k, v in RHYTHMS.items()],
            "arpModes": [("up", "Su"), ("down", "Giù"), ("updown", "Su-giù"), ("random", "Casuale")],
            "strumDirs": [("up", "↑ dal basso"), ("down", "↓ dall'alto"), ("alt", "↕ alternato")],
            "velCurves": [("flat", "Piatta"), ("cresc", "Crescendo"), ("decresc", "Decrescendo"), ("bass", "Accento sul basso")],
            "default": DEFAULT_STYLE}


def _merge(base: dict, over: dict | None) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        elif v is not None:
            out[k] = v
    return out


def style_of(clip: dict, seq: dict) -> dict:
    return _merge(_merge(DEFAULT_STYLE, seq.get("defaultStyle")), clip.get("style"))


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
    return alt_hash(seed & 0xFFFFFFFF, i) / 2 ** 31 - 1.0


def _with_token(st: dict, token: str) -> dict:
    st = copy.deepcopy(st)
    if token in ("strum_up", "strum_down"):
        st["type"] = "strum"
        st["strum"]["dir"] = "up" if token == "strum_up" else "down"
    elif token in ("block", "arp", "rhythm"):
        st["type"] = token
    return st


def _hit(notes, t, dur, acc, how, tpm, spread_ms, k):
    """One strike of the whole chord. how: block | strum_up | strum_down | strum_alt (k = hit index)."""
    if how == "strum_alt":
        how = "strum_up" if k % 2 == 0 else "strum_down"
    order = notes if how != "strum_down" else list(reversed(notes))
    gap = spread_ms * tpm if how.startswith("strum") else 0
    if len(order) > 1:
        gap = min(gap, dur * .5 / (len(order) - 1))
    return [(t + round(i * gap), t + dur, p, v * acc) for i, (p, v) in enumerate(order)]


def _segment(notes, s0, s1, st, tpm, hit_tokens):
    typ = st["type"]
    gate = max(.05, min(1.0, float(st.get("gate", 1.0))))
    strum = st["strum"]
    if typ in ("block", "strum"):
        how = "block" if typ == "block" else f"strum_{strum.get('dir', 'up')}"
        return _hit(notes, s0, max(MIN_LEN, round((s1 - s0) * gate)), 1.0, how, tpm, strum.get("spread", 25), 0)
    if typ == "arp":
        a = st["arp"]
        rate = RATES.get(a.get("rate"), 240)
        pool = list(notes)
        for o in range(1, max(1, min(3, int(a.get("octaves", 1))))):
            pool += [(p + 12 * o, v) for p, v in notes]
        mode = a.get("mode", "up")
        order = list(reversed(pool)) if mode == "down" else pool + list(reversed(pool))[1:-1] if mode == "updown" else pool
        seed = int(st["humanize"].get("seed", 1)) * 7919
        out, k, t = [], 0, s0
        while t < s1:
            p, v = pool[int((_rand(seed, k) + 1) / 2 * len(pool)) % len(pool)] if mode == "random" else order[k % len(order)]
            out.append((t, t + max(MIN_LEN, round(rate * gate)), p, v * (1.0 if (t - s0) % PPQ == 0 else .86)))
            k += 1
            t = s0 + k * rate
        return out
    # rhythm: pattern on the absolute bar grid
    pattern = RHYTHMS.get(st["rhythm"].get("pattern"), RHYTHMS["quarters"])[1]
    base_how = st["rhythm"].get("hit", "block")
    if base_how == "strum":
        base_how = f"strum_{strum.get('dir', 'up')}"
    hits = []
    bar = (s0 // BAR) * BAR
    while bar < s1:
        for pos, ln, acc in pattern:
            t = bar + pos * STEP
            if s0 <= t < s1:
                hits.append((t, ln * STEP, acc))
        bar += BAR
    if not hits or (hits[0][0] > s0 and s0 % PPQ):  # off-beat start (a "push"): strike it there
        hits.insert(0, (s0, (hits[0][0] - s0) if hits else s1 - s0, .92))
    out = []
    for k, (t, ln, acc) in enumerate(hits):
        how = base_how
        if hit_tokens:
            tok = hit_tokens[k % len(hit_tokens)]
            how = tok if tok.startswith("strum") else "block"
        dur = max(MIN_LEN, min(round(ln * gate), s1 - t))
        out += _hit(notes, t, dur, acc, how, tpm, strum.get("spread", 25), k)
    return out


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


def perform(clip: dict, seq: dict, pure: bool = False) -> list[tuple[int, int, int, int]]:
    """[(start tick, end tick, pitch, velocity)] of one clip, never outside the clip."""
    notes = voicing(clip)
    if not notes:
        return []
    c0 = int(clip["start"]) * STEP
    c1 = c0 + max(1, int(clip["len"])) * STEP
    if pure:
        return [(c0, c1, p, v) for p, v in notes]
    st = style_of(clip, seq)
    tpm = PPQ * float(seq.get("bpm", 120)) / 60000.0  # ticks per millisecond
    alt = st.get("alternate") or {}
    tokens = [t for t in alt.get("tokens", []) if t in dict(TOKENS)]
    every = alt.get("every", "off") if tokens else "off"
    if every == "bar":
        events, k, s = [], 0, c0
        while s < c1:
            e = min(c1, (s // BAR + 1) * BAR)
            events += _segment(notes, s, e, _with_token(st, tokens[k % len(tokens)]), tpm, None)
            k, s = k + 1, e
    else:
        events = _segment(notes, c0, c1, st, tpm, tokens if every == "hit" else None)
    curve = st.get("velCurve", "flat")
    low = notes[0][0]
    scale = float(clip.get("vel", 100) or 100) / 100.0
    hz = st.get("humanize") or {}
    h_t, h_v = float(hz.get("timing", 0) or 0) * tpm, float(hz.get("vel", 0) or 0)
    seed = int(hz.get("seed", 1) or 1) ^ zlib.crc32(str(clip.get("id", "")).encode())
    out = []
    for i, (s, e, p, v) in enumerate(sorted(events)):
        frac = (s - c0) / (c1 - c0)
        f = {"cresc": .72 + .42 * frac, "decresc": 1.14 - .42 * frac,
             "bass": 1.12 if p == low else .9}.get(curve, 1.0)
        vel = v * scale * f
        if h_t:
            dt = round(_rand(seed, 2 * i) * h_t)
            s, e = s + dt, e + dt
        if h_v:
            vel += _rand(seed, 2 * i + 1) * h_v
        s, e = max(c0, s), min(c1, e)
        if e - s >= MIN_LEN:
            out.append((s, e, p, int(max(1, min(127, round(vel))))))
    return _fix_overlaps(out)


def render(seq: dict, pure: bool = False) -> list[tuple[int, int, int, int, int]]:
    """Every clip of a sequence: (start, end, pitch, velocity, clip index), cut at the sequence length."""
    length = int(seq.get("bars", 4)) * BAR
    out = []
    for i, clip in enumerate(seq.get("clips", [])):
        for s, e, p, v in perform(clip, seq, pure):
            if s < length:
                out.append((s, min(e, length), p, v, i))
    return sorted(out)
