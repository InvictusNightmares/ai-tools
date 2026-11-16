#!/usr/bin/env python3
"""Scan an APK for API endpoints / security hints without extracting everything.

Usage:
  python3 scan_apk.py --apk mc10086-base.apk
  python3 scan_apk.py --apk mc10086-base.apk --needles doSignature,qwhdhub
"""
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

DEFAULT_NEEDLES = [
    "qwhdhub",
    "qwhdmark",
    "pointclock",
    "appTokenLogin",
    "jwtLogin",
    "jsydsjkhd10086",
    "QWHD_SESSION_TOKEN",
    "QWHDSSO",
    "doSignature",
    "doSignHttpRequest",
    "doSignContent2Header",
    "doCommandNative",
    "SecurityGuard",
    "ISecureSignatureComponent",
    "getAppKey",
    "appKey",
    "authCode",
    "mPaaS",
    "nact/action.do",
    "act2510",
    "client.app.coc.10086.cn",
    "clientaccess.10086.cn",
    "SessionServer-orange",
    "DexHelper",
    "libDexHelper",
]

TEXT_SUFFIXES = (
    ".js", ".json", ".xml", ".txt", ".properties", ".html", ".htm",
    ".css", ".mf", ".prof", ".config", ".yaml", ".yml", ".ini",
)


def context(data: bytes, off: int, radius: int) -> str:
    chunk = data[max(0, off - radius): off + radius]
    # Keep printable runs only so binary noise does not flood the output.
    runs = re.findall(rb"[ -~]{4,}", chunk)
    text = " | ".join(r.decode("latin-1") for r in runs[-8:])
    return text[:1200]


def should_scan(name: str, max_size: int) -> bool:
    low = name.lower()
    if low.endswith(".so") or low.endswith(".dex"):
        return True
    if low.startswith("assets/") and low.endswith(TEXT_SUFFIXES):
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", required=True)
    ap.add_argument("--needles", default=",".join(DEFAULT_NEEDLES))
    ap.add_argument("--max-size", type=int, default=220 * 1024 * 1024)
    ap.add_argument("--context", type=int, default=160)
    args = ap.parse_args()

    apk = Path(args.apk)
    needles = [n.encode() for n in args.needles.split(",") if n]
    hits = 0

    with zipfile.ZipFile(apk) as zf:
        for info in zf.infolist():
            if info.file_size > args.max_size:
                print(f"[skip] {info.filename} ({info.file_size} bytes)")
                continue
            if not should_scan(info.filename, args.max_size):
                continue

            data = zf.read(info)
            found = []
            for needle in needles:
                pos = 0
                while True:
                    idx = data.find(needle, pos)
                    if idx < 0:
                        break
                    found.append((needle.decode("latin-1"), idx))
                    pos = idx + 1
                    if len(found) >= 20:
                        break

            if not found:
                continue

            print(f"\n=== {info.filename} ({len(data)} bytes) ===")
            for needle, idx in found:
                hits += 1
                print(f"[{idx:#x}] {needle}")
                print("  " + context(data, idx, args.context))

    print(f"\n[*] total hits: {hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
