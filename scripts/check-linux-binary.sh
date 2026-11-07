#!/usr/bin/env bash
# Run inside a clean Debian/Ubuntu container, without Python installed.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
    libgl1 libegl1 libx11-6 libxext6 libxrender1 libxi6 \
    libxkbcommon-x11-0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-render-util0 libfontconfig1 libdbus-1-3 xvfb xauth
test "$(/release/clips-1.0-linux-x86_64 --version)" = 'Clips — Mascote do PC 1.0'
mkdir -p /tmp/clips-test
cd /tmp/clips-test
QT_QPA_PLATFORM=xcb xvfb-run -a /release/clips-1.0-linux-x86_64 --preview
test -s preview.png
