"""Pattern model: drum buses (each with sample layers), a bass bus with notes, timing helpers.

A pattern is plain JSON (shared with the UI):
{
  "id", "genre", "name", "bpm", "swing" (50 = straight … 75 = hard shuffle), "bars", "key", "octave",
  "buses": {
     "<bus id>": {"steps": [0..127]*N, "ratchet": [1..4]*N, "volume", "pan", "mute", "solo", "hp", "lp",
                  "layers": [{"ref", "name", "volume", "pitch", "offset_ms", "mute", "solo", "steps"?}]},
     "bass":     {"notes": [{"step", "len", "semi", "vel", "glide"}], ... same mixer fields and layers}
  }
}
`steps[i]` is the velocity of the hit on 16th i (0 = no hit); a layer may override its bus steps.
"""
import copy
import re

from .. import taxonomy

STEPS_PER_BAR = 16
PPQ = 96
TICKS_PER_STEP = PPQ // 4

# id, label, classes used to auto-fill / route samples, GM note
BUSES = [
    ("kick", "Kick", ["kick", "sub808"], 36),
    ("snare", "Snare", ["snare"], 38),
    ("clap", "Clap", ["clap", "snap"], 39),
    ("rim", "Rim", ["rimshot", "woodblock"], 37),
    ("chat", "Closed Hat", ["closed_hat"], 42),
    ("ohat", "Open Hat", ["open_hat"], 46),
    ("cymbal", "Ride / Crash", ["ride", "crash", "cymbal_other"], 51),
    ("perc", "Perc", ["perc_other", "shaker", "tambourine", "cowbell", "hand_drum", "bell"], 70),
    ("tom", "Tom", ["tom"], 45),
    ("fx", "FX", ["riser", "impact", "downlifter", "noise", "vocal", "spoken"], 55),
]
BASS = ("bass", "Bass", ["sub808", "bass"], None)
DRUM_IDS = [b[0] for b in BUSES]
ALL_BUSES = BUSES + [BASS]
BUS_BY_ID = {b[0]: b for b in ALL_BUSES}
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

VEL = {"X": 127, "x": 100, "o": 55, "2": 100, "3": 100, "4": 100}
RATCHET = {"2": 2, "3": 3, "4": 4}


def bus_color(bus_id: str) -> str:
    classes = BUS_BY_ID[bus_id][2]
    return taxonomy.BY_ID[classes[0]].color


def bus_for_class(cls: str) -> str:
    """Which bus a sample of this taxonomy class goes to by default."""
    if cls in ("bass",):
        return "bass"
    for bid, _, classes, _ in BUSES:
        if cls in classes:
            return bid
    return "perc" if cls in ("perc_other",) else "fx"


def ui_buses() -> list[dict]:
    return [{"id": b[0], "label": b[1], "classes": b[2], "gm": b[3], "color": bus_color(b[0]),
             "melodic": b[0] == "bass"} for b in ALL_BUSES]


def note_index(key: str) -> int:
    flats = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
    return NOTE_NAMES.index(flats.get(key, key))


