#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 HAR / mitmproxy flow JSON 提取 autoLogin 模板，生成青龙私有 profile。

用法：
  python3 import_auto_login.py \
    --input cmcc.har --phone 188xxxxxxxx \
    --myway <mywaytoopen_hex> \
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
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

REQ_KEY, REQ_IV = b"tVkdaRWRY0ZkV1Vr", b"VjFSQ1ZtVkQxRTlQ"
RESP_KEY = b"RYV0hCV1lV25KYVJ"
DEFAULT_AUTO_URL = "https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin"
DEFAULT_APP_VERSION = "12.5.6"
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


def _cbc_decrypt(data, key=REQ_KEY, iv=REQ_IV):
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    out = dec.update(data) + dec.finalize()
    pad = out[-1]
    if not 1 <= pad <= 16 or out[-pad:] != bytes([pad]) * pad:
        raise ValueError("invalid PKCS7 padding")
    return out[:-pad]


def _decrypt_json_body(text, key=REQ_KEY, iv=REQ_IV):
    """兼容明文 JSON、base64(明文 JSON)、单层 base64 密文和双层 base64 密文。"""
    if not text:
        return None
    text = str(text).strip()
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
            plain = _cbc_decrypt(raw, key=key, iv=iv)
        except Exception:
            # 可能是 base64(明文 JSON) 或 base64(base64(cipher))；解开一层再试
            decoded = raw.decode("utf-8", "ignore").strip()
            if decoded.startswith("{"):
                try:
                    return json.loads(decoded)
                except ValueError:
                    return None
            text = decoded
            continue
        decoded_plain = plain.decode("utf-8", "ignore").strip()
        if decoded_plain.startswith("{"):
            try:
                return json.loads(decoded_plain)
            except ValueError:
                return None
        text = decoded_plain
    return None


def decrypt_body(text):
    """兼容明文 JSON、单层 base64 和双层 base64。"""
    return _decrypt_json_body(text, key=REQ_KEY, iv=REQ_IV)


def decrypt_response_body(text):
    """解密 autoLogin 响应正文（兼容明文 JSON 与单/双层 base64 密文）。"""
    return _decrypt_json_body(text, key=RESP_KEY, iv=REQ_IV)


def headers_dict(headers):
    if isinstance(headers, dict):
        return {str(k).lower(): str(v or "") for k, v in headers.items() if k}
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


def _extract_response_info(resp):
    if not isinstance(resp, dict):
        return None, ""
    status = resp.get("status_code")
    if status is None:
        status = resp.get("status")
    content = resp.get("content") if isinstance(resp.get("content"), dict) else {}
    body = content.get("text") or resp.get("text") or resp.get("body_base64") or ""
    return status, body


def entries_with_response(data):
    if isinstance(data.get("log"), dict):
        for entry in data["log"].get("entries") or []:
            req = entry.get("request") or {}
            body = (req.get("postData") or {}).get("text") or req.get("text") or req.get("body_base64") or ""
            status, resp_body = _extract_response_info(entry.get("response"))
            yield req.get("url") or "", headers_dict(req.get("headers")), body, status, resp_body
    elif isinstance(data.get("request"), dict):
        req = data["request"]
        body = req.get("text") or req.get("body_base64") or ""
        status, resp_body = _extract_response_info(data.get("response"))
        yield req.get("url") or "", headers_dict(req.get("headers")), body, status, resp_body


def entries(data):
    for url, headers, body, _status, _resp_body in entries_with_response(data):
        yield url, headers, body


def is_auto_login_url(url):
    parts = urlsplit(str(url or "").strip())
    return parts.scheme == "https" and bool(parts.netloc) and parts.path.rstrip("/").endswith("/autoLogin")


def is_valid_template(template):
    if not isinstance(template, dict):
        return False
    if not str(template.get("xk") or "").strip():
        return False
    req_body = template.get("reqBody")
    if not isinstance(req_body, dict) or not req_body:
        return False
    if "cellNum" in req_body and not str(req_body.get("cellNum") or "").strip():
        return False
    return True


def select_auto_login_candidate(data):
    """挑选最佳 autoLogin 记录：优先最新的 retCode=000000 成功记录，其次无响应记录，最后才回退到失败记录。"""
    candidates = []
    for idx, (url, headers, body, resp_status, resp_body) in enumerate(entries_with_response(data)):
        if not is_auto_login_url(url) or not body:
            continue
        template = decrypt_body(body)
        if not is_valid_template(template):
            continue
        resp_payload = decrypt_response_body(resp_body) if resp_body else None
        ret_code = None
        if isinstance(resp_payload, dict) and resp_payload.get("retCode") is not None:
            ret_code = str(resp_payload.get("retCode")).strip()
        if ret_code == "000000":
            tier = 2
        elif ret_code is None and (resp_status is None or resp_status == 200):
            tier = 1
        else:
            tier = 0
        candidates.append({
            "tier": tier,
            "index": idx,
            "url": url.strip(),
            "headers": headers,
            "template": template,
            "resp_status": resp_status,
            "ret_code": ret_code,
        })
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item["tier"], item["index"]))


