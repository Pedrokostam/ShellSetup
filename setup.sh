#!/usr/bin/env bash

extra_args=()
for arg in "$@"; do
    case "$arg" in
        --root)
            root="true"
            export INSTALL_SCRIPT_OVERRIDE_ROOT='1'
            ;;
        *)
            extra_args+=("$arg")
            ;;
    esac
done

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

python3 "$SCRIPT_DIR/setup.py" "${extra_args[@]}"
