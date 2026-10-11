"""Chord progression (and its melody) -> Standard MIDI File: drag it onto MIDI tracks in Ableton.

One part -> type 0, one track; chords + melody -> type 1, one track each ("Accordi", "Melodia")."""
import struct

from ..patterns.midi import _track
from . import melody
from .perform import BAR, PPQ, render

PARTS = ("both", "chords", "melody")


def _note_events(spans) -> list[tuple[int, bytes]]:
    ev = []
    for s, e, p, v, *_ in spans:
        ev.append((s, bytes([0x90, p, v])))
        ev.append((e, bytes([0x80, p, 0])))
    return ev


def events(seq: dict, pure: bool = False) -> list[tuple[int, bytes]]:
    return _note_events(render(seq, pure))


def melody_events(seq: dict) -> list[tuple[int, bytes]]:
    return _note_events(melody.render(seq))


def write(path: str, seq: dict, pure: bool = False, parts: str = "both") -> None:
    """pure: the voicings as plain block chords, without strum/arp/rhythm/humanize.
    parts: both | chords | melody (both without a melody = chords only)."""
    length = int(seq.get("bars", 4)) * BAR
    bpm = float(seq.get("bpm", 120))
    name = seq.get("name") or "Accordi"
    tracks = []
    if parts in ("both", "chords"):
        tracks.append(_track(name, events(seq, pure), bpm, length))
    if parts in ("both", "melody") and melody.notes_of(seq):
        tracks.append(_track("Melodia", melody_events(seq), None if tracks else bpm, length))
    if not tracks:
        tracks.append(_track(name, [], bpm, length))
    fmt = 1 if len(tracks) > 1 else 0
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, fmt, len(tracks), PPQ) + b"".join(tracks))
