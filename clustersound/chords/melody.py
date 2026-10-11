"""Melody layers of a harmony version: render them, normalise imported notes, generate a line over the chords
(lead, bass, arpeggio, riff, pad, keys) and harmonise a melody with the chords of the pack.

    seq["melody"] = {"layers": [{"id", "name", "role", "notes", "vol", "mute"}], "active": layer id}
    note = {"id", "start", "len", "pitch", "vel"}   # start/len in sixteenths; lead/bass/arp/riff are monophonic

The old {"notes": [...]} of a single melody reads as one "lead" layer.

Deterministic for a given seed, like the variations.
"""
import copy
import math
import random
import uuid

from . import harmony, theory
from .perform import BAR, MIN_LEN, PPQ, STEP, _swing, mode_of
from .variations import _fit, bake

DENSITIES = [("low", "Rada"), ("mid", "Media"), ("high", "Fitta"), ("mixed", "Mista")]
CONTOURS = [("arch", "Arco"), ("up", "Sale"), ("down", "Scende"), ("wave", "Onda"), ("free", "Libero")]
RATES = [("bar", "1 accordo per battuta"), ("half", "2 per battuta"), ("auto", "Segue la melodia")]
ARP_SHAPES = [("up", "Sale"), ("down", "Scende"), ("updown", "Sale e scende"), ("random", "Casuale")]
BASS_SHAPES = [("root", "Fondamentali"), ("octave", "Ottave"), ("fifth", "Quinte"), ("walk", "Passaggi")]
# role -> label, default range, shapes for the "contour" option (and their label)
ROLES = {
    "lead": {"label": "Melodia", "lo": 60, "hi": 81, "shapes": CONTOURS, "shapeLabel": "Contorno"},
    "bass": {"label": "Basso", "lo": 36, "hi": 55, "shapes": BASS_SHAPES, "shapeLabel": "Stile"},
    "arp": {"label": "Arpeggio", "lo": 55, "hi": 79, "shapes": ARP_SHAPES, "shapeLabel": "Direzione"},
    "riff": {"label": "Riff", "lo": 55, "hi": 76, "shapes": [], "shapeLabel": ""},
    "pad": {"label": "Pad", "lo": 52, "hi": 72, "shapes": [], "shapeLabel": ""},
    "keys": {"label": "Keys", "lo": 52, "hi": 74, "shapes": [], "shapeLabel": ""},
}
# onsets of one bar (sixteenths), per density
_RHYTHMS = {
    "low": [[0, 8], [0, 12], [0, 4, 8], [0, 6, 8], [0, 8, 12], [0]],
    "mid": [[0, 4, 8, 12], [0, 4, 6, 8], [0, 2, 4, 8, 12], [0, 6, 8, 12], [0, 3, 6, 8, 12], [0, 4, 8, 10, 12]],
    "high": [[0, 2, 4, 6, 8, 10, 12, 14], [0, 2, 4, 6, 8, 12, 14], [0, 3, 4, 6, 8, 10, 11, 12, 14],
             [0, 1, 2, 4, 6, 8, 10, 12], [0, 2, 3, 4, 6, 8, 10, 12, 14]],
}


def _uid() -> str:
    return "m" + uuid.uuid4().hex[:7]


def roles_meta() -> list[dict]:
    return [{"id": k, **v} for k, v in ROLES.items()]


def layers_of(seq: dict) -> list[dict]:
    """The melody layers of seq (an old single melody -> one "lead" layer)."""
    m = seq.get("melody") or {}
    if "layers" in m:
        return m["layers"] or []
    notes = m.get("notes") or []
    return [{"id": "L1", "name": "Melodia", "role": "lead", "notes": notes, "vol": 1, "mute": False}] if notes else []


def active_layer(seq: dict) -> dict | None:
    """The layer being edited: melody.active, else the first lead, else the first one."""
    layers = layers_of(seq)
    act = (seq.get("melody") or {}).get("active")
    return (next((l for l in layers if l["id"] == act), None) or next((l for l in layers if l.get("role") == "lead"), None)
            or (layers[0] if layers else None))


def notes_of(seq: dict, layer_id: str | None = None) -> list[dict]:
    """Notes of a layer (default: the active one), by start."""
    layer = next((l for l in layers_of(seq) if l["id"] == layer_id), None) if layer_id else active_layer(seq)
    return sorted((layer or {}).get("notes") or [], key=lambda n: n["start"])


