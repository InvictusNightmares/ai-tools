#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 HAR / mitmproxy flow JSON 提取 autoLogin 模板，生成青龙私有 profile。

用法：
  python3 import_auto_login.py \
    --input cmcc.har --phone 188xxxxxxxx \
    --myway ff50a5e4eb9a4b15ba9b9e7d40dba32ca1 \
    --out cmcc_profile.json

输入可以是：
  - Proxyman / Charles / mitmproxy 导出的 HAR；
  - capture/qwhd_capture.py 保存的单条 flows/<id>.json。

脚本只读取 autoLogin 请求，解密模板，写出权限 0600 的 profile；不打印
手机号、xk、cellNum 或请求头。首次抓包流程见 notes/jsyd-login-chain.md。
"""

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

REQ_KEY, REQ_IV = b"tVkdaRWRY0ZkV1Vr", b"VjFSQ1ZtVkQxRTlQ"
DEFAULT_AUTO_URL = "https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin"
DEFAULT_JSYD_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/wkwebview "
    "leadeon/12.0.5/CMCCIT"
)
DEFAULT_SSO_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/wkwebview "
    "leadeon/12.5.2/CMCCIT"
)


def _cbc_decrypt(data):
    dec = Cipher(algorithms.AES(REQ_KEY), modes.CBC(REQ_IV)).decryptor()
    out = dec.update(data) + dec.finalize()
    pad = out[-1]
    if not 1 <= pad <= 16 or out[-pad:] != bytes([pad]) * pad:
        raise ValueError("invalid PKCS7 padding")
    return out[:-pad]


def decrypt_body(text):
    """兼容明文 JSON、单层 base64 和双层 base64。"""
    if not text:
        return None
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except ValueError:
            return None
    for _ in range(2):
        try:
            raw = base64.b64decode(text)
        except Exception:
            return None
        try:
            plain = _cbc_decrypt(raw)
        except Exception:
            # 可能是 base64(base64(cipher))；把内层文本再试一次
            text = raw.decode("utf-8", "ignore")
            continue
        try:
            return json.loads(plain.decode())
        except (ValueError, UnicodeDecodeError):
            text = plain.decode("utf-8", "ignore")
    return None


def headers_dict(headers):
    result = {}
    for item in headers or []:
        if isinstance(item, dict):
            name, value = item.get("name"), item.get("value")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            name, value = item
        else:
            continue
        if name:
            result[str(name).lower()] = str(value or "")
    return result


def entries(data):
    if isinstance(data.get("log"), dict):
        for entry in data["log"].get("entries") or []:
            req = entry.get("request") or {}
            body = (req.get("postData") or {}).get("text") or req.get("text") or ""
            yield req.get("url") or "", headers_dict(req.get("headers")), body
    elif isinstance(data.get("request"), dict):
        req = data["request"]
        yield req.get("url") or "", headers_dict(req.get("headers")), req.get("text") or ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="cmcc_profile.json")
    ap.add_argument("--phone", default=os.environ.get("CMCC_PHONE", ""))
    ap.add_argument("--province", default="250")
    ap.add_argument("--city", default="0512")
    ap.add_argument("--carrier", default="002")
    ap.add_argument("--app-version", default="12.5.6")
    ap.add_argument("--source", default="039014")
    ap.add_argument("--myway", default=os.environ.get("CMCC_MYWAY", ""))
    ap.add_argument("--auto-login-url", default=DEFAULT_AUTO_URL)
    ap.add_argument("--jsyd-user-agent", default=DEFAULT_JSYD_UA)
    ap.add_argument("--sso-user-agent", default=DEFAULT_SSO_UA)
    args = ap.parse_args(argv)

    phone = args.phone.strip()
    if not re.fullmatch(r"1\d{10}", phone):
        raise SystemExit("请用 --phone 或 CMCC_PHONE 提供 11 位手机号")
    if not re.fullmatch(r"[0-9a-fA-F]{16,128}", args.myway or ""):
        raise SystemExit("请用 --myway 或 CMCC_MYWAY 提供江苏活动 mywaytoopen 指纹")

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    for url, headers, body in entries(data):
        if "/autoLogin" not in url or not body:
            continue
        template = decrypt_body(body)
        if not isinstance(template, dict) or not template.get("xk"):
            continue
        profile = {
            "auto_login_url": args.auto_login_url or url,
            "auto_login_template": template,
            "xk": template["xk"],
            "phone": phone,
            "province_code": args.province,
            "city_code": args.city,
            "carrier_operator": args.carrier,
            "app_version_code": args.app_version,
            "source_id": args.source,
            "mywaytoopen": args.myway,
            "auto_login_user_agent": headers.get("user-agent", ""),
            "jsyd_user_agent": args.jsyd_user_agent,
            "sso_user_agent": args.sso_user_agent,
        }
        out = Path(args.out)
        out.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(out, 0o600)
        print(f"profile: {out} ({out.stat().st_size} bytes)")
        print(f"template keys: {', '.join(sorted(template.keys()))}")
        print(f"phone: 尾号 {phone[-4:]}；myway: 长度 {len(args.myway)}")
        return 0
    raise SystemExit("输入里没有可解密的 autoLogin 请求")


if __name__ == "__main__":
    sys.exit(main())
