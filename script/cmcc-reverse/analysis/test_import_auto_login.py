#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线测试：autoLogin 模板解密、URL 保留、cv 版本对齐与 HAR/flow 解析。"""

import base64
import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import import_auto_login as m  # noqa: E402


def encrypt(plain, key=m.REQ_KEY, iv=m.REQ_IV):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    data = plain.encode()
    pad = 16 - len(data) % 16
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc.update(data + bytes([pad]) * pad) + enc.finalize()


def encrypt_resp(payload):
    return base64.b64encode(encrypt(json.dumps(payload), key=m.RESP_KEY, iv=m.REQ_IV)).decode()


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.template = {
            "tel": "99999999999",
            "xk": "a" * 72,
            "reqBody": {"cellNum": "synthetic"},
            "packageName": "com.jsmcc.TEST",
        }
        self.phone = "13800000000"
        self.myway = "0123456789abcdef0123456789abcdef"

    def test_single_base64_ciphertext(self):
        body = base64.b64encode(encrypt(json.dumps(self.template))).decode()
        self.assertEqual(m.decrypt_body(body), self.template)

    def test_double_base64_ciphertext(self):
        inner = base64.b64encode(encrypt(json.dumps(self.template))).decode()
        outer = base64.b64encode(inner.encode()).decode()
        self.assertEqual(m.decrypt_body(outer), self.template)

    def test_plaintext_json(self):
        self.assertEqual(m.decrypt_body(json.dumps(self.template)), self.template)

    def test_headers_normalization(self):
        headers = m.headers_dict([["User-Agent", "UA"], {"name": "Cookie", "value": "x"}])
        self.assertEqual(headers, {"user-agent": "UA", "cookie": "x"})

    def test_flow_entry(self):
        body = base64.b64encode(encrypt(json.dumps(self.template))).decode()
        flow = {"request": {"url": "https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin",
                            "headers": [["user-agent", "UA"]], "text": body}}
        found = list(m.entries(flow))
        self.assertEqual(len(found), 1)
        self.assertEqual(m.decrypt_body(found[0][2]), self.template)

    def test_preserves_uamrandcodelogin_url_and_aligns_national_app_cv(self):
        tpl = {
            **self.template,
            "packageName": "cn.10086.app",
            "cv": "12.5.8",
            "sv": "18.7",
        }
        body = base64.b64encode(encrypt(json.dumps(tpl))).decode()
        rand_url = "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin"
        flow = {
            "request": {
                "url": rand_url,
                "headers": [["user-agent", "ChinaMobile/12.5.8 (iPhone; iOS 18.7; Scale/3.00)"]],
                "text": body,
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "flow.json"
            out = Path(tmpdir) / "profile.json"
            src.write_text(json.dumps(flow), encoding="utf-8")
            console = io.StringIO()
            old_umask = os.umask(0o022)
            try:
                with contextlib.redirect_stdout(console):
                    rc = m.main([
                        "--input", str(src),
                        "--out", str(out),
                        "--phone", self.phone,
                        "--myway", self.myway,
                    ])
            finally:
                os.umask(old_umask)
            self.assertEqual(rc, 0)
            profile = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(profile["auto_login_url"], rand_url)
            self.assertEqual(profile["app_version_code"], "12.5.8")
            self.assertEqual(
                profile["auto_login_user_agent"],
                "ChinaMobile/12.5.8 (iPhone; iOS 18.7; Scale/3.00)",
            )
            self.assertIn("leadeon/12.5.8/CMCCIT", profile["sso_user_agent"])
            self.assertIn("leadeon/12.5.8/CMCCIT", profile["jsyd_user_agent"])
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            output = console.getvalue()
            self.assertNotIn(self.phone, output)
            self.assertNotIn(tpl["xk"], output)
            self.assertNotIn(self.myway, output)

    def test_preserves_har_uamrandcodelogin_url_and_aligns_jiangsu_app_cv(self):
        tpl = {
            **self.template,
            "packageName": "com.jsmcc.ZP7267A6ES",
            "cv": "12.0.5",
        }
        body = base64.b64encode(encrypt(json.dumps(tpl))).decode()
        rand_url = "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin"
        har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "url": "https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLoginCheck",
                            "headers": [{"name": "User-Agent", "value": "Other"}],
                            "postData": {"text": body},
                        }
                    },
                    {
                        "request": {
                            "url": rand_url,
                            "headers": [{"name": "User-Agent", "value": "ChinaMobile/12.0.5 (iPhone; iOS 26.6.1; Scale/3.00)"}],
                            "postData": {"text": body},
                        }
                    },
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "capture.har"
            out = Path(tmpdir) / "profile.json"
            src.write_text(json.dumps(har), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = m.main([
                    "--input", str(src),
                    "--out", str(out),
                    "--phone", self.phone,
                    "--myway", self.myway,
                ])
            self.assertEqual(rc, 0)
            profile = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(profile["auto_login_url"], rand_url)
            self.assertEqual(profile["app_version_code"], "12.0.5")
            self.assertIn("leadeon/12.0.5/CMCCIT", profile["sso_user_agent"])
            self.assertIn("leadeon/12.0.5/CMCCIT", profile["jsyd_user_agent"])

    def test_explicit_cli_overrides_url_and_app_version_and_fallback_when_cv_missing(self):
        body = base64.b64encode(encrypt(json.dumps(self.template))).decode()
        flow = {
            "request": {
                "url": "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
                "headers": [],
                "body_base64": base64.b64encode(body.encode()).decode(),
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "flow.json"
            out_default = Path(tmpdir) / "default.json"
            out_override = Path(tmpdir) / "override.json"
            src.write_text(json.dumps(flow), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                m.main([
                    "--input", str(src),
                    "--out", str(out_default),
                    "--phone", self.phone,
                    "--myway", self.myway,
                ])
            prof_default = json.loads(out_default.read_text(encoding="utf-8"))
            self.assertEqual(prof_default["app_version_code"], m.DEFAULT_APP_VERSION)
            self.assertEqual(
                prof_default["auto_login_url"],
                "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
            )

            custom_url = "https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin"
            with contextlib.redirect_stdout(io.StringIO()):
                m.main([
                    "--input", str(src),
                    "--out", str(out_override),
                    "--phone", self.phone,
                    "--myway", self.myway,
                    "--auto-login-url", custom_url,
                    "--app-version", "12.9.9",
                    "--sso-user-agent", "CUSTOM_SSO_UA",
                    "--jsyd-user-agent", "CUSTOM_JSYD_UA",
                ])
            prof_override = json.loads(out_override.read_text(encoding="utf-8"))
            self.assertEqual(prof_override["auto_login_url"], custom_url)
            self.assertEqual(prof_override["app_version_code"], "12.9.9")
            self.assertEqual(prof_override["sso_user_agent"], "CUSTOM_SSO_UA")
            self.assertEqual(prof_override["jsyd_user_agent"], "CUSTOM_JSYD_UA")

    def test_base64_wrapped_plaintext_json_decodes_cleanly(self):
        b64_plain = base64.b64encode(json.dumps(self.template).encode("utf-8")).decode("ascii")
        self.assertEqual(m.decrypt_body(b64_plain), self.template)

    def test_har_prefers_latest_successful_autologin_over_earlier_failed_or_older_entries(self):
        tpl_failed = {**self.template, "xk": "1" * 72, "cv": "12.0.5", "packageName": "com.jsmcc.ZP7267A6ES"}
        tpl_ok_old = {**self.template, "xk": "2" * 72, "cv": "12.0.5", "packageName": "com.jsmcc.ZP7267A6ES"}
        tpl_ok_new = {
            **self.template,
            "xk": "3" * 72,
            "cv": "12.5.8",
            "packageName": "cn.10086.app",
            "reqBody": {"loginNum": "synthetic_rand_login"},
        }
        har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "url": "https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin",
                            "headers": [],
                            "postData": {"text": base64.b64encode(encrypt(json.dumps(tpl_failed))).decode()},
                        },
                        "response": {
                            "status": 200,
                            "content": {"text": encrypt_resp({"retCode": "214103", "retDesc": "risk"})},
                        },
                    },
                    {
                        "request": {
                            "url": "https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin",
                            "headers": [],
                            "postData": {"text": base64.b64encode(encrypt(json.dumps(tpl_ok_old))).decode()},
                        },
                        "response": {
                            "status": 200,
                            "content": {"text": encrypt_resp({"retCode": "000000", "retDesc": "SUCCESS"})},
                        },
                    },
                    {
                        "request": {
                            "url": "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
                            "headers": [{"name": "User-Agent", "value": "ChinaMobile/12.5.8 (iPhone; iOS 18.7; Scale/3.00)"}],
                            "postData": {"text": base64.b64encode(encrypt(json.dumps(tpl_ok_new))).decode()},
                        },
                        "response": {
                            "status": 200,
                            "content": {"text": encrypt_resp({"retCode": "000000", "retDesc": "SUCCESS"})},
                        },
                    },
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "multi.har"
            out = Path(tmpdir) / "profile.json"
            src.write_text(json.dumps(har), encoding="utf-8")
            console = io.StringIO()
            with contextlib.redirect_stdout(console):
                rc = m.main([
                    "--input", str(src),
                    "--out", str(out),
                    "--phone", self.phone,
                    "--myway", f"  {self.myway}\n",
                ])
            self.assertEqual(rc, 0)
            profile = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(
                profile["auto_login_url"],
                "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
            )
            self.assertEqual(profile["xk"], "3" * 72)
            self.assertEqual(profile["app_version_code"], "12.5.8")
            self.assertEqual(profile["mywaytoopen"], self.myway)
            self.assertIn("retCode=000000", console.getvalue())

    def test_single_failed_flow_emits_warning_and_rejects_non_https_or_empty_reqbody(self):
        flow_failed = {
            "request": {
                "url": "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
                "headers": [],
                "text": base64.b64encode(encrypt(json.dumps(self.template))).decode(),
            },
            "response": {
                "status_code": 200,
                "text": encrypt_resp({"retCode": "214103", "retDesc": "face check"}),
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "failed.json"
            out = Path(tmpdir) / "profile.json"
            src.write_text(json.dumps(flow_failed), encoding="utf-8")
            console = io.StringIO()
            with contextlib.redirect_stdout(console):
                rc = m.main([
                    "--input", str(src),
                    "--out", str(out),
                    "--phone", self.phone,
                    "--myway", self.myway,
                ])
            self.assertEqual(rc, 0)
            output = console.getvalue()
            self.assertIn("retCode=214103", output)
            self.assertIn("警告", output)
            self.assertNotIn(self.phone, output)

            bad_http = {
                "request": {
                    "url": "http://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
                    "headers": [],
                    "text": base64.b64encode(encrypt(json.dumps(self.template))).decode(),
                }
            }
            bad_src = Path(tmpdir) / "bad_http.json"
            bad_src.write_text(json.dumps(bad_http), encoding="utf-8")
            with self.assertRaises(SystemExit):
                m.main([
                    "--input", str(bad_src),
                    "--out", str(out),
                    "--phone", self.phone,
                    "--myway", self.myway,
                ])

            bad_tpl = {**self.template, "reqBody": {}}
            bad_body = {
                "request": {
                    "url": "https://client.app.coc.10086.cn/biz-orange/LN/uamrandcodelogin/autoLogin",
                    "headers": [],
                    "text": base64.b64encode(encrypt(json.dumps(bad_tpl))).decode(),
                }
            }
            bad_body_src = Path(tmpdir) / "bad_body.json"
            bad_body_src.write_text(json.dumps(bad_body), encoding="utf-8")
            with self.assertRaises(SystemExit):
                m.main([
                    "--input", str(bad_body_src),
                    "--out", str(out),
                    "--phone", self.phone,
                    "--myway", self.myway,
                ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
