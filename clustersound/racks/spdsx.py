"""Roland SPD-SX rack: 9 pads plus the two trigger inputs, the "configurations" that group them and the
rules that keep a kit playable.

Pads are indexed 0-8 for the instrument's pads 1-9 (1-3 the narrow top row, 4-6 the middle row, 7-9 the
row closest to the player), 9 = Trigger 1 (the kick pedal) and 10 = Trigger 2. MIDI notes are the
SPD-SX factory defaults (pads 60-68, Trigger 1 69, Trigger 2 70).
A rack is the same JSON as the 64-pad one, with "device": "spdsx" and
"triggers": {"trig1": bool, "trig2": bool}; groups settings are keyed "<geometry>:<group key>".
"""
import random

from ..i18n import N_, tr
from . import layouts

PADS = 11
TRIG1, TRIG2 = 9, 10
NOTES = list(range(60, 69)) + [69, 70]
PAD_LABELS = [str(i + 1) for i in range(9)] + [N_("Pedal (Trig 1)"), "Trig 2"]
KICK_PAD = 7  # pad 8, bottom centre: the kick goes here when no pedal is connected
DEFAULT_TRIGGERS = {"trig1": True, "trig2": False}


def _p(*nums: int) -> list[int]:
    return [n - 1 for n in nums]


# id -> (label, [(pads in fill order, family)]); the first pad of a group gets the seed
CONFIGS = {
    "spd_kit": (N_("Classic kit"), [(_p(1, 2, 3), "hatscym"), (_p(5, 4, 6), "snareclap"), (_p(8, 7, 9), "tom")]),
    "spd_rows": (N_("Rows"), [(_p(1, 2, 3), "hats"), (_p(5, 4, 6), "snareclap"), (_p(7, 8, 9), "perc")]),
    "spd_cols": (N_("Columns"), [(_p(1, 4, 7), "hats"), (_p(5, 2, 8), "snareclap"), (_p(3, 6, 9), "perc")]),
    "spd_cross": (N_("Cross"), [(_p(5), "snare"), (_p(2, 4, 6, 8), "perc"), (_p(1, 3, 7, 9), "hatscym")]),
    "spd_perc": (N_("Percussion"), [(_p(1, 2, 3), "shaker"), (_p(4, 5, 6), "perc"), (_p(7, 8, 9), "perc")]),
    "spd_free": (N_("Free"), [([p], "any") for p in range(9)]),
}
GEOMETRIES = list(CONFIGS)
TRIGGER_FAMILIES = {"t1": "kick", "t2": "cymbal"}

# how many pads (pedal included) a role may take before the kit stops being playable
ROLES = {
    "kick": {"kick", "808", "kick808"},
    "snare": {"snare", "clap", "snareclap"},
    "cymbal": {"chat", "ohat", "hats", "cymbal", "hatscym"},
}
ROLE_CAPS = {"kick": 2, "snare": 3, "cymbal": 5}
ROLE_LABELS = {"kick": "kick", "snare": "snare / clap", "cymbal": N_("hat / cymbals")}
# role of a sample by its class, for groups of a generic family (a rimshot is not a snare to play)
_CLASS_ROLE = {"kick": "kick", "sub808": "kick", "snare": "snare", "clap": "snare", "snap": "snare",
               "closed_hat": "cymbal", "open_hat": "cymbal", "ride": "cymbal", "crash": "cymbal", "cymbal_other": "cymbal"}

# random_config: families a group may switch to while keeping its role
_VARIANTS = {
    "snareclap": ["snareclap", "snare", "clap"],
    "snare": ["snare", "clap"],
    "hats": ["hats", "hatscym", "chat"],
    "hatscym": ["hatscym", "hats"],
    "tom": ["tom", "perc"],
    "perc": ["perc", "shaker", "tom", "rim"],
    "shaker": ["shaker", "perc"],
}
_TRIG2_VARIANTS = ["cymbal", "perc", "fx", "tom", "snare", "clap"]


def triggers_of(rack: dict | None) -> dict:
    t = (rack or {}).get("triggers") or {}
    return {k: bool(t.get(k, v)) for k, v in DEFAULT_TRIGGERS.items()}


def layout(geometry: str, triggers: dict | None = None) -> list[tuple[str, list[int], str]]:
    """Effective groups: (key, pads in fill order, default family). Without the pedal the kick moves to
    pad 8 (its own group, key "k"); a disconnected trigger has no group."""
    if geometry not in CONFIGS:
        raise ValueError(f"unknown geometry {geometry!r}")
    t = triggers if triggers is not None else DEFAULT_TRIGGERS
    t = triggers_of({"triggers": t})
    move_kick = not t["trig1"] and geometry != "spd_free"
    out = []
    for g, (pads, fam) in enumerate(CONFIGS[geometry][1]):
        pads = [p for p in pads if not (move_kick and p == KICK_PAD)]
        if pads:
            out.append((str(g), pads, fam))
    if t["trig1"]:
        out.append(("t1", [TRIG1], TRIGGER_FAMILIES["t1"]))
    if t["trig2"]:
        out.append(("t2", [TRIG2], TRIGGER_FAMILIES["t2"]))
    if move_kick:
        out.append(("k", [KICK_PAD], "kick"))
    return out


def groups(geometry: str, triggers: dict | None = None) -> list[list[int]]:
    return [pads for _, pads, _ in layout(geometry, triggers)]


