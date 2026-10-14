"""Install the ClusterSound Max for Live device and the ClusterSoundBridge Remote Script into Live's User Library.

    python tools/install_live.py ["/path/to/User Library"]

Default User Library: ~/Music/Ableton/User Library on macOS, ~/Documents/Ableton/User Library on Windows.
Then restart Live and pick "ClusterSoundBridge" in Preferences > Link/MIDI > Control Surface (Input/Output:
None). Racks for Live are staged in "<User Library>/ClusterSound", which Live's browser always indexes.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]

import build_amxd  # noqa: E402
from clustersound.live.payload import LIBRARY_FOLDER, USER_LIBRARY  # noqa: E402


def main(argv: list[str]) -> int:
    lib = Path(argv[0] if argv else USER_LIBRARY)
    if not lib.is_dir():
        print(f"User Library not found: {lib} (pass it as an argument)", file=sys.stderr)
        return 1
    dev = lib / "Presets" / "MIDI Effects" / "Max MIDI Effect" / "ClusterSound"
    print("Device:        ", build_amxd.build(dev))
    rs = lib / "Remote Scripts" / "ClusterSoundBridge"
    rs.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "remote_script" / "ClusterSoundBridge").glob("*.py"):
        shutil.copy2(f, rs / f.name)
    print("Remote Script: ", rs)
    racks = lib / LIBRARY_FOLDER
    racks.mkdir(exist_ok=True)
    print("Live racks:    ", racks)
    print("Restart Live if the Remote Script changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
