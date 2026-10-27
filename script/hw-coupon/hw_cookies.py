#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从本机 Chrome 里解密华为云登录 Cookie（macOS）。

Chrome 的 Cookie 用 AES-128-CBC 加密，密钥来自钥匙串 "Chrome Safe Storage"，
PBKDF2-HMAC-SHA1(password, b"saltysalt", 1003, 16)，IV 为 16 个空格。
"""
import hashlib
import os
import shutil
import sqlite3
import subprocess
import tempfile

HOSTS = [
    ".huaweicloud.com",
    "developer.huaweicloud.com",
    "devdata.huaweicloud.com",
    ".huawei.com",
    "developer.huawei.com",
    "auth.huaweicloud.com",
]

# 只带这些域名的 cookie 给 devdata API
API_HOSTS = {".huaweicloud.com", "developer.huaweicloud.com", "devdata.huaweicloud.com"}

# 同名 cookie 跨域冲突时的优先级（数字越小越优先）
HOST_PRIORITY = {
    "devdata.huaweicloud.com": 0,
    "developer.huaweicloud.com": 1,
    ".huaweicloud.com": 2,
    "auth.huaweicloud.com": 3,
}

PROFILE = os.path.expanduser(
    os.environ.get("CHROME_PROFILE", "~/Library/Application Support/Google/Chrome/Default")
)


def _key():
    pw = subprocess.check_output(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage", "-a", "Chrome"]
    ).decode().strip()
    return hashlib.pbkdf2_hmac("sha1", pw.encode(), b"saltysalt", 1003, 16)


def _decrypt(enc, key):
    if not enc:
        return None
    if not enc.startswith(b"v10") and not enc.startswith(b"v20"):
        try:
            return enc.decode("utf-8")
        except UnicodeDecodeError:
            return None
    p = subprocess.run(
        ["openssl", "enc", "-aes-128-cbc", "-d", "-K", key.hex(), "-iv", (b" " * 16).hex(), "-nopad"],
        input=enc[3:],
        capture_output=True,
    )
    if p.returncode != 0 or not p.stdout:
        return None
    raw = p.stdout
    pad = raw[-1]
    if 1 <= pad <= 16 and raw.endswith(bytes([pad]) * pad):
        raw = raw[:-pad]
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


def read_jar(profile=PROFILE):
    """返回 {name: value}，失败抛异常。"""
    db = os.path.join(profile, "Cookies")
    if not os.path.exists(db):
        raise FileNotFoundError(f"找不到 Chrome Cookie 数据库: {db}")
    tmpdir = tempfile.mkdtemp(prefix="hwcookies-")
    tmp = os.path.join(tmpdir, "Cookies")
    shutil.copy2(db, tmp)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(db + suffix):
            shutil.copy2(db + suffix, tmp + suffix)
    con = sqlite3.connect(tmp)
    try:
        rows = con.execute(
            "select host_key,name,value,encrypted_value from cookies where host_key in (%s)"
            % ",".join("?" * len(HOSTS)),
            HOSTS,
        ).fetchall()
    finally:
        con.close()
        shutil.rmtree(tmpdir, ignore_errors=True)

    key = _key()
    jar = {}
    for host, name, value, enc in rows:
        if host not in API_HOSTS:
            continue
        v = value if value else _decrypt(enc, key)
        if not v:
            continue
        old = jar.get(name)
        if old is None or HOST_PRIORITY.get(host, 99) < HOST_PRIORITY.get(old[0], 99):
            jar[name] = (host, v)
    if "SessionID" not in jar and "HWS_ID" not in jar:
        raise RuntimeError("没有解出华为云登录态（Chrome 里可能未登录 developer.huaweicloud.com）")
    return {k: v for k, (_, v) in jar.items()}


def cookie_header(profile=PROFILE):
    jar = read_jar(profile)
    return "; ".join(f"{k}={v}" for k, v in jar.items())


if __name__ == "__main__":
    jar = read_jar()
    print(f"解出 {len(jar)} 个 cookie")
    for k in ("SessionID", "HWS_ID", "cbc-sid", "SSOTGC", "csrfToken"):
        if k in jar:
            print(f"  {k} = {jar[k][:16]}...")
    h = cookie_header()
    print("Cookie header 长度:", len(h))
