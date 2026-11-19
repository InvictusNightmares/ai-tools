#!/usr/bin/env python3
"""江苏 act2510 登录链路探测脚本（不保存任何凭证）。

用于验证公开 H5 的 jtTokenLogin / initIndexPage 路径；完整自动续期见
notes/jsyd-login-chain.md 与 ../../qinglong/cmcc-checkin/cmcc_auto.py。

流程：
  1. 可选：GET wx.10086.cn/qwhdhub/user/getYDRZToken?targetSourceId=039014
  2. POST wap.js.10086.cn/nact/action.do  method=jtTokenLogin  jtToken=...
  3. POST action.do  method=initIndexPage  -> isLogin
  4. POST action.do  method=doSign
"""
import argparse
import json
import ssl
import sys

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context


class LegacyAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


def new_session():
    s = requests.Session()
    s.trust_env = False
    s.mount('https://', LegacyAdapter())
    return s

ACTION = "https://wap.js.10086.cn/nact/action.do"
YDRZ = "https://wx.10086.cn/qwhdhub/user/getYDRZToken"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/wkwebview "
      "leadeon/12.0.5/CMCCIT")


def headers():
    return {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://wap.js.10086.cn/nact/resource/2510/html/index.html",
        "Origin": "https://wap.js.10086.cn",
        "X-Requested-With": "XMLHttpRequest",
    }


def post(session, data):
    r = session.post(ACTION, data=data, headers=headers(), timeout=20)
    try:
        return r.status_code, r.json(), r.cookies
    except ValueError:
        return r.status_code, {"raw": r.text[:200]}, r.cookies


def init_index(session, myway="0"):
    return post(session, {
        "reqUrl": "act2510", "method": "initIndexPage", "operType": "1",
        "actCode": "2510", "isJtAPP": "true", "env": "jt_app",
        "extendParams": "", "ywcheckcode": "", "mywaytoopen": myway,
    })


def do_sign(session, myway="0"):
    return post(session, {
        "reqUrl": "act2510", "method": "doSign", "operType": "1",
        "actCode": "2510", "isJtAPP": "true", "fxmobile": "", "env": "jt_app",
        "extendParams": "", "ywcheckcode": "", "mywaytoopen": myway,
    })


def jt_token_login(session, jt_token, myway="0"):
    return post(session, {
        "reqUrl": "wapLogin", "method": "jtTokenLogin", "busiNum": "JTTokenLOGIN",
        "jtToken": jt_token, "loginType": "3", "mywaytoopen": myway,
    })


def get_ydrz(session, source_id="039014"):
    r = session.get(YDRZ, params={"targetSourceId": source_id},
                    headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*"},
                    timeout=20, allow_redirects=False)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:200], "location": r.headers.get("Location")}
    return r.status_code, body


def probe():
    s = new_session()
    print("== getYDRZToken anonymous")
    print(json.dumps(get_ydrz(s), ensure_ascii=False))
    print("== initIndexPage anonymous")
    code, body, _ = init_index(s)
    print(code, json.dumps(body, ensure_ascii=False)[:400])
    print("== jtTokenLogin dummy")
    code, body, cookies = jt_token_login(s, "test")
    print(code, json.dumps(body, ensure_ascii=False)[:400])
    print("== cookies", list(cookies.keys()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="只做匿名接口探测")
    ap.add_argument("--jt-token", help="已有 jtToken")
    ap.add_argument("--cookie", help="QWHD/JSYD Cookie 串，仅用于本次测试")
    ap.add_argument("--myway", default="0")
    args = ap.parse_args()
    if args.probe or not args.jt_token:
        probe()
        return 0
    s = new_session()
    if args.cookie:
        s.headers["Cookie"] = args.cookie
    code, body, _ = jt_token_login(s, args.jt_token, args.myway)
    print("jtTokenLogin:", code, json.dumps(body, ensure_ascii=False)[:400])
    if body.get("resultCode") == "1":
        code, body, _ = init_index(s, args.myway)
        print("initIndexPage:", code, json.dumps(body, ensure_ascii=False)[:400])
        if body.get("resultObj", {}).get("isLogin"):
            code, body, _ = do_sign(s, args.myway)
            print("doSign:", code, json.dumps(body, ensure_ascii=False)[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
