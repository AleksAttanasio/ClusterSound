"""Next-chord suggestions: harmonic function, named cadences, root motion, voice leading and how often the
pack's own progressions make the same move."""
from collections import Counter

from . import theory
from .perform import voicing

# function -> function: how natural the move is
_FLOW = {
    "T": {"T": .45, "S": 1.0, "D": .75, "C": .6},
    "S": {"T": .6, "S": .45, "D": 1.0, "C": .55},
    "D": {"T": 1.0, "S": .3, "D": .35, "C": .45},
    "C": {"T": .8, "S": .6, "D": .7, "C": .45},
}
# (mode, from interval, to interval, minor-from, minor-to | None = any) -> (bonus, label)
_CADENCES = [
    (None, 7, 0, None, None, .6, "cadenza perfetta"),
    (None, 11, 0, True, None, .3, "sensibile → tonica"),
    (None, 5, 0, False, None, .35, "cadenza plagale"),
    ("major", 5, 0, True, False, .4, "plagale minore (iv → I)"),
    ("minor", 5, 0, True, True, .3, "plagale"),
    (None, 2, 7, None, None, .45, "ii → V"),
    ("major", 7, 9, False, True, .35, "cadenza d'inganno"),
    ("minor", 7, 8, False, False, .35, "cadenza d'inganno"),
    ("major", 8, 10, False, False, .35, "bVI → bVII"),
    ("major", 10, 0, False, False, .35, "cadenza mixolidia"),
    ("minor", 8, 10, False, False, .35, "VI → VII"),
    ("minor", 10, 0, False, True, .3, "VII → i"),
    ("major", 1, 0, False, False, .3, "napoletana → I"),
    (None, 0, 5, False, None, .15, "verso la sottodominante"),
]


def describe(clip_or_chord: dict) -> dict:
    """Effective chord of a clip (or a library chord): pitches, root and quality after transposition."""
    notes = [p for p, _ in voicing(clip_or_chord)] if "start" in clip_or_chord else [p for p, _ in clip_or_chord["notes"]]
    root = (int(clip_or_chord.get("root", theory.guess_root(notes))) + int(clip_or_chord.get("transpose", 0) or 0)) % 12
    pcs = {n % 12 for n in notes}
    return {"notes": notes, "root": root, "quality": theory.quality(pcs, root) if notes else "maj", "pcs": pcs,
            "id": clip_or_chord.get("chordId", clip_or_chord.get("id"))}


def label(ch: dict, key: dict) -> dict:
    t, m = key["tonic"], key["mode"]
    return {"degree": theory.degree_label(ch["root"], ch["quality"], t, m),
            "func": theory.function(ch["root"], ch["quality"], ch["pcs"], t, m)}


def voice_distance(a: list[int], b: list[int]) -> float:
    """Average semitone movement: every note of b to the nearest note of a (and back), averaged."""
    if not a or not b:
        return 6.0
    d1 = sum(min(abs(x - y) for y in a) for x in b) / len(b)
    d2 = sum(min(abs(x - y) for y in b) for x in a) / len(a)
    return (d1 + d2) / 2


