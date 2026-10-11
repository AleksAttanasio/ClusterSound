"""Sequences of patterns (arrangement): blocks of grooves played one after the other with a shared kit.

block    = {"id", "label", "source", "repeat", "groove"}
groove   = {"bars", "swing", "buses": {bus: {"steps", "ratchet"}}, "bass": {"notes"}}
sequence = {"name", "blocks": [block, ...]}

flatten() turns kit + sequence into one long ordinary pattern (so MIDI, render, Ableton export and the
sequencer need nothing special), with per-bar swing ("swing_bars") and block boundaries ("sections").
The bass follows the key of the kit pattern for the whole sequence.
"""
import copy

from . import model

MAX_BARS = 256


def groove_of(p: dict) -> dict:
    """Snapshot of the groove of a pattern (no samples, no mix)."""
    p = model.validate(p)
    return {"bars": p["bars"], "swing": p["swing"],
            "buses": {b: {"steps": list(p["buses"][b]["steps"]), "ratchet": list(p["buses"][b]["ratchet"])}
                      for b in model.DRUM_IDS},
            "bass": {"notes": copy.deepcopy(p["buses"]["bass"]["notes"])}}


def total_bars(seq: dict) -> int:
    return sum(int(b["groove"]["bars"]) * max(1, int(b.get("repeat", 1))) for b in seq.get("blocks", []))


def flatten(kit: dict, seq: dict) -> dict:
    kit = model.validate(kit)
    blocks = [b for b in seq.get("blocks", []) if b.get("groove")]
    if not blocks:
        raise ValueError("la sequenza è vuota")
    out = copy.deepcopy(kit)
    steps = {b: [] for b in model.DRUM_IDS}
    ratchet = {b: [] for b in model.DRUM_IDS}
    notes, swing_bars, sections = [], [], []
    bar = 0
    for idx, block in enumerate(blocks):
        g = block["groove"]
        gb = max(1, int(g["bars"]))
        n = gb * model.STEPS_PER_BAR
        reps = max(1, int(block.get("repeat", 1)))
        if bar + gb > MAX_BARS:
            break
        start = bar
        for _ in range(reps):
            if bar + gb > MAX_BARS:
                break
            off = bar * model.STEPS_PER_BAR
            for b in model.DRUM_IDS:
                gbus = g["buses"].get(b) or {}
                s = (list(gbus.get("steps") or []) + [0] * n)[:n]
                r = (list(gbus.get("ratchet") or []) + [1] * n)[:n]
                steps[b] += s
                ratchet[b] += r
            for nt in g.get("bass", {}).get("notes", []):
                if 0 <= nt["step"] < n:
                    notes.append({**nt, "step": nt["step"] + off, "len": max(1, min(nt["len"], n - nt["step"]))})
            swing_bars += [float(g.get("swing", 50))] * gb
            bar += gb
        sections.append({"index": idx, "id": block.get("id"), "label": block.get("label", ""),
                         "start_bar": start, "bars": bar - start, "repeat": (bar - start) // gb})
    total_steps = bar * model.STEPS_PER_BAR
    out["bars"] = bar
    for b in model.DRUM_IDS:
        out["buses"][b]["steps"] = steps[b]
        out["buses"][b]["ratchet"] = ratchet[b]
        for layer in out["buses"][b]["layers"]:
            if layer.get("steps"):  # a layer with its own steps keeps its pattern, tiled over the sequence
                own = layer["steps"]
                layer["steps"] = [own[i % len(own)] for i in range(total_steps)]
    out["buses"]["bass"]["notes"] = notes
    out["swing"] = swing_bars[0] if swing_bars else kit["swing"]
    out["swing_bars"] = swing_bars
    out["sections"] = sections
    out["name"] = seq.get("name") or "Sequenza"
    out["genre"] = "sequence"
    out["id"] = "sequence"
    return model.validate(out)


def outline(p: dict) -> list[str]:
    """Human readable running order, e.g. 'batt. 1-8   DnB Rollers · Main ×2'."""
    lines = []
    for s in p.get("sections", []):
        a, b = s["start_bar"] + 1, s["start_bar"] + s["bars"]
        rep = f" ×{s['repeat']}" if s["repeat"] > 1 else ""
        lines.append(f"batt. {a}-{b}".ljust(14) + f"{s['label']}{rep}")
    return lines
