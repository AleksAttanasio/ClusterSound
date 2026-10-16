#!/bin/sh
# Builds brand/ClusterSound.icns (the app's Dock/Finder icon) and brand/ClusterSound.ico (Windows) from
# brand/logo-mark.png:
# the drop mark on a dark grey squircle (the UI's lowered surface, #1c1c1c), with the ~10% margin macOS icons expect.
set -e
cd "$(dirname "$0")/.."
if [ -z "$SDKROOT" ]; then
  dev_path=$(xcode-select -p 2>/dev/null || true)
  if [ -d "$dev_path/SDKs/MacOSX.sdk" ]; then
    export SDKROOT="$dev_path/SDKs/MacOSX.sdk"
  elif [ -d "$dev_path/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk" ]; then
    export SDKROOT="$dev_path/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk"
  fi
fi
work=$(mktemp -d)
src=$work/logo-app.png
swift tools/render_icon.swift brand/logo-mark.png "$src" 1024 1c1c1c
set_dir=$work/ClusterSound.iconset
mkdir -p "$set_dir"
for s in 16 32 128 256 512; do
  sips -s format png -z $s $s "$src" --out "$set_dir/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2))
  sips -s format png -z $d $d "$src" --out "$set_dir/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$set_dir" -o brand/ClusterSound.icns
ico=""
for s in 16 24 32 48 64 128 256; do
  sips -s format png -z $s $s "$src" --out "$work/ico_$s.png" >/dev/null
  ico="$ico $work/ico_$s.png"
done
python3 tools/make_ico.py brand/ClusterSound.ico $ico >/dev/null
rm -rf "$work"
echo "Ready: brand/ClusterSound.icns, brand/ClusterSound.ico"
