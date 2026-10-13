#!/bin/sh
# Builds brand/ClusterSound.icns (the app's Dock/Finder icon) from brand/logo-app.svg:
# the drop mark on a black squircle, already drawn with the ~10% margin macOS icons expect.
set -e
cd "$(dirname "$0")/.."
work=$(mktemp -d)
src=$work/logo-app.png
swift tools/render_svg.swift brand/logo-app.svg "$src" 1024
set_dir=$work/ClusterSound.iconset
mkdir -p "$set_dir"
for s in 16 32 128 256 512; do
  sips -s format png -z $s $s "$src" --out "$set_dir/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2))
  sips -s format png -z $d $d "$src" --out "$set_dir/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$set_dir" -o brand/ClusterSound.icns
rm -rf "$work"
echo "Pronto: brand/ClusterSound.icns"
