#!/bin/sh
# Install the ClusterSound Max for Live device and the ClusterSoundBridge Remote Script into Live's User Library.
#
#     tools/install_live.sh ["/path/to/User Library"]
#
# Then restart Live, pick "ClusterSoundBridge" in Preferences > Link/MIDI > Control Surface (Input/Output:
# None), and add ~/Music/ClusterSound Patterns to the browser Places.
set -e
cd "$(dirname "$0")/.."
LIB="${1:-$HOME/Music/Ableton/User Library}"
if [ ! -d "$LIB" ]; then
    echo "User Library non trovata: $LIB (passala come argomento)" >&2
    exit 1
fi
PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY=python3

DEV="$LIB/Presets/MIDI Effects/Max MIDI Effect/ClusterSound"
"$PY" tools/build_amxd.py --out "$DEV" >/dev/null
echo "Device:        $DEV/ClusterSound.amxd"

RS="$LIB/Remote Scripts/ClusterSoundBridge"
mkdir -p "$RS"
cp remote_script/ClusterSoundBridge/*.py "$RS/"
echo "Remote Script: $RS"

mkdir -p "$HOME/Music/ClusterSound Patterns"
echo "Aggiungi ai Places del browser di Live: $HOME/Music/ClusterSound Patterns"
