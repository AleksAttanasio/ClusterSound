"""Variations of a single chord clip and of a whole progression (deterministic for a given seed)."""
import copy
import random

from . import harmony, theory
from .perform import voicing

CLIP_KINDS = [("voicing", "Voicing"), ("color", "Colore"), ("substitute", "Sostituzione"), ("performance", "Esecuzione")]
PROG_KINDS = [("reharm", "Riarmonizzazione"), ("rhythm", "Ritmo armonico"), ("voicing", "Voice leading"),
              ("richer", "Più ricca"), ("sparser", "Più scarna"), ("performance", "Esecuzione"), ("ending", "Finale")]
_PERF = [
    ("Strum ↑", {"type": "strum", "strum": {"dir": "up", "spread": 30}}),
    ("Strum alternato a ottavi", {"type": "rhythm", "rhythm": {"pattern": "eighths", "hit": "strum"}, "strum": {"dir": "alt", "spread": 18}, "gate": .9}),
    ("Arpeggio su-giù 1/8", {"type": "arp", "arp": {"mode": "updown", "rate": "1/8", "octaves": 1}, "gate": .9}),
    ("Arpeggio 1/16 su due ottave", {"type": "arp", "arp": {"mode": "up", "rate": "1/16", "octaves": 2}, "gate": .7}),
    ("Offbeat staccato", {"type": "rhythm", "rhythm": {"pattern": "offbeat", "hit": "block"}, "gate": .5}),
    ("Tresillo con strum", {"type": "rhythm", "rhythm": {"pattern": "tresillo", "hit": "strum"}, "strum": {"dir": "up", "spread": 14}, "gate": .8}),
    ("Sincopato house", {"type": "rhythm", "rhythm": {"pattern": "syncopated", "hit": "block"}, "gate": .7}),
    ("Block umanizzato", {"type": "block", "humanize": {"timing": 12, "vel": 10}, "velCurve": "bass"}),
    ("Alterna block / strum ogni battuta", {"type": "block", "alternate": {"every": "bar", "tokens": ["block", "strum_up"]}}),
    ("Ottavi: block, strum ↑, strum ↓", {"type": "rhythm", "rhythm": {"pattern": "eighths", "hit": "block"}, "gate": .8,
                                         "alternate": {"every": "hit", "tokens": ["block", "strum_up", "strum_down"]}}),
]
_ENDINGS = {
    "major": [((5, False), (7, False), "IV → V"), ((8, False), (10, False), "bVI → bVII"),
              ((5, False), (5, True), "IV → iv"), ((2, True), (7, False), "ii → V")],
    "minor": [((8, False), (10, False), "VI → VII"), ((5, True), (7, False), "iv → V"),
              ((1, False), (7, False), "bII → V"), ((3, False), (10, False), "III → VII")],
}


def _sorted(seq: dict) -> list[dict]:
    return sorted(seq.get("clips", []), key=lambda c: c["start"])


def bake(clip: dict) -> dict:
    """Clip with inversion/octave/transposition folded into its notes (and its root)."""
    c = copy.deepcopy(clip)
    c["notes"] = voicing(clip)
    c["root"] = (int(clip.get("root", 0)) + int(clip.get("transpose", 0) or 0)) % 12
    c["transpose"] = c["octave"] = c["inversion"] = 0
    if clip.get("transpose"):
        flats = theory.key_uses_flats(c["root"], "major")
        c["name"] = theory.transpose_name(clip.get("name", ""), int(clip["transpose"]), flats)
    return c


def _pitches(clip: dict) -> list[int]:
    return [p for p, _ in voicing(clip)]


def _center(ps: list[int]) -> float:
    return sum(ps) / len(ps) if ps else 60


def _fit(clip: dict, target: list[int], anchor: list[int] | None = None) -> dict:
    """Pick inversion/octave of clip closest to target (smooth voice leading), staying near anchor's register."""
    anchor = anchor or target
    best, best_d = clip, None
    for inv in range(-2, 3):
        for octv in (-1, 0, 1):
            c = dict(clip, inversion=inv, octave=octv)
            ps = _pitches(c)
            if not ps or min(ps) < 24 or max(ps) > 100:
                continue
            d = harmony.voice_distance(target, ps) + .15 * abs(_center(ps) - _center(anchor)) / 3
            if best_d is None or d < best_d - 1e-9:
                best, best_d = c, d
    return bake(best)


