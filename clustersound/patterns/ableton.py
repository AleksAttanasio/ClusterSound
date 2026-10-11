"""Ableton Live 10 export: folder with samples, Drum Rack / bass Instrument Rack presets, MIDI and a loop.

Rack presets (.adg) are gzip'd XML. They are built from neutral templates (templates/live10_racks.xml.gz,
made by tools/extract_adg_template.py from Live's own presets): one Drum Rack pad per bus, and when a bus
has several layers the pad holds an Instrument Rack with one Simpler per layer, so the layers play
together on that pad exactly like in the sequencer. Sample paths are relative to the .adg file.
"""
import copy
import gzip
import math
import os
import time
import xml.etree.ElementTree as ET

import numpy as np
import soundfile as sf

from ..online.downloads import license_text, safe_name, unique_path
from ..paths import resource_path
from . import arrange, midi, model, render

TEMPLATES = "patterns/templates/live10_racks.xml.gz"
_T: ET.Element | None = None


def _templates() -> ET.Element:
    global _T
    if _T is None:
        with gzip.open(resource_path(TEMPLATES)) as f:
            _T = ET.parse(f).getroot()
    return _T


def _tpl(name: str) -> ET.Element:
    return copy.deepcopy(_templates().find(name)[0])


def _set(el: ET.Element, path: str, value) -> None:
    node = el.find(path)
    if node is None:
        raise KeyError(path)
    node.set("Value", str(value))


def _file_ref(fr: ET.Element, rel_dirs: list[str], filename: str, abs_path: str) -> None:
    for c in list(fr):
        fr.remove(c)
    ET.SubElement(fr, "HasRelativePath", Value="true")
    ET.SubElement(fr, "RelativePathType", Value="1")  # relative to the preset file
    rp = ET.SubElement(fr, "RelativePath")
    for i, d in enumerate(rel_dirs):
        ET.SubElement(rp, "RelativePathElement", Id=str(i), Dir=d)
    ET.SubElement(fr, "Name", Value=filename)
    ET.SubElement(fr, "Type", Value="2")
    ET.SubElement(fr, "Data")
    ET.SubElement(fr, "RefersToFolder", Value="false")
    sh = ET.SubElement(fr, "SearchHint")
    ph = ET.SubElement(sh, "PathHint")
    for i, d in enumerate([x for x in os.path.dirname(abs_path).split(os.sep) if x]):
        ET.SubElement(ph, "RelativePathElement", Id=str(i), Dir=d)
    ET.SubElement(sh, "FileSize", Value=str(os.path.getsize(abs_path)))
    ET.SubElement(sh, "Crc", Value="0")
    ET.SubElement(sh, "MaxCrcSize", Value="16384")
    ET.SubElement(sh, "HasExtendedInfo", Value="false")
    ET.SubElement(fr, "LivePackName", Value="")
    ET.SubElement(fr, "LivePackId", Value="")


def simpler(sample: dict, rel_dirs: list[str], *, one_shot: bool, root: int = 60, transpose: int = 0,
            volume_db: float = 0.0, release_ms: float | None = None, mono: bool = False,
            glide: bool = False) -> ET.Element:
    """AbletonDevicePreset with a Simpler playing `sample` ({'path', 'name', 'frames', 'sr'})."""
    dev = _tpl("Simpler")
    s = dev.find("Device/OriginalSimpler")
    part = s.find("Player/MultiSampleMap/SampleParts/MultiSamplePart")
    frames = sample["frames"]
    _set(part, "Name", os.path.splitext(sample["name"])[0])
    _set(part, "RootKey", root)
    _set(part, "SampleStart", 0)
    _set(part, "SampleEnd", frames)
    for loop in ("SustainLoop", "ReleaseLoop"):
        _set(part, f"{loop}/Start", 0)
        _set(part, f"{loop}/End", frames)
    sref = part.find("SampleRef")
    _file_ref(sref.find("FileRef"), rel_dirs, sample["name"], sample["path"])
    _set(sref, "LastModDate", int(os.path.getmtime(sample["path"])))
    _set(sref, "DefaultDuration", frames)
    _set(sref, "DefaultSampleRate", sample["sr"])
    _set(s, "Globals/PlaybackMode", 1 if one_shot else 0)
    _set(s, "Pitch/TransposeKey/Manual", int(max(-48, min(48, transpose))))
    _set(s, "VolumeAndPan/Volume/Manual", round(max(-36.0, min(6.0, volume_db)), 3))
    if release_ms is not None:
        _set(s, "VolumeAndPan/Envelope/ReleaseTime/Manual", release_ms)
    if mono:
        _set(s, "Globals/NumVoices", 0)  # enum index: 0 = 1 voice
    if glide:
        _set(s, "Globals/PortamentoMode/Manual", 1)  # 1 = Glide
        _set(s, "Globals/PortamentoTime/Manual", 60)
    return dev


