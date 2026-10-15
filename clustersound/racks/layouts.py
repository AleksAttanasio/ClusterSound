"""64-pad rack geometry: pad numbering, MIDI note mappings and the groups each layout splits the grid into.

Pads are numbered row * 8 + col, row 0 at the bottom (the side closest to the player on a Launchpad).
A rack is plain JSON shared with the UI:
{
  "name", "geometry": one of GEOMETRIES, "mapping": "launchpad" | "rows", "quads": see QUAD_BASE,
  "pads": [64 × sample ref or null],
  "groups": {"<geometry>:<group index>": {"family": FAMILIES id, "choke": 0..16, "lock": bool}}
}
Pads do not depend on the geometry: switching it only regroups them.
Racks with "device": "spdsx" (geometries "spd_*") are the Roland SPD-SX's 11 pads: see spdsx.py; the
functions below dispatch to it, a rack without "device" is a 64-pad one.
"""
from .. import taxonomy
from ..i18n import N_, tr

N = 8
PADS = N * N
BASE_NOTE = 36  # C1 in Live
# Live's four 4×4 note blocks by their first note: C = 36-51, D = 52-67, A = 68-83, B = 84-99.
# A 64-pad rack's "quads" names the block at each quadrant, in QUADRANTS order (bottom-left,
# bottom-right, top-left, top-right): "CDAB" is Live's own layout (A B over C D), "CABD" the
# Launchpad's default Drum mode (B D over C A).
QUAD_BASE = {"A": 68, "B": 84, "C": 36, "D": 52}
DEFAULT_QUADS = "CABD"

# id, label, taxonomy classes (empty = anything)
FAMILIES = [
    ("kick", "Kick", ["kick"]),
    ("808", "808 / Sub", ["sub808"]),
    ("kick808", "Kick + 808", ["kick", "sub808"]),
    ("snare", "Snare", ["snare"]),
    ("clap", "Clap / Snap", ["clap", "snap"]),
    ("snareclap", "Snare / Clap / Rim", ["snare", "clap", "snap", "rimshot"]),
    ("rim", "Rim / Wood", ["rimshot", "woodblock"]),
    ("chat", "Closed Hat", ["closed_hat"]),
    ("ohat", "Open Hat", ["open_hat"]),
    ("hats", "Hat", ["closed_hat", "open_hat"]),
    ("cymbal", "Ride / Crash", ["ride", "crash", "cymbal_other"]),
    ("hatscym", "Hat + Cymbal", ["closed_hat", "open_hat", "ride", "crash", "cymbal_other"]),
    ("tom", "Tom", ["tom"]),
    ("shaker", "Shaker / Tamb", ["shaker", "tambourine"]),
    ("perc", "Perc", ["perc_other", "cowbell", "hand_drum", "bell", "woodblock", "shaker", "tambourine"]),
    ("fx", "FX", ["riser", "impact", "downlifter", "noise", "foley"]),
    ("vox", "Vocal", ["vocal", "spoken"]),
    ("any", N_("Any"), []),
]
FAMILY_BY_ID = {f[0]: f for f in FAMILIES}
HAT_FAMILIES = {"chat", "ohat", "hats"}

GEOMETRIES = ["cols8", "blocks2", "blocks4", "quadcols", "free"]
GEOMETRY_LABELS = {
    "cols8": N_("Columns ×8"),
    "blocks2": N_("Blocks 2×2"),
    "blocks4": N_("Blocks 4×4"),
    "quadcols": N_("4×4 in columns"),
    "free": N_("Free"),
}


def pad(row: int, col: int) -> int:
    return row * N + col


def rc(p: int) -> tuple[int, int]:
    return divmod(p, N)


def valid_quads(quads) -> bool:
    return isinstance(quads, str) and sorted(quads) == sorted(QUAD_BASE)


def note_for(p: int, mapping: str = "launchpad", quads: str = DEFAULT_QUADS) -> int:
    """MIDI note of pad p. 'launchpad': four 4×4 blocks of 16 notes placed by quads (see QUAD_BASE),
    each row by row from its bottom-left pad. 'rows': 36 bottom-left, +1 per column, +8 per row."""
    r, c = rc(p)
    if mapping == "rows":
        return BASE_NOTE + p
    quads = quads if valid_quads(quads) else DEFAULT_QUADS
    quadrant = (r >= 4) * 2 + (c >= 4)
    return QUAD_BASE[quads[quadrant]] + 4 * (r % 4) + c % 4


def _block(r0: int, c0: int, h: int, w: int) -> list[int]:
    return [pad(r, c) for r in range(r0, r0 + h) for c in range(c0, c0 + w)]


# quadrants: bottom-left, bottom-right, top-left, top-right
QUADRANTS = [(0, 0), (0, 4), (4, 0), (4, 4)]


def is_spd(rack_or_geometry) -> bool:
    if isinstance(rack_or_geometry, dict):
        return rack_or_geometry.get("device") == "spdsx" or str(rack_or_geometry.get("geometry", "")).startswith("spd_")
    return str(rack_or_geometry).startswith("spd_")


