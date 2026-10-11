"""Dev-only: extract neutral Live 10 rack templates from Drum/Instrument Rack presets installed with Live.

Only the device *structure* (default parameter tree of Drum Rack, Instrument Rack, Simpler and the
chain mixer) is kept; every sample reference, name and browser context is stripped. The result is
used by clustersound/patterns/ableton.py to build Drum Rack presets for exported patterns.

    python tools/extract_adg_template.py \
        "/Applications/Ableton Live 10 Suite.app/Contents/App-Resources/Core Library/Drums/606 Core Kit.adg" \
        "~/Music/Ableton/Factory Packs/Punch and Tilt/Drums/Jackman Kit.adg"
"""
import copy
import gzip
import os
import sys
import xml.etree.ElementTree as ET

OUT = os.path.join(os.path.dirname(__file__), "..", "clustersound", "patterns", "templates",
                   "live10_racks.xml.gz")


def load(path: str) -> ET.Element:
    with gzip.open(os.path.expanduser(path)) as f:
        return ET.parse(f).getroot()


def neutralize(e: ET.Element) -> ET.Element:
    """Drop everything that points at a specific preset/sample (and the kit's return chains/macros)."""
    for rb in e.iter("ReturnBranchPresets"):
        for c in list(rb):
            rb.remove(c)
    for tag in list(e.iter()):
        if tag.tag.startswith("MacroDisplayNames."):
            tag.set("Value", f"Macro {int(tag.tag.split('.')[1]) + 1}")
        if tag.tag.startswith("MacroControls.") or tag.tag.startswith("MacroDefaults."):
            if tag.find("Manual") is not None:
                tag.find("Manual").set("Value", "0")
    for sc in e.iter("SourceContext"):
        for c in list(sc):
            sc.remove(c)
    # references to the kit file itself go; references to Live's built-in device defaults
    # (AbletonDefaultPresetRef -> Devices/Instruments/...) are generic and stay untouched
    for ref in list(e.iter("PresetRef")) + list(e.iter("LastPresetRef")):
        if ref.find(".//FilePresetRef") is not None:
            for c in list(ref):
                ref.remove(c)
            if ref.tag == "LastPresetRef":
                ET.SubElement(ref, "Value")
    for tag in ("UpperDisplayString", "LowerDisplayString"):  # routing labels mention the source kit
        for n in e.iter(tag):
            n.set("Value", "")
    for tag in ("UserName", "Annotation"):
        for n in e.iter(tag):
            n.set("Value", "")
    for parts in e.iter("SampleParts"):
        keep = list(parts)[:1]
        for c in list(parts):
            parts.remove(c)
        for c in keep:
            parts.append(c)
    for sref in e.iter("SampleRef"):
        fr = sref.find("FileRef")
        if fr is not None:
            for c in list(fr):
                fr.remove(c)
    default_refs = {id(n) for r in e.iter("AbletonDefaultPresetRef") for n in r.iter("Name")}
    for name in e.iter("Name"):
        if name.get("Value") is not None and id(name) not in default_refs:
            name.set("Value", "")
    return e


def main(drum_kit: str, instrument_kit: str) -> None:
    drum = load(drum_kit)
    inst = load(instrument_kit)
    gdp = drum.find("GroupDevicePreset")
    if gdp is None or gdp.find("Device/DrumGroupDevice") is None:
        sys.exit("the first preset must be a plain Drum Rack")
    branch = copy.deepcopy(gdp.find("BranchPresets")[0])
    simpler = branch.find("DevicePresets/AbletonDevicePreset")
    if simpler is None or simpler.find("Device/OriginalSimpler") is None:
        sys.exit("the drum pad must contain a Simpler")
    doc = copy.deepcopy(drum)
    bp = doc.find("GroupDevicePreset/BranchPresets")
    for c in list(bp):
        bp.remove(c)

    igdp = inst.find("GroupDevicePreset")
    if igdp is None or igdp.find("Device/InstrumentGroupDevice") is None:
        sys.exit("the second preset must have an Instrument Rack at the top")
    irack = copy.deepcopy(igdp)
    ibranch = copy.deepcopy(irack.find("BranchPresets")[0])
    for c in list(irack.find("BranchPresets")):
        irack.find("BranchPresets").remove(c)
    dp = ibranch.find("DevicePresets")
    for c in list(dp):
        dp.remove(c)
    dbp = branch.find("DevicePresets")
    for c in list(dbp):
        dbp.remove(c)

    root = ET.Element("ClusterSoundRackTemplates", {"Source": "Ableton Live 10 factory presets (structure only)"})
    for tag, el in (("DrumRackDocument", doc), ("DrumBranch", branch), ("Simpler", simpler),
                    ("InstrumentRack", irack), ("InstrumentBranch", ibranch)):
        holder = ET.SubElement(root, tag)
        holder.append(neutralize(el))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with gzip.open(OUT, "wb") as f:
        f.write(ET.tostring(root, encoding="utf-8"))
    print("saved", os.path.normpath(OUT), os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