def _mixer(branch: ET.Element, volume: float, pan: float = 0.0) -> None:
    mixer = branch.find("MixerPreset/AbletonDevicePreset/Device/AudioBranchMixerDevice")
    if mixer is not None:
        _set(mixer, "Volume/Manual", round(max(0.0003, min(1.99, volume)), 4))
        _set(mixer, "Panorama/Manual", round(max(-1.0, min(1.0, pan)), 3))


def instrument_rack(layers: list[tuple[str, ET.Element, float]]) -> ET.Element:
    """GroupDevicePreset with an Instrument Rack: one chain per (name, simpler preset, volume)."""
    rack = _tpl("InstrumentRack")
    bp = rack.find("BranchPresets")
    for i, (name, dev, vol) in enumerate(layers):
        br = _tpl("InstrumentBranch")
        br.set("Id", str(i))
        _set(br, "Name", name)
        dev.set("Id", "0")
        br.find("DevicePresets").append(dev)
        _mixer(br, vol)
        bp.append(br)
    return rack


def drum_rack_document(pads: list[dict]) -> ET.Element:
    """pads: [{'name', 'note', 'devices': [ET], 'volume', 'pan', 'choke'}]"""
    doc = _tpl("DrumRackDocument")
    bp = doc.find("GroupDevicePreset/BranchPresets")
    for i, pad in enumerate(pads):
        br = _tpl("DrumBranch")
        br.set("Id", str(i))
        _set(br, "Name", pad["name"])
        dp = br.find("DevicePresets")
        for j, dev in enumerate(pad["devices"]):
            dev.set("Id", str(j))
            dp.append(dev)
        _set(br, "ZoneSettings/ReceivingNote", 128 - pad["note"])  # Live stores pads as 128 - note
        _set(br, "ZoneSettings/ChokeGroup", pad.get("choke", 0))
        _mixer(br, pad.get("volume", 1.0), pad.get("pan", 0.0))
        bp.append(br)
    return doc


def instrument_rack_document(rack: ET.Element) -> ET.Element:
    doc = _tpl("DrumRackDocument")
    doc.remove(doc.find("GroupDevicePreset"))
    doc.append(rack)
    return doc


def write_adg(doc: ET.Element, path: str) -> None:
    data = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(doc, encoding="utf-8")
    with gzip.open(path, "wb") as f:
        f.write(data)


# ------------------------------------------------------------------ package
def write_sample(src: str, dest: str) -> dict:
    """Copy as 24-bit WAV (Live 10 reads every file the same way; frames needed by Simpler)."""
    x, sr = sf.read(src, dtype="float32", always_2d=True)
    if x.shape[1] > 2:
        x = x[:, :2]
    sf.write(dest, np.clip(x, -1, 1), sr, subtype="PCM_24")
    return {"path": dest, "name": os.path.basename(dest), "frames": len(x), "sr": sr}


def _db(v: float) -> float:
    return 20 * math.log10(max(v, 1e-4))