def group_keys(geometry: str, triggers: dict | None = None) -> list[str]:
    return [k for k, _, _ in layout(geometry, triggers)]


def default_families(geometry: str, triggers: dict | None = None) -> list[str]:
    return [f for _, _, f in layout(geometry, triggers)]


def active_pads(rack: dict) -> list[int]:
    return sorted(p for g in groups(rack["geometry"], triggers_of(rack)) for p in g)


def new_rack(name: str = "Kit") -> dict:
    return {"device": "spdsx", "name": name, "geometry": "spd_kit", "triggers": dict(DEFAULT_TRIGGERS),
            "pads": [None] * PADS, "groups": {}}


def validate(rack: dict) -> dict:
    r = dict(rack or {})
    r["device"] = "spdsx"
    r["name"] = str(r.get("name") or "Kit")[:80]
    if r.get("geometry") not in CONFIGS:
        r["geometry"] = "spd_kit"
    r["triggers"] = triggers_of(r)
    r.pop("mapping", None)
    r.pop("quads", None)
    pads = list(r.get("pads") or [])[:PADS]
    r["pads"] = [p if isinstance(p, dict) and (p.get("path") or p.get("url")) else None for p in pads]
    r["pads"] += [None] * (PADS - len(r["pads"]))
    r["groups"] = r.get("groups") if isinstance(r.get("groups"), dict) else {}
    return r


# ---------------------------------------------------------------- playability
def role_of(family: str) -> str | None:
    return next((role for role, fams in ROLES.items() if family in fams), None)


def _role_counts(rack: dict, families: list[str]) -> dict[str, int]:
    """Pads per role: a group's family decides; groups of a generic family ("any", "fx"…) count the class
    of the sample on each pad."""
    counts = dict.fromkeys(ROLES, 0)
    for pads, fam in zip(groups(rack["geometry"], triggers_of(rack)), families):
        role = role_of(fam)
        for p in pads:
            r = role
            if r is None:
                ref = rack["pads"][p]
                r = _CLASS_ROLE.get(ref.get("cls")) if ref else None
            if r:
                counts[r] += 1
    return counts


def _families(rack: dict) -> list[str]:
    return [s["family"] for s in layouts.group_settings(rack)]


def playability(rack: dict) -> list[str]:
    """Warnings for roles that take more pads than a player can use."""
    rack = validate(rack)
    counts = _role_counts(rack, _families(rack))
    return [tr("{n} {role} pads: too many to play comfortably (at most {max})", n=n, role=tr(ROLE_LABELS[role]), max=ROLE_CAPS[role])
            for role, n in counts.items() if n > ROLE_CAPS[role]]


def allowed_families(rack: dict) -> list[list[str]]:
    """For every group, the families it can switch to without breaking a role's cap (other groups as they
    are); on a kit that is already over a cap, the ones that do not make it worse."""
    rack = validate(rack)
    fams = _families(rack)
    now = _role_counts(rack, fams)
    out = []
    for g in range(len(fams)):
        ok = []
        for f, _, _ in layouts.FAMILIES:
            counts = _role_counts(rack, fams[:g] + [f] + fams[g + 1:])
            if all(counts[r] <= max(ROLE_CAPS[r], now[r]) for r in ROLES):
                ok.append(f)
        out.append(ok)
    return out


def random_config(rng: random.Random | int | None = None, triggers: dict | None = None,
                  geometry: str | None = None) -> dict:
    """A random playable layout: {"geometry", "groups"} where groups overrides each group's family with a
    variant of the same role (the pedal always keeps a kick)."""
    rng = rng if isinstance(rng, random.Random) else random.Random(rng)
    t = triggers_of({"triggers": triggers})
    for _ in range(50):
        geo = geometry or rng.choice([g for g in GEOMETRIES if g != "spd_free"])
        fams = []
        for key, pads, fam in layout(geo, t):
            if key == "t2":
                fam = rng.choice(_TRIG2_VARIANTS)
            elif key not in ("t1", "k"):
                fam = rng.choice(_VARIANTS.get(fam, [fam]))
            fams.append(fam)
        probe = validate({"geometry": geo, "triggers": t})
        counts = _role_counts(probe, fams)
        if all(counts[r] <= ROLE_CAPS[r] for r in ROLES):
            return {"geometry": geo,
                    "groups": {f"{geo}:{k}": {"family": f} for k, f in zip(group_keys(geo, t), fams)}}
    raise RuntimeError("no playable configuration found")


def ui_layout() -> dict:
    return {
        "pads": PADS, "trig1": TRIG1, "trig2": TRIG2, "kick_pad": KICK_PAD,
        "notes": NOTES, "labels": [tr(x) for x in PAD_LABELS],
        "configs": [{"id": g, "label": tr(CONFIGS[g][0])} for g in GEOMETRIES],
        "caps": ROLE_CAPS,
        # effective groups per configuration and trigger state, keyed "<geometry>|<trig1><trig2>" (e.g. "spd_kit|10")
        "layouts": {f"{g}|{int(t1)}{int(t2)}": {"id": g, "groups": groups(g, t), "keys": group_keys(g, t),
                                               "families": default_families(g, t)}
                    for g in GEOMETRIES for t1 in (True, False) for t2 in (True, False)
                    for t in [{"trig1": t1, "trig2": t2}]},
    }
