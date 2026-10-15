"""Built-in chord pack: MIDI files generated in the folder layout of the Unison MIDI Chord Pack, so that
ChordLibrary reads them like any other pack. The app ships it (the build runs this module) and Compose uses
it unless Settings › Compose points to another pack.

    python -m clustersound.chords.builtin <dest>
"""
import os
import shutil
import struct
import sys
import tempfile

from ..paths import cache_dir, resource_path
from ..patterns.midi import _track
from . import theory

VERSION = 1
PPQ = 480
BAR = PPQ * 4
VELOCITY = 96
MAJORS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

# chord kinds: name suffix and intervals from the root (above a bass root an octave lower)
TRIADS = {"maj": (" Maj", (0, 4, 7)), "min": (" min", (0, 3, 7)), "dim": (" dim", (0, 3, 6))}
# extensions by the diatonic seventh chord of the degree
EXTENDED = {
    "maj7": [("maj7", (0, 4, 7, 11)), ("maj9", (0, 4, 7, 11, 14)), ("add9", (0, 4, 7, 14)),
             ("6add9", (0, 4, 9, 14)), ("maj7sus2", (0, 2, 7, 11))],
    "maj7#11": [("maj7", (0, 4, 7, 11)), ("maj9", (0, 4, 7, 11, 14)), ("maj7#11", (0, 4, 7, 11, 18)),
                ("add9", (0, 4, 7, 14))],
    "7": [("7", (0, 4, 7, 10)), ("9", (0, 4, 10, 14)), ("13", (0, 4, 10, 14, 21)), ("9sus4", (0, 5, 10, 14)),
          ("add9", (0, 4, 7, 14))],
    "m7": [("m7", (0, 3, 7, 10)), ("m9", (0, 3, 7, 10, 14)), ("m11", (0, 3, 10, 14, 17)), ("madd9", (0, 3, 7, 14))],
    "m7b9": [("m7", (0, 3, 7, 10)), ("m7add11", (0, 3, 7, 10, 17)), ("m7sus4", (0, 5, 7, 10))],
    "m7b5": [("m7b5", (0, 3, 6, 10)), ("m7add11(b5)", (0, 3, 6, 10, 17))],
}
# borrowed and modal chords: (roman token, interval from the tonic, triad kind[, seventh suffix and intervals])
BORROWED = {
    "major": [("iv", 5, "min"), ("bVI", 8, "maj"), ("bVII", 10, "maj"), ("bIII", 3, "maj"), ("v", 7, "min"),
              ("II", 2, "maj"), ("bII", 1, "maj"), ("ii", 2, "dim", "m7b5", (0, 3, 6, 10))],
    "minor": [("V", 7, "maj"), ("V", 7, "maj", "7", (0, 4, 7, 10)), ("IV", 5, "maj"), ("bII", 1, "maj"),
              ("#vii", 11, "dim"), ("I", 0, "maj"), ("ii", 2, "min")],
}
PROGRESSIONS = {
    "major": [
        ("Diatonic", "I-V-vi-IV"), ("Diatonic", "I-vi-IV-V"), ("Diatonic", "vi-IV-I-V"), ("Diatonic", "I-IV-vi-V"),
        ("Diatonic", "ii-V-I-I"), ("Diatonic", "I-iii-vi-IV"), ("Diatonic", "IV-I-V-vi"), ("Diatonic", "I-vi-ii-V"),
        ("Diatonic", "I-V-IV-V"), ("Diatonic", "I-V-vi-iii-IV-I-IV-V"),
        ("Modal", "I-bVII-IV-I"), ("Modal", "I-bVI-bVII-I"), ("Modal", "I-iv-I-V"), ("Modal", "IV-iv-I-I"),
        ("Modal", "I-bIII-IV-I"), ("Modal", "vi-IV-bVII-I"),
    ],
    "minor": [
        ("Diatonic", "i-VI-III-VII"), ("Diatonic", "i-iv-VII-III"), ("Diatonic", "i-VII-VI-VII"), ("Diatonic", "i-iv-v-i"),
        ("Diatonic", "i-VI-VII-i"), ("Diatonic", "iv-VI-VII-i"), ("Diatonic", "i-III-VII-VI"), ("Diatonic", "VI-VII-i-i"),
        ("Diatonic", "i-v-VI-iv"), ("Diatonic", "i-VII-VI-v"),
        ("Modal", "i-iv-VI-V"), ("Modal", "i-VII-VI-V"), ("Modal", "i-VI-iv-V"), ("Modal", "i-IV-i-IV"),
        ("Modal", "i-bII-i-i"), ("Modal", "VI-iv-i-V"),
    ],
}


