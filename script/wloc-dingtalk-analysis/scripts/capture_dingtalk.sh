#!/bin/bash
# Capture only the DingTalk process traffic from a USB-connected iPhone.
#
# Usage:
#   PMD3=/path/to/pymobiledevice3 ./capture_dingtalk.sh [OUT.pcap] [PROCESS_NAME]
#
# Requires: pymobiledevice3, iPhone unlocked and "Trust This Computer" accepted.
set -euo pipefail

PMD3=${PMD3:-pymobiledevice3}
PMD3_PY=${PMD3_PY:-python3}
OUT=${1:-./dingtalk.pcap}
PROC=${2:-}

if ! "$PMD3" usbmux list --simple 2>/dev/null | grep -q .; then
  echo "No USB device detected. Connect + unlock + Trust this computer first." >&2
  exit 1
fi

echo "== candidate DingTalk / Alibaba processes =="
"$PMD3" processes ps 2>/dev/null | "$PMD3_PY" -c '
import json
import sys

data = json.load(sys.stdin)
for pid, info in data.items():
    name = info.get("ProcessName", "")
    if any(k in name.lower() for k in ("ding", "alibaba", "amap")):
        print(pid, name)
' || true

if [ -z "$PROC" ]; then
  PROC=$("$PMD3" processes ps 2>/dev/null | "$PMD3_PY" -c '
import json
import sys

data = json.load(sys.stdin)
names = [info.get("ProcessName", "") for info in data.values()]
print(next((name for name in names if "dingtalk" in name.lower()), ""))
')
fi

if [ -z "$PROC" ]; then
  echo "Could not auto-detect the process name; pass it as the second argument." >&2
  exit 1
fi

echo "== capturing process: $PROC -> $OUT =="
echo "Now open DingTalk and the check-in page. Press Ctrl-C to stop."
exec "$PMD3" pcap --process "$PROC" --out "$OUT"
