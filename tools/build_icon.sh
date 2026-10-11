#!/bin/sh
# Builds brand/ClusterSound.icns (the app's Dock/Finder icon) from brand/logo-mark.webp.
# The source already has the ~12% transparent margin macOS icons expect, so it is only resized.
set -e
cd "$(dirname "$0")/.."
src=brand/logo-mark.webp
set_dir=$(mktemp -d)/ClusterSound.iconset
mkdir -p "$set_dir"
for s in 16 32 128 256 512; do
  sips -s format png -z $s $s "$src" --out "$set_dir/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2))
  sips -s format png -z $d $d "$src" --out "$set_dir/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$set_dir" -o brand/ClusterSound.icns
rm -rf "$(dirname "$set_dir")"
echo "Pronto: brand/ClusterSound.icns"
