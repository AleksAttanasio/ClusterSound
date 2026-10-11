"""Chord progression -> Standard MIDI File (type 0, one track): drag it onto a MIDI track in Ableton."""
import struct

from ..patterns.midi import _track
from .perform import BAR, PPQ, render


def events(seq: dict, pure: bool = False) -> list[tuple[int, bytes]]:
    ev = []
    for s, e, p, v, _ in render(seq, pure):
        ev.append((s, bytes([0x90, p, v])))
        ev.append((e, bytes([0x80, p, 0])))
    return ev


def write(path: str, seq: dict, pure: bool = False) -> None:
    """pure: the voicings as plain block chords, without strum/arp/rhythm/humanize."""
    length = int(seq.get("bars", 4)) * BAR
    track = _track(seq.get("name") or "Accordi", events(seq, pure), float(seq.get("bpm", 120)), length)
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, PPQ) + track)
