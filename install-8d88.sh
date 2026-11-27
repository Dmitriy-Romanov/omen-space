#!/usr/bin/env bash
# Install this 8D88 fork from a fresh Linux system.
# Run as a normal user with sudo; do not run the curl pipe as root.
set -euo pipefail

if [[ $EUID -eq 0 ]]; then
    echo "Run this script as your normal user, not as root. It will call sudo."
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    echo "git is required. Install it first (apt/dnf/pacman), then rerun."
    exit 1
fi
if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required."
    exit 1
fi

REPO="Dmitriy-Romanov/omen-space"
TMP_DIR="$(mktemp -d /tmp/omen-space-8d88.XXXXXX)"
echo "Cloning https://github.com/$REPO.git into $TMP_DIR"
git clone --depth 1 "https://github.com/$REPO.git" "$TMP_DIR"
cd "$TMP_DIR"

echo "Building and installing (the project installer will ask for sudo)..."
sudo ./setup.sh install --non-interactive

echo
echo "Installed. Check:"
echo "  systemctl is-active omen-space-daemon"
echo "  omen-gui"

if command -v mokutil >/dev/null 2>&1 && mokutil --sb-state 2>/dev/null | grep -q "SecureBoot enabled"; then
    echo
    echo "Secure Boot is enabled. If hp-omen-extra is not loaded, sign it:"
    echo "  sudo $TMP_DIR/driver/sign-modules.sh"
    echo "Then reboot and complete MOK enrolment if prompted."
fi

echo
echo "Source kept at $TMP_DIR for the signing script."
