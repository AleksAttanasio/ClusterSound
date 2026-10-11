# -*- coding: utf-8 -*-
"""Messages between the ClusterSound Max for Live device and this Remote Script (no Live imports, so it is
testable outside Live). Python 2.7 (Live 10) and 3 compatible.

Max's [udpsend] / [udpreceive] speak OSC, so every message is an OSC message "/clustersound" with a single
string argument holding a JSON object:

    device -> script  {"id": n, "cmd": "ping"}
                      {"id": n, "cmd": "load", "track": <track index>, "place": "<Place>/<dir>/…/<file>.adg"}
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


# ------------------------------------------------------------------ instrument suggestions
# Browser categories to draw from for each role of an imported track (folder names in Live's "Sounds",
# matched case-insensitively by prefix); the presets of installed Packs show up in these categories too.
ROLE_SOURCES = {
    "bass": [("sounds", ["bass"])],
    "chords": [("sounds", ["piano", "pad", "synth keys", "strings", "mallets", "keys"])],
    "drums": [("drums", None)],
}
FALLBACK_SOURCES = [("instruments", None)]
AUDIO_EXT = (".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg", ".m4a")
MAX_VISITS = 2500   # browser children are fetched lazily by Live: keep the walk short
MAX_ITEMS = 400


def _ok_name(name):
    return not name.lower().endswith(AUDIO_EXT)


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


def role_roots(browser, role):
    """Browser items to search for a role, and whether they are the generic fallback."""
    for sources, fallback in ((ROLE_SOURCES.get(role, []), False), (FALLBACK_SOURCES, True)):
        roots = []
        for attr, prefixes in sources:
            cat = getattr(browser, attr, None)
            if cat is None:
                continue
            if prefixes is None:
                roots.extend(cat.children)
            else:
                roots.extend(c for c in cat.children if any(c.name.lower().startswith(p) for p in prefixes))
        if roots:
            return roots, fallback
    return [], True


def pick(pool, count, seed):
    """`count` distinct entries of pool, reproducible for a seed."""
    import random
    if len(pool) <= count:
        return list(pool)
    return random.Random(seed).sample(pool, count)


def display_name(name):
    return _stem(name)
