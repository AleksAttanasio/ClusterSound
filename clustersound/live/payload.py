"""Payloads for the Max for Live device: tracks to create in Live, each with an optional rack preset and clips.

    payload = {"kind": "pattern"|"rack"|"compose", "name", "bpm", "folder",
               "tracks": [{"name", "adg": abs path | None, "adg_place": "<Place>/…/x.adg" | None,
                           "clips": [{"name", "length": beats, "notes": [[pitch, start, dur, vel], …]}]}]}

Times are in beats (quarter notes), which is what Live's clip API takes. Presets are written by the regular
Ableton exporters into a staging folder inside EXPORT_DIR; "adg_place" is the same file as a path that
starts with the name of that folder, so the Remote Script can find it among Live's browser Places.
"""
import glob
import os

from ..chords import perform as chord_perform
from ..patterns import ableton as pat_ableton
from ..patterns import midi as pat_midi
from ..patterns import model as pat_model
from ..racks import ableton as rack_ableton

STAGING = "_Live"


def staging_dir(export_dir: str, kind: str) -> str:
    path = os.path.join(export_dir, STAGING, kind)
    os.makedirs(path, exist_ok=True)
    return path


def place_path(export_dir: str, path: str | None) -> str | None:
    """'ClusterSound Patterns/_Live/…/x.adg' for a file inside export_dir (the folder added to Places)."""
    if not path:
        return None
    root = os.path.normpath(export_dir)
    return os.path.join(os.path.basename(root), os.path.relpath(path, root)).replace(os.sep, "/")


def _round(x: float) -> float:
    return round(x, 6)


def notes_from_spans(spans, ppq: int) -> list[list]:
    """[(start, end, pitch, vel)] in ticks -> [[pitch, start, dur, vel]] in beats."""
    return [[int(p), _round(s / ppq), _round(max(1, e - s) / ppq), int(v)] for s, e, p, v in sorted(spans)]


def notes_from_events(events: list[tuple[int, bytes]], ppq: int) -> list[list]:
    """SMF-style (tick, raw) note on/off events -> [[pitch, start, dur, vel]] in beats."""
    open_, spans = {}, []
    for tick, raw in sorted(events, key=lambda e: (e[0], 0 if e[1][0] & 0xF0 == 0x80 else 1)):
        kind, pitch = raw[0] & 0xF0, raw[1]
        if kind == 0x90 and raw[2] > 0:
            if pitch in open_:
                s, v = open_.pop(pitch)
                spans.append((s, tick, pitch, v))
            open_[pitch] = (tick, raw[2])
        elif kind in (0x80, 0x90) and pitch in open_:
            s, v = open_.pop(pitch)
            spans.append((s, tick, pitch, v))
    return notes_from_spans(spans, ppq)


def _track(name: str, adg: str | None, export_dir: str, clips: list[dict]) -> dict:
    return {"name": name, "adg": adg, "adg_place": place_path(export_dir, adg), "clips": clips}


def _first(folder: str, pattern: str) -> str | None:
    hits = sorted(glob.glob(os.path.join(glob.escape(folder), pattern)))
    return hits[0] if hits else None


def pattern(p: dict, export_dir: str, resolve, describe, title: str) -> dict:
    """A pattern (or a flattened sequence): Drums and Bass tracks with their racks and clips.

    The presets and MIDI come from patterns/ableton.export_package, so the clip notes hit the pads of the
    exported Drum Rack exactly as in the package. Without samples there is no rack, only the clip."""
    p = pat_model.validate(p)
    folder = pat_ableton.export_package(p, staging_dir(export_dir, "pattern"), resolve, describe, title)
    length = pat_model.n_steps(p) / pat_model.STEPS_PER_BAR * 4
    name = p.get("name") or "Pattern"
    tracks = []

    drum_adg = _first(folder, "* Drum Rack.adg")
    drum_mid = os.path.join(folder, "Drums.mid")
    if os.path.isfile(drum_mid):
        ppq, spans = pat_midi.read_note_spans(drum_mid)
        notes = notes_from_spans(spans, ppq)
    else:
        notes = notes_from_events(pat_midi.drum_events(p, "drumrack"), pat_model.PPQ)
    if notes:
        tracks.append(_track("Drums", drum_adg, export_dir, [{"name": f"{name} – Drums", "length": length, "notes": notes}]))

    bass_adg = _first(folder, "* Bass.adg")
    notes = notes_from_events(pat_midi.bass_events(p), pat_model.PPQ)
    if notes:
        tracks.append(_track("Bass", bass_adg, export_dir, [{"name": f"{name} – Bass", "length": length, "notes": notes}]))
    return {"kind": "pattern", "name": title, "bpm": float(p["bpm"]), "folder": folder, "tracks": tracks}


def rack(r: dict, export_dir: str, resolve, describe) -> dict:
    """A 64-pad rack: one track with its Drum Rack, no clips."""
    folder = rack_ableton.export_rack(r, staging_dir(export_dir, "rack"), resolve, describe)
    name = r.get("name") or "Rack"
    adg = _first(folder, "* Drum Rack.adg")
    return {"kind": "rack", "name": name, "bpm": None, "folder": folder,
            "tracks": [_track(name, adg, export_dir, [])]}


def _compose_clip(seq: dict, name: str, pure: bool) -> dict:
    spans = [(s, e, p, v) for s, e, p, v, _ in chord_perform.render(seq, pure)]
    return {"name": name, "length": float(int(seq.get("bars", 4)) * 4), "notes": notes_from_spans(spans, chord_perform.PPQ)}


def compose(proj: dict, pure: bool = False, versions: list[str] | None = None) -> dict:
    """A Compose project ({versions, order, modes, modeActive, bpm, name}) or a single playable seq.

    Every harmony version becomes a clip of one "Accordi" track, played with the active Modalità."""
    name = proj.get("name") or "Progressione"
    bpm = float(proj.get("bpm") or 120)
    if "versions" not in proj:
        clips = [_compose_clip(proj, name, pure)]
    else:
        mode = (proj.get("modes") or {}).get(str(proj.get("modeActive", "1")))
        order = versions or proj.get("order") or list(proj["versions"])
        many = len(order) > 1
        clips = []
        for v in order:
            seq = proj["versions"].get(v)
            if not seq:
                continue
            seq = {**seq, "bpm": bpm, "name": name, **({"mode": mode} if mode else {})}
            clips.append(_compose_clip(seq, f"{name} {v}" if many else name, pure))
    return {"kind": "compose", "name": name, "bpm": bpm, "folder": None,
            "tracks": [{"name": f"Accordi – {name}", "adg": None, "adg_place": None, "clips": clips}]}

