"""64-pad rack geometry: pad numbering, MIDI note mappings and the groups each layout splits the grid into.

Pads are numbered row * 8 + col, row 0 at the bottom (the side closest to the player on a Launchpad).
A rack is plain JSON shared with the UI:
{
  "name", "geometry": one of GEOMETRIES, "mapping": "launchpad" | "rows",
  "pads": [64 × sample ref or null],
  "groups": {"<geometry>:<group index>": {"family": FAMILIES id, "choke": 0..16, "lock": bool}}
}
Pads do not depend on the geometry: switching it only regroups them.
"""
from .. import taxonomy

N = 8
PADS = N * N
BASE_NOTE = 36  # C1 in Live

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
    ("any", "Qualsiasi", []),
]
FAMILY_BY_ID = {f[0]: f for f in FAMILIES}
HAT_FAMILIES = {"chat", "ohat", "hats"}

GEOMETRIES = ["cols8", "blocks2", "blocks4", "quadcols", "free"]
GEOMETRY_LABELS = {
    "cols8": "Colonne ×8",
    "blocks2": "Blocchi 2×2",
    "blocks4": "Blocchi 4×4",
    "quadcols": "4×4 a colonne",
    "free": "Libero",
}


def pad(row: int, col: int) -> int:
    return row * N + col


def rc(p: int) -> tuple[int, int]:
    return divmod(p, N)


def note_for(p: int, mapping: str = "launchpad") -> int:
    """MIDI note of pad p. 'launchpad': Live's 64-pad drum layout, four 4×4 quadrants
    (bottom-left 36-51, bottom-right 52-67, top-left 68-83, top-right 84-99), each row by row
    from its bottom-left pad. 'rows': 36 bottom-left, +1 per column, +8 per row."""
    r, c = rc(p)
    if mapping == "rows":
        return BASE_NOTE + p
    quadrant = (r >= 4) * 2 + (c >= 4)
    return BASE_NOTE + 16 * quadrant + 4 * (r % 4) + c % 4


def _block(r0: int, c0: int, h: int, w: int) -> list[int]:
    return [pad(r, c) for r in range(r0, r0 + h) for c in range(c0, c0 + w)]


# quadrants in note order: bottom-left, bottom-right, top-left, top-right
QUADRANTS = [(0, 0), (0, 4), (4, 0), (4, 4)]


def groups(geometry: str) -> list[list[int]]:
    """Pads of each group, in fill order (row by row from the bottom-left, columns bottom to top)."""
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


def default_families(geometry: str) -> list[str]:
    if geometry == "free":
        return ["any"] * PADS
    return list(_DEFAULT_FAMILIES[geometry])


def group_settings(rack: dict, geometry: str | None = None) -> list[dict]:
    """Effective {family, choke, lock} of every group of the rack's (or the given) geometry."""
    geometry = geometry or rack.get("geometry", "cols8")
    saved = rack.get("groups") or {}
    out = []
    for g, fam in enumerate(default_families(geometry)):
        s = saved.get(f"{geometry}:{g}") or {}
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


def new_rack(name: str = "Kit") -> dict:
    return {"name": name, "geometry": "cols8", "mapping": "launchpad", "pads": [None] * PADS, "groups": {}}


def validate(rack: dict) -> dict:
    r = dict(rack or {})
    r["name"] = str(r.get("name") or "Kit")[:80]
    if r.get("geometry") not in GEOMETRIES:
        r["geometry"] = "cols8"
    if r.get("mapping") not in ("launchpad", "rows"):
        r["mapping"] = "launchpad"
    pads = list(r.get("pads") or [])[:PADS]
    r["pads"] = [p if isinstance(p, dict) and (p.get("path") or p.get("url")) else None for p in pads]
    r["pads"] += [None] * (PADS - len(r["pads"]))
    r["groups"] = r.get("groups") if isinstance(r.get("groups"), dict) else {}
    return r


def ui_layouts() -> dict:
    return {
        "geometries": [{"id": g, "label": GEOMETRY_LABELS[g], "groups": groups(g), "families": default_families(g)}
                       for g in GEOMETRIES],
        "families": [{"id": f, "label": label, "classes": classes, "color": family_color(f)}
                     for f, label, classes in FAMILIES],
        "notes": {m: [note_for(p, m) for p in range(PADS)] for m in ("launchpad", "rows")},
    }
