"""Wrap m4l/ClusterSound.maxpat into a Max for Live MIDI effect (.amxd).

    python tools/build_amxd.py [--out build/m4l]

An unfrozen .amxd is a small binary header followed by the patcher JSON:
    "ampf" <u32 LE 4> <device type: "mmmm" MIDI effect> "meta" <u32 LE 4> <u32 0> "ptch" <u32 LE n> <n bytes JSON>
ClusterSound.js is copied next to it: Max finds files in the device's own folder. To get a single
self-contained file, open the device in Live, then Edit → Freeze Device → Save.
"""
import argparse
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "m4l"
DEVICE_TYPES = {"midi": b"mmmm", "audio": b"aaaa", "instrument": b"iiii"}


def amxd_bytes(patcher_json: bytes, device: str = "midi") -> bytes:
    body = patcher_json.rstrip() + b"\n\0"
    return (b"ampf" + struct.pack("<I", 4) + DEVICE_TYPES[device]
            + b"meta" + struct.pack("<I", 4) + struct.pack("<I", 0)
            + b"ptch" + struct.pack("<I", len(body)) + body)


def build(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    amxd = out_dir / "ClusterSound.amxd"
    amxd.write_bytes(amxd_bytes((SRC / "ClusterSound.maxpat").read_bytes()))
    shutil.copy2(SRC / "ClusterSound.js", out_dir / "ClusterSound.js")
    return amxd


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "build" / "m4l"))
    print(build(Path(ap.parse_args().out)))
