#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从本机 Chrome 解密 GLaDOS 登录 Cookie（macOS），生成 .env.local。

Chrome 的 Cookie 用 AES-128-CBC 加密，密钥来自钥匙串 "Chrome Safe Storage"：
PBKDF2-HMAC-SHA1(password, b"saltysalt", 1003, 16)，IV 为 16 个空格。

用法：
  python3 import_chrome.py
  set -a; source .env.local; set +a
  python3 glados_checkin.py --check

仅在 Chrome 已登录 https://glados.cloud 时有效。钥匙串可能弹窗要求授权。
"""

import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

PROFILE = os.path.expanduser(
    os.environ.get("CHROME_PROFILE", "~/Library/Application Support/Google/Chrome/Default")
)
HOSTS = ("glados.cloud", ".glados.cloud")
WANTED = ("gld:sess", "gld:sess.sig", "gld:accts", "gld:accts.sig", "koa:sess", "koa:sess.sig")
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.local")


def _key():
    password = subprocess.check_output(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage", "-a", "Chrome"]
    ).decode().strip()
    return hashlib.pbkdf2_hmac("sha1", password.encode(), b"saltysalt", 1003, 16)


def _decrypt(encrypted, key):
    if not encrypted:
        return None
    if not encrypted.startswith((b"v10", b"v20")):
        try:
            return encrypted.decode("utf-8")
        except UnicodeDecodeError:
            return None
    proc = subprocess.run(
        ["openssl", "enc", "-aes-128-cbc", "-d", "-K", key.hex(),
         "-iv", (b" " * 16).hex(), "-nopad"],
        input=encrypted[3:], capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return None
    raw = proc.stdout
    pad = raw[-1]
    if 1 <= pad <= 16 and raw.endswith(bytes([pad]) * pad):
        raw = raw[:-pad]
    # 新版 Chrome 在明文前附加 32 字节域名哈希
    for host in HOSTS:
        if raw.startswith(hashlib.sha256(host.encode()).digest()):
            raw = raw[32:]
            break
    else:
        if len(raw) > 32:
            try:
                raw[32:].decode("utf-8")
                raw = raw[32:]
            except UnicodeDecodeError:
                pass
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def read_cookies():
    db = os.path.join(PROFILE, "Cookies")
    if not os.path.exists(db):
        raise SystemExit(f"找不到 Chrome Cookie 数据库：{db}")
    tmpdir = tempfile.mkdtemp(prefix="glados-cookies-")
    shutil.copy2(db, os.path.join(tmpdir, "Cookies"))
    for suffix in ("-wal", "-shm"):
        if os.path.exists(db + suffix):
            shutil.copy2(db + suffix, os.path.join(tmpdir, "Cookies" + suffix))
    con = sqlite3.connect(os.path.join(tmpdir, "Cookies"))
    try:
        rows = con.execute(
            "select host_key,name,value,encrypted_value from cookies "
            "where host_key in (%s)" % ",".join("?" * len(HOSTS)),
            HOSTS,
        ).fetchall()
    finally:
        con.close()
        shutil.rmtree(tmpdir, ignore_errors=True)

    key = _key()
    jar = {}
    for host, name, value, encrypted in rows:
        if name not in WANTED:
            continue
        resolved = value or _decrypt(encrypted, key)
        if resolved:
            jar[name] = resolved
    if "gld:sess" not in jar or "gld:sess.sig" not in jar:
        raise SystemExit(
            "Chrome 里没有完整的 GLaDOS 登录态（gld:sess / gld:sess.sig）。"
            "请先在 Chrome 打开 https://glados.cloud 并登录。"
        )
    return jar


def detect_ua():
    """优先用 Playwright 读取真实 Chrome UA，失败则按版本拼接。"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page()
            page.goto("about:blank")
            ua = page.evaluate("navigator.userAgent")
            browser.close()
        # 无头模式会带 HeadlessChrome，真实浏览器不会
        return ua.replace("HeadlessChrome/", "Chrome/")
    except Exception:  # noqa: BLE001
        pass
    try:
        version = subprocess.check_output(
            ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"]
        ).decode().strip()
        major = re.search(r"(\d+)\.", version).group(1)
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{major}.0.0.0 Safari/537.36"
        )
    except Exception:  # noqa: BLE001
        return ""


def shell_quote(value):
    return "'" + value.replace("'", "'\\''") + "'"


def main():
    jar = read_cookies()
    ua = detect_ua()
    cookie = "; ".join(f"{name}={value}" for name, value in jar.items())
    lines = [
        "# 由 import_chrome.py 生成，含登录凭据，禁止提交或分享",
        f"export GLADOS_COOKIE={shell_quote(cookie)}",
    ]
    if ua:
        lines.append(f"export GLADOS_USER_AGENT={shell_quote(ua)}")
    lines.append("")
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    os.chmod(OUTPUT, 0o600)

    print(f"已写入 {OUTPUT}（权限 0600）")
    print("Cookie: " + "; ".join(f"{name}=***" for name in jar))
    print("User-Agent: " + (ua or "未获取"))
    print("\n下一步：")
    print(f"  set -a; source {OUTPUT}; set +a")
    print("  python3 glados_checkin.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
