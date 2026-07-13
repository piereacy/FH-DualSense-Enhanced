#!/usr/bin/env bash
# FH-DualSense-Enhanced launcher.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$ROOT/app"
BUNDLE="$APP/FH-DualSense-Enhanced.zuv.py"
MANUAL="$ROOT/FH-DualSense-Enhanced.zuv.py"
REPO="piereacy/FH-DualSense-Enhanced"
URL="https://github.com/$REPO/releases/latest/download/FH-DualSense-Enhanced.zuv.py"

mkdir -p "$APP"
if [[ ! -f "$BUNDLE" && -f "$MANUAL" ]]; then
    echo "Using manually downloaded FH-DualSense-Enhanced.zuv.py..."
    cp "$MANUAL" "$BUNDLE"
fi
if [[ ! -f "$BUNDLE" ]]; then
    echo "Downloading FH-DualSense-Enhanced.zuv.py..."
    curl -LsSf --fail "$URL" -o "$BUNDLE" || {
        echo "Download failed. Download the ZUV manually from:" >&2
        echo "https://github.com/$REPO/releases" >&2
        echo "Then place it beside linux_start.sh and retry." >&2
        exit 1
    }
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

unset PYTHONHOME
unset PYTHONPATH
export PYTHONNOUSERSITE=1
export UV_PYTHON_PREFERENCE=only-managed

exec uv run "$BUNDLE" "$@"
