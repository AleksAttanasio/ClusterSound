#!/bin/sh
# Builds dist/ClusterSound.app and removes the intermediate onedir folder.
# That folder holds a bare Unix executable which Finder opens inside Terminal.app.
set -e
cd "$(dirname "$0")/.."
.venv/bin/pyinstaller --noconfirm ClusterSound.spec
rm -rf dist/ClusterSound
echo "Pronto: dist/ClusterSound.app"