def _triad_kind(iv: int, minor: bool, mode: str) -> str:
    """Triad of a roman token: uppercase major, lowercase minor, diminished on the scale's leading/second degree."""
    if minor and (mode, iv) in (("major", 11), ("minor", 2), ("minor", 11)):
        return "dim"
    return "min" if minor else "maj"


def _seventh_kind(iv: int, mode: str) -> str:
    """Diatonic seventh chord of a degree (natural minor), as a key of EXTENDED."""
    scale = theory.SCALES[mode]
    i = scale.index(iv)
    third, fifth, seventh = ((scale[(i + k) % 7] - iv) % 12 for k in (2, 4, 6))
    ninth = (scale[(i + 1) % 7] - iv) % 12
    if third == 4:
        if seventh == 10:
            return "7"
        return "maj7#11" if (scale[(i + 3) % 7] - iv) % 12 == 6 else "maj7"
    if fifth == 6:
        return "m7b5"
    return "m7b9" if ninth == 1 else "m7"


def _voicing(root_pc: int, intervals) -> list[int]:
    """Bass root in octave 2, the chord in close position from the root in octave 3."""
    root = 48 + root_pc % 12
    if root > 54:
        root -= 12
    return [root - 12] + [root + i for i in intervals]


def _lead(prev: list[int] | None, root_pc: int, intervals) -> list[int]:
    """Voicing of a progression chord: bass root plus the inversion of the upper voices nearest to prev."""
    bass = 36 + root_pc % 12
    if bass > 43:
        bass -= 12
    pcs = [(root_pc + i) % 12 for i in intervals]
    best = None
    for low in range(52, 64):
        upper, n = [], low
        for pc in sorted(pcs, key=lambda p: (p - low) % 12):
            n = n + (pc - n) % 12
            upper.append(n)
        if upper[0] != low:
            continue
        cost = sum(abs(a - b) for a, b in zip(upper, prev[1:])) if prev and len(prev) - 1 == len(upper) else abs(low - 57)
        if best is None or cost < best[0]:
            best = (cost, upper)
    return [bass] + best[1]


def _write(path: str, chords: list[list[int]]) -> None:
    ev = []
    for i, notes in enumerate(chords):
        for p in notes:
            ev.append((i * BAR, bytes([0x90, p, VELOCITY])))
            ev.append(((i + 1) * BAR - 1, bytes([0x80, p, 0])))
    name = os.path.splitext(os.path.basename(path))[0]
    data = b"MThd" + struct.pack(">IHHH", 6, 0, 1, PPQ) + _track(name, ev, None, len(chords) * BAR)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def _fname(s: str) -> str:
    return s.replace("/", ";")


