"""Class taxonomy: ids, labels, groups, colours, filename keywords and AudioSet mapping.

This module is the single source of truth for classes and their colours (the UI reads
them through api.classes()).
"""
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SoundClass:
    id: str
    label: str
    group: str
    color: str
    keywords: tuple[str, ...] = ()
    # AudioSet (YAMNet) class index -> weight
    audioset: dict[int, float] = field(default_factory=dict)


GROUPS = ["Drums", "Percussion", "Melodic/Bass", "Vocal", "FX & altro"]

CLASSES: list[SoundClass] = [
    # ---- Drums: reds / oranges / yellows ---------------------------------------
    SoundClass("kick", "Kick", "Drums", "#ff4d4d",
               ("kick", "kik", "kck", "kicks", "bd", "bassdrum", "bdrum", "kickdrum", "kd"),
               {163: 1.0, 454: 0.6, 455: 0.4, 59: 0.4, 430: 0.3}),
    SoundClass("sub808", "808 / Sub Kick", "Drums", "#ff9eaa",
               ("808", "808s", "subkick", "boom"),
               {163: 0.5, 487: 0.6, 430: 0.6, 137: 0.4, 495: 0.4, 516: 0.4}),
    SoundClass("tom", "Tom", "Drums", "#e0603a",
               ("tom", "toms", "floortom", "hitom", "lotom", "midtom", "lowtom", "hightom", "tm"),
               {159: 1.0, 164: 0.8, 165: 0.3}),
    SoundClass("snare", "Snare", "Drums", "#ff9f1c",
               ("snare", "snr", "sd", "snares", "sn", "snre"),
               {160: 1.0, 162: 0.5, 159: 0.3}),
    SoundClass("rimshot", "Rimshot / Sidestick", "Drums", "#ffd1a1",
               ("rim", "rimshot", "sidestick", "stick", "xstick", "rims"),
               {161: 1.0, 168: 0.4, 353: 0.4}),
    SoundClass("clap", "Clap", "Drums", "#d9480f",
               ("clap", "claps", "clp", "handclap", "cp"),
               {58: 1.0, 62: 0.6, 461: 0.5}),
    SoundClass("snap", "Snap", "Drums", "#fff1e6",
               ("snap", "snaps", "fingersnap", "snp", "finger"),
               {57: 1.0, 485: 0.4}),
    SoundClass("closed_hat", "Closed Hat", "Drums", "#ffe14d",
               ("chh", "ch", "closedhat", "hhc", "hatc", "closed", "cl", "pedal", "phh"),
               {167: 1.0, 447: 0.3, 485: 0.3}),
    SoundClass("open_hat", "Open Hat", "Drums", "#c9a227",
               ("oh", "ohh", "ohat", "openhat", "hho", "hatopen", "open", "op"),
               {167: 0.8, 166: 0.5, 484: 0.4}),
    SoundClass("ride", "Ride", "Drums", "#fff59d",
               ("ride", "rides", "rd"),
               {166: 0.7, 195: 0.3}),
    SoundClass("crash", "Crash", "Drums", "#a3a336",
               ("crash", "crsh", "crashes", "cr"),
               {166: 1.0, 463: 0.5, 172: 0.3}),
    SoundClass("cymbal_other", "Other Cymbal", "Drums", "#f4c430",
               ("cymbal", "cym", "splash", "china", "cymbals", "cymb"),
               {166: 0.8, 172: 0.6}),
    # ---- Percussion: greens ------------------------------------------------------
    SoundClass("shaker", "Shaker", "Percussion", "#7bd389",
               ("shaker", "shk", "shake", "maraca", "maracas", "cabasa", "egg", "shakers"),
               {171: 1.0, 170: 0.8, 130: 0.6, 481: 0.4}),
    SoundClass("tambourine", "Tambourine", "Percussion", "#2fa84f",
               ("tamb", "tambourine", "tambo", "tamborine", "tmb", "tambourin"),
               {169: 1.0, 197: 0.6, 489: 0.5}),
    SoundClass("cowbell", "Cowbell", "Percussion", "#c5f5c8",
               ("cowbell", "cow", "cb", "agogo"),
               {87: 1.0, 195: 0.3}),
    SoundClass("woodblock", "Woodblock / Clave", "Percussion", "#1fb5a0",
               ("woodblock", "block", "wood", "clave", "claves", "blk", "click", "tick"),
               {168: 1.0, 431: 0.5, 353: 0.5, 354: 0.5, 401: 0.4}),
    SoundClass("hand_drum", "Conga / Bongo / Hand Drum", "Percussion", "#a6d75b",
               ("conga", "congas", "bongo", "bongos", "djembe", "tabla", "cajon", "timbale",
                "timbales", "darbuka", "udu", "tumba", "quinto", "surdo", "handdrum"),
               {165: 1.0, 159: 0.6, 156: 0.4}),
    SoundClass("bell", "Bell / Triangle", "Percussion", "#5aa832",
               ("bell", "bells", "triangle", "tri", "chime", "chimes", "gong"),
               {195: 1.0, 200: 0.9, 201: 0.8, 173: 0.8, 196: 0.7, 476: 0.5, 477: 0.5,
                209: 0.6, 199: 0.6, 172: 0.5}),
    SoundClass("perc_other", "Other Perc", "Percussion", "#5fd3bc",
               ("perc", "percussion", "prc", "percs", "guiro", "vibraslap", "whistle"),
               {156: 1.0, 158: 0.5, 157: 0.4}),
    # ---- Melodic / Bass: blues / violets ----------------------------------------
    SoundClass("bass", "Bass", "Melodic/Bass", "#3b82f6",
               ("bass", "bs", "bassline", "reese", "subbass", "sub", "basses"),
               {137: 1.0, 189: 0.8}),
    SoundClass("synth", "Synth (lead/pluck)", "Melodic/Bass", "#60c0ff",
               ("synth", "lead", "pluck", "arp", "stab", "saw", "square", "seq", "syn",
                "plucks", "leads", "synths", "stabs", "chord", "chords"),
               {153: 1.0, 154: 0.5, 234: 0.3}),
    SoundClass("pad", "Pad", "Melodic/Bass", "#b3d4ff",
               ("pad", "pads", "drone", "swell"),
               {153: 0.5, 241: 0.8, 248: 0.6, 185: 0.3}),
    SoundClass("keys", "Keys / Piano", "Melodic/Bass", "#818cf8",
               ("keys", "key", "piano", "pno", "rhodes", "ep", "organ", "wurli",
                "wurlitzer", "clav", "epiano", "harpsichord"),
               {147: 0.8, 148: 1.0, 149: 1.0, 150: 1.0, 151: 1.0, 152: 1.0, 155: 1.0}),
    SoundClass("guitar", "Guitar", "Melodic/Bass", "#6366f1",
               ("guitar", "gtr", "gtrs", "strum", "riff", "guitars", "banjo", "mandolin",
                "ukulele", "uke", "sitar"),
               {135: 1.0, 136: 1.0, 138: 1.0, 139: 1.0, 141: 0.8, 134: 0.8, 142: 1.0,
                144: 1.0, 146: 1.0, 143: 1.0, 145: 1.0}),
    SoundClass("strings", "Strings", "Melodic/Bass", "#a78bfa",
               ("strings", "string", "violin", "viola", "cello", "str", "orch", "orchestral",
                "pizz", "pizzicato", "harp"),
               {184: 1.0, 185: 1.0, 186: 1.0, 188: 1.0, 187: 1.0, 179: 0.6, 194: 0.7}),
    SoundClass("brass", "Brass / Wind", "Melodic/Bass", "#e0d4ff",
               ("brass", "horn", "horns", "trumpet", "trombone", "sax", "saxophone", "flute",
                "clarinet", "woodwind", "tpt", "tuba", "oboe"),
               {180: 1.0, 181: 1.0, 182: 1.0, 183: 1.0, 190: 1.0, 191: 1.0, 192: 1.0,
                193: 1.0, 203: 0.8, 204: 0.8}),
    SoundClass("mallets", "Mallets", "Melodic/Bass", "#8b5cf6",
               ("marimba", "xylophone", "vibraphone", "vibes", "glock", "glockenspiel",
                "kalimba", "mallet", "mallets", "steelpan"),
               {174: 1.0, 175: 1.0, 176: 1.0, 177: 1.0, 178: 1.0}),
    # ---- Vocal: pinks / magentas -------------------------------------------------
    SoundClass("vocal", "Vocal / Vox", "Vocal", "#ff5fa2",
               ("vocal", "vox", "vocals", "voice", "vocalchop", "acapella", "adlib", "adlibs",
                "sing", "choir", "hum", "vocalchops", "voc"),
               {24: 1.0, 25: 1.0, 29: 1.0, 30: 1.0, 31: 1.0, 32: 0.8, 249: 0.9, 250: 1.0,
                26: 1.0, 213: 0.5}),
    SoundClass("spoken", "Spoken / Chant", "Vocal", "#e0559b",
               ("spoken", "speech", "talk", "phrase", "word", "words", "shout", "chant",
                "spoke", "yell", "laugh"),
               {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 5: 1.0, 6: 0.9, 9: 0.9, 27: 0.8, 28: 0.8,
                13: 0.7}),
    # ---- FX & other: cyans / greys / brown ----------------------------------------
    SoundClass("riser", "Riser / Sweep", "FX & altro", "#22d3ee",
               ("riser", "rise", "uplifter", "uplift", "sweep", "sweepup", "buildup", "build",
                "whoosh", "swoosh", "risers", "sweeps"),
               {453: 1.0, 497: 0.5, 390: 0.4, 482: 0.4}),
    SoundClass("impact", "Impact / Hit", "FX & altro", "#0fa3b1",
               ("impact", "hit", "hits", "slam", "thud", "braam", "impacts", "crashfx"),
               {460: 1.0, 420: 1.0, 430: 0.7, 462: 0.8, 463: 0.6, 454: 0.4, 478: 0.7, 421: 0.6}),
    SoundClass("downlifter", "Downlifter", "FX & altro", "#a5f3fc",
               ("downlifter", "downer", "down", "fall", "sweepdown", "downsweep"),
               {453: 0.7, 497: 0.4}),
    SoundClass("noise", "Noise / Texture / Ambience", "FX & altro", "#94a3b8",
               ("noise", "texture", "ambience", "ambient", "atmo", "atmos", "atmosphere",
                "field", "vinyl", "crackle", "room", "textures", "soundscape"),
               {507: 1.0, 514: 1.0, 515: 1.0, 509: 0.9, 508: 0.9, 277: 0.8, 283: 0.8,
                282: 0.6, 288: 0.8, 520: 0.8, 505: 0.4, 510: 0.8, 490: 0.7, 241: 0.4, 293: 0.6}),
    SoundClass("foley", "Foley", "FX & altro", "#b08968",
               ("foley", "fol", "footstep", "footsteps", "door", "glass", "metal", "paper",
                "water", "cloth", "keys_jangle", "zip"),
               {48: 1.0, 348: 1.0, 352: 0.8, 435: 1.0, 436: 0.9, 358: 0.9, 372: 1.0, 373: 1.0,
                374: 1.0, 470: 0.8, 469: 0.8, 473: 0.9, 474: 0.9, 483: 0.8, 465: 0.8, 488: 0.8,
                439: 0.8, 378: 0.8, 380: 0.8}),
]

