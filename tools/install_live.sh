#!/bin/sh
# Install the ClusterSound Max for Live device and the ClusterSoundBridge Remote Script into Live's User Library.
#
#     tools/install_live.sh ["/path/to/User Library"]
#
# Same as tools/install_live.py (which also runs on Windows): see there for the steps in Live.
set -e
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY=python3
exec "$PY" tools/install_live.py "$@"