def _swap(clip: dict, chord: dict) -> dict:
    """Clip playing another library chord, same place, same style, register fitted to the old one."""
    c = copy.deepcopy(clip)
    c.update(chordId=chord["id"], name=chord["name"], root=chord["root"], quality=chord["quality"],
             notes=copy.deepcopy(chord["notes"]), srcKey=chord.get("srcKey"), transpose=0, octave=0, inversion=0)
    return _fit(c, _pitches(clip))


def _desc(clip: dict) -> dict:
    return harmony.describe(clip)


def _deg(clip: dict, key: dict) -> str:
    return harmony.label(_desc(clip), key)["degree"]


def _same_root(pool: list[dict], d: dict) -> list[dict]:
    return [c for c in pool if c["root"] == d["root"] and theory.is_minor(c["quality"]) == theory.is_minor(d["quality"])]


def _voicings(clip: dict) -> list[tuple[str, list[list[int]]]]:
    base = voicing(clip)
    ps = [p for p, _ in base]
    vel = {p: v for p, v in base}
    out = []
    for inv, name in ((1, "1ª inversione"), (2, "2ª inversione"), (-1, "rivolto verso il basso")):
        out.append((name, voicing(dict(clip, inversion=int(clip.get("inversion", 0) or 0) + inv))))
    if len(ps) >= 4:
        top = sorted(ps)
        d2 = sorted(top[:-2] + [top[-2] - 12, top[-1]])
        out.append(("drop-2", [[p, vel.get(p, vel.get(p + 12, 100))] for p in d2]))
    if len(ps) >= 3:
        s = sorted(ps)
        op = sorted([s[0], s[1] + 12] + s[2:])
        out.append(("aperto (open voicing)", [[p, vel.get(p, vel.get(p - 12, 100))] for p in op]))
        bass = s[0]
        close = sorted({bass} | {bass + ((p - bass) % 12 or 12) for p in s[1:]})
        out.append(("stretto (close voicing)", [[p, 100] for p in close]))
    if ps and min(ps) >= 36:
        out.append(("basso raddoppiato all'ottava", sorted(base + [[min(ps) - 12, vel[min(ps)]]])))
    seen, uniq = {tuple(ps)}, []
    for name, notes in out:
        k = tuple(sorted(p for p, _ in notes))
        if k not in seen and notes:
            seen.add(k)
            uniq.append((name, notes))
    return uniq


def vary_clip(seq: dict, clip_id: str, kinds: list[str], seed: int, pool: list[dict], key: dict,
              bigrams) -> list[dict]:
    clips = _sorted(seq)
    idx = next((i for i, c in enumerate(clips) if c["id"] == clip_id), None)
    if idx is None:
        return []
    clip = clips[idx]
    prev = clips[idx - 1] if idx > 0 else None
    nxt = clips[idx + 1] if idx + 1 < len(clips) else None
    rng = random.Random(seed)
    d = _desc(clip)
    out = []
    if "voicing" in kinds:
        vs = _voicings(clip)
        rng.shuffle(vs)
        if prev:
            fit = _fit(bake(clip), _pitches(prev), _pitches(clip))
            if _pitches(fit) != _pitches(clip):
                vs.insert(0, ("voice leading minimo dal precedente", fit["notes"]))
        for name, notes in vs[:4]:
            c = bake(clip)
            c["notes"] = notes
            out.append({"kind": "voicing", "label": name, "clip": c})
    if "color" in kinds:
        same = [c for c in _same_root(pool, d) if c["id"] != clip.get("chordId")]
        rng.shuffle(same)
        n0 = len(clip.get("notes", []))
        same.sort(key=lambda c: (len(c["notes"]) == n0, rng.random()))
        for ch in same[:4]:
            out.append({"kind": "color", "label": f"{clip.get('name', '')} → {ch['name']}", "clip": _swap(clip, ch)})
    if "substitute" in kinds:
        cands = [c for c in pool if c["root"] != d["root"]]
        ranked = harmony.suggest([prev] if prev else [], cands, key, bigrams, nxt=nxt, limit=8)
        if not prev and not nxt:
            f = harmony.label(d, key)["func"]
            ranked.sort(key=lambda r: (r["func"] != f, -r["score"]))
        picks = ranked[:2] + rng.sample(ranked[2:], min(2, len(ranked[2:])))
        for r in picks:
            why = ", ".join(r["reasons"][:2])
            out.append({"kind": "substitute", "label": f"{_deg(clip, key)} → {r['degree']} ({r['chord']['name']})" + (f" · {why}" if why else ""),
                        "clip": _swap(clip, r["chord"])})
    if "performance" in kinds:
        cur = (clip.get("style") or {}).get("type")
        opts = [p for p in _PERF if p[1]["type"] != cur or "alternate" in p[1]]
        for name, st in rng.sample(opts, min(4, len(opts))):
            c = copy.deepcopy(clip)
            c["style"] = {**copy.deepcopy(st), "humanize": {**st.get("humanize", {"timing": 0, "vel": 0}), "seed": rng.randrange(1, 1 << 30)}}
            out.append({"kind": "performance", "label": name, "clip": c})
    return out


