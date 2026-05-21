#!/usr/bin/env sh
set -eu

SCRIPT_NAME="install.js"
DEFAULT_BASE_URL="https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent"
BASE_URL="${AI_TOOLS_INSTALLER_BASE_URL:-$DEFAULT_BASE_URL}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || pwd)
LOCAL_SCRIPT="$SCRIPT_DIR/$SCRIPT_NAME"
MIN_NODE_MAJOR=18
NODE_INSTALL_MAJOR=22

node_is_usable() {
  command -v node >/dev/null 2>&1 || return 1
  command -v npm >/dev/null 2>&1 || return 1
  node -e "process.exit(Number(process.versions.node.split('.')[0]) >= $MIN_NODE_MAJOR ? 0 : 1)" >/dev/null 2>&1
}

install_node_macos() {
  if command -v brew >/dev/null 2>&1; then
    printf '%s\n' "Installing Node.js with Homebrew..."
    brew install node
    return
  fi

  if ! command -v curl >/dev/null 2>&1; then
    printf '%s\n' "Error: curl is required to install Node.js." >&2
    exit 1
  fi

  if ! command -v sudo >/dev/null 2>&1; then
    printf '%s\n' "Error: sudo is required to install the official Node.js pkg." >&2
    exit 1
  fi

  case "$(uname -m)" in
    arm64|aarch64) NODE_ARCH=arm64 ;;
    *) NODE_ARCH=x64 ;;
  esac

  PKG_NAME=$(curl -fsSL "https://nodejs.org/dist/latest-v${NODE_INSTALL_MAJOR}.x/SHASUMS256.txt" | awk -v suffix="darwin-${NODE_ARCH}.pkg" '$2 ~ suffix "$" { print $2; exit }')
  if [ -z "$PKG_NAME" ]; then
    printf '%s\n' "Error: could not resolve Node.js macOS pkg name." >&2
    exit 1
  fi

  TMP_NODE_DIR=$(mktemp -d)
  trap 'rm -rf "$TMP_NODE_DIR"' EXIT INT TERM
  curl -fsSL "https://nodejs.org/dist/latest-v${NODE_INSTALL_MAJOR}.x/$PKG_NAME" -o "$TMP_NODE_DIR/$PKG_NAME"
  sudo installer -pkg "$TMP_NODE_DIR/$PKG_NAME" -target /
  rm -rf "$TMP_NODE_DIR"
  trap - EXIT INT TERM
}

ensure_node() {
  if node_is_usable; then
    return
  fi

  if [ "$(uname -s)" = "Darwin" ]; then
    printf '%s\n' "Node.js ${MIN_NODE_MAJOR}+ with npm was not found. Installing Node.js first..."
    install_node_macos
    PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:$PATH"
    export PATH
  else
    printf '%s\n' "Error: Node.js ${MIN_NODE_MAJOR}+ with npm is required on this platform." >&2
    exit 1
  fi

  if ! node_is_usable; then
    printf '%s\n' "Error: Node.js is installed but not available in PATH. Reopen the terminal and retry." >&2
    exit 1
  fi
}

ensure_node

if [ -f "$LOCAL_SCRIPT" ]; then
  if ( : < /dev/tty ) 2>/dev/null; then
    exec node "$LOCAL_SCRIPT" "$@" < /dev/tty
  fi
  exec node "$LOCAL_SCRIPT" "$@"
fi

if ! command -v curl >/dev/null 2>&1; then
  printf '%s\n' "Error: curl is required." >&2
  exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM
DOWNLOADED_SCRIPT="$TMP_DIR/$SCRIPT_NAME"

curl -fsSL "$BASE_URL/$SCRIPT_NAME" -o "$DOWNLOADED_SCRIPT"
if ( : < /dev/tty ) 2>/dev/null; then
  exec node "$DOWNLOADED_SCRIPT" "$@" < /dev/tty
fi
exec node "$DOWNLOADED_SCRIPT" "$@"