def _key_files(dest: str, n: int, major: int) -> None:
    minor = (major + 9) % 12
    flats = theory.key_uses_flats(major, "major")
    nm = lambda pc: theory.note_name(pc, flats)  # noqa: E731
    key_dir = os.path.join(dest, f"{n:02d} - {nm(major)} Major - {nm(minor)} Minor")
    for sub, mode, tonic in (("01", "major", major), ("02", "minor", minor)):
        mode_dir = f"{sub} - {nm(tonic)} {mode.title()}"
        scale = theory.SCALES[mode]
        triads, ext = [], []
        for idx, iv in enumerate(scale):
            minor_q = ((scale[(idx + 2) % 7] - iv) % 12) == 3
            kind = ("dim" if ((scale[(idx + 4) % 7] - iv) % 12) == 6 else "min") if minor_q else "maj"
            token = theory.ROMAN[idx].lower() if minor_q else theory.ROMAN[idx]
            root = (tonic + iv) % 12
            suffix, ints = TRIADS[kind]
            triads.append((root, ints))
            _write(os.path.join(key_dir, "1 Triads", mode_dir, f"{token} - {nm(root)}{suffix}.mid"), [_voicing(root, ints)])
            for name, ints7 in EXTENDED[_seventh_kind(iv, mode)]:
                ext.append(name)
                _write(os.path.join(key_dir, "2 Extended Chords", mode_dir, f"{token} - {_fname(nm(root) + name)}.mid"),
                       [_voicing(root, ints7)])
        prev, seq = None, []
        for root, ints in triads:
            prev = _lead(prev, root, ints)
            seq.append(prev)
        _write(os.path.join(key_dir, "1 Triads", mode_dir, f"All Triads ({nm(tonic)} {mode.title()}).mid"), seq)
        for token, iv, kind, *seventh in BORROWED[mode]:
            root = (tonic + iv) % 12
            label, ints = (seventh[0], seventh[1]) if seventh else (TRIADS[kind][0], TRIADS[kind][1])
            note = theory.note_name(root, {"b": True, "#": False}.get(token[0], flats))  # bVI: Ab, not G#
            _write(os.path.join(key_dir, "3 Borrowed & Modal Chords", mode_dir, f"{token} - {note}{label}.mid"),
                   [_voicing(root, ints)])
        counts = {}
        for group, prog in PROGRESSIONS[mode]:
            counts[group] = counts.get(group, 0) + 1
            prev, seq = None, []
            for token in prog.split("-"):
                iv, minor_q = theory.parse_degree(token, mode)
                prev = _lead(prev, (tonic + iv) % 12, TRIADS[_triad_kind(iv, minor_q, mode)][1])
                seq.append(prev)
            folder = "1 Diatonic Progressions" if group == "Diatonic" else "2 Modal Progressions"
            _write(os.path.join(key_dir, "4 Progressions", folder, f"{mode.title()} Progressions",
                                f"{mode.title()} {group} {counts[group]} ({prog}).mid"), seq)


def generate(dest: str) -> str:
    """Write the whole pack into dest (replaced if it exists)."""
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    for n, major in enumerate(MAJORS, 1):
        _key_files(dest, n, major)
    with open(os.path.join(dest, "VERSION"), "w") as f:
        f.write(str(VERSION))
    return dest


def _current(path: str) -> bool:
    try:
        with open(os.path.join(path, "VERSION")) as f:
            return f.read().strip() == str(VERSION)
    except OSError:
        return False


def builtin_dir() -> str:
    """The pack bundled with the app; from source (or if missing) one generated once in the cache folder."""
    bundled = str(resource_path("chords/builtin_pack"))
    if getattr(sys, "frozen", False) and _current(bundled):
        return bundled
    path = str(cache_dir() / f"chord_pack_v{VERSION}")
    if not _current(path):
        os.makedirs(cache_dir(), exist_ok=True)
        tmp = tempfile.mkdtemp(prefix="chord_pack_", dir=cache_dir())
        generate(os.path.join(tmp, "pack"))
        if os.path.isdir(path):
            shutil.rmtree(path)
        os.replace(os.path.join(tmp, "pack"), path)
        shutil.rmtree(tmp, ignore_errors=True)
    return path


if __name__ == "__main__":
    print(generate(sys.argv[1] if len(sys.argv) > 1 else str(resource_path("chords/builtin_pack"))))
