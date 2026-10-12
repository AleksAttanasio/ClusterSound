# -*- coding: utf-8 -*-
"""Messages between the ClusterSound Max for Live device and this Remote Script (no Live imports, so it is
testable outside Live). Python 2.7 (Live 10) and 3 compatible.

Max's [udpsend] / [udpreceive] speak OSC, so every message is an OSC message "/clustersound" with a single
string argument holding a JSON object:

    device -> script  {"id": n, "cmd": "ping"}
                      {"id": n, "cmd": "load", "track": <track index>, "place": "<Place>/<dir>/…/<file>.adg"}
                      {"id": n, "cmd": "load_audio", "track": <audio track index>, "slot": <empty clip slot>,
                       "root": "user_library"|"places", "path": "ClusterSound/Audio/<file>.wav"}
    script -> device  {"id": n, "ok": true, ...} | {"id": n, "ok": false, "error": "..."}
"""
from __future__ import absolute_import, unicode_literals

import json
import struct

ADDRESS = "/clustersound"
IN_PORT = 9101   # the script listens here
OUT_PORT = 9102  # the device listens here


def _pad(b):
    return b + b"\0" * (4 - len(b) % 4)


def _read_str(data, pos):
    end = data.index(b"\0", pos)
    s = data[pos:end].decode("utf-8")
    return s, (end // 4 + 1) * 4


def osc_encode(obj, address=ADDRESS):
    text = json.dumps(obj).encode("ascii")  # \uXXXX escapes: same bytes on Python 2 and 3
    return _pad(address.encode("utf-8")) + _pad(b",s") + _pad(text)


def osc_decode(data):
    """(address, [args]) of an OSC message with s / i / f arguments."""
    address, pos = _read_str(data, 0)
    tags, pos = _read_str(data, pos)
    args = []
    for t in tags[1:]:
        if t == "s":
            s, pos = _read_str(data, pos)
            args.append(s)
        elif t == "i":
            args.append(struct.unpack(">i", data[pos:pos + 4])[0])
            pos += 4
        elif t == "f":
            args.append(struct.unpack(">f", data[pos:pos + 4])[0])
            pos += 4
    return address, args


def parse(data):
    """The JSON command in an OSC packet, or None."""
    try:
        address, args = osc_decode(data)
        if address != ADDRESS or not args:
            return None
        msg = json.loads(" ".join(a for a in args if isinstance(a, type(""))))
        return msg if isinstance(msg, dict) and msg.get("cmd") else None
    except (ValueError, IndexError, struct.error, UnicodeDecodeError):
        return None


def _stem(name):
    return name.rsplit(".", 1)[0] if "." in name else name


def _same(item_name, wanted):
    return item_name == wanted or _stem(item_name) == _stem(wanted)


def find_item(roots, place):
    """BrowserItem for "<Place>/a/b/file.adg" among the browser's user folders (Places), else None.

    Every item needs .name and .children; names are compared with and without the file extension."""
    parts = [p for p in place.replace("\\", "/").split("/") if p]
    if not parts:
        return None
    level = [r for r in roots if _same(r.name, parts[0])]
    for part in parts[1:]:
        level = [c for item in level for c in item.children if _same(c.name, part)]
        if not level:
            return None
    return level[0] if level else None


# ------------------------------------------------------------------ instrument browser
# The device shows Live's library as types (the folders of "Sounds" with the presets of installed Packs, the
# drum kits, the presets of each instrument) and, for the chosen type, all its presets, page by page.
DRUM_KITS = "drums:kits"
AUDIO_EXT = (".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg", ".m4a")
MAX_VISITS = 10000  # browser children are fetched lazily by Live: keep every walk bounded
MAX_ITEMS = 1500
PAGE = 60           # presets per reply (one UDP packet)
ROLE_DEFAULTS = {
    "chords": ["sounds:Piano & Keys", "sounds:Synth Keys", "sounds:Pad"],
    "melody": ["sounds:Synth Lead", "sounds:Piano & Keys", "sounds:Synth Keys"],
    "bass": ["sounds:Bass"],
    "drums": [DRUM_KITS],
}


def _ok_name(name):
    return not name.lower().endswith(AUDIO_EXT)


def _children(item):
    return list(item.children) if item is not None else []


def collect(roots, limit=MAX_ITEMS, max_visits=MAX_VISITS):
    """[(item, folder name)] of loadable presets under the given browser items, breadth first.

    Folders and devices (e.g. "Operator", whose children are its presets) are opened; audio files skipped."""
    out, queue, visits = [], [(r, getattr(r, "name", "")) for r in roots], 0
    while queue and len(out) < limit and visits < max_visits:
        item, folder = queue.pop(0)
        visits += 1
        if getattr(item, "is_loadable", False) and not getattr(item, "is_folder", False) and _ok_name(item.name):
            out.append((item, folder))
        if getattr(item, "is_folder", False) or getattr(item, "is_device", False):
            queue.extend((c, item.name) for c in item.children)
    return out


def categories(browser):
    """[(key, label)]: the Sounds folders, the drum kits and every instrument's presets."""
    out = [("sounds:" + c.name, c.name) for c in _children(getattr(browser, "sounds", None))
           if getattr(c, "is_folder", False)]
    out.append((DRUM_KITS, "Kit di batteria"))
    out += [("instruments:" + d.name, "Preset di " + d.name) for d in _children(getattr(browser, "instruments", None))
            if getattr(d, "is_folder", False) or getattr(d, "is_device", False)]
    return out


def defaults(keys):
    """Type to start from for each role of an imported track."""
    out = {}
    for role, wanted in ROLE_DEFAULTS.items():
        out[role] = next((k for k in wanted if k in keys), keys[0] if keys else None)
    return out


# A drum bus of a sequence ("bus:<id>"): single hits (samples or Simpler presets, not whole kits) from Live's
# Drums category whose name, or the name of a folder above them, contains one of these words.
BUS_WORDS = {
    "kick": ["kick", "bassdrum", "bass drum", "bd "],
    "snare": ["snare", "sd "],
    "clap": ["clap", "snap"],
    "rim": ["rim", "stick", "woodblock"],
    "chat": ["closed", "hihat", "hi-hat", "hi hat", "hat"],
    "ohat": ["open", "hihat", "hi-hat", "hi hat", "hat"],
    "cymbal": ["cymbal", "ride", "crash", "china", "splash"],
    "perc": ["perc", "conga", "bongo", "shaker", "tamb", "cowbell", "clave", "block"],
    "tom": ["tom"],
    "fx": ["fx", "noise", "riser", "impact", "sweep", "reverse"],
}
BUS_MAX_VISITS = 6000


def _matches(name, words):
    n = " " + name.lower().replace("_", " ") + " "
    return any(w in n for w in words)


def collect_bus(roots, words, limit=MAX_ITEMS, max_visits=BUS_MAX_VISITS):
    """[(item, folder name)] of single hits for a drum bus under the given browser items, breadth first."""
    out, visits = [], 0
    queue = [(r, getattr(r, "name", ""), False) for r in roots]
    while queue and len(out) < limit and visits < max_visits:
        item, folder, matched = queue.pop(0)
        visits += 1
        name = item.name
        if getattr(item, "is_folder", False) or getattr(item, "is_device", False):
            here = matched or _matches(name, words)
            queue.extend((c, name, here) for c in item.children)
        elif getattr(item, "is_loadable", False) and not name.lower().endswith(".adg") \
                and (matched or _matches(name, words)):
            out.append((item, folder))
    return out


def bus_of(role):
    return role[4:] if role and role.startswith("bus:") and role[4:] in BUS_WORDS else None


def category_pool(browser, key):
    """All presets of a type, sorted by name: [(item, folder name)]."""
    bus = bus_of(key)
    kind, _, name = key.partition(":")
    if bus:
        pool = collect_bus(_children(browser.drums), BUS_WORDS[bus])
    elif key == DRUM_KITS:
        pool = [(i, f) for i, f in collect(_children(browser.drums)) if i.name.lower().endswith(".adg")]
    elif kind in ("sounds", "instruments"):
        pool = collect([c for c in _children(getattr(browser, kind, None)) if c.name == name])
    else:
        pool = []
    return sorted(pool, key=lambda e: _stem(e[0].name).lower())


def display_name(name):
    return _stem(name)
