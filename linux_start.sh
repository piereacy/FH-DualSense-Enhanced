#!/usr/bin/env bash
# FH DualSense - Linux/macOS launcher (zuv).
# Bundle self-updates from GitHub Releases on each run; ZUV_NO_UPDATE=1 disables.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BUNDLE="$ROOT/fhds.zuv.py"

trap 'c=$?; echo; [ $# -eq 0 ] && read -r -p "Press Enter to close..." _ || true; exit $c' EXIT

if [ ! -f "$BUNDLE" ]; then
    echo "Could not find $BUNDLE."
    echo "Download fhds.zuv.py from https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python/releases/latest"
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    command -v uv >/dev/null 2>&1 || { echo "uv not on PATH - restart shell."; exit 1; }
fi

# Linux only: install DualSense udev rule once (needs sudo; can't live in the
# zuv bundle because /etc/udev is system-wide).
RULE_DST="/etc/udev/rules.d/70-dualsense.rules"
RULE_SRC="$ROOT/70-dualsense.rules"
if [ "$(uname -s)" = "Linux" ] && [ ! -f "$RULE_DST" ] && [ -f "$RULE_SRC" ]; then
    read -r -p "Install DualSense udev rule (sudo)? [Y/n] " ans
    case "${ans:-Y}" in [Nn]*) ;; *)
        sudo cp "$RULE_SRC" "$RULE_DST" \
            && sudo udevadm control --reload-rules && sudo udevadm trigger \
            && echo "Installed udev rule. Re-plug controller." ;;
    esac
fi

# Optional Steam wrapper: pass `steam steam://rungameid/1551360` (or any cmd)
# as launcher args. The game starts; fhds runs until the game exits.
if [ "$#" -gt 0 ]; then "$@" & fi

exec uv run "$BUNDLE"
