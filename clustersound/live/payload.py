"""Payloads for the Max for Live device: tracks to create in Live, each with an optional rack preset and clips.

    payload = {"kind": "pattern"|"rack"|"compose"|"audio", "name", "bpm", "folder",
               "tracks": [{"name", "role": "drums"|"bass"|"chords"|"melody"|"audio", "adg": abs path | None,
                           "adg_root": "user_library"|"places" | None, "adg_path": "dir/…/x.adg" | None,
                           "clips": [{"name", "length": beats, "notes": [[pitch, start, dur, vel], …]}]}]}

An "audio" track (the Recorder's audio) has no rack and no MIDI clips but a staged WAV instead:
audio_file (abs path, for Live 12's create_audio_clip), audio_root / audio_path (browser item, as adg_*).

Times are in beats (quarter notes), which is what Live's clip API takes. Presets are written by the regular
Ableton exporters into a Stage: by default a "ClusterSound" folder of Live's User Library, which Live always
indexes, so the Remote Script finds the preset under browser.user_library by adg_path. Without a User Library
the stage is a folder of EXPORT_DIR that the user adds to the browser Places (adg_path starts with its name).
"""
import glob
import os
from dataclasses import dataclass

import soundfile as sf

from ..chords import melody as chord_melody
from ..chords import perform as chord_perform
from ..patterns import ableton as pat_ableton
from ..patterns import midi as pat_midi
from ..patterns import model as pat_model
from ..online.downloads import safe_name, unique_path
from ..paths import IS_WIN
from ..racks import ableton as rack_ableton
from ..sampler import export as sampler_export
from ..sampler import slicing
from ..sampler.session import SamplerSession

USER_LIBRARY = os.path.expanduser("~/Documents/Ableton/User Library" if IS_WIN else "~/Music/Ableton/User Library")
LIBRARY_FOLDER = "ClusterSound"
PLACES_FOLDER = "Live Import"


@dataclass
class Stage:
    """Where presets are written, and how the Remote Script finds them in Live's browser."""
    base: str   # the browser root on disk: the User Library, or the folder added to Places
    root: str   # "user_library" | "places"
    sub: str    # folder inside base for our files

    @classmethod
    def user_library(cls, library: str = USER_LIBRARY) -> "Stage":
        return cls(library, "user_library", LIBRARY_FOLDER)

    @classmethod
    def places(cls, export_dir: str) -> "Stage":
        return cls(export_dir, "places", PLACES_FOLDER)

    @classmethod
    def default(cls, export_dir: str, library: str | None = None) -> "Stage":
        library = library or USER_LIBRARY
        return cls.user_library(library) if os.path.isdir(library) else cls.places(export_dir)

    def folder(self, kind: str) -> str:
        path = os.path.join(self.base, self.sub, kind)
        os.makedirs(path, exist_ok=True)
        return path

    def browser_path(self, path: str | None) -> str | None:
        """Path of a staged file as seen from the browser root: inside the User Library, or starting with
        the name of the Places folder."""
        if not path:
            return None
        base = os.path.normpath(self.base)
        rel = os.path.relpath(path, base)
        if self.root == "places":
            rel = os.path.join(os.path.basename(base), rel)
        return rel.replace(os.sep, "/")


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


def _track(name: str, role: str, adg: str | None, stage: Stage | None, clips: list[dict]) -> dict:
    return {"name": name, "role": role, "adg": adg, "adg_root": stage.root if adg and stage else None,
            "adg_path": stage.browser_path(adg) if adg and stage else None, "clips": clips}


def _first(folder: str, pattern: str) -> str | None:
    hits = sorted(glob.glob(os.path.join(glob.escape(folder), pattern)))
    return hits[0] if hits else None


def drum_buses(p: dict, resolve=None) -> list[dict]:
    """[{id, label, note}] of the drum buses that play, with the Drum Rack pad of each (its first pad when
    the bus alternates layers). With resolve, only buses with a sample, as in export_package's rack."""
    include = None
    if resolve is not None:
        include = {b for b in pat_model.DRUM_IDS
                   if any(resolve(ly.get("ref")) for ly in pat_model.active_layers(p["buses"][b]))}
    layout = pat_midi.drum_layout(p, "drumrack", include=include)
    return [{"id": b, "label": pat_model.BUS_BY_ID[b][1], "note": notes[0]} for b, notes in layout.items()]


def pattern(p: dict, stage: Stage, resolve, describe, title: str) -> dict:
    """A pattern (or a flattened sequence): Drums and Bass tracks with their racks and clips.

    The presets and MIDI come from patterns/ableton.export_package, so the clip notes hit the pads of the
    exported Drum Rack exactly as in the package. Without samples there is no rack, only the clip."""
    p = pat_model.validate(p)
    folder = pat_ableton.export_package(p, stage.folder("pattern"), resolve, describe, title)
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
        drums = _track("Drums", "drums", drum_adg, stage, [{"name": f"{name} – Drums", "length": length, "notes": notes}])
        drums["buses"] = drum_buses(p, resolve if drum_adg else None)
        tracks.append(drums)

    bass_adg = _first(folder, "* Bass.adg")
    notes = notes_from_events(pat_midi.bass_events(p), pat_model.PPQ)
    if notes:
        tracks.append(_track("Bass", "bass", bass_adg, stage, [{"name": f"{name} – Bass", "length": length, "notes": notes}]))
    return {"kind": "pattern", "name": title, "bpm": float(p["bpm"]), "folder": folder, "tracks": tracks}