# ------------------------------------------------------------------ render
def render(seq: dict, layer_id: str | None = None) -> list[tuple[int, int, int, int]]:
    """[(start tick, end tick, pitch, velocity)] of a layer (default: all the layers that aren't muted) with
    the swing of the Modalità, cut at the sequence length."""
    if layer_id:
        notes = notes_of(seq, layer_id)
    else:
        notes = sorted((n for l in layers_of(seq) if not l.get("mute") for n in l.get("notes") or []),
                       key=lambda n: n["start"])
    return _render_notes(seq, notes)


def render_layers(seq: dict) -> list[dict]:
    """[{id, name, role, vol, mute, events}] for every layer with notes."""
    return [{"id": l["id"], "name": l.get("name") or ROLES.get(l.get("role"), ROLES["lead"])["label"],
             "role": l.get("role", "lead"), "vol": l.get("vol", 1), "mute": bool(l.get("mute")),
             "events": _render_notes(seq, sorted(l["notes"], key=lambda n: n["start"]))}
            for l in layers_of(seq) if l.get("notes")]


def _render_notes(seq: dict, notes: list[dict]) -> list[tuple[int, int, int, int]]:
    length = int(seq.get("bars", 4)) * BAR
    swing = float(mode_of(seq).get("swing", 50))
    out = []
    for n in notes:
        s = _swing(int(n["start"]) * STEP, swing)
        e = min(length, (int(n["start"]) + max(1, int(n["len"]))) * STEP)
        if s < length and e - s >= MIN_LEN:
            out.append((s, e, max(0, min(127, int(n["pitch"]))), max(1, min(127, int(n.get("vel", 100))))))
    return out


# ------------------------------------------------------------------ import
def from_spans(spans: list[tuple[int, int, int, int]], ppq: int, grid: int = 1, keep: bool = False) -> list[dict]:
    """Imported notes (start, end, pitch, vel in ticks at ppq) -> melody notes: quantised to `grid`
    sixteenths, one voice (the top line wins a chord), moved so the first note keeps its place in the bar
    (keep: not moved, a take recorded against the progression)."""
    if not spans:
        return []
    six = ppq / 4
    q = lambda t: int(round(t / six / grid)) * grid
    by_start: dict[int, tuple] = {}
    for s, e, p, v in spans:
        st = q(s)
        ln = max(grid, q(e) - st)
        if st not in by_start or p > by_start[st][1]:
            by_start[st] = (ln, p, v)
    starts = sorted(by_start)
    shift = 0 if keep else (starts[0] // 16) * 16
    out = []
    for i, st in enumerate(starts):
        ln, p, v = by_start[st]
        if i + 1 < len(starts):
            ln = min(ln, starts[i + 1] - st)
        out.append({"id": _uid(), "start": st - shift, "len": ln, "pitch": int(p), "vel": int(v)})
    return out


def detect_key(notes: list[dict]) -> dict:
    """Krumhansl-Schmuckler key of a melody (durations weighted, first and last note count double)."""
    major = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
    minor = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
    hist = [0.0] * 12
    for i, n in enumerate(notes):
        hist[n["pitch"] % 12] += max(1, n["len"]) * (2 if i in (0, len(notes) - 1) else 1)
    if not any(hist):
        return {"tonic": 0, "mode": "major"}

    def corr(prof, t):
        xs = [prof[(i - t) % 12] for i in range(12)]
        mx, my = sum(xs) / 12, sum(hist) / 12
        num = sum((x - mx) * (y - my) for x, y in zip(xs, hist))
        den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in hist)) ** .5
        return num / den if den else 0

    best = max(((corr(major if m == "major" else minor, t), t, m) for t in range(12) for m in ("major", "minor")))
    return {"tonic": best[1], "mode": best[2]}


# ------------------------------------------------------------------ chords over time
def _chord_map(seq: dict) -> list[dict | None]:
    """Described chord sounding on every sixteenth of the sequence (None where there is no clip)."""
    n = int(seq.get("bars", 4)) * 16
    out: list[dict | None] = [None] * n
    for c in sorted(seq.get("clips", []), key=lambda c: c["start"]):
        d = harmony.describe(c)
        if not d["notes"]:
            continue
        for s in range(max(0, int(c["start"])), min(n, int(c["start"]) + int(c["len"]))):
            out[s] = d
    return out


