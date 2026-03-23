#!/usr/bin/env bash
# Build and install the Flatpak locally.
set -euo pipefail

APP_ID="dev.bayhan.GnomeTodo"
MANIFEST="$APP_ID.json"
BUILD_DIR="build-dir"
RUNTIME_VERSION="49"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check for required tools.
for cmd in flatpak flatpak-builder; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: $cmd is not installed." >&2
        exit 1
    fi
done

# Ensure user-level Flathub remote is configured.
if ! flatpak remote-list --user | grep -q flathub; then
    echo "Adding Flathub user remote..."
    flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
fi

# Ensure runtime and SDK are installed.
for ref in org.gnome.Platform org.gnome.Sdk; do
    if ! flatpak info "$ref//$RUNTIME_VERSION" &>/dev/null; then
        echo "Installing $ref $RUNTIME_VERSION..."
        flatpak install --user -y "$ref//$RUNTIME_VERSION"
    fi
done

# Build and install.
echo "Building $APP_ID..."
flatpak-builder --user --install --force-clean "$BUILD_DIR" "$MANIFEST"

echo "Done. Launch with: flatpak run $APP_ID"
