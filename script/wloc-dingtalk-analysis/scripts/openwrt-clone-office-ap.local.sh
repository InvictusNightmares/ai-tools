#!/bin/sh
# Office-specific: clone the office AP on a 5GHz OpenWrt radio.
# Run this ON THE ROUTER over SSH, not on the Mac.
set -eu

SSID='CPI-RHZL-OFFICE'
BSSID='20:20:27:83:eb:10'
CHANNEL='44'
HTMODE='VHT40'          # Wi-Fi 6 routers: try HE40
PASSWORD='CHANGE_ME'    # set a local password for the clone

RADIO=$(uci show wireless | awk -F'[.=]' "/\.band='5g'/{print \$2; exit}")
if [ -z "${RADIO:-}" ]; then
  echo "No 5GHz radio found. Run 'uci show wireless' and set RADIO manually." >&2
  exit 1
fi

IFACE=$(uci show wireless | awk -F'[.=]' "/\.device='$RADIO'/{print \$2; exit}")
if [ -z "${IFACE:-}" ]; then
  IFACE="default_$RADIO"
  uci set wireless.$IFACE='wifi-iface'
  uci set wireless.$IFACE.device="$RADIO"
  uci set wireless.$IFACE.mode='ap'
  uci set wireless.$IFACE.network='lan'
fi

uci set wireless.$RADIO.channel="$CHANNEL"
uci set wireless.$RADIO.country='CN'
uci set wireless.$RADIO.htmode="$HTMODE"
uci set wireless.$IFACE.ssid="$SSID"
uci set wireless.$IFACE.encryption='psk2'
uci set wireless.$IFACE.key="$PASSWORD"
uci set wireless.$IFACE.macaddr="$BSSID"
uci commit wireless
wifi reload

sleep 2
echo '== verify: look for Access Point:' "$BSSID"
iwinfo 2>/dev/null | grep -i -B4 -A8 "$BSSID" || iwinfo
