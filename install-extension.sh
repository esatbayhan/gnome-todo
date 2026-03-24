#!/usr/bin/env bash
# Install the GNOME Shell extension locally.
set -euo pipefail

UUID="gnome-todo-shell-ext@dev.bayhan"
RELOAD=0

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/extensions/$UUID"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
TARGET_DIR="$DATA_HOME/gnome-shell/extensions/$UUID"

usage() {
    cat <<EOF
Usage: $0 [--reload]

Installs the GNOME Shell extension into:
  $TARGET_DIR

Options:
  --reload   After copying files, try to disable/enable the extension so
             code changes are picked up without a full logout.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --reload)
            RELOAD=1
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

if ! command -v gsettings &>/dev/null; then
    echo "Error: gsettings is not installed." >&2
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is not installed." >&2
    exit 1
fi

if (( RELOAD )) && ! command -v gnome-extensions &>/dev/null; then
    echo "Error: gnome-extensions is required for --reload." >&2
    exit 1
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Error: Extension source directory not found: $SOURCE_DIR" >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"

for file in metadata.json extension.js stylesheet.css; do
    if [[ ! -f "$SOURCE_DIR/$file" ]]; then
        echo "Error: Missing extension file: $SOURCE_DIR/$file" >&2
        exit 1
    fi
    install -m 0644 "$SOURCE_DIR/$file" "$TARGET_DIR/$file"
done

echo "Marking $UUID as enabled..."
CURRENT_ENABLED="$(gsettings get org.gnome.shell enabled-extensions)"
UPDATED_ENABLED="$(
    CURRENT_ENABLED="$CURRENT_ENABLED" UUID="$UUID" python3 - <<'PY'
import ast
import os

raw = os.environ["CURRENT_ENABLED"].strip()
uuid = os.environ["UUID"]

if raw.startswith("@as "):
    raw = raw[4:]

enabled = ast.literal_eval(raw)
if uuid not in enabled:
    enabled.append(uuid)

print(repr(enabled))
PY
)"
gsettings set org.gnome.shell enabled-extensions "$UPDATED_ENABLED"
ACTUAL_ENABLED="$(gsettings get org.gnome.shell enabled-extensions)"

if [[ "$ACTUAL_ENABLED" != *"$UUID"* ]]; then
    echo "Error: Failed to enable $UUID in org.gnome.shell enabled-extensions." >&2
    echo "Current value: $ACTUAL_ENABLED" >&2
    exit 1
fi

echo "Extension installed at: $TARGET_DIR"
echo "Enabled extensions updated in org.gnome.shell."

if (( RELOAD )); then
    echo "Reloading $UUID..."
    if gnome-extensions disable "$UUID" >/dev/null 2>&1; then
        :
    fi

    if gnome-extensions enable "$UUID"; then
        echo "Extension reloaded successfully."
    else
        echo "Extension files were installed, but GNOME Shell could not reload it automatically." >&2
        echo "If this is the first install or GNOME Shell has not discovered it yet, log out and back in once." >&2
        exit 1
    fi
else
    echo "Use './install-extension.sh --reload' for faster code-test cycles."
    echo "Log out and back in for GNOME Shell to pick up a newly installed local extension."
fi