# ------------------------------------------------------------------ progression
def _reharm(seq, amount, rng, pool, key, bigrams):
    clips = _sorted(seq)
    inner = list(range(1, len(clips) - 1))
    if not inner:
        return None
    k = max(1, round(amount * len(inner)))
    changes = []
    for i in sorted(rng.sample(inner, min(k, len(inner)))):
        d = _desc(clips[i])
        cands = [c for c in pool if c["root"] != d["root"]]
        ranked = harmony.suggest([clips[i - 1]], cands, key, bigrams, nxt=clips[i + 1], limit=5)
        if not ranked:
            continue
        r = ranked[min(int(rng.random() ** 2 * len(ranked)), len(ranked) - 1)]
        changes.append(f"{_deg(clips[i], key)} → {r['degree']}")
        clips[i] = _swap(clips[i], r["chord"])
    return (clips, "Riarmonizzata: " + ", ".join(changes)) if changes else None


def _rhythm(seq, amount, rng, pool, key, bigrams):
    clips = [copy.deepcopy(c) for c in _sorted(seq)]
    pairs = [i for i in range(1, len(clips)) if clips[i - 1]["start"] + clips[i - 1]["len"] == clips[i]["start"]]
    if not pairs and not any(c["len"] >= 8 for c in clips):
        return None
    changes = []
    n = max(1, round(amount * max(1, len(pairs))))
    ops = ["push", "longshort", "split"]
    for _ in range(n * 3):
        if len(changes) >= n:
            break
        op = rng.choice(ops)
        if op == "push" and pairs:
            i = rng.choice(pairs)
            a, b = clips[i - 1], clips[i]
            if a["len"] >= 6 and b["start"] % 4 == 0 and a["start"] + a["len"] == b["start"]:
                a["len"] -= 2
                b["start"] -= 2
                b["len"] += 2
                changes.append(f"anticipo di un ottavo su {b.get('name', '')}")
        elif op == "longshort" and pairs:
            i = rng.choice(pairs)
            a, b = clips[i - 1], clips[i]
            L = a["len"]
            if L == b["len"] and L >= 8 and L % 4 == 0 and a["start"] + L == b["start"]:
                a["len"] = L + L // 2
                b["start"] = a["start"] + a["len"]
                b["len"] = L // 2
                changes.append(f"{a.get('name', '')} lungo, {b.get('name', '')} corto")
        elif op == "split":
            cand = [j for j, c in enumerate(clips) if c["len"] >= 16 and c["len"] % 2 == 0]
            if not cand:
                continue
            j = rng.choice(cand)
            c = clips[j]
            nxt = clips[j + 1] if j + 1 < len(clips) else None
            ranked = harmony.suggest([c], [x for x in pool if x["root"] != c["root"]], key, bigrams, nxt=nxt, limit=4)
            if not ranked:
                continue
            half = c["len"] // 2
            c["len"] = half
            new = _swap(dict(c, id=f"{c['id']}s{rng.randrange(1 << 20)}", start=c["start"] + half), ranked[0]["chord"])
            clips.insert(j + 1, new)
            pairs = [i for i in range(1, len(clips)) if clips[i - 1]["start"] + clips[i - 1]["len"] == clips[i]["start"]]
            changes.append(f"{c.get('name', '')} diviso con {new['name']}")
    return (clips, "Ritmo armonico: " + "; ".join(changes)) if changes else None