def transition(a: dict, b: dict, key: dict, bigrams: Counter, big_max: float) -> tuple[float, list[str]]:
    t, mode = key["tonic"], key["mode"]
    fa = theory.function(a["root"], a["quality"], a["pcs"], t, mode)
    fb = theory.function(b["root"], b["quality"], b["pcs"], t, mode)
    s, why = _FLOW[fa][fb], []
    da, db = (a["root"] - t) % 12, (b["root"] - t) % 12
    ma, mb = theory.is_minor(a["quality"]), theory.is_minor(b["quality"])
    for m, x, y, qa, qb, bonus, name in _CADENCES:
        if (m in (None, mode)) and da == x and db == y and qa in (None, ma) and qb in (None, mb):
            s += bonus
            why.append(name)
            break
    iv = (b["root"] - a["root"]) % 12
    if iv == 5:
        s += .35
        why.append("basso scende di quinta")
    elif iv == 7:
        s += .15
    elif iv in (1, 2, 10, 11):
        s += .15
        why.append("moto per grado")
    elif iv == 6:
        s -= .3
    elif iv == 0:
        s -= .3 if a["quality"] != b["quality"] else .7
        if a["quality"] != b["quality"]:
            why.append("stesso basso, colore diverso")
    common = len(a["pcs"] & b["pcs"])
    s += .08 * min(common, 3)
    if common >= 2 and iv != 0:
        why.append(f"{common} note comuni")
    vl = voice_distance(a["notes"], b["notes"])
    s += max(0.0, .3 - .03 * vl)
    if vl <= 2.0 and iv != 0:
        why.append("voice leading fluido")
    if big_max:
        w = bigrams.get((theory.degree_key(a["root"], a["quality"], t), theory.degree_key(b["root"], b["quality"], t)), 0) / big_max
        s += .6 * w
        if w >= .25:
            why.append("frequente nel pack")
    if fb == "C":
        why.append("prestito modale")
    return s, why


def _start_score(b: dict, key: dict) -> tuple[float, list[str]]:
    t, mode = key["tonic"], key["mode"]
    f = theory.function(b["root"], b["quality"], b["pcs"], t, mode)
    s = {"T": 1.0, "S": .55, "D": .35, "C": .2}[f]
    why = []
    if (b["root"] - t) % 12 == 0 and f == "T":
        s += .4
        why.append("tonica: apre la progressione")
    elif f == "T":
        why.append("funzione di tonica")
    elif f == "S":
        why.append("partenza sospesa (sottodominante)")
    return s, why


def suggest(prev: list[dict], candidates: list[dict], key: dict, bigrams: Counter, nxt: dict | None = None,
            limit: int = 8) -> list[dict]:
    """Rank candidates (library chords) to follow prev[-1] (and lead into nxt). One entry per root and
    quality: the variant with the smoothest voice leading wins, the others are listed as alternatives."""
    big_max = max(bigrams.values(), default=0)
    a = describe(prev[-1]) if prev else None
    before = describe(prev[-2]) if len(prev) > 1 else None
    n = describe(nxt) if nxt else None
    groups: dict = {}
    for c in candidates:
        b = describe(c)
        if a:
            s, why = transition(a, b, key, bigrams, big_max)
            if a["id"] and a["id"] == b["id"]:
                s -= .8
            if before and before["root"] == b["root"] and before["quality"] == b["quality"]:
                s -= .15  # A B A ping-pong
        else:
            s, why = _start_score(b, key)
        if n:
            s2, why2 = transition(b, n, key, bigrams, big_max)
            s += .6 * s2
            why += [f"→ {w}" for w in why2[:1]]
        g = (b["root"], theory.is_minor(b["quality"]), b["quality"] == "dim")
        groups.setdefault(g, []).append((s, why, c, b))
    ranked = []
    for items in groups.values():
        items.sort(key=lambda x: -x[0])
        s, why, c, b = items[0]
        ranked.append({"chord": c, "score": s, "reasons": list(dict.fromkeys(why))[:4], **label(b, key),
                       "alts": [x[2] for x in items[1:6]]})
    ranked.sort(key=lambda r: -r["score"])
    ranked = ranked[:limit]
    top = ranked[0]["score"] if ranked else 1
    lo = min((r["score"] for r in ranked), default=0)
    for r in ranked:
        r["score"] = round(.35 + .65 * (r["score"] - lo) / (top - lo), 3) if top > lo else 1.0
    return ranked


def related_keys(key: dict) -> list[dict]:
    """Keys a free progression can borrow from: dominant, subdominant, relative and parallel."""
    t, m = key["tonic"], key["mode"]
    rel = {"tonic": (t + 9) % 12, "mode": "minor"} if m == "major" else {"tonic": (t + 3) % 12, "mode": "major"}
    par = {"tonic": t, "mode": "minor" if m == "major" else "major"}
    return [{"tonic": (t + 7) % 12, "mode": m}, {"tonic": (t + 5) % 12, "mode": m}, rel, par]