UNSORTED = SoundClass("unsorted", "Unsorted", "FX & altro", "#8a8f98")

CLASS_IDS = [c.id for c in CLASSES]
CLASS_INDEX = {c.id: i for i, c in enumerate(CLASSES)}
BY_ID = {c.id: c for c in CLASSES} | {UNSORTED.id: UNSORTED}
N_CLASSES = len(CLASSES)

# Tokens that describe a hi-hat without saying open/closed.
HAT_TOKENS = {"hh", "hat", "hats", "hihat", "hihats", "hi-hat", "hhat", "hht"}
OPEN_TOKENS = {"open", "op", "oh", "ohh", "opn"}
LOOP_TOKENS = {"loop", "loops", "lp", "bpm", "groove", "beat", "break", "breaks", "fill",
               "pattern", "top", "tops"}
GENERIC_FX = {"fx", "sfx", "effect", "effects", "transition", "transitions"}

_KEYWORD_MAP: dict[str, list[tuple[str, float]]] = {}
for _c in CLASSES:
    for _k in _c.keywords:
        _KEYWORD_MAP.setdefault(_k, []).append((_c.id, 1.0))
# Weak or ambiguous tokens get lower weight.
_WEAK = {"sub": 0.5, "boom": 0.4, "open": 0.4, "closed": 0.5, "cl": 0.4, "op": 0.4, "cr": 0.5,
         "rd": 0.5, "sn": 0.7, "cp": 0.7, "ch": 0.5, "cb": 0.6, "tm": 0.5, "tri": 0.6,
         "down": 0.4, "fall": 0.5, "rise": 0.6, "build": 0.5, "hit": 0.6, "hits": 0.6,
         "key": 0.5, "ep": 0.6, "str": 0.6, "stick": 0.6, "wood": 0.6, "block": 0.6,
         "click": 0.5, "tick": 0.5, "egg": 0.6, "cow": 0.6, "field": 0.5, "room": 0.4,
         "metal": 0.5, "water": 0.5, "glass": 0.6, "word": 0.5, "words": 0.5, "talk": 0.6,
         "hum": 0.5, "sing": 0.7, "saw": 0.6, "square": 0.6, "seq": 0.6, "chord": 0.6,
         "chords": 0.6, "swell": 0.6, "finger": 0.6, "pedal": 0.6, "zip": 0.6, "whistle": 0.5,
         "kd": 0.7, "sd": 0.9, "bd": 0.9, "bs": 0.7, "808": 0.8, "808s": 0.8, "harp": 0.8}
