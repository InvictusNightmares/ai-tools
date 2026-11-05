#!/bin/sh
# Generic template: clone an office AP BSSID on a 5GHz OpenWrt radio.
#
# Run ON THE ROUTER over SSH:
#   OFFICE_SSID='OFFICE_SSID' \
#   OFFICE_BSSID='AA:BB:CC:DD:EE:FF' \
#   OFFICE_CHANNEL='44' \
#   WIFI_PASSWORD='CHANGE_ME' \
#   ./openwrt-clone-office-ap.sh
#
# Optional: RADIO=radio1 IFACE=default_radio1 HTMODE=VHT40
set -eu

SSID=${OFFICE_SSID:?set OFFICE_SSID}
BSSID=${OFFICE_BSSID:?set OFFICE_BSSID}
CHANNEL=${OFFICE_CHANNEL:-44}
HTMODE=${HTMODE:-VHT40}
PASSWORD=${WIFI_PASSWORD:?set WIFI_PASSWORD}

RADIO=${RADIO:-$(uci show wireless | awk -F'[.=]' "/\.band='5g'/{print \$2; exit}")}
if [ -z "${RADIO:-}" ]; then
  echo "No 5GHz radio found. Run 'uci show wireless' and set RADIO manually." >&2
  exit 1
fi

IFACE=${IFACE:-$(uci show wireless | awk -F'[.=]' "/\.device='$RADIO'/{print \$2; exit}")}
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
