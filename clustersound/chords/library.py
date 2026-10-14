"""Index of a chord MIDI pack laid out like the Unison MIDI Chord Pack.

    <NN - X Major - Y Minor>/<1 Triads|2 Extended Chords|3 Borrowed & Modal Chords>/<01 - X Major|02 - Y Minor>/<degree> - <name>.mid
    <NN - X Major - Y Minor>/4 Progressions/<…>/<Major|Minor> Progressions/<Prog N (I-V-vi-IV)>.mid

Every chord file holds one voicing (one bar); files with several onsets (progressions, "All Triads") are
split into one chord per onset. Keys missing from the pack are served by transposing the nearest one.
"""
import os
import re
import threading
from collections import Counter

from ..patterns.midi import read_note_spans
from ..i18n import N_
from . import theory

PPQ = 480
STEP = PPQ // 4  # one sixteenth
DEFAULT_DIR = os.path.expanduser("~/Documents/Unison MIDI Chord Pack")
CATEGORIES = [("triad", N_("Triads")), ("extended", N_("Extended")), ("borrowed", N_("Borrowed & modal")), ("progression", N_("Progressions"))]
_KEY_DIR = re.compile(r"^\s*\d*\s*-?\s*([A-G][b#]?)\s+Major\s*-\s*([A-G][b#]?)\s+Minor", re.I)


def _category(parts: list[str]) -> str:
    joined = " ".join(parts).lower()
    for word, cat in (("progression", "progression"), ("borrowed", "borrowed"), ("modal", "borrowed"),
                      ("extended", "extended"), ("triad", "triad")):
        if word in joined:
            return cat
    return "other"