def _revoice(seq, amount, rng, pool, key, bigrams):
    clips = _sorted(seq)
    if len(clips) < 2:
        return None
    out = [bake(clips[0])]
    for c in clips[1:]:
        out.append(_fit(bake(c), _pitches(out[-1]), _pitches(c)))
    if [_pitches(c) for c in out] == [_pitches(c) for c in clips]:
        return None
    moved = sum(harmony.voice_distance(_pitches(a), _pitches(b)) for a, b in zip(out, out[1:]))
    return out, f"Voice leading minimo (movimento medio {moved / (len(out) - 1):.1f} semitoni)"


def _density(seq, amount, rng, pool, key, bigrams, richer: bool):
    clips = _sorted(seq)
    idx = list(range(len(clips)))
    rng.shuffle(idx)
    idx = sorted(idx[:max(1, round(amount * len(clips))) if amount < 1 else len(clips)])
    changes = []
    for i in idx:
        c = clips[i]
        d = _desc(c)
        n = len(d["notes"])
        same = [x for x in _same_root(pool, d) if x["id"] != c.get("chordId") and {n % 12 for n, _ in x["notes"]} != d["pcs"]]
        same = [x for x in same if (len(x["notes"]) > n if richer else len(x["notes"]) < n or x["category"] == "triad")]
        if not same:
            continue
        same.sort(key=lambda x: (-len(x["notes"]) if richer else (x["category"] != "triad", len(x["notes"]))))
        ch = rng.choice(same[:3]) if richer else same[0]
        changes.append(f"{c.get('name', '')} → {ch['name']}")
        clips[i] = _swap(c, ch)
    if not changes:
        return None
    return clips, ("Più ricca: " if richer else "Più scarna: ") + ", ".join(changes)


def _perf(seq, amount, rng, pool, key, bigrams):
    clips = [copy.deepcopy(c) for c in _sorted(seq)]
    name, st = rng.choice(_PERF)
    seed = rng.randrange(1, 1 << 30)
    for c in clips:
        c["style"] = {**copy.deepcopy(st), "humanize": {**st.get("humanize", {"timing": round(6 * amount), "vel": round(8 * amount)}), "seed": seed}}
    return clips, f"Esecuzione: {name}"


def _ending(seq, amount, rng, pool, key, bigrams):
    clips = _sorted(seq)
    if len(clips) < 2:
        return None
    opts = list(_ENDINGS[key["mode"]])
    rng.shuffle(opts)
    for a, b, name in opts:
        picks = []
        for (iv, minor), c in ((a, clips[-2]), (b, clips[-1])):
            root = (key["tonic"] + iv) % 12
            m = [x for x in pool if x["root"] == root and theory.is_minor(x["quality"]) == minor]
            if not m:
                break
            n0 = len(c.get("notes", []))
            m.sort(key=lambda x: (abs(len(x["notes"]) - n0), rng.random()))
            picks.append(m[0])
        if len(picks) == 2 and [p["root"] for p in picks] != [_desc(clips[-2])["root"], _desc(clips[-1])["root"]]:
            clips[-2], clips[-1] = _swap(clips[-2], picks[0]), _swap(clips[-1], picks[1])
            return clips, f"Finale: {name} ({picks[0]['name']} → {picks[1]['name']})"
    return None


_GEN = {"reharm": _reharm, "rhythm": _rhythm, "voicing": _revoice, "performance": _perf, "ending": _ending,
        "richer": lambda *a: _density(*a, richer=True), "sparser": lambda *a: _density(*a, richer=False)}


def vary_progression(seq: dict, kinds: list[str], amount: float, seed: int, pool: list[dict], key: dict,
                     bigrams, count: int = 4) -> list[dict]:
    """Up to `count` alternative sequences, each with a readable label of what changed."""
    kinds = [k for k in kinds if k in _GEN] or ["reharm"]
    amount = max(.05, min(1.0, float(amount)))
    rng = random.Random(seed)
    out, seen = [], set()
    for attempt in range(count * 4):
        if len(out) >= count:
            break
        kind = kinds[attempt % len(kinds)]
        res = _GEN[kind](copy.deepcopy(seq), amount, random.Random(rng.randrange(1 << 30)), pool, key, bigrams)
        if not res:
            continue
        clips, label = res
        sig = repr([(c["start"], c["len"], _pitches(c), c.get("style")) for c in clips])
        if sig in seen:
            continue
        seen.add(sig)
        new = copy.deepcopy(seq)
        new["clips"] = clips
        out.append({"kind": kind, "label": label, "seq": new})
    return out
