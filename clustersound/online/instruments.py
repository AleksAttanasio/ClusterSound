"""Instrument filter for online search: taxonomy class -> search terms, and result -> class.

Uses the same classes (and colours) as the local library (taxonomy.py).
"""
import re

from .. import classifier, taxonomy

# Catalogue terms per class: what people type/tag on sample sites. Multi-word terms are phrases.
TERMS: dict[str, list[str]] = {
    "kick": ["kick", "bass drum", "kickdrum", "bassdrum"],
    "sub808": ["808", "808 bass", "sub kick"],
    "tom": ["tom", "toms", "floor tom"],
    "snare": ["snare", "snare drum"],
    "rimshot": ["rimshot", "rim shot", "sidestick", "side stick"],
    "clap": ["clap", "handclap", "hand clap"],
    "snap": ["snap", "finger snap", "fingersnap"],
    "closed_hat": ["hihat", "hi-hat", "hi hat", "closed hat", "closed hihat"],
    "open_hat": ["open hihat", "open hi-hat", "open hat"],
    "ride": ["ride", "ride cymbal"],
    "crash": ["crash", "crash cymbal"],
    "cymbal_other": ["cymbal", "splash", "china cymbal"],
    "shaker": ["shaker", "maraca", "maracas", "cabasa"],
    "tambourine": ["tambourine"],
    "cowbell": ["cowbell", "agogo"],
    "woodblock": ["woodblock", "wood block", "clave", "claves"],
    "hand_drum": ["conga", "bongo", "djembe", "tabla", "cajon", "timbale"],
    "bell": ["bell", "triangle", "chime", "gong"],
    "perc_other": ["percussion", "perc"],
    "bass": ["bass", "bassline", "bass synth"],
    "synth": ["synth", "lead", "pluck", "arp", "stab"],
    "pad": ["pad", "drone", "synth pad"],
    "keys": ["piano", "keys", "rhodes", "organ", "electric piano"],
    "guitar": ["guitar"],
    "strings": ["strings", "violin", "cello", "orchestra"],
    "brass": ["brass", "trumpet", "saxophone", "flute", "horn"],
    "mallets": ["marimba", "xylophone", "vibraphone", "glockenspiel", "kalimba"],
    "vocal": ["vocal", "vox", "acapella", "singing", "voice"],
    "spoken": ["speech", "spoken", "spoken word"],
    "riser": ["riser", "uplifter", "sweep", "build up"],
    "impact": ["impact", "hit", "boom"],
    "downlifter": ["downlifter", "downsweep"],
    "noise": ["noise", "texture", "ambience", "atmosphere"],
    "foley": ["foley"],
}

# Phrases rewritten before keyword matching (catalogue spelling -> taxonomy keyword).
_PHRASES = [
    (r"bass[\s_-]?drum", "kick"), (r"kick[\s_-]?drum", "kick"), (r"hi[\s_-]?hats?", "hihat"),
    (r"floor[\s_-]?tom", "tom"), (r"side[\s_-]?stick", "sidestick"), (r"rim[\s_-]?shot", "rimshot"),
    (r"hand[\s_-]?clap", "clap"), (r"finger[\s_-]?snap", "snap"), (r"sub[\s_-]?bass", "subbass"),
    (r"snare[\s_-]?drum", "snare"), (r"wood[\s_-]?block", "woodblock"), (r"spoken[\s_-]?word", "spoken"),
    (r"build[\s_-]?up", "buildup"), (r"electric[\s_-]?piano", "epiano"),
    (r"down[\s_-]?sweep", "downsweep"), (r"sub[\s_-]?drop", "downlifter"),
    (r"open[\s_-]?hihat", "open hihat"),
    (r"(?<![a-z])sdr(?![a-z])", "snare"), (r"(?<![a-z])bdr(?![a-z])", "kick"),  # SDR-204.wav, BDR-01.wav
]

# Context that means "not a musical sample" (a football kick, a door hit, …)
NONMUSIC = {"soccer", "football", "ball", "punch", "fight", "body", "door", "car", "engine", "gun",
            "gunshot", "footstep", "footsteps", "walking", "rain", "bird", "dog", "animal", "baby",
            "explosion", "crowd", "traffic", "kitchen", "game", "sport", "sports", "karate", "waves",
            "ocean", "sea", "water", "wind", "thunder", "nature", "forest", "river", "applause", "slate",
            "film", "yelling", "cough", "sneeze"}
