"""Small music-theory helpers: note names, chord quality from a voicing, roman degrees and harmonic function."""
import re

SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
PC = {n: i for i, n in enumerate(SHARPS)} | {n: i for i, n in enumerate(FLATS)} | {"Cb": 11, "Fb": 4, "E#": 5, "B#": 0}
SCALES = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10)}
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]
_ROMAN_RE = re.compile(r"^(b|#)?(VII|VI|IV|V|III|II|I|vii|vi|iv|v|iii|ii|i)(.*)$")
# keys spelled with flats (major tonic pc / minor tonic pc)
_FLAT_KEYS = {"major": {1, 3, 5, 6, 8, 10}, "minor": {0, 2, 3, 5, 7, 10}}
# interval from the tonic -> roman numeral, per mode (natural minor for minor keys)
_DEGREE_NAMES = {
    "major": ["I", "bII", "II", "bIII", "III", "IV", "#IV", "V", "bVI", "VI", "bVII", "VII"],
    "minor": ["I", "bII", "II", "III", "#III", "IV", "#IV", "V", "VI", "#VI", "VII", "#VII"],
}
# harmonic function of a root interval: T tonic, S subdominant, D dominant
_FUNCTION = {
    "major": {0: "T", 2: "S", 4: "T", 5: "S", 7: "D", 9: "T", 11: "D", 1: "S", 3: "T", 8: "S", 10: "S", 6: "D"},
    "minor": {0: "T", 2: "S", 3: "T", 5: "S", 7: "D", 8: "S", 10: "D", 11: "D", 1: "S", 4: "T", 6: "D", 9: "S"},
}


def note_name(pc: int, flats: bool = False) -> str:
    return (FLATS if flats else SHARPS)[pc % 12]


def key_uses_flats(tonic: int, mode: str) -> bool:
    return tonic % 12 in _FLAT_KEYS.get(mode, set())


def key_name(tonic: int, mode: str) -> str:
    return f"{note_name(tonic, key_uses_flats(tonic, mode))} {'maggiore' if mode == 'major' else 'minore'}"


def parse_pc(s: str) -> int | None:
    m = re.match(r"^([A-G])([b#]?)", s.strip())
    return PC.get(m.group(1) + m.group(2)) if m else None


def name_root(name: str) -> int | None:
    """Root pitch class from a chord name ('Bb9(#11)', 'G;B', 'C Maj')."""
    return parse_pc(name)


def transpose_name(name: str, semis: int, flats: bool) -> str:
    """Transpose the root and the slash bass (after ';' or '/') of a chord name."""
    if semis % 12 == 0:
        return name

    def sub(m):
        return note_name(PC[m.group(0)] + semis, flats)

    head = re.sub(r"^[A-G][b#]?", sub, name)
    return re.sub(r"(?<=[;/])[A-G][b#]?", sub, head)


def quality(pcs: set[int], root: int) -> str:
    """'maj' | 'min' | 'dim' | 'aug' | 'dom' | 'sus' from the pitch classes relative to the root."""
    iv = {(p - root) % 12 for p in pcs}
    if 4 in iv:
        if 8 in iv and 7 not in iv:
            return "aug"
        return "dom" if 10 in iv and 11 not in iv else "maj"
    if 3 in iv:
        return "dim" if 6 in iv and 7 not in iv else "min"
    return "sus"


def is_minor(q: str) -> bool:
    return q in ("min", "dim")


def guess_root(notes: list[int]) -> int:
    """Root of an unnamed voicing: the pitch class that best explains a triad, ties to the bass."""
    pcs = {n % 12 for n in notes}
    bass = min(notes) % 12 if notes else 0

    def score(r):
        iv = {(p - r) % 12 for p in pcs}
        s = (3 in iv or 4 in iv) * 2 + (7 in iv) * 1.5 + (6 in iv and 3 in iv) * 1 + (10 in iv or 11 in iv) * .5
        return s + (r == bass) * .75

    return max(sorted(pcs), key=score) if pcs else bass


def parse_degree(token: str, mode: str) -> tuple[int, bool] | None:
    """Roman token of the pack ('bVII', 'iv', 'Vsus', 'bvii') -> (interval from the tonic, minor quality)."""
    m = _ROMAN_RE.match(token.strip())
    if not m:
        return None
    acc, num, _ = m.groups()
    idx = ROMAN.index(num.upper())
    iv = SCALES[mode][idx] + (-1 if acc == "b" else 1 if acc == "#" else 0)
    return iv % 12, num.islower()


def degree_label(root: int, q: str, tonic: int, mode: str) -> str:
    """Roman numeral of a chord in a key, lowercase for minor/diminished, ° / + / 7 / sus suffixes."""
    iv = (root - tonic) % 12
    base = _DEGREE_NAMES[mode][iv]
    acc = base.rstrip("IV")
    num = base[len(acc):]
    if is_minor(q):
        num = num.lower()
    suffix = {"dim": "°", "aug": "+", "dom": "7", "sus": "sus"}.get(q, "")
    return acc + num + suffix


def function(root: int, q: str, pcs: set[int], tonic: int, mode: str) -> str:
    """'T' | 'S' | 'D' for diatonic chords, 'C' (colour) when the chord leaves the scale."""
    iv = (root - tonic) % 12
    scale = {(tonic + s) % 12 for s in SCALES[mode]}
    if mode == "minor":  # harmonic minor V / vii° are still functional
        scale |= {(tonic + 11) % 12}
    core = {p for p in pcs if (p - root) % 12 in (0, 3, 4, 7)}  # the triad decides, extensions don't
    diatonic = (iv in SCALES[mode] or (mode == "minor" and iv == 11)) and core <= scale
    if mode == "minor" and iv == 2 and q == "dim":
        diatonic = True
    return _FUNCTION[mode][iv] if diatonic else "C"


def degree_key(root: int, q: str, tonic: int) -> tuple[int, bool]:
    """Key used by the progression statistics: (interval from the tonic, minor quality)."""
    return (root - tonic) % 12, is_minor(q)


def short_name(root: int, q: str, flats: bool) -> str:
    return note_name(root, flats) + {"maj": "", "min": "m", "dim": "°", "aug": "+", "dom": "7", "sus": "sus"}[q]
