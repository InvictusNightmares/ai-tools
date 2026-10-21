#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
desktop_node='/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness'

if [ ! -x "$desktop_node" ]; then
  printf '%s\n' '未找到 /Applications/DeepSeek Harness.app；此脚本用于官方 macOS 桌面版。' >&2
  exit 1
fi

ELECTRON_RUN_AS_NODE=1 exec "$desktop_node" --expose-internals "$script_dir/local-install-desktop.mjs" "$@"