def export_package(p: dict, dest_root: str, resolve, describe, title: str) -> str:
    """Write the whole package; returns its folder.

    resolve(ref) -> local path; describe(ref) -> OnlineResult for online samples (licence file) or None.
    """
    p = model.validate(p)
    folder = unique_path(os.path.join(dest_root, safe_name(title)))
    os.makedirs(os.path.join(folder, "Samples"))
    pads = []
    licences = []

    def place(bus_label: str, idx: int, layer: dict) -> dict | None:
        src = resolve(layer["ref"])
        if not src:
            return None
        sub = os.path.join(folder, "Samples", safe_name(bus_label))
        os.makedirs(sub, exist_ok=True)
        base = os.path.splitext(layer.get("name") or os.path.basename(src))[0]
        dest = unique_path(os.path.join(sub, safe_name(f"{idx:02d} {bus_label} - {base}") + ".wav"))
        info = write_sample(src, dest)
        meta = describe(layer["ref"])
        if meta is not None:
            with open(dest + ".license.txt", "w", encoding="utf-8") as f:
                f.write(license_text(meta, meta.download_url or ""))
            licences.append(meta)
        return info

    loaded: dict[str, tuple] = {}
    for bid in model.DRUM_IDS:
        bus = p["buses"][bid]
        label = model.BUS_BY_ID[bid][1].replace("/", "-")
        layers = model.active_layers(bus)
        placed = []
        for i, layer in enumerate(layers, 1):
            info = place(label, i, layer)
            if info:
                placed.append((i - 1, layer, info))
        if placed:
            loaded[bid] = (label, placed)
    layout = midi.drum_layout(p, "drumrack", include=set(loaded))
    for bid, notes in layout.items():
        bus = p["buses"][bid]
        label, placed = loaded[bid]
        rel = ["Samples", safe_name(label)]
        mix = {"volume": bus.get("volume", 0.8) / 0.8, "pan": bus.get("pan", 0.0),
               "choke": 1 if bid in ("chat", "ohat") else 0}
        if len(notes) > 1:
            # alternating bus: one pad per layer, the MIDI picks the layer of every hit
            for j, layer, info in placed:
                dev = simpler(info, rel, one_shot=True, transpose=layer.get("pitch", 0),
                              volume_db=_db(layer.get("volume", 1.0)))
                pads.append({"name": f"{model.BUS_BY_ID[bid][1]} {j + 1}", "note": notes[j], "devices": [dev], **mix})
            continue
        note = notes[0]
        placed = [(layer, info) for _, layer, info in placed]
        if len(placed) == 1:
            layer, info = placed[0]
            devices = [simpler(info, rel, one_shot=True, transpose=layer.get("pitch", 0),
                               volume_db=_db(layer.get("volume", 1.0)))]
        else:
            chains = [(os.path.splitext(info["name"])[0],
                       simpler(info, rel, one_shot=True, transpose=layer.get("pitch", 0)), layer.get("volume", 1.0))
                      for layer, info in placed]
            devices = [instrument_rack(chains)]
        pads.append({"name": model.BUS_BY_ID[bid][1], "note": note, "devices": devices, **mix})
    base = safe_name(title)
    if pads:
        write_adg(drum_rack_document(pads), os.path.join(folder, f"{base} Drum Rack.adg"))
        midi.write(os.path.join(folder, "Drums.mid"), p, "drums", "drumrack", include=set(layout))
        midi.write(os.path.join(folder, "Drums (General MIDI).mid"), p, "drums", "gm", include=set(layout))

    bass = p["buses"]["bass"]
    blayers = model.active_layers(bass)
    if bass["notes"] and blayers:
        chains = []
        for i, layer in enumerate(blayers, 1):
            info = place("Bass", i, layer)
            if not info:
                continue
            root = layer.get("root") if layer.get("root") is not None else model.bass_root_midi(p)
            dev = simpler(info, ["Samples", "Bass"], one_shot=False, root=int(round(root)),
                          transpose=layer.get("pitch", 0), release_ms=60, mono=True,
                          glide=any(nt.get("glide") for nt in bass["notes"]))
            chains.append((os.path.splitext(info["name"])[0], dev, layer.get("volume", 1.0)))
        if chains:
            write_adg(instrument_rack_document(instrument_rack(chains)), os.path.join(folder, f"{base} Bass.adg"))
            midi.write(os.path.join(folder, "Bass.mid"), p, "bass")
    midi.write(os.path.join(folder, "Pattern (Drums + Bass, GM).mid"), p, "both", "gm")
    loop_name = "Sequenza.wav" if p.get("sections") else "Loop.wav"
    render.write_wav(os.path.join(folder, loop_name), p, resolve)

    with open(os.path.join(folder, "LEGGIMI.txt"), "w", encoding="utf-8") as f:
        f.write(readme(p, base, pads, bool(bass["notes"] and blayers), licences))
    return folder


