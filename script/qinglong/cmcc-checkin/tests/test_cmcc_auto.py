#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线单元测试：完全不发网络请求，覆盖签名对齐、风控硬熔断、冷却、随机延迟与双端兼容。"""

import base64
import contextlib
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cmcc_auto as m  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[4]
LOCAL_CAPTURE_DIR = REPO_ROOT / "script" / "cmcc-reverse" / "out" / "captures" / "flows"
LOCAL_COLD_CAPTURE = LOCAL_CAPTURE_DIR / "d6244ffd-0e3b-4389-8cd2-fa19e5de0215.json"
LOCAL_WARM_CAPTURE = LOCAL_CAPTURE_DIR / "a0ecaf1e-f05b-4259-83ba-57137c578f71.json"


def encrypt_resp(payload):
    plain = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(m._cbc(m.RESP_KEY, m.REQ_IV, plain, True))


def decrypt_token(token_b64):
    return m._cbc(m.TOK_KEY, m.TOK_IV, base64.b64decode(token_b64), False).decode("utf-8")


def decrypt_req_raw(text):
    raw = base64.b64decode(text.strip())
    dec = Cipher(algorithms.AES(m.REQ_KEY), modes.CBC(m.REQ_IV)).decryptor()
    out = dec.update(raw) + dec.finalize()
    return out[:-out[-1]].decode("utf-8")


def make_profile(
    *,
    package_name="com.jsmcc.ZP7267A6ES",
    cv="12.0.5",
    sv="26.6.1",
    url="https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin",
    xk="a" * 72,
    phone="13800000000",
    myway="0123456789abcdef0123456789abcdef",
    app_version_code=None,
    auto_login_user_agent=None,
):
    template = {
        "tel": phone,
        "sv": sv,
        "nt": "-1",
        "packageName": package_name,
        "prov": "250",
        "t": "",
        "sn": "iPhone16,2",
        "imei": "SYNTHETIC_IMEI_0001",
        "city": "0512",
        "ctid": "SYNTHETIC_CTID_0001",
        "appKey": "00000160",
        "sp": "1290x2796",
        "en": "0",
        "componentVersion": "1.0.0",
        "reqBody": {
            "cellNum": "SYNTHETIC_RSA_CELLNUM_BASE64==",
            "channelId": "1",
            "devToken": "SYNTHETIC_DEV_TOKEN",
            "imei": "SYNTHETIC_IMEI_0001",
            "pageUrl": "ZF10000",
            "reqSource": "init",
            "mnc1": "65535",
            "sendSmsFlag": "0",
            "mnc2": "65535",
            "caid": "SYNTHETIC_CAID",
        },
        "cid": "SYNTHETIC_CID",
        "xk": xk,
        "xc": "B2012",
        "componentID": "BI2021SI000024",
        "ak": "SYNTHETIC_AK_0001",
        "cv": cv,
        "sb": "apple",
        "baseFrameVersion": "1.0.0",
        "st": 2,
    }
    profile = {
        "auto_login_url": url,
        "auto_login_template": template,
        "xk": xk,
        "phone": phone,
        "province_code": "250",
        "city_code": "0512",
        "carrier_operator": "002",
        "source_id": "039014",
        "mywaytoopen": myway,
    }
    if app_version_code is not None:
        profile["app_version_code"] = app_version_code
    if auto_login_user_agent is not None:
        profile["auto_login_user_agent"] = auto_login_user_agent
    return profile


