#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中国移动江苏 act2510 自动签到（会话自动续期）。

链路：
  1. autoLogin 现签 client.app.coc 会话
  2. appTokenLogin 换 QWHD 会话
  3. getYDRZToken(sourceId=039014) 换 JSYD jtToken
  4. jtWx10086AuthLogin 换江苏活动 Cookie
  5. initIndexPage 查状态，必要时 doSign

私有配置（0600）：/ql/data/config/cmcc_profile.json

用法：
  python3 cmcc_auto.py --check     # 只查登录/签到状态
  python3 cmcc_auto.py             # 签到，成功后发飞书通知

环境变量：
  CMCC_PROFILE      私有配置路径，默认 /ql/data/config/cmcc_profile.json
  QL_FEISHU_APP_ID / QL_FEISHU_APP_SECRET / QL_FEISHU_OPEN_ID  可选通知
"""

import argparse
import base64
import hashlib
import json
import os
import random
import re
import ssl
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

SALT = "Leadeon/SecurityOrganization"
REQ_KEY, REQ_IV = b"tVkdaRWRY0ZkV1Vr", b"VjFSQ1ZtVkQxRTlQ"
RESP_KEY = b"RYV0hCV1lV25KYVJ"
TOK_KEY, TOK_IV = b"bAIgvwAuA4tbDr9d", b"9791027341711819"

QWHD_BASE = "https://wx.10086.cn"
SSO_LOGIN = QWHD_BASE + "/qwhdsso/login"
DEFAULT_ACT_URL = QWHD_BASE + "/qwhdhub/qwhdmark/1021122301?channelId=P00000109876"
JSYD_LOGIN = "https://wap.js.10086.cn/vw/gateway/auth/auth/jtWx10086AuthLogin"
JSYD_ACTION = "https://wap.js.10086.cn/nact/action.do"
JSYD_REFERER = "https://wap.js.10086.cn/nact/resource/2510/html/index.html"
DEFAULT_PROFILE = "/ql/data/config/cmcc_profile.json"
LEGACY_SERVER_CONNECT = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
DEFAULT_SSO_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/wkwebview "
    "leadeon/12.5.2/CMCCIT"
)
DEFAULT_JSYD_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/wkwebview "
    "leadeon/12.0.5/CMCCIT"
)


class LegacyAdapter(HTTPAdapter):
    """wx.10086.cn / client.app.coc 需要 legacy renegotiation。"""

    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.set_ciphers("DEFAULT@SECLEVEL=1")
        context.options |= LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)


def new_session():
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", LegacyAdapter())
    return session


def _cbc(key, iv, data, encrypt):
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    if encrypt:
        pad = 16 - len(data) % 16
        enc = cipher.encryptor()
        return enc.update(data + bytes([pad]) * pad) + enc.finalize()
    dec = cipher.decryptor()
    out = dec.update(data) + dec.finalize()
    pad = out[-1]
    if not 1 <= pad <= 16 or out[-pad:] != bytes([pad]) * pad:
        raise ValueError("invalid PKCS7 padding")
    return out[:-pad]


def encrypt_body(plain):
    return base64.b64encode(_cbc(REQ_KEY, REQ_IV, plain.encode(), True)).decode()


def decrypt_response(raw):
    text = raw.decode("utf-8", "replace").strip()
    for _ in range(2):
        try:
            plain = _cbc(RESP_KEY, REQ_IV, base64.b64decode(text), False).decode()
        except Exception:
            return None
        if plain.startswith("{"):
            return json.loads(plain)
        text = plain
    return None


def build_headers(url, plain, cookie, xk, user_agent):
    jsid = re.search(r"JSESSIONID=([^;]+)", cookie).group(1)
    ts = str(int(time.time() * 1000))
    nonce = str(random.randint(10_000_000, 99_999_999))
    path = re.sub(r"^https?://[^/]+", "", url)
    token = base64.b64encode(
        _cbc(TOK_KEY, TOK_IV, f"{xk}_{path}_{ts}_{nonce}".encode(), True)
    ).decode()
    return {
        "x-qen": "14",
        "Accept": "*/*",
        "xs": hashlib.md5(f"{url}_{plain}_{SALT}".encode()).hexdigest(),
        "x-sign": hashlib.md5(f"{token}_{ts}_{nonce}_{jsid}".encode()).hexdigest(),
        "x-nonce": nonce,
        "x-token": token,
        "Accept-Encoding": "deflate",
        "Content-Type": "application/Json",
        "x-time": ts,
        "User-Agent": user_agent,
        "Cookie": cookie,
    }


def api_headers(referer):
    return {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json;charset=UTF-8",
        "origin": QWHD_BASE,
        "referer": referer,
        "login-check": "1",
        "x-requested-with": "XMLHttpRequest",
    }


def load_profile(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = ("auto_login_url", "auto_login_template", "xk", "phone",
                "province_code", "city_code", "source_id", "mywaytoopen")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise RuntimeError("配置缺少字段：" + ", ".join(missing))
    return data


def mint_session(profile):
    url = profile["auto_login_url"]
    template = profile["auto_login_template"]
    plain = json.dumps(template, separators=(",", ":"), ensure_ascii=False)
    placeholder = f"JSESSIONID={uuid.uuid4()}; UID=placeholder"
    headers = build_headers(
        url, plain, placeholder, profile["xk"],
        profile.get("auto_login_user_agent", "ChinaMobile/12.0.5 (iPhone; iOS 26.6.1; Scale/3.00)"),
    )
    session = new_session()
    response = session.post(url, data=encrypt_body(plain), headers=headers, timeout=25)
    payload = decrypt_response(response.content) or {}
    code = str(payload.get("retCode"))
    if code != "000000":
        raise RuntimeError(f"autoLogin 失败: retCode={code} {str(payload.get('retDesc', ''))[:80]}")
    cookie = response.headers.get("Set-Cookie")
    if not cookie:
        raise RuntimeError("autoLogin 未返回 Set-Cookie")
    return cookie


def exchange_qwhd(profile, app_cookie):
    session = new_session()
    session.headers.update({
        "user-agent": profile.get("sso_user_agent", DEFAULT_SSO_UA),
        "accept-language": "zh-CN,zh-Hans;q=0.9",
    })
    act_url = profile.get("act_url", DEFAULT_ACT_URL)
    response = session.get(SSO_LOGIN, params={"dlwmh": "true", "actUrl": act_url}, timeout=30)
    match = re.search(r"loginPath\s*=\s*'([^']+)'", response.text)
    if not match:
        raise RuntimeError("SSO 登录页未返回 loginPath")
    login_url = QWHD_BASE + "/qwhdsso" + match.group(1)
    body = {
        "provinceCode": profile["province_code"],
        "cityCode": profile["city_code"],
        "userCheckId": format(int(profile["phone"]), "x"),
        "carrierOperator": profile.get("carrier_operator", "002"),
        "appVersionCode": profile.get("app_version_code", "12.5.6"),
        "took": random.randint(120, 900),
        "jwtToken": None,
        "token": app_cookie,
    }
    response = session.post(login_url, json=body, timeout=30)
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("appTokenLogin 返回非 JSON")
    if data.get("code") != "SUCCESS":
        raise RuntimeError(f"appTokenLogin 失败: {data.get('code')} {str(data.get('msg'))[:80]}")
    url = (data.get("data") or {}).get("url") or ""
    if not url.startswith(QWHD_BASE + "/"):
        raise RuntimeError("appTokenLogin 返回了非预期地址")
    session.get(url, timeout=30, allow_redirects=False)
    if not any(name.endswith("SESSION_TOKEN") for name in session.cookies.keys()):
        raise RuntimeError("appTokenLogin 未下发活动会话")
    return session, url


def get_jt_token(session, referer, source_id):
    response = session.get(
        QWHD_BASE + "/qwhdhub/user/getYDRZToken",
        params={"targetSourceId": source_id},
        headers=api_headers(referer),
        timeout=30,
    )
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("getYDRZToken 返回非 JSON")
    token = data.get("data")
    if data.get("code") != "SUCCESS" or not token:
        raise RuntimeError(f"getYDRZToken 失败: {data.get('code')}")
    return token


def jsyd_login(profile, jt_token):
    session = new_session()
    user_agent = profile.get("jsyd_user_agent", DEFAULT_JSYD_UA)
    body = {
        "wapContext": {"bizCode": "JTWX10086LOGIN", "subBizCode": "login_KT", "optType": "1"},
        "jtToken": jt_token,
        "pageCode": "logintest",
        "tokenType": 3,
        "packageType": 2,
    }
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://wap.js.10086.cn",
        "referer": "https://wap.js.10086.cn/hyl/content/super-market/market-index?channelId=10000000",
        "user-agent": user_agent,
    }
    response = session.post(JSYD_LOGIN, json=body, headers=headers, timeout=30)
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("jtWx10086AuthLogin 返回非 JSON")
    if str(data.get("code")) != "200" or str(data.get("success")) != "0":
        raise RuntimeError(f"jtWx10086AuthLogin 失败: {data.get('code')} {str(data.get('message'))[:80]}")
    return session


def act(session, profile, method, extra=""):
    myway = profile["mywaytoopen"]
    session.cookies.set("mywaytoopen", myway, domain=".js.10086.cn", path="/")
    data = (
        f"reqUrl=act2510&method={method}&operType=1&actCode=2510&isJtAPP=true"
        f"&env=jt_app&extendParams=&ywcheckcode=&mywaytoopen={myway}{extra}"
    )
    response = session.post(
        JSYD_ACTION,
        data=data,
        headers={
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://wap.js.10086.cn",
            "referer": JSYD_REFERER,
            "user-agent": profile.get("jsyd_user_agent", DEFAULT_JSYD_UA),
        },
        timeout=30,
    )
    try:
        return response.json()
    except ValueError:
        raise RuntimeError(f"{method} 返回非 JSON（HTTP {response.status_code}）")


def streak_days(result):
    """从 toolSignList 计算截至今天的连续签到天数。"""
    signed = set()
    for item in result.get("toolSignList") or []:
        if not isinstance(item, dict):
            continue
        day = str(item.get("signDate") or "")
        state = str(item.get("signState") or item.get("state") or "")
        if day and state == "1":
            signed.add(day)
    if result.get("isSignToday") and result.get("today"):
        signed.add(str(result["today"]))
    if not signed:
        return 0
    today = str(result.get("today") or max(signed))
    try:
        cursor = datetime.strptime(today, "%Y%m%d").date()
    except ValueError:
        return 0
    if today not in signed:
        prior = [day for day in signed if day <= today]
        if not prior:
            return 0
        cursor = datetime.strptime(max(prior), "%Y%m%d").date()
    count = 0
    while cursor.strftime("%Y%m%d") in signed:
        count += 1
        cursor -= timedelta(days=1)
    return count


def connect(profile):
    app_cookie = mint_session(profile)
    qwhd, referer = exchange_qwhd(profile, app_cookie)
    jt_token = get_jt_token(qwhd, referer, profile["source_id"])
    return jsyd_login(profile, jt_token)


def send_feishu(title, body):
    app_id = os.environ.get("QL_FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("QL_FEISHU_APP_SECRET", "").strip()
    open_id = os.environ.get("QL_FEISHU_OPEN_ID", "").strip()
    if not (app_id and app_secret and open_id):
        return False
    try:
        auth = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret}, timeout=15,
        )
        token = auth.json().get("tenant_access_token") if auth.ok else None
        if not token:
            return False
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": open_id,
                "msg_type": "text",
                "content": json.dumps({"text": f"{title}\n\n{body}"}, ensure_ascii=False),
                "uuid": str(uuid.uuid4()),
            },
            timeout=15,
        )
        return resp.json().get("code") == 0
    except (requests.RequestException, ValueError):
        return False


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只查状态，不签到")
    parser.add_argument("--profile", default=os.environ.get("CMCC_PROFILE", DEFAULT_PROFILE))
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    try:
        session = connect(profile)
        init = act(session, profile, "initIndexPage")
        result = init.get("resultObj") or {}
        if str(init.get("resultCode")) != "1" or not result.get("isLogin"):
            raise RuntimeError("活动会话未登录")
        already = bool(result.get("isSignToday"))
        month = result.get("monthSignCnt")
        streak = streak_days(result)
        print(f"登录=成功 今日已签到={already} 连续签到={streak}天 本月已签={month}天")

        if args.check:
            return 0

        if already:
            body = f"今日已签到，已连续签到 {streak} 天，本月已签到 {month} 天。"
            title = "中国移动签到 · 已签到"
        else:
            sign = act(session, profile, "doSign", "&fxmobile=")
            if str(sign.get("resultCode")) != "1":
                raise RuntimeError(f"doSign 失败: resultCode={sign.get('resultCode')}")
            after = act(session, profile, "initIndexPage")
            after_obj = after.get("resultObj") or {}
            if not after_obj.get("isSignToday"):
                raise RuntimeError("doSign 后仍未确认今日签到")
            month = after_obj.get("monthSignCnt", month)
            streak = streak_days(after_obj)
            body = f"签到成功，已连续签到 {streak} 天，本月已签到 {month} 天。"
            title = "中国移动签到 · 成功"
        print(body)
        print("飞书通知已发送" if send_feishu(title, body) else "未配置或发送失败飞书通知")
        return 0
    except Exception as exc:  # noqa: BLE001 - 单次任务失败要通知
        message = f"{type(exc).__name__}: {exc}"
        print("任务失败：" + message)
        send_feishu("中国移动签到 · 失败", message)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