def _scale(key: dict) -> set[int]:
    return {(key["tonic"] + s) % 12 for s in theory.SCALES[key["mode"]]}


# ------------------------------------------------------------------ melody from harmony
def _bar_rhythm(density: str, rng: random.Random) -> list[int]:
    if density == "mixed":
        density = rng.choice(["low", "mid", "mid", "high"])
    return list(rng.choice(_RHYTHMS.get(density, _RHYTHMS["mid"])))


def _mutate(onsets: list[int], rng: random.Random) -> list[int]:
    """Answer of a phrase: same rhythm with one onset added or removed."""
    out = set(onsets)
    if rng.random() < .5 and len(out) > 2:
        out.discard(rng.choice(sorted(out - {0})))
    else:
        out.add(rng.choice([s for s in range(0, 16, 2) if s not in out] or [0]))
    return sorted(out)


def _target(contour: str, x: float, lo: int, hi: int, rng_phase: float) -> float:
    """Contour centre at x in [0, 1] of the phrase."""
    mid, span = (lo + hi) / 2, (hi - lo) / 2
    f = {"arch": math.sin(x * math.pi) * 1.2 - .4, "up": -.6 + 1.2 * x, "down": .6 - 1.2 * x,
         "wave": math.sin((x * 2 + rng_phase) * math.pi) * .6}.get(contour, rng_phase * .4 - .2)
    return mid + span * .7 * f


def _pick(cands: list[int], prev: int | None, target: float, strong: bool, last_leap: int, rng: random.Random) -> int:
    best, best_s = None, None
    for p in cands:
        s = -.25 * abs(p - target)
        if prev is not None:
            iv = p - prev
            a = abs(iv)
            s -= .35 * a if a <= 4 else 1.4 + .6 * (a - 4)
            if a > 7:
                s -= 3
            if a == 0:
                s -= .9 if strong else 1.6
            if abs(last_leap) > 4 and (iv * last_leap > 0 or a > 2):  # recover a leap stepwise, the other way
                s -= 1.5
        s += rng.random() * .9
        if best_s is None or s > best_s:
            best, best_s = p, s
    return best


def _one_melody(seq: dict, key: dict, cmap: list, opts: dict, rng: random.Random) -> list[dict]:
    lo, hi = int(opts.get("lo", 60)), int(opts.get("hi", 81))
    if hi - lo < 7:
        hi = lo + 12
    density, contour = opts.get("density", "mid"), opts.get("contour", "arch")
    plen = 2 if density == "high" else 4 if density == "low" else rng.choice([2, 4])
    total = int(seq.get("bars", 4))
    b0 = max(0, min(total - 1, int(opts.get("fromBar", 0) or 0)))
    b1 = max(b0 + 1, min(total, int(opts.get("toBar", total) or total)))
    scale = _scale(key)
    out: list[dict] = []
    prev, leap = None, 0
    phrase_rhythm: list[list[int]] = []
    phase = rng.random()
    for bar in range(b0, b1):
        k = (bar - b0) % plen
        pi = (bar - b0) // plen
        if pi % 2 == 1 and k < len(phrase_rhythm) and rng.random() < .75:  # answer: the question's rhythm
            on = phrase_rhythm[k] if k < plen - 1 else _mutate(phrase_rhythm[k], rng)
        else:
            on = _bar_rhythm(density, rng)
            if pi % 2 == 0:
                phrase_rhythm = phrase_rhythm[:k] + [on]
        end_of_phrase = k == plen - 1 or bar == b1 - 1
        if end_of_phrase:  # breathe: the phrase ends on a longer note
            on = [s for s in on if s <= 8] or [0]
        for j, s in enumerate(on):
            t = bar * 16 + s
            nxt = bar * 16 + on[j + 1] if j + 1 < len(on) else (bar + 1) * 16
            ch = cmap[t] if t < len(cmap) else None
            tones = ch["pcs"] if ch else {key["tonic"], (key["tonic"] + 4 - (key["mode"] == "minor")) % 12, (key["tonic"] + 7) % 12}
            strong = s % 4 == 0
            last = end_of_phrase and j == len(on) - 1
            if last:  # a phrase comes to rest on the root
                pcs = {ch["root"]} if ch else {key["tonic"]}
            elif strong:
                pcs = set(tones)
            else:
                pcs = scale | set(tones)
            cands = [p for p in range(lo, hi + 1) if p % 12 in pcs] or list(range(lo, hi + 1))
            x = ((bar - b0) % plen * 16 + s) / (plen * 16)
            p = _pick(cands, prev, _target(contour, x, lo, hi, phase), strong, leap, rng)
            leap = p - prev if prev is not None else 0
            prev = p
            ln = max(1, nxt - t)
            if not last and ln > 2 and rng.random() < .2:
                ln -= 1  # a little air between notes
            vel = 104 if s == 0 else 92 if strong else 80
            out.append({"id": _uid(), "start": t, "len": ln, "pitch": p, "vel": vel + rng.randint(-6, 6)})
    return out


