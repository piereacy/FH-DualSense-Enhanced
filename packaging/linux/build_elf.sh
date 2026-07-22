#!/usr/bin/env bash
# Build a standalone single-file ELF of FH-DualSense-Enhanced.
# Output: packaging/linux/dist/FH-DualSense-Enhanced-RN
# (no install, no traces - MEIPASS auto-cleans on exit)
# Requires: uv  (https://docs.astral.sh/uv/)
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DIST="$HERE/dist"
WORK="$HERE/build"

# MARK: read the internal numeric version from src/pyproject.toml
VER="$(grep -m1 '^version' "$ROOT/src/pyproject.toml" | cut -d'"' -f2)"
if [ -z "$VER" ]; then
    echo "Could not read version from src/pyproject.toml"
    exit 1
fi
echo "Building FH-DualSense-Enhanced R$VER ..."

rm -rf "$WORK" "$DIST"

# The frozen build uses pystray's locked python-xlib backend. PyGObject and
# pycairo are source-build dependencies on Linux and are not required inside
# this one-file artifact.
uv sync --project "$ROOT/src" --frozen \
    --no-install-package pygobject --no-install-package pycairo
uv run --project "$ROOT/src" --frozen --no-sync \
    pyinstaller "$HERE/fhds.spec" \
    --distpath "$DIST" --workpath "$WORK" \
    --noconfirm --clean

# MARK: rename output to include version
mv -f "$DIST/FH-DualSense-Enhanced" "$DIST/FH-DualSense-Enhanced-R$VER"
chmod +x "$DIST/FH-DualSense-Enhanced-R$VER"

echo
echo "Build OK. Binary: $DIST/FH-DualSense-Enhanced-R$VER"
