#!/bin/sh
# Builds clustersound/bin/cs-tap, the Core Audio process-tap helper used by the Recorder (macOS 14.2+).
set -e
cd "$(dirname "$0")/.."
mkdir -p clustersound/bin
if [ -z "$SDKROOT" ]; then
  dev_path=$(xcode-select -p 2>/dev/null || true)
  if [ -d "$dev_path/SDKs/MacOSX.sdk" ]; then
    export SDKROOT="$dev_path/SDKs/MacOSX.sdk"
  elif [ -d "$dev_path/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk" ]; then
    export SDKROOT="$dev_path/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk"
  fi
fi
swiftc -O -swift-version 5 -target "$(uname -m)-apple-macos14.2" -o clustersound/bin/cs-tap clustersound/native/cs_tap.swift
codesign --force --sign - clustersound/bin/cs-tap
echo "Pronto: clustersound/bin/cs-tap"
