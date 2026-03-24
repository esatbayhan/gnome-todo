#!/usr/bin/env bash
# Install the Flatpak app and GNOME Shell extension.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REFRESH_SOURCES=0

usage() {
    cat <<EOF
Usage: $0 [--refresh-sources]

Runs both installers:
  1. install-flatpak.sh
  2. install-extension.sh

Options:
  --refresh-sources  Refresh cached Flatpak dependency sources.
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

flatpak_args=()
if (( REFRESH_SOURCES )); then
    flatpak_args+=(--refresh-sources)
fi

"$SCRIPT_DIR/install-flatpak.sh" "${flatpak_args[@]}"
"$SCRIPT_DIR/install-extension.sh"

echo "Done. The app and GNOME Shell extension are installed."