for _k, _w in _WEAK.items():
    _KEYWORD_MAP[_k] = [(cid, _w) for cid, _ in _KEYWORD_MAP.get(_k, [])]


_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")
_ALNUM_SPLIT = re.compile(r"(?<=[a-zA-Z])(?=\d)|(?<=\d)(?=[a-zA-Z])")


def tokenize(text: str) -> list[str]:
    """'TR808_KickHard01.wav' -> ['tr', '808', 'kick', 'hard', '01', 'tr808', 'kickhard']."""
    text = re.sub(r"\.[a-z0-9]{2,4}$", "", text, flags=re.I)
    parts = re.split(r"[^A-Za-z0-9]+", text)
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        low = p.lower()
        pieces = _ALNUM_SPLIT.sub(" ", _CAMEL.sub(" ", p)).lower().split()
        out.extend(pieces)
        if len(pieces) > 1:
            out.append(low)
            letters = re.sub(r"\d+", "", low)
            if letters and letters != low:
                out.append(letters)
    return out


def keyword_scores(tokens: list[str]) -> dict[str, float]:
    """Accumulate per-class keyword evidence from a token list (one path component)."""
    scores: dict[str, float] = {}
    toks = set(tokens)
    has_hat = bool(toks & HAT_TOKENS) or any(t.endswith("hat") or t.startswith("hihat") for t in toks)
    for t in toks:
        for cid, w in _KEYWORD_MAP.get(t, []):
            scores[cid] = max(scores.get(cid, 0.0), w)
    if has_hat:
        if toks & OPEN_TOKENS or any("open" in t for t in toks):
            scores["open_hat"] = max(scores.get("open_hat", 0), 1.0)
        else:
            scores["closed_hat"] = max(scores.get("closed_hat", 0), 0.8)
            scores["open_hat"] = max(scores.get("open_hat", 0), 0.3)
    elif "open" in toks or "op" in toks or "closed" in toks or "cl" in toks:
        # "open"/"closed" without a hat word is weak evidence at best
        for cid in ("open_hat", "closed_hat"):
            if cid in scores:
                scores[cid] *= 0.5
    # "808" next to a specific drum name means a TR-808 drum, not a sub kick
    if "sub808" in scores and any(c in scores for c in ("snare", "clap", "closed_hat", "open_hat",
                                                         "tom", "rimshot", "cowbell", "crash",
                                                         "ride", "woodblock", "hand_drum")):
        scores["sub808"] *= 0.2
    if "sub808" in scores and "kick" in scores:
        scores["sub808"] *= 0.6
    if "sub808" in scores and "bass" in scores:
        scores["sub808"] = 1.0
        scores["bass"] *= 0.7
    # generic words lose against a specific one in the same name
    if "cymbal_other" in scores and any(c in scores for c in ("crash", "ride", "open_hat")):
        scores["cymbal_other"] *= 0.4
    if "perc_other" in scores and len(scores) > 1:
        scores["perc_other"] *= 0.4
    if toks & GENERIC_FX:
        for cid in ("riser", "impact", "downlifter", "noise"):
            scores[cid] = max(scores.get(cid, 0.0), 0.3)
    return scores


def is_loop_name(tokens: list[str]) -> bool:
    return bool(set(tokens) & LOOP_TOKENS) or any(re.fullmatch(r"\d{2,3}bpm", t) for t in tokens)


def ui_classes() -> list[dict]:
    return [{"id": c.id, "label": c.label, "group": c.group, "color": c.color}
            for c in CLASSES + [UNSORTED]]
