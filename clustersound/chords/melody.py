"""Melody of a harmony version: render it, normalise imported notes, generate a melody over the chords and
harmonise a melody with the chords of the pack.

    seq["melody"] = {"notes": [{"id", "start", "len", "pitch", "vel"}]}   # start/len in sixteenths, monophonic

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
# onsets of one bar (sixteenths), per density
_RHYTHMS = {
    "low": [[0, 8], [0, 12], [0, 4, 8], [0, 6, 8], [0, 8, 12], [0]],
    "mid": [[0, 4, 8, 12], [0, 4, 6, 8], [0, 2, 4, 8, 12], [0, 6, 8, 12], [0, 3, 6, 8, 12], [0, 4, 8, 10, 12]],
    "high": [[0, 2, 4, 6, 8, 10, 12, 14], [0, 2, 4, 6, 8, 12, 14], [0, 3, 4, 6, 8, 10, 11, 12, 14],
             [0, 1, 2, 4, 6, 8, 10, 12], [0, 2, 3, 4, 6, 8, 10, 12, 14]],
}


def _uid() -> str:
    return "m" + uuid.uuid4().hex[:7]


def notes_of(seq: dict) -> list[dict]:
    return sorted((seq.get("melody") or {}).get("notes") or [], key=lambda n: n["start"])


# ------------------------------------------------------------------ render
def render(seq: dict) -> list[tuple[int, int, int, int]]:
    """[(start tick, end tick, pitch, velocity)] with the swing of the Modalità, cut at the sequence length."""
    length = int(seq.get("bars", 4)) * BAR
    swing = float(mode_of(seq).get("swing", 50))
    out = []
    for n in notes_of(seq):
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


def generate(seq: dict, key: dict, opts: dict | None = None, seed: int = 1, count: int = 4) -> list[dict]:
    """Up to `count` melodies over the chords of seq: chord tones on the beats, scale steps in between,
    phrases of 2-4 bars answered by a variation of their rhythm. opts: density, contour, lo, hi, fromBar, toBar
    (bars outside the range keep the current melody)."""
    opts = opts or {}
    cmap = _chord_map(seq)
    rng = random.Random(seed)
    total = int(seq.get("bars", 4))
    b0 = max(0, int(opts.get("fromBar", 0) or 0))
    b1 = min(total, int(opts.get("toBar", total) or total))
    keep = [n for n in notes_of(seq) if n["start"] < b0 * 16 or n["start"] >= b1 * 16]
    dname = dict(DENSITIES).get(opts.get("density", "mid"), "")
    cname = dict(CONTOURS).get(opts.get("contour", "arch"), "")
    out, seen = [], set()
    for attempt in range(count * 3):
        if len(out) >= count:
            break
        notes = _one_melody(seq, key, cmap, opts, random.Random(rng.randrange(1 << 30)))
        sig = tuple((n["start"], n["pitch"]) for n in notes)
        if not notes or sig in seen:
            continue
        seen.add(sig)
        merged = sorted(keep + notes, key=lambda n: n["start"])
        out.append({"label": f"Melodia {len(out) + 1} · {dname.lower()}, {cname.lower()}", "melody": {"notes": merged}})
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