class SigningTests(unittest.TestCase):
    def test_cold_start_omits_cookie_uses_literal_null_and_accept_language(self):
        profile = make_profile(
            package_name="com.jsmcc.ZP7267A6ES",
            cv="12.0.5",
            url="https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin",
        )
        url = profile["auto_login_url"]
        plain = json.dumps(profile["auto_login_template"], separators=(",", ":"), ensure_ascii=False)
        ua = "ChinaMobile/12.0.5 (iPhone; iOS 26.6.1; Scale/3.00)"

        for empty_cookie in (None, "", "   "):
            with self.subTest(cookie=empty_cookie):
                headers = m.build_headers(
                    url, plain, empty_cookie, profile["xk"], ua,
                    ts="1795053684904", nonce="17665658",
                )
                self.assertNotIn("Cookie", headers)
                self.assertEqual(headers["Accept-Language"], "zh-CN,zh-Hans;q=0.9")
                self.assertEqual(
                    decrypt_token(headers["x-token"]),
                    f"{profile['xk']}_/biz-orange/LN/uamonekeylogin/autoLogin_1795053684904_17665658",
                )
                self.assertEqual(
                    headers["xs"],
                    hashlib.md5(f"{url}_{plain}_{m.SALT}".encode()).hexdigest(),
                )
                self.assertEqual(
                    headers["x-sign"],
                    hashlib.md5(
                        f"{headers['x-token']}_1795053684904_17665658_null".encode()
                    ).hexdigest(),
                )

    def test_warm_cookie_keeps_cookie_header_and_signs_jsessionid(self):
        url = "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin"
        plain = '{"xk":"' + ("b" * 72) + '"}'
        cookie = "JSESSIONID=SYNTHETIC-JSID-9999; UID=SYNTHETIC_UID"
        headers = m.build_headers(
            url, plain, cookie, "b" * 72, "ChinaMobile/12.5.8 (iPhone; iOS 18.7; Scale/3.00)",
            ts="1795053685000", nonce="87654321",
        )
        self.assertEqual(headers["Cookie"], cookie)
        self.assertEqual(headers["Accept-Language"], "zh-CN,zh-Hans;q=0.9")
        self.assertEqual(
            decrypt_token(headers["x-token"]),
            f"{'b' * 72}_/biz-orange/LN/uamrandcodelogin/autoLogin_1795053685000_87654321",
        )
        self.assertEqual(
            headers["x-sign"],
            hashlib.md5(
                f"{headers['x-token']}_1795053685000_87654321_SYNTHETIC-JSID-9999".encode()
            ).hexdigest(),
        )

    def test_non_empty_cookie_without_jsessionid_falls_back_to_null_without_crash(self):
        url = "https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin"
        plain = "{}"
        for cookie in ("UID=only", "JSESSIONID=; UID=only"):
            headers = m.build_headers(url, plain, cookie, "c" * 32, "UA", ts="1000", nonce="12345678")
            self.assertEqual(headers["Cookie"], cookie)
            self.assertEqual(
                headers["x-sign"],
                hashlib.md5(f"{headers['x-token']}_1000_12345678_null".encode()).hexdigest(),
            )

    @unittest.skipUnless(LOCAL_COLD_CAPTURE.exists(), "本地真机冷启动抓包 d6244ffd 不存在（CI/洁净环境跳过）")
    def test_aligns_byte_for_byte_with_local_cold_start_capture_d6244ffd(self):
        flow = json.loads(LOCAL_COLD_CAPTURE.read_text(encoding="utf-8"))
        req = flow["request"]
        hdrs = {k.lower(): v for k, v in req["headers"]}
        plain = decrypt_req_raw(req["text"])
        tpl = json.loads(plain)
        built = m.build_headers(
            req["url"],
            plain,
            None,
            tpl["xk"],
            hdrs["user-agent"],
            ts=hdrs["x-time"],
            nonce=hdrs["x-nonce"],
        )
        self.assertNotIn("Cookie", built)
        self.assertEqual(built["Accept-Language"], "zh-CN,zh-Hans;q=0.9")
        self.assertEqual(built["x-token"], hdrs["x-token"])
        self.assertEqual(built["xs"], hdrs["xs"])
        self.assertEqual(built["x-sign"], hdrs["x-sign"])

    @unittest.skipUnless(LOCAL_WARM_CAPTURE.exists(), "本地真机带 Cookie 抓包不存在（CI/洁净环境跳过）")
    def test_aligns_byte_for_byte_with_local_warm_capture(self):
        flow = json.loads(LOCAL_WARM_CAPTURE.read_text(encoding="utf-8"))
        req = flow["request"]
        hdrs = {k.lower(): v for k, v in req["headers"]}
        joined_cookie = "; ".join(v for k, v in req["headers"] if k.lower() == "cookie")
        plain = decrypt_req_raw(req["text"])
        tpl = json.loads(plain)
        built = m.build_headers(
            req["url"],
            plain,
            joined_cookie,
            tpl["xk"],
            hdrs["user-agent"],
            ts=hdrs["x-time"],
            nonce=hdrs["x-nonce"],
        )
        self.assertEqual(built["Cookie"], joined_cookie)
        self.assertEqual(built["x-token"], hdrs["x-token"])
        self.assertEqual(built["xs"], hdrs["xs"])
        self.assertEqual(built["x-sign"], hdrs["x-sign"])

    def test_mint_session_cold_start_sends_no_cookie_and_returns_set_cookie(self):
        profile = make_profile(
            package_name="cn.10086.app",
            cv="12.5.8",
            sv="18.7",
            url="https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
        )
        captured = {}

        class FakeSession:
            def post(self, url, data, headers, timeout):
                captured["url"] = url
                captured["data"] = data
                captured["headers"] = headers
                return SimpleNamespace(
                    status_code=200,
                    content=encrypt_resp({"retCode": "000000", "retDesc": "SUCCESS"}),
                    headers={"Set-Cookie": "JSESSIONID=SYNTHETIC_NEW; UID=SYNTHETIC_U"},
                )

        cookie = m.mint_session(profile, session=FakeSession())
        self.assertEqual(cookie, "JSESSIONID=SYNTHETIC_NEW; UID=SYNTHETIC_U")
        self.assertEqual(captured["url"], profile["auto_login_url"])
        self.assertNotIn("Cookie", captured["headers"])
        self.assertEqual(captured["headers"]["Accept-Language"], "zh-CN,zh-Hans;q=0.9")
        self.assertEqual(
            captured["headers"]["User-Agent"],
            "ChinaMobile/12.5.8 (iPhone; iOS 18.7; Scale/3.00)",
        )
        self.assertEqual(
            captured["headers"]["x-sign"],
            hashlib.md5(
                f"{captured['headers']['x-token']}_{captured['headers']['x-time']}_{captured['headers']['x-nonce']}_null".encode()
            ).hexdigest(),
        )

    def test_mint_session_raises_typed_autologin_error_for_risk_and_non_risk_codes(self):
        profile = make_profile()

        class RiskSession:
            def post(self, url, data, headers, timeout):
                return SimpleNamespace(
                    status_code=200,
                    content=encrypt_resp({"retCode": "214103", "retDesc": "需要实人校验"}),
                    headers={},
                )

        with self.assertRaises(m.AutoLoginError) as ctx:
            m.mint_session(profile, session=RiskSession())
        self.assertEqual(ctx.exception.ret_code, "214103")
        self.assertTrue(ctx.exception.is_risk_lockout)

        class Gateway403Session:
            def post(self, url, data, headers, timeout):
                return SimpleNamespace(status_code=403, content=b"Forbidden", headers={})

        with self.assertRaises(m.AutoLoginError) as ctx403:
            m.mint_session(profile, session=Gateway403Session())
        self.assertEqual(ctx403.exception.ret_code, "")
        self.assertEqual(ctx403.exception.http_status, 403)
        self.assertFalse(ctx403.exception.is_risk_lockout)


