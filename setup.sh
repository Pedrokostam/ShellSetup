#!/usr/bin/env bash

# echo "Elevation will be required at some points of the installation process."
# echo "The script will attempt to run a sudo command to cache credentials."
# sudo echo "Password cached"

if [ "$(id -u)" -eq 0 ] && [ "$FORCE" != true ]; then
    echo "Error: This script must not be run as root." >&2
    exit 1
fi

SCRIPT_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

# ensure python 3.9+; everything else lives in setup.py
if ! command -v python3 &> /dev/null || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo "Installing Python 3.9+..."
    # python is in Arch's official repos, so pacman suffices (no AUR/yay needed).
    if command -v pacman &> /dev/null; then
        sudo pacman -Sy --noconfirm python
    elif command -v apt &> /dev/null; then
        sudo apt update && sudo apt install -y python3
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3
    elif command -v zypper &> /dev/null; then
        sudo zypper --non-interactive install python3
    else
        echo "No supported package manager (pacman/apt/dnf/zypper) found for Python install." >&2
        exit 1
    fi
fi

python3 "$SCRIPT_DIR/setup.py"
