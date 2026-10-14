#!/bin/sh
# Builds dist/ClusterSound.app and removes the intermediate onedir folder.
# That folder holds a bare Unix executable which Finder opens inside Terminal.app.
set -e
cd "$(dirname "$0")/.."
[ -f brand/ClusterSound.icns ] || sh tools/build_icon.sh
sh tools/build_tap.sh  # Recorder helper (Core Audio process taps)
.venv/bin/pyinstaller --noconfirm ClusterSound.spec
rm -rf dist/ClusterSound
echo "Ready: dist/ClusterSound.app"
