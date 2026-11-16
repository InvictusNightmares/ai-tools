#!/usr/bin/env bash
# Extract the mPaaS SecurityGuard component from libsgmain.so.
# libsgmain.so is itself a ZIP/APK containing classes.dex + libsgmainso-*.so
# Usage: ./extract_securityguard.sh /path/to/mc10086-base.apk [out-dir]
set -euo pipefail

APK="${1:?usage: $0 <apk> [out-dir]}"
OUT="${2:-$(pwd)/out}"
APK="$(cd "$(dirname "$APK")" && pwd)/$(basename "$APK")"
SG="$OUT/securityguard"

mkdir -p "$OUT/libs" "$SG"

echo "[*] extract arm64 libs"
unzip -o -q "$APK" 'lib/arm64-v8a/*' -d "$OUT/_apk_libs"
cp -a "$OUT/_apk_libs/lib/arm64-v8a/." "$OUT/libs/" 2>/dev/null || true

echo "[*] extract libsgmain.so"
if [ ! -f "$OUT/libs/libsgmain.so" ]; then
  echo "[!] libsgmain.so not found"
  exit 1
fi
cp "$OUT/libs/libsgmain.so" "$SG/libsgmain.so"
file "$SG/libsgmain.so"

rm -rf "$SG/sgmain" "$SG/jadx"
mkdir -p "$SG/sgmain"
if unzip -tq "$SG/libsgmain.so" >/dev/null 2>&1; then
  echo "[*] nested APK detected; unzip"
  unzip -o -q "$SG/libsgmain.so" -d "$SG/sgmain"
else
  echo "[!] libsgmain.so is not a ZIP; copy as-is"
  cp "$SG/libsgmain.so" "$SG/sgmain/libsgmain.so"
fi

echo "[*] mpaas.properties"
unzip -p "$APK" assets/mpaas.properties > "$SG/mpaas.properties" 2>/dev/null || true
cat "$SG/mpaas.properties" 2>/dev/null || true

if [ -f "$SG/sgmain/classes.dex" ] && command -v jadx >/dev/null 2>&1; then
  echo "[*] jadx SecurityGuard classes.dex -> $SG/jadx"
  jadx -d "$SG/jadx" --no-res "$SG/sgmain/classes.dex"
fi

echo "[*] SecurityGuard native libs"
find "$SG/sgmain" -type f -name '*.so' -exec ls -lh {} \; 2>/dev/null || true
echo "[*] done: $SG"