# ------------------------------------------------------------------ other roles
_BASS_RHYTHMS = {
    "low": [[0], [0, 8], [0, 12], [0, 10]],
    "mid": [[0, 8], [0, 6, 8], [0, 8, 12], [0, 3, 8, 11], [0, 4, 8, 12], [0, 8, 10, 14]],
    "high": [[0, 2, 4, 6, 8, 10, 12, 14], [0, 3, 6, 8, 11, 14], [0, 2, 4, 8, 10, 12], [0, 2, 6, 8, 10, 14]],
}
_COMP_RHYTHMS = {
    "low": [[0, 8], [0], [0, 12]],
    "mid": [[0, 4, 8, 12], [0, 6, 8, 14], [0, 3, 6, 8, 11], [0, 6, 12]],
    "high": [[0, 2, 4, 6, 8, 10, 12, 14], [0, 3, 6, 8, 10, 14], [0, 2, 6, 8, 10, 14]],
}


def _density(opts: dict, rng: random.Random) -> str:
    d = opts.get("density", "mid")
    return rng.choice(["low", "mid", "mid", "high"]) if d == "mixed" else d if d in _RHYTHMS else "mid"


def _chord_spans(seq: dict, key: dict, b0: int, b1: int) -> list[tuple[int, int, dict]]:
    """(start, len, described chord) of the clips inside bars [b0, b1), cut to the range; the tonic triad
    where there is no clip."""
    tonic = {"root": key["tonic"], "pcs": {key["tonic"], (key["tonic"] + 4 - (key["mode"] == "minor")) % 12,
                                          (key["tonic"] + 7) % 12}}
    cmap = _chord_map(seq)
    out, s = [], b0 * 16
    while s < b1 * 16:
        ch = cmap[s] if s < len(cmap) else None
        e = s + 1
        while e < b1 * 16 and e < len(cmap) and cmap[e] is ch:
            e += 1
        out.append((s, e - s, ch or tonic))
        s = e
    return out


def _near(pc: int, ref: float, lo: int, hi: int) -> int:
    """The pitch of pitch class pc inside [lo, hi] closest to ref (the edge of the range if there is none)."""
    cands = [p for p in range(lo, hi + 1) if p % 12 == pc]
    return min(cands, key=lambda p: (abs(p - ref), p)) if cands else max(lo, min(hi, int(ref)))