class AppCompatibilityTests(unittest.TestCase):
    def test_supports_both_national_v1258_and_jiangsu_v1205_profiles(self):
        cases = [
            (
                "cn.10086.app",
                "12.5.8",
                "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
                "ChinaMobile/12.5.8 (iPhone; iOS 18.7; Scale/3.00)",
                "leadeon/12.5.8/CMCCIT",
            ),
            (
                "com.jsmcc.ZP7267A6ES",
                "12.0.5",
                "https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin",
                "ChinaMobile/12.0.5 (iPhone; iOS 26.6.1; Scale/3.00)",
                "leadeon/12.0.5/CMCCIT",
            ),
        ]
        for pkg, cv, url, expected_ua, expected_leadeon in cases:
            with self.subTest(package=pkg, cv=cv):
                sv = "18.7" if pkg == "cn.10086.app" else "26.6.1"
                profile = make_profile(package_name=pkg, cv=cv, sv=sv, url=url, auto_login_user_agent="")
                m.validate_profile(profile)
                self.assertEqual(m.resolve_app_version(profile), cv)
                self.assertEqual(m.resolve_auto_login_ua(profile), expected_ua)
                self.assertIn(expected_leadeon, m.resolve_webview_ua(profile, "sso_user_agent", m.DEFAULT_SSO_UA))
                self.assertIn(expected_leadeon, m.resolve_webview_ua(profile, "jsyd_user_agent", m.DEFAULT_JSYD_UA))

    def test_exchange_qwhd_uses_template_cv_when_app_version_code_omitted(self):
        profile = make_profile(package_name="cn.10086.app", cv="12.5.8")
        posted = {}

        class FakeQwhdSession:
            def __init__(self):
                self.headers = {}
                self.cookies = {}

            def get(self, url, params=None, timeout=30, allow_redirects=True):
                if url == m.SSO_LOGIN:
                    return SimpleNamespace(text="var loginPath = '/appTokenLogin?sid=SYNTHETIC';")
                self.cookies["QWHD_SESSION_TOKEN"] = "SYNTHETIC_QWHD"
                return SimpleNamespace(text="ok")

            def post(self, url, json=None, timeout=30):
                posted["url"] = url
                posted["json"] = json
                posted["ua"] = self.headers.get("user-agent")
                return SimpleNamespace(
                    json=lambda: {
                        "code": "SUCCESS",
                        "data": {"url": "https://wx.10086.cn/qwhdhub/qwhdmark/1021122301?token=SYNTHETIC"},
                    }
                )

        with mock.patch.object(m, "new_session", return_value=FakeQwhdSession()):
            sess, target = m.exchange_qwhd(profile, "JSESSIONID=SYNTHETIC")
        self.assertEqual(posted["json"]["appVersionCode"], "12.5.8")
        self.assertIn("leadeon/12.5.8/CMCCIT", posted["ua"])
        self.assertIn("QWHD_SESSION_TOKEN", sess.cookies)
        self.assertTrue(target.startswith(m.QWHD_BASE + "/"))


class GuardrailAndCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cmcc-auto-test-")
        self.addCleanup(self.tmp.cleanup)
        self.profile_path = Path(self.tmp.name) / "cmcc_profile.json"
        self.state_path = Path(self.tmp.name) / "cmcc_profile.state.json"
        self.write_profile(make_profile())

    def write_profile(self, profile):
        self.profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")

    def run_cli(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = m.main(argv)
        return rc, buf.getvalue()

    def test_all_eleven_risk_codes_trigger_persistent_lockout_and_zero_request_subsequent_exit(self):
        expected_codes = [
            "214100", "214101", "214102", "214103", "214104", "214105",
            "214200", "214300", "213245", "420000", "233031",
        ]
        self.assertEqual(set(m.RISK_LOCKOUT_CODES.keys()), set(expected_codes))

        for code in expected_codes:
            with self.subTest(ret_code=code):
                if self.state_path.exists():
                    self.state_path.unlink()
                feishu_calls = []
                connect_calls = []

                def fake_connect(_profile):
                    connect_calls.append(1)
                    raise m.AutoLoginError(ret_code=code, ret_desc="风控触发", http_status=200)

                def fake_feishu(title, body):
                    feishu_calls.append((title, body))
                    return True

                with mock.patch.object(m, "connect", side_effect=fake_connect), \
                        mock.patch.object(m, "send_feishu", side_effect=fake_feishu), \
                        mock.patch.object(m.time, "sleep") as sleep_mock:
                    rc1, out1 = self.run_cli([
                        "--profile", str(self.profile_path),
                        "--state-file", str(self.state_path),
                        "--now",
                        "--min-interval", "0",
                    ])
                self.assertEqual(rc1, 2)
                self.assertEqual(len(connect_calls), 1)
                self.assertEqual(len(feishu_calls), 1)
                self.assertIn("风控熔断", feishu_calls[0][0])
                self.assertIn(code, feishu_calls[0][1])
                self.assertIn(code, out1)
                sleep_mock.assert_not_called()

                self.assertTrue(self.state_path.exists())
                self.assertEqual(stat.S_IMODE(self.state_path.stat().st_mode), 0o600)
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
                self.assertTrue(state["locked"])
                self.assertEqual(state["lockout"]["code"], code)
                # 状态文件不得包含明文敏感信息
                raw_state = self.state_path.read_text(encoding="utf-8")
                self.assertNotIn("13800000000", raw_state)
                self.assertNotIn("a" * 72, raw_state)
                self.assertNotIn("SYNTHETIC_RSA_CELLNUM_BASE64", raw_state)

                # 后续定时（即使去掉 --now）也必须零延迟、零网络请求、零飞书通知直接退出
                with mock.patch.object(m, "connect", side_effect=AssertionError("must not connect")), \
                        mock.patch.object(m, "send_feishu", side_effect=AssertionError("must not notify")), \
                        mock.patch.object(m.time, "sleep", side_effect=AssertionError("must not sleep")):
                    rc2, out2 = self.run_cli([
                        "--profile", str(self.profile_path),
                        "--state-file", str(self.state_path),
                    ])
                self.assertEqual(rc2, 2)
                self.assertIn("风控硬熔断", out2)
                self.assertIn(code, out2)

    def test_clear_lockout_is_local_only_and_allows_subsequent_run(self):
        profile = make_profile()
        self.write_profile(profile)
        m.record_lockout(self.state_path, m.profile_hash(profile), "214103", "face check", now_fn=lambda: 1000.0)
        # 同时记录旧调用时间（已超过冷却期）
        state = m.load_state(self.state_path)
        state["last_auto_login_at"] = 100.0
        m.save_state(self.state_path, state)

        with mock.patch.object(m, "connect", side_effect=AssertionError("must not connect")), \
                mock.patch.object(m, "send_feishu", side_effect=AssertionError("must not notify")), \
                mock.patch.object(m.time, "sleep", side_effect=AssertionError("must not sleep")):
            rc, out = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--clear-lockout",
            ])
        self.assertEqual(rc, 0)
        self.assertIn("已清除风控熔断状态", out)
        after = m.load_state(self.state_path)
        self.assertFalse(after["locked"])
        self.assertIsNone(after["lockout"])
        self.assertEqual(after["last_auto_login_at"], 100.0)

        # 解除后可恢复正常 --check
        with mock.patch.object(m, "connect", return_value=object()), \
                mock.patch.object(m, "act", return_value={
                    "resultCode": "1",
                    "resultObj": {"isLogin": True, "isSignToday": True, "monthSignCnt": 7, "today": "20261128"},
                }), \
                mock.patch.object(m, "send_feishu", side_effect=AssertionError("check must not notify")):
            rc2, out2 = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--check",
            ])
        self.assertEqual(rc2, 0)
        self.assertIn("登录=成功", out2)

    def test_profile_hash_change_auto_unlocks_lockout(self):
        old_profile = make_profile(xk="a" * 72)
        self.write_profile(old_profile)
        m.record_lockout(self.state_path, m.profile_hash(old_profile), "214103", "face", now_fn=lambda: 100.0)

        # 更换为新的抓包 profile（例如切换为全国版 12.5.8 + uamrandcodelogin）
        new_profile = make_profile(
            package_name="cn.10086.app",
            cv="12.5.8",
            url="https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
            xk="b" * 72,
        )
        self.write_profile(new_profile)

        # --dry-run 应预告自动解锁，但不得修改状态文件
        rc_dry, out_dry = self.run_cli([
            "--profile", str(self.profile_path),
            "--state-file", str(self.state_path),
            "--dry-run",
        ])
        self.assertEqual(rc_dry, 0)
        self.assertIn("将自动解除原熔断", out_dry)
        self.assertTrue(m.load_state(self.state_path)["locked"])

        # 正式执行时自动解除熔断并继续
        with mock.patch.object(m, "connect", return_value=object()), \
                mock.patch.object(m, "act", return_value={
                    "resultCode": "1",
                    "resultObj": {"isLogin": True, "isSignToday": True, "monthSignCnt": 8, "today": "20261128"},
                }), \
                mock.patch.object(m, "send_feishu", return_value=True):
            rc_run, out_run = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--now",
            ])
        self.assertEqual(rc_run, 0)
        self.assertIn("已自动解除历史风控熔断", out_run)
        state = m.load_state(self.state_path)
        self.assertFalse(state["locked"])
        self.assertEqual(state["profile_hash"], m.profile_hash(new_profile))
        self.assertEqual(state["unlocked_reason"], "profile_changed")

    def test_cross_process_cooldown_blocks_rapid_repeat_and_allows_after_interval(self):
        fake_now = [1000.0]

        with mock.patch.object(m.time, "time", side_effect=lambda: fake_now[0]), \
                mock.patch.object(m, "connect", return_value=object()) as conn_mock, \
                mock.patch.object(m, "act", return_value={
                    "resultCode": "1",
                    "resultObj": {"isLogin": True, "isSignToday": True, "monthSignCnt": 3, "today": "20261128"},
                }):
            rc1, _ = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--check",
                "--min-interval", "300",
            ])
            self.assertEqual(rc1, 0)
            self.assertEqual(conn_mock.call_count, 1)

            # 120 秒后再次调用应被跨进程冷却拦截（零网络请求、零飞书通知）
            fake_now[0] = 1120.0
            with mock.patch.object(m, "send_feishu", side_effect=AssertionError("cooldown must not notify")), \
                    mock.patch.object(m.time, "sleep", side_effect=AssertionError("cooldown must not sleep")):
                rc2, out2 = self.run_cli([
                    "--profile", str(self.profile_path),
                    "--state-file", str(self.state_path),
                    "--check",
                    "--min-interval", "300",
                ])
            self.assertEqual(rc2, 2)
            self.assertIn("跨进程冷却保护", out2)
            self.assertEqual(conn_mock.call_count, 1)

            # 301 秒后冷却解除，可以正常调用
            fake_now[0] = 1301.0
            rc3, _ = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--check",
                "--min-interval", "300",
            ])
            self.assertEqual(rc3, 0)
            self.assertEqual(conn_mock.call_count, 2)

    def test_backward_clock_jump_caps_cooldown_safely(self):
        info = m.inspect_guard_state(
            {"locked": False, "last_auto_login_at": 2000.0},
            "hash",
            now=1990.0,
            min_interval=300,
        )
        self.assertEqual(info["cooldown_remaining"], 300.0)

    def test_corrupted_state_file_fails_closed_without_network(self):
        self.state_path.write_text("{not valid json", encoding="utf-8")
        with mock.patch.object(m, "connect", side_effect=AssertionError("must not connect")), \
                mock.patch.object(m, "send_feishu", side_effect=AssertionError("must not notify")):
            rc, out = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--now",
            ])
        self.assertEqual(rc, 1)
        self.assertIn("状态文件损坏", out)

        # --clear-lockout 可修复损坏的状态文件
        rc_clear, _ = self.run_cli([
            "--profile", str(self.profile_path),
            "--state-file", str(self.state_path),
            "--clear-lockout",
        ])
        self.assertEqual(rc_clear, 0)
        self.assertFalse(m.load_state(self.state_path)["locked"])

    def test_non_exact_hour_random_delay_and_skip_flags(self):
        # 默认模式：应调用 sleep，且范围默认 30~900（非 0）
        with mock.patch.object(m.random, "randint", return_value=123) as rand_mock, \
                mock.patch.object(m.time, "sleep") as sleep_mock, \
                mock.patch.object(m, "connect", return_value=object()), \
                mock.patch.object(m, "act", return_value={
                    "resultCode": "1",
                    "resultObj": {"isLogin": True, "isSignToday": True, "monthSignCnt": 5, "today": "20261128"},
                }), \
                mock.patch.object(m, "send_feishu", return_value=True):
            rc, out = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--min-interval", "0",
            ])
        self.assertEqual(rc, 0)
        rand_mock.assert_called_once_with(m.DEFAULT_DELAY_MIN, m.DEFAULT_DELAY_MAX)
        sleep_mock.assert_called_once_with(123)
        self.assertIn("非整点随机等待 2 分 3 秒", out)

        # --now / --check / --dry-run 必须跳过随机延迟
        for flag in ("--now", "--check", "--dry-run"):
            with self.subTest(flag=flag):
                with mock.patch.object(m.time, "sleep", side_effect=AssertionError("must skip sleep")), \
                        mock.patch.object(m, "connect", return_value=object()), \
                        mock.patch.object(m, "act", return_value={
                            "resultCode": "1",
                            "resultObj": {"isLogin": True, "isSignToday": True, "monthSignCnt": 5, "today": "20261128"},
                        }), \
                        mock.patch.object(m, "send_feishu", return_value=True):
                    rc_flag, _ = self.run_cli([
                        "--profile", str(self.profile_path),
                        "--state-file", str(self.state_path),
                        "--min-interval", "0",
                        flag,
                    ])
                self.assertEqual(rc_flag, 0)

    def test_dry_run_is_purely_offline_and_never_mutates_state_or_leaks_secrets(self):
        with mock.patch.object(m.requests.Session, "request", side_effect=AssertionError("network forbidden")), \
                mock.patch.object(m.requests, "post", side_effect=AssertionError("network forbidden")), \
                mock.patch.object(m, "connect", side_effect=AssertionError("connect forbidden")), \
                mock.patch.object(m, "send_feishu", side_effect=AssertionError("notify forbidden")), \
                mock.patch.object(m.time, "sleep", side_effect=AssertionError("sleep forbidden")):
            rc, out = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--dry-run",
            ])
        self.assertEqual(rc, 0)
        self.assertFalse(self.state_path.exists())
        self.assertIn("[dry-run] 离线配置与冷启动签名校验通过", out)
        self.assertIn("com.jsmcc.ZP7267A6ES", out)
        self.assertNotIn("13800000000", out)
        self.assertNotIn("a" * 72, out)
        self.assertNotIn("0123456789abcdef0123456789abcdef", out)
        self.assertNotIn("SYNTHETIC_RSA_CELLNUM_BASE64", out)

    def test_dry_run_rejects_invalid_profiles_offline(self):
        bad_cases = [
            make_profile(url="http://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin"),
            make_profile(phone="12345"),
            {**make_profile(), "xk": "mismatch" * 9},
        ]
        for bad in bad_cases:
            self.write_profile(bad)
            with mock.patch.object(m, "connect", side_effect=AssertionError("must not connect")), \
                    mock.patch.object(m, "send_feishu", side_effect=AssertionError("must not notify")):
                rc, _ = self.run_cli([
                    "--profile", str(self.profile_path),
                    "--state-file", str(self.state_path),
                    "--dry-run",
                ])
            self.assertEqual(rc, 1)

    def test_unsigned_flow_calls_dosign_once_and_sanitizes_errors(self):
        actions = []

        def fake_act(_session, _profile, method, extra=""):
            actions.append((method, extra))
            if method == "initIndexPage" and len(actions) == 1:
                return {
                    "resultCode": "1",
                    "resultObj": {
                        "isLogin": True,
                        "isSignToday": False,
                        "monthSignCnt": 4,
                        "today": "20261128",
                        "toolSignList": [{"signDate": "20261127", "signState": "1"}],
                    },
                }
            if method == "doSign":
                return {"resultCode": "1"}
            return {
                "resultCode": "1",
                "resultObj": {
                    "isLogin": True,
                    "isSignToday": True,
                    "monthSignCnt": 5,
                    "today": "20261128",
                    "toolSignList": [
                        {"signDate": "20261127", "signState": "1"},
                        {"signDate": "20261128", "signState": "1"},
                    ],
                },
            }

        sent = []
        with mock.patch.object(m, "connect", return_value=object()), \
                mock.patch.object(m, "act", side_effect=fake_act), \
                mock.patch.object(m, "send_feishu", side_effect=lambda t, b: sent.append((t, b)) or True):
            rc, out = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--now",
                "--min-interval", "0",
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(actions, [("initIndexPage", ""), ("doSign", "&fxmobile="), ("initIndexPage", "")])
        self.assertEqual(sent[0][0], "中国移动签到 · 成功")
        self.assertIn("连续签到 2 天", sent[0][1])
        self.assertIn("本月已签到 5 天", out)

        # 错误消息脱敏：上游回显手机号/xk/mywaytoopen 不得进入日志或飞书
        leaked = []
        with mock.patch.object(
            m, "connect",
            side_effect=RuntimeError(f"err 13800000000 {'a' * 72} 0123456789abcdef0123456789abcdef"),
        ), mock.patch.object(m, "send_feishu", side_effect=lambda t, b: leaked.append((t, b)) or True):
            rc_err, out_err = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--now",
                "--min-interval", "0",
            ])
        self.assertEqual(rc_err, 1)
        combined = out_err + leaked[0][1]
        self.assertNotIn("13800000000", combined)
        self.assertNotIn("a" * 72, combined)
        self.assertNotIn("0123456789abcdef0123456789abcdef", combined)
        self.assertFalse(m.load_state(self.state_path)["locked"])

    def test_lockout_triggered_during_random_delay_blocks_after_wakeup(self):
        profile = make_profile()
        self.write_profile(profile)
        p_hash = m.profile_hash(profile)

        def sleep_and_trip_lockout(_seconds):
            m.record_lockout(self.state_path, p_hash, "214103", "face check", now_fn=lambda: 2000.0)

        with mock.patch.object(m.random, "randint", return_value=45), \
                mock.patch.object(m.time, "sleep", side_effect=sleep_and_trip_lockout), \
                mock.patch.object(m, "connect", side_effect=AssertionError("must not connect after wakeup")), \
                mock.patch.object(m, "send_feishu", side_effect=AssertionError("must not notify after wakeup")):
            rc, out = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--min-interval", "0",
            ])
        self.assertEqual(rc, 2)
        self.assertIn("风控硬熔断", out)

    def test_default_state_path_and_invalid_cli_args_and_missing_state_clear(self):
        self.assertEqual(
            m.default_state_path("/ql/data/config/cmcc_profile.json"),
            Path("/ql/data/config/cmcc_profile.state.json"),
        )
        self.assertEqual(
            m.default_state_path("/tmp/cmcc_profile"),
            Path("/tmp/cmcc_profile.state.json"),
        )

        # 不存在状态文件时 --clear-lockout 应安静返回 0
        rc_clear, out_clear = self.run_cli([
            "--profile", str(self.profile_path),
            "--clear-lockout",
        ])
        self.assertEqual(rc_clear, 0)
        self.assertIn("未处于风控熔断状态", out_clear)

        # 非法参数范围应返回 1 且不发起网络请求
        for bad_args in (
            ["--min-interval", "-1"],
            ["--delay-min", "100", "--delay-max", "50"],
        ):
            with mock.patch.object(m, "connect", side_effect=AssertionError("must not connect")):
                rc_bad, _ = self.run_cli(["--profile", str(self.profile_path), *bad_args])
            self.assertEqual(rc_bad, 1)

        # 未传 --state-file 时默认使用 profile 同目录的 *.state.json
        with mock.patch.object(m, "connect", side_effect=m.AutoLoginError("233031", "freq")), \
                mock.patch.object(m, "send_feishu", return_value=False):
            rc_default, _ = self.run_cli([
                "--profile", str(self.profile_path),
                "--now",
                "--min-interval", "0",
            ])
        self.assertEqual(rc_default, 2)
        self.assertTrue(self.state_path.exists())
        self.assertEqual(m.load_state(self.state_path)["lockout"]["code"], "233031")

    def test_plaintext_risk_response_triggers_lockout_and_truncated_json_raises_autologin_error(self):
        profile = make_profile()

        class PlaintextRiskSession:
            def post(self, url, data, headers, timeout):
                return SimpleNamespace(
                    status_code=200,
                    content=b'  {"retCode":"214103","retDesc":"face verify required"} ',
                    headers={},
                )

        with self.assertRaises(m.AutoLoginError) as ctx:
            m.mint_session(profile, session=PlaintextRiskSession())
        self.assertEqual(ctx.exception.ret_code, "214103")
        self.assertTrue(ctx.exception.is_risk_lockout)

        # 截断的非合法 JSON（以 { 开头）应安全降级为 AutoLoginError，不得抛出裸 JSONDecodeError
        bad_cipher = base64.b64encode(m._cbc(m.RESP_KEY, m.REQ_IV, b'{"retCode":', True))

        class TruncatedJsonSession:
            def post(self, url, data, headers, timeout):
                return SimpleNamespace(status_code=200, content=bad_cipher, headers={})

        with self.assertRaises(m.AutoLoginError) as ctx_bad:
            m.mint_session(profile, session=TruncatedJsonSession())
        self.assertEqual(ctx_bad.exception.ret_code, "")
        self.assertFalse(ctx_bad.exception.is_risk_lockout)

    def test_invalid_env_int_and_blank_env_paths_behave_cleanly(self):
        # 显式传入 --min-interval 时应覆盖非法环境变量，不提前崩在 parse_args
        with mock.patch.dict(os.environ, {"CMCC_MIN_INTERVAL": "not-an-int", "CMCC_STATE_FILE": "   "}):
            rc_override, _ = self.run_cli([
                "--profile", str(self.profile_path),
                "--min-interval", "0",
                "--dry-run",
            ])
        self.assertEqual(rc_override, 0)

        # 未显式传参时，非法环境变量应返回退出码 1 而非抛 SystemExit
        with mock.patch.dict(os.environ, {"CMCC_MIN_INTERVAL": "not-an-int"}):
            rc_err, out_err = self.run_cli([
                "--profile", str(self.profile_path),
                "--dry-run",
            ])
        self.assertEqual(rc_err, 1)
        self.assertIn("CMCC_MIN_INTERVAL", out_err)

        # 空字符串 CMCC_PROFILE 应回退到 DEFAULT_PROFILE（而不是尝试读取当前目录 ""）
        with mock.patch.dict(os.environ, {"CMCC_PROFILE": "   "}):
            with mock.patch.object(m, "DEFAULT_PROFILE", str(self.profile_path)):
                rc_fallback, _ = self.run_cli(["--dry-run"])
        self.assertEqual(rc_fallback, 0)

    def test_malformed_state_field_types_fail_closed_and_clear_lockout_handles_os_errors(self):
        for bad_state in (
            {"locked": False, "last_auto_login_at": True},
            {"locked": False, "last_auto_login_at": "1000.0"},
            {"locked": "false", "last_auto_login_at": 1000.0},
            {"locked": False, "lockout": "bad"},
            {"locked": False, "profile_hash": 12345},
        ):
            with self.subTest(bad_state=bad_state):
                self.state_path.write_text(json.dumps(bad_state), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    m.load_state(self.state_path)
                with mock.patch.object(m, "connect", side_effect=AssertionError("must not connect")):
                    rc, out = self.run_cli([
                        "--profile", str(self.profile_path),
                        "--state-file", str(self.state_path),
                        "--now",
                    ])
                self.assertEqual(rc, 1)
                self.assertIn("状态文件格式异常", out)

        # inspect_guard_state 直接传入非法时间戳也必须按保守策略拦截
        for bad_ts in (True, "1000.0", float("nan"), float("inf")):
            info = m.inspect_guard_state({"locked": False, "last_auto_login_at": bad_ts}, "h", 2000.0, 300)
            self.assertEqual(info["cooldown_remaining"], 300.0)

        # --clear-lockout 遇到目录路径等 OSError 应返回 1 而非裸 traceback
        dir_state = Path(self.tmp.name) / "state_is_dir"
        dir_state.mkdir()
        rc_dir, out_dir = self.run_cli([
            "--profile", str(self.profile_path),
            "--state-file", str(dir_state),
            "--clear-lockout",
        ])
        self.assertEqual(rc_dir, 1)
        self.assertIn("清除风控熔断状态失败", out_dir)

    def test_validate_profile_normalizes_whitespace_supports_randcode_reqbody_and_redacts_cid_hex_phone(self):
        # 含换行控制字符的 URL 必须拒绝
        bad_url_prof = make_profile(url="https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin\n")
        with self.assertRaises(RuntimeError):
            m.validate_profile(bad_url_prof)

        # 首尾空白应规范化，且允许非 cellNum 字段的 uamrandcodelogin reqBody
        padded = make_profile(
            package_name="cn.10086.app",
            cv="12.5.8",
            url="  https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin  ",
            phone=" 13800000000 ",
            myway=" 0123456789abcdef0123456789abcdef ",
        )
        padded["xk"] = f" {padded['xk']} "
        padded["auto_login_template"]["reqBody"] = {"loginNum": "SYNTHETIC_LOGIN_NUM", "token": "SYNTHETIC_TOK_12345"}
        normalized = m.validate_profile(padded)
        self.assertEqual(
            normalized["auto_login_url"],
            "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
        )
        self.assertEqual(normalized["phone"], "13800000000")
        self.assertEqual(normalized["mywaytoopen"], "0123456789abcdef0123456789abcdef")
        self.assertFalse(normalized["xk"].startswith(" "))

        # sanitize_text 应脱敏 cid、loginNum、token 与十六进制 userCheckId
        hex_phone = format(int("13800000000"), "x")
        cleaned = m.sanitize_text(
            f"cid=SYNTHETIC_CID hex={hex_phone} login=SYNTHETIC_LOGIN_NUM tok=SYNTHETIC_TOK_12345",
            normalized,
        )
        self.assertNotIn("SYNTHETIC_CID", cleaned)
        self.assertNotIn(hex_phone, cleaned)
        self.assertNotIn("SYNTHETIC_LOGIN_NUM", cleaned)
        self.assertNotIn("SYNTHETIC_TOK_12345", cleaned)

    def test_lockout_persist_failure_still_alerts_feishu_and_exits_2(self):
        sent = []
        with mock.patch.object(m, "connect", side_effect=m.AutoLoginError("214103", "face check")), \
                mock.patch.object(m, "record_lockout", side_effect=OSError("read-only filesystem")), \
                mock.patch.object(m, "send_feishu", side_effect=lambda t, b: sent.append((t, b)) or True):
            rc, out = self.run_cli([
                "--profile", str(self.profile_path),
                "--state-file", str(self.state_path),
                "--now",
                "--min-interval", "0",
            ])
        self.assertEqual(rc, 2)
        self.assertEqual(len(sent), 1)
        self.assertIn("214103", sent[0][1])
        self.assertIn("熔断状态落盘失败", sent[0][1])
        self.assertIn("飞书风控告警已发送", out)

    def test_real_multiprocess_flock_allows_only_one_winner(self):
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        start_at = time.time() + 0.35
        worker_code = "\n".join([
            "import sys, time",
            f"sys.path.insert(0, {script_dir!r})",
            "import cmcc_auto as m",
            f"wait = {start_at!r} - time.time()",
            "if wait > 0:",
            "    time.sleep(wait)",
            "try:",
            f"    m.check_and_reserve_auto_login({str(self.state_path)!r}, 'hash-mp', 300)",
            "    print('WIN')",
            "except m.GuardrailBlocked as exc:",
            "    print('BLOCK:' + exc.reason)",
        ])
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", worker_code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(4)
        ]
        outputs = []
        try:
            for proc in procs:
                out, err = proc.communicate(timeout=15)
                self.assertEqual(proc.returncode, 0, f"worker failed: {err}")
                outputs.append(out.strip())
        finally:
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
        self.assertEqual(outputs.count("WIN"), 1, f"expected exactly 1 winner, got {outputs}")
        self.assertEqual(outputs.count("BLOCK:cooldown"), 3, f"expected 3 blocked, got {outputs}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
