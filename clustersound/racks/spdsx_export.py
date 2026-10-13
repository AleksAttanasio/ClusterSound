"""Export of a Roland SPD-SX rack: an Ableton Drum Rack on the SPD-SX default MIDI notes (pads 60-68,
Trigger 1 69, Trigger 2 70) so the instrument plays Live over USB MIDI, plus the same samples as 16-bit /
44.1 kHz WAVs named by pad, ready to be imported with SPD-SX Wave Manager.
"""
import os

import numpy as np
import soundfile as sf
import soxr

from ..i18n import tr
from ..online.downloads import license_text, safe_name, unique_path
from ..patterns import ableton as live
from . import layouts, spdsx
from .ableton import _label, note_name

SPD_SR = 44100
SHORT = {spdsx.TRIG1: "T1 Pedal", spdsx.TRIG2: "T2"}


def pad_tag(p: int) -> str:
    return SHORT.get(p, f"P{p + 1}")


def write_spd_wav(src: str, dest: str) -> None:
    """16-bit / 44.1 kHz WAV (what Wave Manager imports without converting), mono or stereo."""
    x, sr = sf.read(src, dtype="float32", always_2d=True)
    if x.shape[1] > 2:
        x = x[:, :2]
    if sr != SPD_SR:
        x = soxr.resample(x, sr, SPD_SR)
    sf.write(dest, np.clip(x, -1, 1), SPD_SR, subtype="PCM_16")


def export_rack(rack: dict, dest_root: str, resolve, describe) -> str:
    """Write the package into a new folder under dest_root; returns the folder.

    resolve(ref) -> local path or None; describe(ref) -> OnlineResult for online samples (licence) or None.
    """
    rack = spdsx.validate(rack)
    title = safe_name(rack["name"])
    folder = unique_path(os.path.join(dest_root, title))
    os.makedirs(os.path.join(folder, "Samples"))
    os.makedirs(os.path.join(folder, "SPD-SX"))
    settings = layouts.group_settings(rack)
    group_of = {p: g for g, pads in enumerate(layouts.groups_of(rack)) for p in pads}

    pads, licences, names = [], [], {}
    for p in spdsx.active_pads(rack):
        ref = rack["pads"][p]
        src = ref and resolve(ref)
        if not src:
            continue
        g = group_of[p]
        note = spdsx.NOTES[p]
        label = _label(ref, src)
        base = safe_name(f"{pad_tag(p)} - {label}")
        dest = unique_path(os.path.join(folder, "Samples", base + ".wav"))
        info = live.write_sample(src, dest)
        write_spd_wav(src, unique_path(os.path.join(folder, "SPD-SX", base + ".wav")))
        meta = describe(ref)
        if meta is not None:
            with open(dest + ".license.txt", "w", encoding="utf-8") as f:
                f.write(license_text(meta, meta.download_url or ""))
            licences.append(meta)
        dev = live.simpler(info, ["Samples"], one_shot=True)
        pads.append({"name": f"{pad_tag(p)} {label}"[:40], "note": note, "devices": [dev],
                     "choke": settings[g]["choke"]})
        names[p] = label
    if not pads:
        raise ValueError(tr("no pad with a sample to export"))
    pads.sort(key=lambda x: x["note"])
    adg = f"{title} SPD-SX Drum Rack.adg"
    live.write_adg(live.drum_rack_document(pads), os.path.join(folder, adg))
    with open(os.path.join(folder, live.readme_file()), "w", encoding="utf-8") as f:
        f.write(readme(rack, adg, names, settings, bool(licences)))
    return folder


def pad_map(rack: dict, names: dict[int, str], width: int = 18) -> list[str]:
    """The 3×3 pads as seen from the player (pads 1-3 at the top), then the trigger inputs."""
    sep = "+" + "+".join(["-" * width] * 3) + "+"
    out = [sep]
    for row in range(3):
        cells = range(row * 3, row * 3 + 3)
        out.append("|" + "|".join(f" {p + 1} · {note_name(spdsx.NOTES[p])}".ljust(width) for p in cells) + "|")
        out.append("|" + "|".join(f" {names.get(p, '·')[: width - 2]}".ljust(width) for p in cells) + "|")
        out.append(sep)
    t = spdsx.triggers_of(rack)
    for p, key in ((spdsx.TRIG1, "trig1"), (spdsx.TRIG2, "trig2")):
        state = names.get(p, "·") if t[key] else tr("not connected")
        out.append(f"{tr(spdsx.PAD_LABELS[p])} · {note_name(spdsx.NOTES[p])}: {state}")
    return out


def readme(rack: dict, adg: str, names: dict[int, str], settings: list[dict], has_licences: bool) -> str:
    config = spdsx.CONFIGS[rack["geometry"]][0]
    lines = [
        rack["name"], tr("Roland SPD-SX · {n} pads · layout {config}", n=len(names), config=tr(config)), "",
        tr("PAD MAP (as you see them while playing: the row of pads 1-3 is the top one)"),
        *pad_map(rack, names), "",
        tr("ON THE SPD-SX (no computer)"),
        tr("1. Open SPD-SX Wave Manager, connect the SPD-SX over USB and import the files in the SPD-SX/ folder"),
        "   " + tr("(16-bit / 44.1 kHz WAV: no conversion needed)."),
        tr("2. In a free kit assign every wave to the pad shown at the start of its name"),
        "   " + tr('(P1-P9 = pads 1-9, "T1 Pedal" = Trigger 1, "T2" = Trigger 2).'),
        tr("3. For the pedal: connect the pedal/trigger (e.g. KT-10) to TRIG IN 1 and choose its type in"),
        "   MENU > SETUP > TRIGGER.",
        "",
        tr("IN ABLETON LIVE (the SPD-SX as a MIDI controller)"),
        tr('1. Drag "{file}" onto an empty MIDI track.', file=adg),
        tr("2. Connect the SPD-SX over USB and enable it as a MIDI input (Settings > Link, Tempo & MIDI > Track)."),
        tr("3. The notes are the SPD-SX factory ones: pads 1-9 = 60-68 (C3-G#3 in Live), Trigger 1 = 69,"),
        "   " + tr("Trigger 2 = 70. If you changed them: MENU > KIT > MIDI > NOTE# on the SPD-SX."),
        "   " + tr("If the SPD-SX kit already has sounds, use an empty kit to hear only Live."),
    ]
    chokes = sorted({s["choke"] for s in settings if s["choke"]})
    if chokes:
        lines.append("   " + tr("Active choke groups: {groups} (pads of the same group silence each other).",
                               groups=", ".join(map(str, chokes))))
    lines += ["", tr("IF THE .adg PRESET DOES NOT OPEN"),
              tr("Create an empty Drum Rack and drag every file in Samples/ onto the pad of the note shown in the map."), ""]
    if has_licences:
        lines += live.license_lines() + [""]
    lines.append(live.created_line())
    return "\n".join(lines) + "\n"
