"""Pack square PNGs into a Windows .ico (PNG-compressed entries, Windows Vista and later).

    python tools/make_ico.py out.ico icon_16.png icon_32.png … icon_256.png
"""
import struct
import sys
from pathlib import Path


def png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])


def make_ico(pngs: list[bytes]) -> bytes:
    pngs = sorted(pngs, key=lambda d: png_size(d)[0])
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, body = b"", b""
    for data in pngs:
        w, h = png_size(data)
        assert w == h and w <= 256, f"icon sizes must be square, at most 256: {w}x{h}"
        entries += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(data), offset + len(body))
        body += data
    return head + entries + body


if __name__ == "__main__":
    out, *srcs = sys.argv[1:]
    Path(out).write_bytes(make_ico([Path(s).read_bytes() for s in srcs]))
    print(out)