def rack(r: dict, stage: Stage, resolve, describe) -> dict:
    """A 64-pad rack: one track with its Drum Rack, no clips."""
    folder = rack_ableton.export_rack(r, stage.folder("rack"), resolve, describe)
    name = r.get("name") or "Rack"
    adg = _first(folder, "* Drum Rack.adg")
    return {"kind": "rack", "name": name, "bpm": None, "folder": folder,
            "tracks": [_track(name, "drums", adg, stage, [])]}


def _compose_clip(seq: dict, name: str, pure: bool) -> dict:
    spans = [(s, e, p, v) for s, e, p, v, _ in chord_perform.render(seq, pure)]
    return {"name": name, "length": float(int(seq.get("bars", 4)) * 4), "notes": notes_from_spans(spans, chord_perform.PPQ)}


LIVE_ROLE = {"bass": "bass", "pad": "chords", "keys": "chords"}  # melody layer role -> Live track role


def _layer_clips(seq: dict, suffix: str = "") -> dict[str, tuple[str, dict]]:
    """layer name -> (Live role, clip named "<layer> <suffix>") for every melody layer of seq that isn't muted."""
    length = float(int(seq.get("bars", 4)) * 4)
    return {l["name"]: (LIVE_ROLE.get(l["role"], "melody"),
                        {"name": f"{l['name']} {suffix}".strip(),
                         "length": length, "notes": notes_from_spans(l["events"], chord_perform.PPQ)})
            for l in chord_melody.render_layers(seq) if not l["mute"]}


def compose(proj: dict, pure: bool = False, versions: list[str] | None = None) -> dict:
    """A Compose project ({versions, order, modes, modeActive, bpm, name}) or a single playable seq.

    Every harmony version becomes a clip of one "Accordi" track, played with the active Modalità; every melody
    layer (by name: "Melodia", "Basso"…) gets its own track, with its clip in the scene of its harmony."""
    name = proj.get("name") or "Progressione"
    bpm = float(proj.get("bpm") or 120)
    if "versions" not in proj:
        clips = [_compose_clip(proj, name, pure)]
        mel = [_layer_clips(proj)]
    else:
        mode = (proj.get("modes") or {}).get(str(proj.get("modeActive", "1")))
        order = versions or proj.get("order") or list(proj["versions"])
        many = len(order) > 1
        clips, mel = [], []
        for v in order:
            seq = proj["versions"].get(v)
            if not seq:
                continue
            seq = {**seq, "bpm": bpm, "name": name, **({"mode": mode} if mode else {})}
            clips.append(_compose_clip(seq, f"{name} {v}" if many else name, pure))
            mel.append(_layer_clips(seq, v if many else ""))
    tracks = [_track(f"Accordi – {name}", "chords", None, None, clips)]
    for lname in dict.fromkeys(k for m in mel for k in m):  # an empty slot keeps a clip in the scene of its harmony
        role = next(m[lname][0] for m in mel if lname in m)
        tracks.append(_track(f"{lname} – {name}", role, None, None,
                             [m[lname][1] if lname in m else {"name": "", "length": c["length"], "notes": []}
                              for m, c in zip(mel, clips)]))
    return {"kind": "compose", "name": name, "bpm": bpm, "folder": None, "tracks": tracks}


def audio(s: SamplerSession, stage: Stage, start: float | None = None, end: float | None = None,
          opts: dict | None = None) -> dict:
    """The Recorder's audio (all of it, or the region start..end with the export fades) staged as a WAV in
    <stage>/Audio, as a payload with one audio track. It is also in Live's browser, to drag by hand."""
    o = opts or {}
    if start is None or end is None:
        a, b, y, name = 0.0, s.duration, s.audio, s.title or "Audio"
    else:
        a, b = slicing.clamp(start, end, float("inf"), s.duration)
        y = slicing.render(s, a, b, float("inf"), float(o.get("fade_in_ms", 1)), float(o.get("fade_out_ms", 10)),
                           bool(o.get("normalize")))
        name = f"{s.title or 'Audio'} {a:.2f}-{b:.2f}s"
    if y.shape[0] == 0:
        raise ValueError("regione vuota")
    path = unique_path(os.path.join(stage.folder("Audio"), safe_name(name) + ".wav"))
    sf.write(path, y, s.sr, subtype="PCM_24")
    sampler_export.write_note(s, path, a, b)
    name = os.path.splitext(os.path.basename(path))[0]
    track = {"name": name, "role": "audio", "adg": None, "adg_root": None, "adg_path": None, "clips": [],
             "audio_file": path, "audio_root": stage.root, "audio_path": stage.browser_path(path),
             "seconds": round(y.shape[0] / s.sr, 3)}
    return {"kind": "audio", "name": name, "bpm": None, "folder": os.path.dirname(path), "tracks": [track]}
