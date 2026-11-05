#!/bin/bash
# Generic pymobiledevice3 location simulation wrapper.
#
# Usage:
#   ./simulate-location.sh beijing
#   OFFICE_LAT=31.19161987 OFFICE_LON=121.28696441 ./simulate-location.sh office
#   ./simulate-location.sh clear
#
# The "set" command runs in the foreground and must stay alive to keep the
# simulated location active. Ctrl-C stops it and the phone returns to its real
# location (or run "clear" in another terminal).
set -euo pipefail

PMD3=${PMD3:-pymobiledevice3}
BEIJING_LAT=${BEIJING_LAT:-39.908700}
BEIJING_LON=${BEIJING_LON:-116.397500}

case "${1:-}" in
  beijing)
    exec "$PMD3" developer dvt simulate-location set -- "$BEIJING_LAT" "$BEIJING_LON"
    ;;
  office)
    : "${OFFICE_LAT:?set OFFICE_LAT}"
    : "${OFFICE_LON:?set OFFICE_LON}"
    exec "$PMD3" developer dvt simulate-location set -- "$OFFICE_LAT" "$OFFICE_LON"
    ;;
  clear)
    exec "$PMD3" developer dvt simulate-location clear
    ;;
  *)
    echo "usage: $0 {beijing|office|clear}" >&2
    echo "office requires OFFICE_LAT and OFFICE_LON" >&2
    exit 2
    ;;
esac