# ------------------------------------------------------------------ notation
def parse_steps(text: str, n_steps: int) -> tuple[list[int], list[int]]:
    """'X..x|o.2.' -> velocities and ratchets, repeated/truncated to n_steps."""
    chars = [c for c in re.sub(r"[\s|]", "", text)]
    if not chars:
        return [0] * n_steps, [1] * n_steps
    vel = [VEL.get(c, 0) for c in chars]
    rat = [RATCHET.get(c, 1) for c in chars]
    reps = -(-n_steps // len(chars))
    return (vel * reps)[:n_steps], (rat * reps)[:n_steps]


def parse_bass(text: str) -> list[dict]:
    """'0:4:0 6:2:0 10:4:-2g' -> notes (step:len:semitones, g = glide into the next note, ! = accent)."""
    notes = []
    for tok in (text or "").split():
        glide = tok.endswith("g") or "g!" in tok or "!g" in tok
        accent = "!" in tok
        tok = tok.rstrip("g!").rstrip("!g")
        step, length, semi = (int(x) for x in tok.split(":"))
        notes.append({"step": step, "len": length, "semi": semi, "vel": 120 if accent else 100, "glide": glide})
    return notes


def empty_bus(bus_id: str, n_steps: int) -> dict:
    d = {"volume": 0.8, "pan": 0.0, "mute": False, "solo": False, "hp": 0, "lp": 0, "layers": []}
    if bus_id == "bass":
        d["notes"] = []
        d["volume"] = 0.7
    else:
        d["steps"] = [0] * n_steps
        d["ratchet"] = [1] * n_steps
    return d


def new_layer(ref: dict | None, name: str = "", **kw) -> dict:
    layer = {"ref": ref, "name": name, "volume": 1.0, "pitch": 0, "offset_ms": 0, "mute": False, "solo": False,
             "steps": None, "root": None}
    layer.update(kw)
    return layer


def n_steps(p: dict) -> int:
    return int(p["bars"]) * STEPS_PER_BAR


def validate(p: dict) -> dict:
    """Clamp and fill a pattern coming from the UI or from disk."""
    p = copy.deepcopy(p)
    p["bars"] = max(1, min(256, int(p.get("bars", 1))))
    p["bpm"] = max(40.0, min(250.0, float(p.get("bpm", 120))))
    p["swing"] = max(50.0, min(75.0, float(p.get("swing", 50))))
    if p.get("swing_bars"):  # sequences: one swing value per bar
        sb = [max(50.0, min(75.0, float(v))) for v in p["swing_bars"]]
        p["swing_bars"] = (sb + [p["swing"]] * p["bars"])[: p["bars"]]
    p.setdefault("key", "F")
    p["octave"] = max(0, min(4, int(p.get("octave", 1))))
    n = n_steps(p)
    buses = p.setdefault("buses", {})
    for bid, *_ in ALL_BUSES:
        b = buses.setdefault(bid, empty_bus(bid, n))
        for k, v in empty_bus(bid, n).items():
            b.setdefault(k, v)
        if bid != "bass":
            b["steps"] = ([int(max(0, min(127, v))) for v in b["steps"]] + [0] * n)[:n]
            b["ratchet"] = ([int(max(1, min(4, v))) for v in b["ratchet"]] + [1] * n)[:n]
        else:
            b["notes"] = [nt for nt in b["notes"] if 0 <= int(nt["step"]) < n and int(nt["len"]) >= 1]
        for layer in b["layers"]:
            for k, v in new_layer(None).items():
                layer.setdefault(k, v)
            if layer.get("steps") is not None:
                layer["steps"] = ([int(max(0, min(127, v))) for v in layer["steps"]] + [0] * n)[:n]
    return p


# ------------------------------------------------------------------ timing
def step_tick(step: int, swing: float) -> int:
    """Tick of a 16th step with MPC-style swing on the off 16ths."""
    t = step * TICKS_PER_STEP
    if step % 2 == 1:
        t += round((swing / 100.0 * 2 * TICKS_PER_STEP) - TICKS_PER_STEP)
    return t


def swing_at(p: dict, step: int) -> float:
    sb = p.get("swing_bars")
    if sb:
        return sb[min(len(sb) - 1, step // STEPS_PER_BAR)]
    return p["swing"]


def tick(p: dict, step: int) -> int:
    """Tick of a step in pattern p (honours per-bar swing of sequences)."""
    return step_tick(step, swing_at(p, step))


def active_layers(bus: dict) -> list[dict]:
    layers = [ly for ly in bus.get("layers", []) if ly.get("ref")]
    solo = [ly for ly in layers if ly.get("solo")]
    return [ly for ly in (solo or layers) if not ly.get("mute")]


def audible_buses(p: dict) -> list[str]:
    buses = p["buses"]
    solo = [b for b in buses if buses[b].get("solo")]
    return [b for b in (solo or list(buses)) if not buses[b].get("mute")]


def drum_hits(p: dict, bus_id: str, layer: dict | None = None):
    """(tick, velocity) for every hit of a drum bus (or of a layer with its own steps)."""
    bus = p["buses"][bus_id]
    steps = layer["steps"] if layer is not None and layer.get("steps") is not None else bus["steps"]
    out = []
    for i, v in enumerate(steps):
        if not v:
            continue
        t0 = tick(p, i)
        r = bus["ratchet"][i] if i < len(bus["ratchet"]) else 1
        for k in range(r):
            # roll hits decay a little so they sound like a roll, not a machine gun
            out.append((t0 + k * TICKS_PER_STEP // r, max(1, int(v * (1 - 0.12 * k)))))
    return out


def bass_root_midi(p: dict) -> int:
    """MIDI note of the bass root (key + octave; octave 1 = C1..B1, the 808/sub register)."""
    return 12 * (p["octave"] + 1) + note_index(p["key"])
