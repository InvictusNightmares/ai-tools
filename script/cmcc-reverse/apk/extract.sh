#!/usr/bin/env bash
# Extract China Mobile APK and decompile the shell DEX.
# Usage: ./extract.sh /path/to/mc10086-base.apk [out-dir]
set -euo pipefail

APK="${1:?usage: $0 <apk> [out-dir]}"
OUT="${2:-$(pwd)/out}"
APK="$(cd "$(dirname "$APK")" && pwd)/$(basename "$APK")"

mkdir -p "$OUT"

echo "[*] APK: $APK"
echo "[*] OUT: $OUT"

echo "[*] unzip apk"
rm -rf "$OUT/apk"
mkdir -p "$OUT/apk"
unzip -o -q "$APK" -d "$OUT/apk"

echo "[*] extract arm64 libs"
rm -rf "$OUT/libs"
mkdir -p "$OUT/libs"
if [ -d "$OUT/apk/lib/arm64-v8a" ]; then
  cp -a "$OUT/apk/lib/arm64-v8a/." "$OUT/libs/"
fi

echo "[*] list dex / nested apk-like libs"
find "$OUT/apk" -maxdepth 2 -name 'classes*.dex' -print
for f in "$OUT/libs/libsgmain.so" "$OUT/libs/libsgmainso.ucb.so"; do
  [ -f "$f" ] && file "$f" || true
done

if command -v jadx >/dev/null 2>&1; then
  echo "[*] jadx shell DEX -> $OUT/jadx"
  rm -rf "$OUT/jadx"
  jadx -d "$OUT/jadx" --no-res "$APK"
else
  echo "[!] jadx not found; skip decompile"
fi

echo "[*] done"