MUSIC = {"drum", "drums", "percussion", "beat", "sample", "samples", "oneshot", "one-shot", "808", "909",
         "music", "musical", "instrument", "synth", "loop", "kit", "drumkit", "electronic", "hiphop",
         "hip-hop", "techno", "house", "trap", "edm", "producer", "acoustic"}


def _rewrite(text: str) -> str:
    t = text.lower()
    for pat, rep in _PHRASES:
        t = re.sub(pat, rep, t)
    return t


# Context that means "several instruments together" (a drum loop, a kit, a beat)
_MIX_CONTEXT = {"kit", "kits", "drumkit", "drumkits", "drums", "beat", "beats", "breakbeat", "breakbeats",
                "loop", "loops", "groove", "pack", "full"}
_KIT = {"kit", "kits", "drumkit", "drumkits"}
_BEAT = {"beat", "beats", "breakbeat", "breakbeats", "groove", "grooves", "drumloop", "drumloops"}
_MUSICAL_GROUPS = {"Drums", "Percussion", "Melodic/Bass", "Vocal"}
_GROUP = {c.id: c.group for c in taxonomy.CLASSES}
_ORDER = {c.id: i for i, c in enumerate(taxonomy.CLASSES)}
SURE = 0.7     # one strong keyword (weights >= 0.7) or two weak ones that agree
SURE_IN_PACK = 0.6
CANDIDATE = 0.7
MARGIN = 0.15
THRESHOLD = 0.45
ONE_SHOT_MAX = 1.5  # seconds


def _tag_evidence(tags: list[str]) -> tuple[dict[str, float], dict[str, int]]:
    """Tag scores (all tags together, so 'open' + 'hihat' still works) and how many tags back each class."""
    joined = taxonomy.keyword_scores(taxonomy.tokenize(" ".join(_rewrite(t) for t in tags)))
    support: dict[str, int] = {}
    for t in dict.fromkeys(tags):
        for cid, s in taxonomy.keyword_scores(taxonomy.tokenize(_rewrite(t))).items():
            if s >= 0.5:
                support[cid] = support.get(cid, 0) + 1
    return joined, support


def infer_label(title: str, tags: list[str] | None = None, path: str = "",
                duration: float | None = None) -> tuple[str | None, str | None]:
    """Class of a result and how sure it is: (cid, "sure" | "weak"), (None, "mix") or (None, None).

    "mix" = several instruments together (a drum loop, a kit); "weak" = only ambiguous words or a
    near tie. Ties are broken by the title, then by how many tags agree, then by taxonomy order:
    never by tag order (Freesound sorts tags alphabetically). A one-shot is never a mix: a
    one-shot tagged "kick snare toms" (pack-wide tags) with nothing in its name stays unlabelled.
    """
    tags = [t.lower() for t in (tags or [])]
    if path:
        title_scores, loop = classifier.name_scores(_rewrite(path))
        title_toks = taxonomy.tokenize(path)
    else:
        title_toks = taxonomy.tokenize(_rewrite(title))
        title_scores, loop = taxonomy.keyword_scores(title_toks), taxonomy.is_loop_name(title_toks)
    tag_scores, support = _tag_evidence(tags) if tags else ({}, {})
    context = set(title_toks) | {t for tag in tags for t in taxonomy.tokenize(tag)} | set(tags)
    # a drum kit is several instruments by definition ("TR-909 Drum Kit", "808 Drum Kit")
    kit = bool(set(title_toks) & _KIT)
    scores: dict[str, float] = {}
    for cid in set(title_scores) | set(tag_scores):
        a, b = title_scores.get(cid, 0.0), 0.8 * tag_scores.get(cid, 0.0)
        bonus = 0.1 * max(0, support.get(cid, 0) - 1)
        scores[cid] = min(1.2, max(a, b) + 0.2 * min(a, b) + bonus)
    if not scores:
        return (None, "mix") if kit else (None, None)
    ranked = sorted(scores, key=lambda c: (-scores[c], -title_scores.get(c, 0.0), -support.get(c, 0), _ORDER[c]))
    best = ranked[0]
    if scores[best] < THRESHOLD:
        return None, None
    # a football kick, a car crash: musical classes need a musical context
    if context & NONMUSIC and not context & MUSIC and _GROUP[best] in _MUSICAL_GROUPS:
        return None, None
    one_shot = (duration is not None and duration <= ONE_SHOT_MAX) or bool(context & {"oneshot", "one-shot"}) \
        or {"one", "shot"} <= context
    if not one_shot and _is_mix(best, ranked, scores, title_scores, kit, loop, context, tags):
        return None, "mix"
    close = len(ranked) > 1 and scores[best] - scores[ranked[1]] < MARGIN
    if close and not title_scores.get(best):
        return None, None  # only conflicting tags, nothing in the name to choose by
    # inside a pack the parent folder ("Kicks/K1.wav", weight 0.65) is reliable on its own
    if scores[best] < (SURE_IN_PACK if path else SURE) or close:
        return best, "weak"
    return best, "sure"


