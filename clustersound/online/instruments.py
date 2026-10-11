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
    "open_hat": ["open hihat", "open hi-hat", "open hat", "hihat", "hi-hat"],
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


def infer(title: str, tags: list[str] | None = None, path: str = "") -> str | None:
    """Most likely taxonomy class from a result's title, tags and (inside packs) folder path."""
    tags = tags or []
    tagset = {t.lower() for t in tags}
    if tagset & NONMUSIC and not tagset & MUSIC:
        return None
    if path:
        scores, _ = classifier.name_scores(_rewrite(path))
    else:
        scores = taxonomy.keyword_scores(taxonomy.tokenize(_rewrite(title)))
    if tags:
        tag_toks = taxonomy.tokenize(" ".join(_rewrite(t) for t in tags))
        for cid, s in taxonomy.keyword_scores(tag_toks).items():
            scores[cid] = max(scores.get(cid, 0.0), 0.8 * s)
    if not scores:
        return None
    best = max(scores, key=scores.get)
    return best if scores[best] >= 0.45 else None


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
    if result.instrument is None and result.matched:
        tagset = set(result.tags)
        return not (tagset & NONMUSIC and not tagset & MUSIC)
    return False
