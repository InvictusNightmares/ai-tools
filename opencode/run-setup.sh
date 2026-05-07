#!/usr/bin/env sh
set -eu

SCRIPT_NAME="setup-opencode-bailian.js"
DEFAULT_BASE_URL="https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/opencode"
BASE_URL="${OPENCODE_SETUP_BASE_URL:-$DEFAULT_BASE_URL}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || pwd)
LOCAL_SCRIPT="$SCRIPT_DIR/$SCRIPT_NAME"

if [ -f "$LOCAL_SCRIPT" ]; then
  exec node "$LOCAL_SCRIPT" "$@"
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM
DOWNLOADED_SCRIPT="$TMP_DIR/$SCRIPT_NAME"

curl -fsSL "$BASE_URL/$SCRIPT_NAME" -o "$DOWNLOADED_SCRIPT"
exec node "$DOWNLOADED_SCRIPT" "$@"