def groups(geometry: str, triggers: dict | None = None) -> list[list[int]]:
    """Pads of each group, in fill order (row by row from the bottom-left, columns bottom to top)."""
    if is_spd(geometry):
        return spdsx.groups(geometry, triggers)
    if geometry == "cols8":
        return [_block(0, c, 8, 1) for c in range(N)]
    if geometry == "blocks2":
        return [_block(r0 + r, c0 + c, 2, 2) for r0, c0 in QUADRANTS for r in (0, 2) for c in (0, 2)]
    if geometry == "blocks4":
        return [_block(r0, c0, 4, 4) for r0, c0 in QUADRANTS]
    if geometry == "quadcols":
        return [_block(r0, c0 + c, 4, 1) for r0, c0 in QUADRANTS for c in range(4)]
    if geometry == "free":
        return [[p] for p in range(PADS)]
    raise ValueError(f"unknown geometry {geometry!r}")


# default family per group, same order as groups()
_DEFAULT_FAMILIES = {
    "cols8": ["kick", "snare", "clap", "chat", "ohat", "perc", "tom", "cymbal"],
    "blocks2": ["kick", "kick", "snare", "clap",       # bottom-left quadrant
                "chat", "chat", "ohat", "cymbal",      # bottom-right
                "rim", "shaker", "perc", "tom",        # top-left
                "808", "fx", "fx", "vox"],             # top-right
    "blocks4": ["kick808", "snareclap", "hatscym", "perc"],
    "quadcols": ["kick", "kick", "kick", "808",
                 "snare", "snare", "clap", "rim",
                 "chat", "chat", "ohat", "cymbal",
                 "perc", "shaker", "tom", "fx"],
}


def groups_of(rack: dict) -> list[list[int]]:
    """Effective groups of a rack (an SPD-SX rack's disconnected triggers have none)."""
    if is_spd(rack):
        return spdsx.groups(rack["geometry"], spdsx.triggers_of(rack))
    return groups(rack["geometry"])


def group_keys(geometry: str, triggers: dict | None = None) -> list[str]:
    """Key of each group in rack["groups"] (after "<geometry>:"): its index, or the SPD-SX group key."""
    if is_spd(geometry):
        return spdsx.group_keys(geometry, triggers)
    return [str(g) for g in range(len(groups(geometry)))]


def default_families(geometry: str, triggers: dict | None = None) -> list[str]:
    if is_spd(geometry):
        return spdsx.default_families(geometry, triggers)
    if geometry == "free":
        return ["any"] * PADS
    return list(_DEFAULT_FAMILIES[geometry])


def group_settings(rack: dict, geometry: str | None = None) -> list[dict]:
    """Effective {family, choke, lock} of every group of the rack's (or the given) geometry."""
    geometry = geometry or rack.get("geometry", "cols8")
    triggers = spdsx.triggers_of(rack) if is_spd(geometry) else None
    saved = rack.get("groups") or {}
    out = []
    for key, fam in zip(group_keys(geometry, triggers), default_families(geometry, triggers)):
        s = saved.get(f"{geometry}:{key}") or {}
        fam = s.get("family") if s.get("family") in FAMILY_BY_ID else fam
        choke = s.get("choke")
        if choke is None:
            choke = 1 if fam in HAT_FAMILIES else 0
        out.append({"family": fam, "choke": max(0, min(16, int(choke))), "lock": bool(s.get("lock"))})
    return out


def family_classes(fam: str) -> list[str]:
    return FAMILY_BY_ID.get(fam, FAMILY_BY_ID["any"])[2]


def family_color(fam: str) -> str:
    classes = family_classes(fam)
    return taxonomy.BY_ID[classes[0]].color if classes else "#8a8f98"


def new_rack(name: str = "Kit", device: str = "grid64") -> dict:
    if device == "spdsx":
        return spdsx.new_rack(name)
    return {"name": name, "geometry": "cols8", "mapping": "launchpad", "quads": DEFAULT_QUADS,
            "pads": [None] * PADS, "groups": {}}


def validate(rack: dict) -> dict:
    if is_spd(rack or {}):
        return spdsx.validate(rack)
    r = dict(rack or {})
    r["name"] = str(r.get("name") or "Kit")[:80]
    if r.get("geometry") not in GEOMETRIES:
        r["geometry"] = "cols8"
    if r.get("mapping") not in ("launchpad", "rows"):
        r["mapping"] = "launchpad"
    if not valid_quads(r.get("quads")):
        r["quads"] = DEFAULT_QUADS
    pads = list(r.get("pads") or [])[:PADS]
    r["pads"] = [p if isinstance(p, dict) and (p.get("path") or p.get("url")) else None for p in pads]
    r["pads"] += [None] * (PADS - len(r["pads"]))
    r["groups"] = r.get("groups") if isinstance(r.get("groups"), dict) else {}
    return r


def pad_count(rack: dict) -> int:
    return spdsx.PADS if is_spd(rack) else PADS


def note_of(rack: dict, p: int) -> int:
    return spdsx.NOTES[p] if is_spd(rack) else note_for(p, rack.get("mapping", "launchpad"), rack.get("quads", DEFAULT_QUADS))


def ui_layouts() -> dict:
    return {
        "geometries": [{"id": g, "label": tr(GEOMETRY_LABELS[g]), "groups": groups(g), "families": default_families(g)}
                       for g in GEOMETRIES],
        "families": [{"id": f, "label": tr(label), "classes": classes, "color": family_color(f)}
                     for f, label, classes in FAMILIES],
        "notes": {m: [note_for(p, m) for p in range(PADS)] for m in ("launchpad", "rows")},
        "quad_bases": QUAD_BASE,
        "default_quads": DEFAULT_QUADS,
        "spdsx": spdsx.ui_layout(),
    }


from . import spdsx  # noqa: E402  (spdsx uses the families defined above)
