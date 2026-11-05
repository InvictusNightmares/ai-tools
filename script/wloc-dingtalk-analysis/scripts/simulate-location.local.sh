#!/bin/bash
# Convenience wrapper for pymobiledevice3 location simulation (office coordinates included).
set -euo pipefail

PMD3=${PMD3:-pymobiledevice3}

case "${1:-}" in
  beijing)
    exec "$PMD3" developer dvt simulate-location set -- 39.908700 116.397500
    ;;
  office)
    exec "$PMD3" developer dvt simulate-location set -- 31.19161987 121.28696441
    ;;
  clear)
    exec "$PMD3" developer dvt simulate-location clear
    ;;
  *)
    echo "usage: $0 {beijing|office|clear}" >&2
    exit 2
    ;;
esac