def _segments(path: str) -> list[dict]:
    """Split a file into chords: notes starting together (within a 32nd) form one chord."""
    ppq, spans = read_note_spans(path)
    if not spans:
        return []
    k = PPQ / ppq
    spans = [(round(s * k), round(e * k), n, v) for s, e, n, v in spans]
    groups: list[list] = []
    for s, e, n, v in sorted(spans):
        if groups and s - groups[-1][0][0] < STEP // 2:
            groups[-1].append((s, e, n, v))
        else:
            groups.append([(s, e, n, v)])
    end = max(e for _, e, _, _ in spans)
    end = -(-end // (PPQ * 4)) * PPQ * 4  # files are whole bars
    out = []
    for i, g in enumerate(groups):
        start = g[0][0]
        nxt = groups[i + 1][0][0] if i + 1 < len(groups) else end
        notes = {}
        for _, _, n, v in g:
            notes[n] = max(v, notes.get(n, 0))
        out.append({"start": start // STEP, "len": max(1, round((nxt - start) / STEP)),
                    "notes": sorted([n, v] for n, v in notes.items())})
    return out


class ChordLibrary:
    def __init__(self, root: str = DEFAULT_DIR):
        self.root = root
        self._lock = threading.Lock()
        self._files: list[dict] | None = None
        self._mtime = None
        self._key_cache: dict = {}

    # ---------------------------------------------------------------- scan
    def exists(self) -> bool:
        return os.path.isdir(self.root)

    def _dir_mtime(self):
        try:
            return os.stat(self.root).st_mtime
        except OSError:
            return None

    def scan(self, force: bool = False) -> list[dict]:
        with self._lock:
            mt = self._dir_mtime()
            if self._files is None or force or mt != self._mtime:
                self._files = self._scan() if mt is not None else []
                self._mtime = mt
                self._key_cache = {}
            return self._files

    def _scan(self) -> list[dict]:
        files = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames.sort()
            for fn in sorted(filenames):
                if not fn.lower().endswith((".mid", ".midi")) or fn.startswith("."):
                    continue
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, self.root)
                entry = self._describe(rel, path)
                if entry:
                    files.append(entry)
        return files

    def _describe(self, rel: str, path: str) -> dict | None:
        parts = rel.split(os.sep)
        m = _KEY_DIR.match(parts[0]) if len(parts) > 1 else None
        if not m:
            return None
        maj, mnr = theory.PC.get(m.group(1)), theory.PC.get(m.group(2))
        if maj is None or mnr is None:
            return None
        inner = parts[1:-1]
        mode = "minor" if any("minor" in p.lower() for p in inner) else "major"
        tonic = mnr if mode == "minor" else maj
        stem = os.path.splitext(parts[-1])[0].strip()
        try:
            segs = _segments(path)
        except (AssertionError, IndexError, OSError, ValueError):
            return None
        if not segs:
            return None
        category = _category(inner)
        tokens = None
        tm = re.search(r"\(([^)]*)\)\s*$", stem)
        if tm:
            toks = [t for t in tm.group(1).split("-") if t.strip()]
            if toks and all(theory.parse_degree(t, mode) for t in toks):
                tokens = toks
        if len(segs) > 1:
            category = "progression"
        elif category in ("other", "progression"):
            category = "extended"
        degree, name = None, stem
        if len(segs) == 1 and " - " in stem:
            degree, name = (x.strip() for x in stem.split(" - ", 1))
        return {"file": rel, "key": {"tonic": tonic, "mode": mode}, "category": category, "stem": stem,
                "degree_token": degree, "name": name, "tokens": tokens, "segments": segs}

    # ---------------------------------------------------------------- keys
    def available_keys(self) -> list[dict]:
        seen = {(f["key"]["tonic"], f["key"]["mode"]) for f in self.scan()}
        return [{"tonic": t, "mode": m, "label": theory.key_name(t, m)} for t, m in sorted(seen, key=lambda k: (k[1], k[0]))]

    def _source_key(self, tonic: int, mode: str, category: str) -> tuple[int, int] | None:
        """(source tonic, shift in -6..5) of the nearest pack key that has chords of this category."""
        sources = sorted({f["key"]["tonic"] for f in self.scan() if f["key"]["mode"] == mode and f["category"] == category})
        if not sources:
            return None
        best = min(sources, key=lambda s: (abs(((tonic - s + 6) % 12) - 6), s))
        return best, ((tonic - best + 6) % 12) - 6

    def chords_for_key(self, tonic: int, mode: str) -> dict:
        """Single chords and progressions of a key. Categories missing for that key in the pack (or the
        whole key) are transposed from the nearest key that has them."""
        tonic %= 12
        ck = (tonic, mode)
        self.scan()
        if ck in self._key_cache:
            return self._key_cache[ck]
        out = {"key": {"tonic": tonic, "mode": mode, "label": theory.key_name(tonic, mode)},
               "transposed": 0, "partial": False, "chords": [], "progressions": []}
        shifts = set()
        for cat, _ in CATEGORIES:
            src = self._source_key(tonic, mode, cat)
            if not src:
                continue
            s_tonic, shift = src
            shifts.add(shift)
            for f in self._files:
                if f["key"] != {"tonic": s_tonic, "mode": mode} or f["category"] != cat:
                    continue
                if cat == "progression":
                    out["progressions"].append(self._progression(f, shift, tonic, mode))
                else:
                    out["chords"].append(self._chord(f, f["segments"][0], shift, tonic, mode, f"{f['file']}@{shift}",
                                                     f["name"], f["degree_token"]))
        nonzero = shifts - {0}
        out["transposed"] = next(iter(nonzero)) if len(shifts) == 1 and nonzero else 0
        out["partial"] = bool(nonzero) and len(shifts) > 1
        self._key_cache[ck] = out
        return out

    def _chord(self, f: dict, seg: dict, shift: int, tonic: int, mode: str, cid: str, name: str | None,
               token: str | None) -> dict:
        flats = theory.key_uses_flats(tonic, mode)
        notes = [[n + shift, v] for n, v in seg["notes"]]
        pitches = [n for n, _ in notes]
        root = theory.name_root(name) if name else None
        if root is None and token:
            d = theory.parse_degree(token, mode)
            root = (f["key"]["tonic"] + d[0]) % 12 if d else None
        if root is None:
            root = theory.guess_root([n for n, _ in seg["notes"]])
        root = (root + shift) % 12
        pcs = {n % 12 for n in pitches}
        q = theory.quality(pcs, root)
        disp = theory.transpose_name(name, shift, flats) if name and theory.name_root(name) is not None else theory.short_name(root, q, flats)
        return {"id": cid, "file": f["file"], "name": disp.replace(";", "/"), "category": f["category"],
                "srcKey": {"tonic": tonic, "mode": mode}, "root": root, "quality": q, "notes": notes,
                "len": seg["len"], "degree": theory.degree_label(root, q, tonic, mode),
                "func": theory.function(root, q, pcs, tonic, mode)}

    def _progression(self, f: dict, shift: int, tonic: int, mode: str) -> dict:
        segs = f["segments"]
        toks = f["tokens"] if f["tokens"] and len(f["tokens"]) == len(segs) else None
        chords = []
        for i, seg in enumerate(segs):
            root = None
            if toks:
                d = theory.parse_degree(toks[i], mode)
                root = (f["key"]["tonic"] + d[0]) % 12
            if root is None:
                root = theory.guess_root([n for n, _ in seg["notes"]])
            flats = theory.key_uses_flats(f["key"]["tonic"], mode)
            pcs = {n % 12 for n, _ in seg["notes"]}
            name = theory.short_name(root, theory.quality(pcs, root), flats)
            c = self._chord(f, seg, shift, tonic, mode, f"{f['file']}#{i}@{shift}", name, None)
            c["start"] = seg["start"]
            chords.append(c)
        stem = f["stem"]
        if shift:
            stem = re.sub(r"\(([A-G][b#]?) (Major|Minor)\)", lambda m: f"({theory.key_name(tonic, mode)})", stem)
        return {"id": f"{f['file']}@{shift}", "name": stem, "category": f["category"],
                "srcKey": {"tonic": tonic, "mode": mode}, "chords": chords}

    # ---------------------------------------------------------------- statistics
    def bigrams(self, mode: str) -> Counter:
        """Degree transitions in the pack's progressions: ((iv, minor), (iv, minor)) -> weight."""
        ck = ("bigrams", mode)
        self.scan()
        if ck in self._key_cache:
            return self._key_cache[ck]
        c = Counter()
        for f in self._files:
            if f["key"]["mode"] != mode or not f["tokens"]:
                continue
            degs = [theory.parse_degree(t, mode) for t in f["tokens"]]
            for a, b in zip(degs, degs[1:]):
                if a != b:
                    c[(a, b)] += 1
            if degs[-1] != degs[0]:
                c[(degs[-1], degs[0])] += .5  # progressions loop
        self._key_cache[ck] = c
        return c
