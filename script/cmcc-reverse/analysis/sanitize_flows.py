#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把原始抓包 flow 脱敏成可提交的分析样本。

输入：capture/qwhd_capture.py 保存的单条 flows/<id>.json，或 HAR 条目。
输出：analysis/samples/*.sanitized.json，敏感值统一替换，保留 URL、方法、
请求头名称、参数名、状态码和字段结构。

不处理 APK、二进制或未解密 body；这些只输出长度占位。
"""

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_auto_login import decrypt_body  # noqa: E402

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError:  # pragma: no cover
    Cipher = None

RESP_KEY, RESP_IV = b"RYV0hCV1lV25KYVJ", b"VjFSQ1ZtVkQxRTlQ"
SENSITIVE_KEYS = {
    "tel", "mobile", "cellnum", "imei", "imsi", "iccid", "xk", "ctid", "ak",
    "cid", "devtoken", "caid", "userid", "crmuserid", "username", "token",
    "jttoken", "accesstoken", "refreshtoken", "jwt", "jwttoken", "password",
    "passwd", "mobiledes", "email", "contactname", "contacttel", "contactaddr",
    "last_login_mobile", "sessionid", "jsessionid", "cmtokenid",
    "cmjsssocookie", "usermobileforbigdata", "usercountry", "usercounty",
    "userapplydate", "custicno", "custictype", "authcode", "sign", "xtoken",
    "gdpmobile", "webmobile", "webtrendsmobile", "appmobile", "bdmobile",
    "touchmobile", "mobileinfo", "usermobile", "mywaytoopen",
    "provincename", "cityname", "usessionid", "ssoid", "sessionid",
    "ticketid", "sessiontoken",
}
SENSITIVE_HEADERS = {
    "cookie", "set-cookie", "authorization", "x-token", "xs", "x-sign",
    "r-token", "hgvhv", "via", "x-request-id",
}
COOKIE_ATTRS = {"path", "domain", "expires", "max-age", "httponly", "secure", "samesite", "priority"}
SENSITIVE_PARAMS = {"token", "sid", "sign", "jwt", "ticket", "jtToken", "jt_token"}
PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
HEX_RE = re.compile(r"\b[0-9a-fA-F]{40,}\b")


def _decrypt_response(text):
    if Cipher is None or not text:
        return None
    for _ in range(2):
        try:
            raw = base64.b64decode(text.strip())
        except Exception:
            return None
        try:
            dec = Cipher(algorithms.AES(RESP_KEY), modes.CBC(RESP_IV)).decryptor()
            out = dec.update(raw) + dec.finalize()
            pad = out[-1]
            if not 1 <= pad <= 16 or out[-pad:] != bytes([pad]) * pad:
                return None
            return json.loads(out[:-pad].decode())
        except Exception:
            text = text.strip()
    return None


def mask_scalar(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return 0
    return "***"


def sanitize(value, key=""):
    if isinstance(value, dict):
        return {k: mask_scalar(v) if str(k).lower() in SENSITIVE_KEYS else sanitize(v, k)
                for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(item, key) for item in value]
    if isinstance(value, str):
        text = PHONE_RE.sub("188****0000", value)
        text = HEX_RE.sub("***", text)
        return text
    return value


def sanitize_headers(headers):
    result = {}
    for item in headers or []:
        if isinstance(item, dict):
            name, value = item.get("name"), item.get("value")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            name, value = item
        else:
            continue
        if not name:
            continue
        name = str(name).lower()
        value = str(value or "")
        if name in ("referer", "location"):
            result[name] = sanitize_url(value)
        elif name == "cookie":
            parts = []
            for pair in value.split(";"):
                key, sep, _ = pair.strip().partition("=")
                if not sep:
                    continue
                parts.append(f"{key}=***" if key.lower() not in COOKIE_ATTRS else pair.strip())
            result[name] = "; ".join(parts)
        elif name == "set-cookie":
            parts = []
            for pair in value.split(";"):
                key, sep, _ = pair.strip().partition("=")
                if not sep:
                    parts.append(pair.strip())
                elif key.lower() in COOKIE_ATTRS:
                    parts.append(pair.strip())
                else:
                    parts.append(f"{key}=***")
            result.setdefault(name, []).append("; ".join(parts))
        elif name in SENSITIVE_HEADERS or "token" in name or "auth" in name or "session" in name or "sign" in name:
            result[name] = "***"
        else:
            result[name] = value
    return result


def sanitize_url(url):
    parts = urlsplit(url)
    query = [(k, "***" if k.lower() in {p.lower() for p in SENSITIVE_PARAMS} else v)
             for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def sanitize_text_body(text):
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            return sanitize(json.loads(text))
        except ValueError:
            pass
    if "=" in text and "&" in text:
        pairs = []
        for key, value in parse_qsl(text, keep_blank_values=True):
            pairs.append(f"{key}={'***' if key.lower() in SENSITIVE_KEYS or key == 'mywaytoopen' else value}")
        return "&".join(pairs)
    return f"<{len(text)} bytes, redacted>"


def sanitize_flow(data):
    req = data.get("request") or {}
    resp = data.get("response") or {}
    url = req.get("url") or ""
    out = {
        "note": "已脱敏；*** 表示敏感值已移除",
        "request": {
            "method": req.get("method"),
            "url": sanitize_url(url),
            "headers": sanitize_headers(req.get("headers")),
        },
        "response": {
            "status_code": resp.get("status_code"),
            "headers": sanitize_headers(resp.get("headers")),
        },
    }
    body = req.get("text") or req.get("body_base64") or ""
    if "/autoLogin" in url:
        template = decrypt_body(body)
        out["request"]["body_plaintext"] = sanitize(template) if template else f"<{len(body)} bytes, redacted>"
        resp_body = resp.get("text") or ""
        decrypted = _decrypt_response(resp_body)
        out["response"]["body_plaintext"] = sanitize(decrypted) if decrypted else f"<{len(resp_body)} bytes, redacted>"
    else:
        out["request"]["body"] = sanitize_text_body(body)
        out["response"]["body"] = sanitize_text_body(resp.get("text") or "")
    return out


def name_for(req):
    url = req.get("url") or ""
    if "/autoLogin" in url:
        return "autoLogin.sanitized.json"
    if "jtWx10086AuthLogin" in url:
        return "jtWx10086AuthLogin.sanitized.json"
    if "provider-user/sso" in url:
        return "hyl-sso.sanitized.json"
    if "nact/action.do" in url:
        body = req.get("text") or ""
        for method in ("initIndexPage", "initChallengeFloor", "doSign"):
            if f"method={method}" in body:
                return f"act2510-{method}.sanitized.json"
        return "act2510-action.sanitized.json"
    return "flow.sanitized.json"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="+", required=True)
    ap.add_argument("--out-dir", default="analysis/samples")
    args = ap.parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = set()
    for path in args.input:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        req = data.get("request") or {}
        name = name_for(req)
        if name in names:
            stem = Path(path).stem[:8]
            name = name.replace(".sanitized.json", f"-{stem}.sanitized.json")
        names.add(name)
        out = sanitize_flow(data)
        target = out_dir / name
        target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(target, 0o644)
        print(f"{path} -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