def resolve_auto_login_url(captured_url, override_url=""):
    override = (override_url or "").strip()
    if override:
        return override
    captured = (captured_url or "").strip()
    if captured:
        return captured
    return DEFAULT_AUTO_URL


def resolve_app_version(template, override_version=""):
    override = (override_version or "").strip()
    if override:
        return override
    if isinstance(template, dict):
        cv = str(template.get("cv") or "").strip()
        if cv:
            return cv
    return DEFAULT_APP_VERSION


def build_webview_ua(app_version, fallback_ua):
    ver = str(app_version or "").strip()
    if re.fullmatch(r"\d+(?:\.\d+)+", ver):
        return re.sub(r"leadeon/[^/\s]+/CMCCIT", f"leadeon/{ver}/CMCCIT", fallback_ua)
    return fallback_ua


def safe_url_for_log(url):
    parts = urlsplit(str(url or ""))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def write_private_json(out_path, payload):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=out.parent, prefix=".profile-", delete=False
        ) as fh:
            tmp_path = Path(fh.name)
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, out)
        os.chmod(out, 0o600)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="cmcc_profile.json")
    ap.add_argument("--phone", default=os.environ.get("CMCC_PHONE", ""))
    ap.add_argument("--province", default="250")
    ap.add_argument("--city", default="0512")
    ap.add_argument("--carrier", default="002")
    ap.add_argument("--app-version", default="", help="显式覆盖 appVersionCode；默认优先对齐抓包模板 cv")
    ap.add_argument("--source", default="039014")
    ap.add_argument("--myway", default=os.environ.get("CMCC_MYWAY", ""))
    ap.add_argument("--auto-login-url", default="", help="显式覆盖 autoLogin URL；默认保留抓包真实 URL")
    ap.add_argument("--jsyd-user-agent", default="")
    ap.add_argument("--sso-user-agent", default="")
    args = ap.parse_args(argv)

    phone = (args.phone or "").strip()
    if not re.fullmatch(r"1\d{10}", phone):
        raise SystemExit("请用 --phone 或 CMCC_PHONE 提供 11 位手机号")
    myway = (args.myway or "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{16,128}", myway):
        raise SystemExit("请用 --myway 或 CMCC_MYWAY 提供江苏活动 mywaytoopen 指纹")

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    selected = select_auto_login_candidate(data)
    if selected is None:
        raise SystemExit("输入里没有可解密的 autoLogin 请求")

    url = selected["url"]
    headers = selected["headers"]
    template = selected["template"]
    auto_login_url = resolve_auto_login_url(url, args.auto_login_url)
    app_version = resolve_app_version(template, args.app_version)
    jsyd_ua = (args.jsyd_user_agent or "").strip() or build_webview_ua(app_version, DEFAULT_JSYD_UA)
    sso_ua = (args.sso_user_agent or "").strip() or build_webview_ua(app_version, DEFAULT_SSO_UA)
    profile = {
        "auto_login_url": auto_login_url,
        "auto_login_template": template,
        "xk": str(template["xk"]).strip(),
        "phone": phone,
        "province_code": str(args.province).strip(),
        "city_code": str(args.city).strip(),
        "carrier_operator": str(args.carrier).strip(),
        "app_version_code": app_version,
        "source_id": str(args.source).strip(),
        "mywaytoopen": myway,
        "auto_login_user_agent": headers.get("user-agent", "").strip(),
        "jsyd_user_agent": jsyd_ua,
        "sso_user_agent": sso_ua,
    }
    out = write_private_json(args.out, profile)
    print(f"profile: {out} ({out.stat().st_size} bytes)")
    print(f"auto_login_url: {safe_url_for_log(auto_login_url)}")
    print(f"app_version_code: {app_version} (packageName={template.get('packageName') or '-'})")
    if selected["ret_code"] is not None:
        print(f"captured_response: HTTP {selected['resp_status']} retCode={selected['ret_code']}")
        if selected["ret_code"] != "000000":
            print(f"警告：抓包响应 retCode={selected['ret_code']} 非 000000，请确认是否选错失败记录后再部署")
    elif selected["resp_status"] is not None and selected["resp_status"] != 200:
        print(f"警告：抓包响应 HTTP {selected['resp_status']}，请确认抓包是否成功")
    print(f"template keys: {', '.join(sorted(template.keys()))}")
    print(f"phone: 尾号 {phone[-4:]}；myway: 长度 {len(myway)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
