#!/usr/bin/env bash
# Build and install the Flatpak locally.
set -euo pipefail

APP_ID="dev.bayhan.GnomeTodo"
MANIFEST="$APP_ID.json"
BUILD_DIR="build-dir"
STATE_DIR=".flatpak-builder"
RUNTIME_VERSION="49"
REFRESH_SOURCES=0

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

usage() {
    cat <<EOF
Usage: $0 [--refresh-sources]

  --refresh-sources  Update cached VCS sources such as blueprint-compiler.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --refresh-sources)
            REFRESH_SOURCES=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$arg'." >&2
            usage >&2
            exit 1
            ;;
    esac
done

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

# Ensure required sources are available in the local Flatpak cache. By default
# we avoid updating cached VCS mirrors so pinned dependencies like
# blueprint-compiler are reused once downloaded.
download_args=(
    --download-only
    --force-clean
    --state-dir="$STATE_DIR"
)

if (( REFRESH_SOURCES )); then
    echo "Refreshing cached dependency sources..."
else
    echo "Reusing cached dependency sources..."
    download_args+=(--disable-updates)
fi

flatpak-builder "${download_args[@]}" "$BUILD_DIR" "$MANIFEST"

# Build and install.
echo "Building $APP_ID..."
builder_args=(
    --user
    --install
    --state-dir="$STATE_DIR"
    --force-clean
    --disable-download
)

flatpak-builder "${builder_args[@]}" "$BUILD_DIR" "$MANIFEST"

echo "Done. Launch with: flatpak run $APP_ID"
