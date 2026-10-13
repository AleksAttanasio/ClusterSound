"""Ableton Live export of a 64-pad rack: Samples/ folder, one Drum Rack .adg, pad map and licences.

The Drum Rack is built with the same templates as the Pattern export (patterns/ableton.py): one pad
(DrumBranch) per filled pad of the grid, on the note given by the rack's mapping, so on a Launchpad
in Live's 64-pad drum layout every pad of the controller plays the sample shown in ClusterSound.
"""
import os
import time

from ..online.downloads import license_text, safe_name, unique_path
from ..paths import file_manager
from ..patterns import ableton as live
from ..patterns.model import NOTE_NAMES
from . import layouts


def note_name(n: int) -> str:
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 2}"  # Live: C1 = 36


def _label(ref: dict, src: str) -> str:
    return os.path.splitext(ref.get("name") or os.path.basename(src))[0]


def export_rack(rack: dict, dest_root: str, resolve, describe) -> str:
    """Write the package into a new folder under dest_root; returns the folder.

    resolve(ref) -> local path or None; describe(ref) -> OnlineResult for online samples (licence) or None.
    """
    if layouts.is_spd(rack or {}):
        from . import spdsx_export
        return spdsx_export.export_rack(rack, dest_root, resolve, describe)
    rack = layouts.validate(rack)
    title = safe_name(rack["name"])
    folder = unique_path(os.path.join(dest_root, title))
    os.makedirs(os.path.join(folder, "Samples"))
    geometry, mapping = rack["geometry"], rack["mapping"]
    settings = layouts.group_settings(rack)
    group_of = {p: g for g, pads in enumerate(layouts.groups(geometry)) for p in pads}

    pads, licences, names = [], [], {}
    for p, ref in enumerate(rack["pads"]):
        src = ref and resolve(ref)
        if not src:
            continue
        g = group_of[p]
        fam = settings[g]["family"]
        sub = safe_name(f"{g + 1:02d} {layouts.FAMILY_BY_ID[fam][1].replace('/', '-')}")
        os.makedirs(os.path.join(folder, "Samples", sub), exist_ok=True)
        note = layouts.note_for(p, mapping)
        label = _label(ref, src)
        dest = unique_path(os.path.join(folder, "Samples", sub, safe_name(f"{note_name(note)} - {label}") + ".wav"))
        info = live.write_sample(src, dest)
        meta = describe(ref)
        if meta is not None:
            with open(dest + ".license.txt", "w", encoding="utf-8") as f:
                f.write(license_text(meta, meta.download_url or ""))
            licences.append(meta)
        dev = live.simpler(info, ["Samples", sub], one_shot=True)
        pads.append({"name": label[:40], "note": note, "devices": [dev], "choke": settings[g]["choke"]})
        names[p] = label
    if not pads:
        raise ValueError("nessun pad con un sample da esportare")
    pads.sort(key=lambda x: x["note"])
    adg = f"{title} Drum Rack.adg"
    live.write_adg(live.drum_rack_document(pads), os.path.join(folder, adg))
    with open(os.path.join(folder, "LEGGIMI.txt"), "w", encoding="utf-8") as f:
        f.write(readme(rack, adg, names, settings, bool(licences)))
    return folder


def pad_map(rack: dict, names: dict[int, str], width: int = 14) -> list[str]:
    """8×8 text grid as seen on the controller (top row first): note and start of the sample name."""
    sep = "+" + "+".join(["-" * width] * layouts.N) + "+"
    out = [sep]
    for row in range(layouts.N - 1, -1, -1):
        top, bottom = [], []
        for col in range(layouts.N):
            p = layouts.pad(row, col)
            top.append(f" {note_name(layouts.note_for(p, rack['mapping']))}".ljust(width))
            bottom.append(f" {names.get(p, '·')[: width - 2]}".ljust(width))
        out += ["|" + "|".join(top) + "|", "|" + "|".join(bottom) + "|", sep]
    return out


def readme(rack: dict, adg: str, names: dict[int, str], settings: list[dict], has_licences: bool) -> str:
    mapping = ("layout Drum del Launchpad / di Live: 4 quadranti 4×4 (36-51 in basso a sinistra, 52-67 in basso"
               " a destra, 68-83 in alto a sinistra, 84-99 in alto a destra)") if rack["mapping"] == "launchpad" \
        else "righe sequenziali: 36 in basso a sinistra, +1 per colonna, +8 per riga"
    lines = [
        rack["name"], f"{len(names)} pad · geometria {layouts.GEOMETRY_LABELS[rack['geometry']]} · note: {mapping}", "",
        "IN ABLETON LIVE (10 o successivo)",
        f"1. Trascina \"{adg}\" su una traccia MIDI vuota (da {file_manager()} o dal Browser > Places).",
        "2. Arma/seleziona la traccia e metti il Launchpad Pro in modalità Note: con un Drum Rack Live mostra",
        "   la griglia a 64 pad e ogni tasto suona il sample indicato qui sotto.",
    ]
    if rack["mapping"] == "rows":
        lines.append("   (Mappa a righe: usala con una Custom Mode del Launchpad che invia 36 + riga*8 + colonna.)")
    chokes = sorted({s["choke"] for s in settings if s["choke"]})
    if chokes:
        lines.append("   Choke group attivi: " + ", ".join(map(str, chokes)) + " (i pad dello stesso gruppo si zittiscono a vicenda).")
    lines += ["", "MAPPA DEI PAD (come sul controller, riga in alto per prima)"] + pad_map(rack, names)
    lines += ["", "SE IL PRESET .adg NON SI APRE",
              "Crea un Drum Rack vuoto e trascina ogni file di Samples/ sul pad della nota indicata all'inizio del nome.", ""]
    if has_licences:
        lines += ["LICENZE", "Alcuni sample vengono da fonti online: leggi i file .license.txt accanto a ciascuno",
                  "(autore, licenza e testo di attribuzione da riportare se richiesto).", ""]
    lines.append(f"Creato con ClusterSound il {time.strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines) + "\n"
