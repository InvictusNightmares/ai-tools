#!/usr/bin/env python3
"""Automate China Mobile check-in on a non-root Android phone via ADB.

The phone must be logged in to the app and stay online. No root, no token,
no Frida. This script only taps the UI.

Example:
  python3 adb_checkin.py --device 100.x.x.x:5555
  python3 adb_checkin.py --device emulator-5554 --dry-run
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE = "com.greenpoint.android.mc10086.activity"
ACTIVITY = f"{PACKAGE}/com.mc10086.cmcc.base.StartPageActivity"
HOME_ENTRY = "签到有礼"
SIGN_RE = re.compile(r"(立即签到|补签|签到)")


def adb(device: str, *args: str, check: bool = True) -> str:
    cmd = ["adb", "-s", device, *args]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {result.stderr.strip()}")
    return result.stdout


def dump_ui(device: str) -> ET.Element:
    with tempfile.TemporaryDirectory() as tmp:
        remote = "/sdcard/cmcc_window.xml"
        local = Path(tmp) / "window.xml"
        adb(device, "shell", "uiautomator", "dump", remote)
        adb(device, "pull", remote, str(local))
        return ET.fromstring(local.read_text(encoding="utf-8"))


def find_node(root: ET.Element, text: str, contains: bool = False):
    for node in root.iter("node"):
        value = node.attrib.get("text", "")
        if (text in value) if contains else (value == text):
            return node
    return None


def find_sign_node(root: ET.Element):
    for node in root.iter("node"):
        value = node.attrib.get("text", "").strip()
        if value and SIGN_RE.search(value):
            return node
    return None


def center(node: ET.Element) -> tuple[int, int] | None:
    bounds = node.attrib.get("bounds", "")
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    if not match:
        return None
    x1, y1, x2, y2 = map(int, match.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def tap(device: str, node: ET.Element, dry_run: bool = False) -> None:
    point = center(node)
    if point is None:
        raise RuntimeError("node has no bounds")
    if dry_run:
        print(f"[dry] tap {point} text={node.attrib.get('text')!r}")
        return
    adb(device, "shell", "input", "tap", str(point[0]), str(point[1]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", required=True, help="adb serial, e.g. 100.x.x.x:5555")
    ap.add_argument("--home-entry", default=HOME_ENTRY)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--wait-home", type=float, default=7.0)
    ap.add_argument("--wait-page", type=float, default=5.0)
    args = ap.parse_args()

    d = args.device
    print(f"[*] device: {d}")

    adb(d, "shell", "input", "keyevent", "KEYCODE_WAKEUP", check=False)
    adb(d, "shell", "wm", "dismiss-keyguard", check=False)
    adb(d, "shell", "am", "force-stop", PACKAGE, check=False)
    adb(d, "shell", "am", "start", "-n", ACTIVITY)
    time.sleep(args.wait_home)

    print("[*] dump home")
    root = dump_ui(d)
    entry = find_node(root, args.home_entry, contains=True)
    if entry is None:
        print("[!] 未找到“签到有礼”，当前页面文本：")
        for node in root.iter("node"):
            text = node.attrib.get("text", "").strip()
            if text:
                print("   ", text[:80])
        return 2
    tap(d, entry, args.dry_run)

    time.sleep(args.wait_page)
    print("[*] dump check-in page")
    root = dump_ui(d)
    sign = find_sign_node(root)
    if sign is None:
        print("[!] 未找到签到按钮，当前页面文本：")
        for node in root.iter("node"):
            text = node.attrib.get("text", "").strip()
            if text:
                print("   ", text[:80])
        return 3
    print(f"[*] click: {sign.attrib.get('text')!r}")
    tap(d, sign, args.dry_run)

    time.sleep(3)
    root = dump_ui(d)
    texts = [n.attrib.get("text", "").strip() for n in root.iter("node")]
    if any("成功" in t or "已签到" in t for t in texts):
        print("[+] check-in success")
        return 0
    print("[?] clicked; verify manually if the page says something else")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