def _is_mix(best, ranked, scores, title_scores, kit, loop, context, tags) -> bool:
    """Several instruments together: a kit, a beat, or many strong classes at once."""
    if _GROUP[best] in ("Drums", "Percussion"):
        if kit:
            return True
        # a beat tagged "snare" is still a whole beat, unless its title names the drum ("Kick loop")
        if (loop or context & _BEAT) and title_scores.get(best, 0.0) < CANDIDATE:
            return True
    strong = [c for c in ranked if scores[c] >= CANDIDATE]
    drums = [c for c in strong if _GROUP[c] in ("Drums", "Percussion")]
    return len(strong) >= 3 or (len(drums) >= 2 and bool(loop or context & _MIX_CONTEXT or taxonomy.is_loop_name(tags)))


def infer(title: str, tags: list[str] | None = None, path: str = "") -> str | None:
    """Most likely taxonomy class from a result's title, tags and (inside packs) folder path."""
    return infer_label(title, tags, path)[0]


# ------------------------------------------------------------ name metadata
_BPM = re.compile(r"(?<!\d)(\d{2,3})\s*-?\s*bpm|bpm\s*-?\s*(\d{2,3})(?!\d)", re.I)
_KEY = re.compile(r"(?<![A-Za-z])([A-G])(#|b|sharp|flat)?\s?(maj(?:or)?|min(?:or)?|m)?(?![A-Za-z#])")


def bpm_from_text(text: str) -> float | None:
    m = _BPM.search(text or "")
    if not m:
        return None
    v = int(m.group(1) or m.group(2))
    return float(v) if 50 <= v <= 220 else None


def key_from_text(text: str) -> str | None:
    """'Bass_C#min.wav' -> 'C# minor'. Needs an accidental or a mode, to avoid matching words."""
    for m in _KEY.finditer((text or "").replace("_", " ").replace("-", " ")):
        note, acc, mode = m.group(1), m.group(2), m.group(3)
        if not acc and not mode:
            continue
        acc = {"sharp": "#", "flat": "b"}.get(acc, acc or "")
        mode = "minor" if mode and mode.startswith("m") and not mode.startswith("maj") else "major"
        return f"{note}{acc} {mode}"
    return None


def infer_type(duration: float | None, title: str, tags: list[str] | None = None) -> str | None:
    toks = taxonomy.tokenize(title or "") + [t for t in (tags or [])]
    if taxonomy.is_loop_name(toks) or "loop" in (tags or []) or "loops" in (tags or []):
        return "Loop"
    if duration is None:
        return None
    if duration <= 2.5:
        return "One-shot"
    if bpm_from_text(title):
        return "Loop"
    return "One-shot" if duration <= 4 else "Long/Texture"


def query_terms(instruments: list[str]) -> list[str]:
    """All catalogue terms for the selected classes (deduplicated, order kept)."""
    out: list[str] = []
    for cid in instruments:
        for t in TERMS.get(cid, []):
            if t not in out:
                out.append(t)
    return out


def tag_terms(instruments: list[str]) -> list[str]:
    """Single-token tag variants (sites hyphenate multi-word tags)."""
    out: list[str] = []
    for t in query_terms(instruments):
        for v in {t.replace(" ", "-"), t.replace(" ", "")}:
            if v not in out:
                out.append(v)
    return out


def keep(result, instruments: list[str]) -> bool:
    """Instrument filter shared by all sources."""
    if not instruments:
        return True
    if result.instrument in instruments:
        return True
    if result.instrument is None and result.matched:  # unlabelled or a mix the server matched
        tagset = set(result.tags)
        return not (tagset & NONMUSIC and not tagset & MUSIC)
    return False