def readme(p: dict, base: str, pads: list[dict], has_bass: bool, licences: list) -> str:
    lines = [
        f"{base}", f"{p['bpm']:.0f} BPM · swing {p['swing']:.0f}% · {p['bars']} battut{'a' if p['bars'] == 1 else 'e'}"
        f" · tonalità {p['key']}", "",
        "IN ABLETON LIVE (10 o successivo)",
        "0. Imposta il tempo del progetto a " + f"{p['bpm']:.0f} BPM.",
    ]
    if pads:
        lines += [f"1. Trascina \"{base} Drum Rack.adg\" su una traccia MIDI vuota (dal Finder o dal Browser > Places).",
                  "2. Trascina \"Drums.mid\" in uno slot clip della stessa traccia.",
                  "   Pad del Drum Rack: " + ", ".join(f"{pd['name']} = {_note_name(pd['note'])}" for pd in pads) + "."]
        alt = [model.BUS_BY_ID[b][1] for b in model.DRUM_IDS if model.alternating(p["buses"][b])]
        if alt:
            lines.append("   " + ", ".join(alt) + ": i sample si alternano, quindi ognuno ha il suo pad e il MIDI suona"
                         " quello giusto a ogni colpo (con \"casuale ogni giro\" è registrato il primo giro).")
    if has_bass:
        lines += [f"3. Trascina \"{base} Bass.adg\" su una seconda traccia MIDI e poi \"Bass.mid\" nello slot clip.",
                  "   Il Simpler del basso è monofonico, con la nota radice del sample già impostata"
                  " (e Glide attivo se il pattern ha note legate)."]
    if p.get("sections"):
        lines += ["", "SCALETTA DELLA SEQUENZA (Drums.mid e Bass.mid la contengono tutta, dalla battuta 1)"]
        lines += ["   " + x for x in arrange.outline(p)]
    loop_name = "Sequenza.wav" if p.get("sections") else "Loop.wav"
    lines += ["", f"{loop_name} è già renderizzato: puoi trascinarlo direttamente su una traccia audio.",
              "\"Pattern (Drums + Bass, GM).mid\" usa la mappa General MIDI (per altri sampler/DAW).", "",
              "SE IL PRESET .adg NON SI APRE",
              "Crea un Drum Rack vuoto, seleziona tutti i file di Samples/ nell'ordine delle cartelle e trascinali sul pad C1:",
              "si dispongono sui pad successivi. Poi trascina Drums.mid.", ""]
    if licences:
        lines += ["LICENZE", "Alcuni sample vengono da fonti online: leggi i file .license.txt accanto a ciascuno",
                  "(autore, licenza e testo di attribuzione da riportare se richiesto)."]
    lines.append(f"\nCreato con ClusterSound il {time.strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines) + "\n"


def _note_name(n: int) -> str:
    return f"{model.NOTE_NAMES[n % 12]}{n // 12 - 2}"  # Live: C1 = 36