def _tiled(rhythm: list[int], s: int, ln: int) -> list[int]:
    """Onsets of a one-bar rhythm repeated over [s, s+ln), aligned to the bar."""
    out = [b + o for b in range((s // 16) * 16, s + ln, 16) for o in rhythm if s <= b + o < s + ln]
    return sorted(set(out) | {s})


def _note(t: int, ln: int, p: int, vel: int, rng: random.Random) -> dict:
    return {"id": _uid(), "start": t, "len": max(1, ln), "pitch": int(p), "vel": max(1, min(127, vel + rng.randint(-5, 5)))}


def _one_bass(seq, key, spans, opts, rng) -> list[dict]:
    lo, hi = opts["lo"], opts["hi"]
    style = opts.get("contour") if opts.get("contour") in dict(BASS_SHAPES) else "root"
    rhythm = list(rng.choice(_BASS_RHYTHMS[_density(opts, rng)]))
    scale = sorted(_scale(key))
    home = lo + 5
    out, prev = [], home
    for i, (s, ln, ch) in enumerate(spans):
        root = _near(ch["root"], (prev + home) / 2, lo, hi)  # near the last root, pulled to the bottom of the range
        nxt_root = _near(spans[i + 1][2]["root"], (root + home) / 2, lo, hi) if i + 1 < len(spans) else None
        on = _tiled(rhythm, s, ln)
        walk = []
        if style == "walk" and len(on) > 2:  # scale steps from the root towards the next root
            goal = nxt_root if nxt_root is not None else root
            step = 1 if goal >= root else -1
            p = root
            for _ in on[1:]:
                p += step
                while p % 12 not in scale:
                    p += step
                walk.append(max(lo, min(hi, p)))
        for j, t in enumerate(on):
            end = on[j + 1] if j + 1 < len(on) else s + ln
            last = j == len(on) - 1 and j > 0
            if j == 0:
                p = root
            elif last and nxt_root is not None and rng.random() < .7:  # approach the next root
                p = nxt_root + rng.choice([-1, 1, -2, 2])
                p = p if lo <= p <= hi else nxt_root
            elif style == "walk" and walk:
                p = walk[j - 1]
            elif style == "octave":
                p = root + 12 if j % 2 and root + 12 <= hi else root
            elif style == "fifth":
                f = root + 7 if root + 7 <= hi else root - 5
                p = f if j % 2 and lo <= f else root
            else:
                p = root
            gap = end - t
            dur = gap if gap <= 2 or rng.random() < .6 else gap - 1
            out.append(_note(t, dur, p, 108 if t % 16 == 0 else 96 if t % 4 == 0 else 84, rng))
        prev = root
    return out


def _arp_tones(ch: dict, lo: int, hi: int) -> list[int]:
    return [p for p in range(lo, hi + 1) if p % 12 in ch["pcs"]] or [_near(ch["root"], (lo + hi) / 2, lo, hi)]


def _one_arp(seq, key, spans, opts, rng) -> list[dict]:
    lo, hi = opts["lo"], opts["hi"]
    shape = opts.get("contour") if opts.get("contour") in dict(ARP_SHAPES) else "up"
    dens = _density(opts, rng)
    step = {"low": 4, "mid": 2, "high": 1}[dens]
    out, prev = [], None
    for s, ln, ch in spans:
        tones = _arp_tones(ch, lo, hi)
        if len(tones) > 7:  # about two octaves around the previous note
            c = prev if prev is not None else (lo + hi) / 2
            i0 = min(range(len(tones)), key=lambda i: abs(tones[i] - c))
            a = max(0, min(len(tones) - 7, i0 - 3))
            tones = tones[a:a + 7]
        seq_i = list(range(len(tones)))
        if shape == "down":
            seq_i.reverse()
        elif shape == "updown" and len(tones) > 2:
            seq_i = seq_i + seq_i[-2:0:-1]
        cur = 0 if prev is None or shape == "random" else min(range(len(seq_i)), key=lambda k: abs(tones[seq_i[k]] - prev))
        for t in range(s, s + ln, step):
            p = tones[rng.randrange(len(tones))] if shape == "random" else tones[seq_i[cur % len(seq_i)]]
            cur += 1
            dur = min(step, s + ln - t)
            out.append(_note(t, dur if dur < 2 else dur - (rng.random() < .3), p, 100 if t % 4 == 0 else 84, rng))
            prev = p
    return out


def _one_riff(seq, key, spans, opts, rng) -> list[dict]:
    """A one-bar cell (rhythm + intervals from the chord root) repeated on every bar, moved to the chord that
    sounds and snapped to its tones on the beats; the last bar of every 4 varies its rhythm."""
    lo, hi = opts["lo"], opts["hi"]
    dens = _density(opts, rng)
    cell_on = _bar_rhythm(dens if dens != "low" else "mid", rng)
    first = spans[0][2]
    base = _near(first["root"], lo + (hi - lo) / 3, lo, hi)
    cands0 = [p for p in range(lo, hi + 1) if p % 12 in (_scale(key) | first["pcs"])]
    offs, prev, leap = [], None, 0
    for j, o in enumerate(cell_on):
        x = j / max(1, len(cell_on) - 1)
        cands = [p for p in cands0 if p % 12 in first["pcs"]] if o % 4 == 0 else cands0
        p = _pick(cands or cands0, prev, _target("wave", x, base - 2, base + 12, rng.random()), o % 4 == 0, leap, rng)
        leap = p - prev if prev is not None else 0
        prev = p
        offs.append(p - base)
    by_on = dict(zip(cell_on, offs))
    scale = _scale(key)
    cmap = {t: ch for s, ln, ch in spans for t in range(s, s + ln)}
    b0, b1 = spans[0][0] // 16, -(-(spans[-1][0] + spans[-1][1]) // 16)
    out, anchor = [], base
    for bar in range(b0, b1):
        on = cell_on if (bar - b0) % 4 != 3 else _mutate(cell_on, rng)
        for j, o in enumerate(on):
            t = bar * 16 + o
            ch = cmap.get(t)
            if ch is None:
                continue
            nxt = bar * 16 + on[j + 1] if j + 1 < len(on) else (bar + 1) * 16
            off = by_on.get(o, by_on[max(k for k in by_on if k <= o)] if any(k <= o for k in by_on) else 0)
            root = _near(ch["root"], (anchor + base) / 2, lo, hi)  # follows the chords without drifting away
            pcs = ch["pcs"] if o % 4 == 0 else scale | ch["pcs"]
            want = root + off
            p = min((q for q in range(lo, hi + 1) if q % 12 in pcs), key=lambda q: (abs(q - want), q), default=want)
            ln = min(nxt, max(s + l for s, l, c in spans if c is ch and s <= t < s + l)) - t
            out.append(_note(t, ln if ln < 3 else ln - 1, p, 104 if o == 0 else 92 if o % 4 == 0 else 80, rng))
            if j == 0:
                anchor = root
    return out


def _voicing(ch: dict, lo: int, hi: int, prev: list[int] | None) -> list[int]:
    """Close-position voicing of the chord (up to 4 notes) inside [lo, hi], nearest to the previous one."""
    pcs = list(ch["pcs"])
    if len(pcs) > 4:  # drop the fifth, then any colour tone
        fifth = (ch["root"] + 7) % 12
        pcs = [pc for pc in pcs if pc != fifth][:4] if fifth in pcs else pcs[:4]
    best, best_d = None, None
    for b in range(lo, hi + 1):
        if b % 12 not in pcs:
            continue
        v = sorted(b + (pc - b) % 12 for pc in pcs)
        if v[-1] > hi:
            continue
        d = harmony.voice_distance(prev, v) if prev else abs(sum(v) / len(v) - (lo + hi) / 2)
        if best_d is None or d < best_d:
            best, best_d = v, d
    return best or sorted(_near(pc, (lo + hi) / 2, lo, hi) for pc in pcs)


def _one_chords(seq, key, spans, opts, rng, comp: bool) -> list[dict]:
    """Pad: the chord held (low), again every bar (mid) or every half bar (high). Keys: comping stabs."""
    lo, hi = opts["lo"], opts["hi"]
    dens = _density(opts, rng)
    rhythm = rng.choice(_COMP_RHYTHMS[dens]) if comp else {"low": [], "mid": [0], "high": [0, 8]}[dens]
    out, prev = [], None
    for s, ln, ch in spans:
        v = _voicing(ch, lo, hi, prev)
        on = _tiled(rhythm, s, ln)
        for j, t in enumerate(on):
            end = on[j + 1] if j + 1 < len(on) else s + ln
            gap = end - t
            dur = gap if not comp else min(gap, 2 if dens == "high" else 3 if gap > 3 and rng.random() < .5 else gap)
            vel = (100 if t % 16 == 0 else 90 if t % 4 == 0 else 80) if comp else 84
            out += [_note(t, dur, p, vel - 4 * k, rng) for k, p in enumerate(v)]
        prev = v
    return out


def generate(seq: dict, key: dict, opts: dict | None = None, seed: int = 1, count: int = 4) -> list[dict]:
    """Up to `count` lines of one role over the chords of seq. opts: role (lead, bass, arp, riff, pad, keys),
    density, contour (the role's shape), lo, hi, fromBar, toBar, layer (id of the layer whose notes outside
    the bar range are kept; default the active one, None: nothing kept).
    lead: chord tones on the beats, scale steps in between, phrases of 2-4 bars answered by a variation of
    their rhythm. bass: roots on the downbeats, octaves/fifths/steps, an approach note into the next chord.
    arp: chord tones in a pattern. riff: a one-bar cell following the chords. pad/keys: voice-led chords."""
    opts = dict(opts or {})
    role = opts.get("role") if opts.get("role") in ROLES else "lead"
    meta = ROLES[role]
    opts["lo"], opts["hi"] = int(opts.get("lo", meta["lo"])), int(opts.get("hi", meta["hi"]))
    if opts["hi"] - opts["lo"] < 7:
        opts["hi"] = opts["lo"] + 12
    cmap = _chord_map(seq)
    rng = random.Random(seed)
    total = int(seq.get("bars", 4))
    b0 = max(0, min(total - 1, int(opts.get("fromBar", 0) or 0)))
    b1 = max(b0 + 1, min(total, int(opts.get("toBar", total) or total)))
    layer = opts.get("layer", "active")
    old = (notes_of(seq) if layer == "active" else notes_of(seq, layer) if layer else [])
    keep = [n for n in old if n["start"] < b0 * 16 or n["start"] >= b1 * 16]
    spans = _chord_spans(seq, key, b0, b1)
    make = {"bass": _one_bass, "arp": _one_arp, "riff": _one_riff,
            "pad": lambda *a: _one_chords(*a, comp=False), "keys": lambda *a: _one_chords(*a, comp=True)}.get(role)
    dname = dict(DENSITIES).get(opts.get("density", "mid"), "")
    sname = dict(meta["shapes"]).get(opts.get("contour"), "")
    out, seen = [], set()
    for attempt in range(count * 3):
        if len(out) >= count:
            break
        r = random.Random(rng.randrange(1 << 30))
        notes = make(seq, key, spans, opts, r) if make else _one_melody(seq, key, cmap, opts, r)
        sig = tuple((n["start"], n["pitch"]) for n in notes)
        if not notes or sig in seen:
            continue
        seen.add(sig)
        merged = sorted(keep + notes, key=lambda n: (n["start"], n["pitch"]))
        desc = ", ".join(x.lower() for x in (dname, sname) if x)
        out.append({"label": f"{meta['label']} {len(out) + 1} · {desc}", "role": role, "melody": {"notes": merged}})
    return out


# ------------------------------------------------------------------ harmony from melody
def _segments(notes: list[dict], bars: int, rate: str, fits) -> list[tuple[int, int]]:
    if rate == "half":
        return [(s, 8) for s in range(0, bars * 16, 8)]
    if rate != "auto":
        return [(s, 16) for s in range(0, bars * 16, 16)]
    out = []
    for b in range(bars):  # split a bar in two when one chord can't hold its melody
        s = b * 16
        whole = fits(s, 16)
        out += [(s, 8), (s + 8, 8)] if whole < .7 and fits(s, 8) + fits(s + 8, 8) > 2 * whole + .3 else [(s, 16)]
    return out


def _weights(notes: list[dict], s: int, ln: int) -> dict:
    """Pitch class -> weight of the melody inside [s, s+ln): duration, more on the beats and the downbeat.
    Key None: pitch class of the note sounding on the downbeat."""
    w: dict = {}
    for n in notes:
        a, b = max(s, n["start"]), min(s + ln, n["start"] + n["len"])
        if b <= a:
            continue
        k = (b - a) * (1.5 if n["start"] % 4 == 0 else 1.0) * (2.0 if n["start"] == s else 1.0)
        w[n["pitch"] % 12] = w.get(n["pitch"] % 12, 0) + k
        if a == s:
            w[None] = n["pitch"] % 12
    return w


def _fit_score(ch: dict, w: dict, scale: set[int]) -> float:
    """How well a chord holds the melody of a segment, about -1..1 (0 for an empty segment)."""
    down = w.get(None)
    w = {pc: k for pc, k in w.items() if pc is not None}
    tot = sum(w.values())
    if not tot:
        return 0.0
    s = .15 * tot if down == ch["root"] else 0.0  # the downbeat note as the root: the most stable reading
    for pc, k in w.items():
        if pc in ch["pcs"]:
            s += k
        else:
            s -= (.15 if pc in scale else .6) * k
            if (pc + 1) % 12 in ch["pcs"] or (pc - 1) % 12 in ch["pcs"]:
                s -= .25 * k  # a semitone against a chord tone
    return s / tot - .03 * max(0, len(ch["pcs"]) - 3)


def harmonize(seq: dict, pool: list[dict], key: dict, bigrams, opts: dict | None = None, seed: int = 1,
              count: int = 4) -> list[dict]:
    """Up to `count` harmony versions for the melody of seq: every segment gets the pack chord that holds
    its melody best, chained with the same transition scores as the next-chord suggestions (Viterbi)."""
    opts = opts or {}
    notes = notes_of(seq)
    if not notes or not pool:
        return []
    end = max(n["start"] + n["len"] for n in notes)
    bars = max(int(seq.get("bars", 4)), -(-end // 16))
    scale = _scale(key)
    # candidates: one per (root, pitch classes)
    cands, seen = [], set()
    for c in pool:
        d = harmony.describe(c)
        sig = (d["root"], frozenset(d["pcs"]))
        if d["notes"] and sig not in seen:
            seen.add(sig)
            cands.append((c, d))
    big_max = max(bigrams.values(), default=0)
    trans = [[harmony.transition(a, b, key, bigrams, big_max)[0] for _, b in cands] for _, a in cands]
    start = [harmony._start_score(d, key)[0] for _, d in cands]
    final = [.8 if theory.function(d["root"], d["quality"], d["pcs"], key["tonic"], key["mode"]) == "T"
             and d["root"] == key["tonic"] else 0 for _, d in cands]

    def best_fit(s, ln):
        w = _weights(notes, s, ln)
        return max((_fit_score(d, w, scale) for _, d in cands), default=0)

    rate = opts.get("rate", "bar")
    segs = _segments(notes, bars, rate, best_fit)
    fit = [[_fit_score(d, _weights(notes, s, ln), scale) for _, d in cands] for s, ln in segs]
    rng = random.Random(seed)
    N, S = len(cands), len(segs)
    out, used, sigs = [], [set() for _ in segs], set()
    for v in range(count * 2):
        if len(out) >= count:
            break
        noise = .0 if v == 0 else .25
        f = [[x + rng.gauss(0, noise) - (.35 if j in used[i] else 0) for j, x in enumerate(row)] for i, row in enumerate(fit)]
        score = [2.2 * f[0][j] + .5 * start[j] for j in range(N)]
        back = []
        for i in range(1, S):
            nxt, bp = [], []
            for j in range(N):
                k = max(range(N), key=lambda k: score[k] + .6 * trans[k][j] - (.5 if k == j else 0))
                bp.append(k)
                nxt.append(score[k] + .6 * trans[k][j] - (.5 if k == j else 0) + 2.2 * f[i][j] + (final[j] if i == S - 1 else 0))
            score, back = nxt, back + [bp]
        j = max(range(N), key=lambda j: score[j])
        path = [j]
        for bp in reversed(back):
            j = bp[j]
            path.append(j)
        path.reverse()
        sig = tuple(path)
        if sig in sigs:
            continue
        sigs.add(sig)
        for i, j in enumerate(path):
            used[i].add(j)
        new = copy.deepcopy(seq)
        new["bars"] = bars
        new["clips"] = _clips(path, segs, cands, notes, key)
        degrees = " – ".join(c["degree"] for c in new["clips"])
        out.append({"label": f"Armonia {len(out) + 1}: {degrees}", "seq": new})
    return out


def _clips(path: list[int], segs: list[tuple[int, int]], cands: list, notes: list[dict], key: dict) -> list[dict]:
    """Merge repeated chords, voice-lead them and keep them under the melody."""
    runs: list[list] = []
    for (s, ln), j in zip(segs, path):
        if runs and runs[-1][0] == j:
            runs[-1][2] += ln
        else:
            runs.append([j, s, ln])
    clips, prev = [], None
    for j, s, ln in runs:
        ch, d = cands[j]
        c = {"id": "k" + uuid.uuid4().hex[:7], "chordId": ch["id"], "name": ch["name"], "root": ch["root"],
             "quality": ch["quality"], "notes": copy.deepcopy(ch["notes"]), "srcKey": ch.get("srcKey"),
             "category": ch.get("category"), "start": s, "len": ln, "transpose": 0, "octave": 0, "inversion": 0,
             "vel": 100, "style": None}
        c = _fit(c, prev or [p for p, _ in c["notes"]], [48, 55, 60, 64])
        under = [n["pitch"] for n in notes if n["start"] < s + ln and n["start"] + n["len"] > s]
        while under and max(p for p, _ in c["notes"]) > min(under) and min(p for p, _ in c["notes"]) >= 36:
            c = bake(dict(c, octave=-1))
        lab = harmony.label(harmony.describe(c), key)
        c["degree"], c["func"] = lab["degree"], lab["func"]
        prev = [p for p, _ in c["notes"]]
        clips.append(c)
    return clips
