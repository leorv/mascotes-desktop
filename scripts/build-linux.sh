#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

image=clips-build:1.0
binary=clips-1.0-linux-x86_64
docker build --platform linux/amd64 -f packaging/Dockerfile.linux -t "$image" .
container=$(docker create "$image")
trap 'docker rm "$container" >/dev/null' EXIT
mkdir -p dist
docker cp "$container:/app/dist/$binary" "dist/$binary"
chmod +x "dist/$binary"
mkdir -p "dist/$binary-package"
cp "dist/$binary" LICENSE README.md "dist/$binary-package/"
tar -czf "dist/$binary.tar.gz" -C "dist/$binary-package" .
(cd dist && sha256sum "$binary" "$binary.tar.gz" > SHA256SUMS)
