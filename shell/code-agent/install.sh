#!/usr/bin/env sh
set -eu

SCRIPT_NAME="install.js"
DEFAULT_BASE_URL="https://raw.githubusercontent.com/InvictusNightmares/ai-tools/main/shell/code-agent"
BASE_URL="${AI_TOOLS_INSTALLER_BASE_URL:-$DEFAULT_BASE_URL}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || pwd)
LOCAL_SCRIPT="$SCRIPT_DIR/$SCRIPT_NAME"

if [ -f "$LOCAL_SCRIPT" ]; then
  exec node "$LOCAL_SCRIPT" "$@"
fi

if ! command -v node >/dev/null 2>&1; then
  printf '%s\n' "Error: Node.js is required. Install Node.js 18+ and retry." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  printf '%s\n' "Error: curl is required." >&2
  exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM
DOWNLOADED_SCRIPT="$TMP_DIR/$SCRIPT_NAME"

curl -fsSL "$BASE_URL/$SCRIPT_NAME" -o "$DOWNLOADED_SCRIPT"
exec node "$DOWNLOADED_SCRIPT" "$@"
