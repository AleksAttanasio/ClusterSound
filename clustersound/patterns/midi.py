"""Standard MIDI File writer (no dependencies) for drum and bass parts of a pattern."""
import struct

from . import model

DRUM_LEN = model.TICKS_PER_STEP // 2  # 1/32: drum pads are one-shots anyway


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _track(name: str, events: list[tuple[int, bytes]], tempo_bpm: float | None, length_ticks: int) -> bytes:
    """events: (absolute tick, raw MIDI bytes). Note-offs sort before note-ons at the same tick."""
    data = bytearray()
    meta = [(0, b"\xff\x03" + _vlq(len(name.encode())) + name.encode())]
    if tempo_bpm:
        us = int(round(60_000_000 / tempo_bpm))
        meta.append((0, b"\xff\x51\x03" + us.to_bytes(3, "big")))
        meta.append((0, b"\xff\x58\x04\x04\x02\x18\x08"))  # 4/4
    evs = meta + sorted(events, key=lambda e: (e[0], 0 if e[1][0] & 0xF0 == 0x80 else 1))
    last = 0
    for tick, raw in evs:
        data += _vlq(max(0, tick - last)) + raw
        last = tick
    data += _vlq(max(0, length_ticks - last)) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(data)) + bytes(data)


def drum_notes(p: dict, mapping: str = "drumrack", include: set | None = None) -> dict[str, int]:
    """bus id -> MIDI note. Drum Rack: consecutive pads from C1 for the buses that are used
    (optionally only those in `include`, e.g. the buses that actually have a sample)."""
    used = [b for b in model.DRUM_IDS if (include is None or b in include) and (any(p["buses"][b]["steps"]) or
            any(ly.get("steps") and any(ly["steps"]) for ly in p["buses"][b]["layers"]))]
    if mapping == "gm":
        return {b: model.BUS_BY_ID[b][3] for b in used}
    return {b: 36 + i for i, b in enumerate(used)}


def drum_events(p: dict, mapping: str = "drumrack", channel: int = 9,
                include: set | None = None) -> list[tuple[int, bytes]]:
    notes = drum_notes(p, mapping, include)
    ev = []
    for bid in model.audible_buses(p):
        if bid not in notes:
            continue
        hits = set(model.drum_hits(p, bid))
        for layer in p["buses"][bid]["layers"]:  # layers with their own steps still play this pad
            if layer.get("steps") is not None:
                hits |= set(model.drum_hits(p, bid, layer))
        for tick, vel in sorted(hits):
            ev.append((tick, bytes([0x90 | channel, notes[bid], vel])))
            ev.append((tick + DRUM_LEN, bytes([0x80 | channel, notes[bid], 0])))
    return ev


def bass_events(p: dict, channel: int = 0) -> list[tuple[int, bytes]]:
    bus = p["buses"]["bass"]
    if bus.get("mute"):
        return []
    root = model.bass_root_midi(p)
    notes = sorted(bus["notes"], key=lambda n: n["step"])
    ev = []
    for i, n in enumerate(notes):
        start = model.tick(p, n["step"])
        end = start + n["len"] * model.TICKS_PER_STEP
        if n.get("glide") and i + 1 < len(notes):
            # legato overlap: with Glide/Portamento on, the synth slides into the next note
            end = max(end, model.tick(p, notes[i + 1]["step"]) + model.TICKS_PER_STEP // 4)
        pitch = max(0, min(127, root + n["semi"]))
        ev.append((start, bytes([0x90 | channel, pitch, int(n.get("vel", 100))])))
        ev.append((end, bytes([0x80 | channel, pitch, 0])))
    return ev


def length_ticks(p: dict) -> int:
    return model.n_steps(p) * model.TICKS_PER_STEP


def write(path: str, p: dict, parts: str = "both", mapping: str = "drumrack", include: set | None = None) -> None:
    """parts: 'drums', 'bass' or 'both' (type 1 file, one track each). include: drum buses to export."""
    p = model.validate(p)
    L = length_ticks(p)
    title = f"{p.get('name', 'Pattern')}"
    if parts == "drums":
        tracks = [_track(f"Drums – {title}", drum_events(p, mapping, include=include), p["bpm"], L)]
    elif parts == "bass":
        tracks = [_track(f"Bass – {title}", bass_events(p), p["bpm"], L)]
    else:
        tracks = [_track("Tempo", [], p["bpm"], L),
                  _track(f"Drums – {title}", drum_events(p, mapping, include=include), None, L),
                  _track(f"Bass – {title}", bass_events(p), None, L)]
    fmt = 0 if len(tracks) == 1 else 1
    header = b"MThd" + struct.pack(">IHHH", 6, fmt, len(tracks), model.PPQ)
    with open(path, "wb") as f:
        f.write(header + b"".join(tracks))


def read_notes(path: str) -> list[tuple[int, int, int, int]]:
    """Minimal reader (tests/debug): (track, tick, note, velocity) of every note-on."""
    data = open(path, "rb").read()
    assert data[:4] == b"MThd"
    ntracks = struct.unpack(">H", data[10:12])[0]
    pos = 14
    out = []
    for t in range(ntracks):
        assert data[pos:pos + 4] == b"MTrk"
        size = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        i, end, tick, status = pos + 8, pos + 8 + size, 0, 0
        while i < end:
            delta = 0
            while True:
                b = data[i]
                i += 1
                delta = (delta << 7) | (b & 0x7F)
                if not b & 0x80:
                    break
            tick += delta
            b = data[i]
            if b == 0xFF:
                ln = 0
                j = i + 2
                while True:
                    c = data[j]
                    j += 1
                    ln = (ln << 7) | (c & 0x7F)
                    if not c & 0x80:
                        break
                i = j + ln
                continue
            if b & 0x80:
                status = b
                i += 1
            kind = status & 0xF0
            if kind in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                a, v = data[i], data[i + 1]
                i += 2
                if kind == 0x90 and v > 0:
                    out.append((t, tick, a, v))
            else:
                i += 1
        pos = end
    return out
