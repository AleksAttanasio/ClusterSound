#!/bin/sh
# Builds clustersound/bin/cs-tap, the Core Audio process-tap helper used by the Recorder (macOS 14.2+).
set -e
cd "$(dirname "$0")/.."
mkdir -p clustersound/bin
swiftc -O -swift-version 5 -target "$(uname -m)-apple-macos14.2" -o clustersound/bin/cs-tap clustersound/native/cs_tap.swift
codesign --force --sign - clustersound/bin/cs-tap
echo "Ready: clustersound/bin/cs-tap"
