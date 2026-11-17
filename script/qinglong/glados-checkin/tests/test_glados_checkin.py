#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线单元测试：不访问网络，只验证纯函数与配置解析。"""

import hashlib
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glados_checkin as g  # noqa: E402


class ProofTests(unittest.TestCase):
    def test_known_vector(self):
        self.assertEqual(g.proof_for("abc"), g.PROOF_TEST_DIGEST)

    def test_digest_is_sha256_hex(self):
        value = g.proof_for("nonce-123")
        self.assertEqual(len(value), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in value))
        self.assertEqual(
            value,
            hashlib.sha256(b"nonce-123.glados-observe-v1").hexdigest(),
        )


class ClassifyTests(unittest.TestCase):
    def test_success(self):
        self.assertEqual(g.classify({"code": 0, "message": "Checkin! Got 10"}), "success")

    def test_repeat(self):
        self.assertEqual(
            g.classify({"code": 1, "message": "Checkin Repeats! Please Try Tomorrow"}),
            "repeat",
        )

    def test_turnstile(self):
        self.assertEqual(
            g.classify({"code": 5, "reason": "turnstile", "message": "Cloudflare verification failed"}),
            "turnstile",
        )

    def test_device_mismatch(self):
        self.assertEqual(
            g.classify({"code": 4, "reason": "device-mismatch"}), "device-mismatch"
        )

    def test_auth(self):
        self.assertEqual(g.classify({"code": -2, "message": "没有权限"}), "auth")
        self.assertEqual(g.classify({"http_status": 401}), "auth")

    def test_network_failure(self):
        self.assertEqual(g.classify({"request_failed": True}), "failed")


class ConfigTests(unittest.TestCase):
    def test_single_and_multi_cookie(self):
        env = {"GLADOS_COOKIES": "b=2\n# comment\n\nc=3", "GLADOS_COOKIE": "a=1"}
        with mock.patch.dict(os.environ, env, clear=True):
            accounts = g.load_accounts()
        self.assertEqual([c for c, _ in accounts], ["a=1", "b=2", "c=3"])

    def test_user_agent_assignment(self):
        env = {
            "GLADOS_COOKIES": "a=1\nb=2",
            "GLADOS_USER_AGENTS": "UA-ONE\nUA-TWO",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            accounts = g.load_accounts()
        self.assertEqual([ua for _, ua in accounts], ["UA-ONE", "UA-TWO"])

    def test_fallback_user_agent(self):
        env = {"GLADOS_COOKIE": "a=1", "GLADOS_USER_AGENT": "CUSTOM"}
        with mock.patch.dict(os.environ, env, clear=True):
            accounts = g.load_accounts()
        self.assertEqual(accounts[0][1], "CUSTOM")

    def test_chrome_headers_follow_user_agent(self):
        headers = g.browser_headers(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        self.assertEqual(headers["Sec-CH-UA-Platform"], '"macOS"')
        self.assertIn('v="131"', headers["Sec-CH-UA"])

    def test_cookie_masking_hides_values(self):
        masked = g.mask_cookie("gld:sess=secret; gld:sess.sig=signature")
        self.assertNotIn("secret", masked)
        self.assertNotIn("signature", masked)
        self.assertIn("gld:sess=***", masked)


class CheckinFlowTests(unittest.TestCase):
    def test_challenge_then_signed_post(self):
        calls = []

        def fake_api(session, method, path, cookie, ua, domain, payload=None, timeout=None):
            calls.append((method, path, domain, payload))
            if path.endswith("/challenge"):
                return {"code": 0, "nonce": "nonce-1", "ttl": 300000}
            return {"code": 0, "points": 12}

        with mock.patch.object(g, "api_call", side_effect=fake_api), \
                mock.patch.object(g.time, "sleep", return_value=None):
            result = g.api_checkin(object(), "c=1", "UA", ["https://glados.cloud"])

        self.assertEqual(result["code"], 0)
        self.assertEqual([c[1] for c in calls], ["/api/user/checkin/challenge", "/api/user/checkin"])
        payload = calls[1][3]
        self.assertEqual(payload["token"], "glados.cloud")
        self.assertEqual(payload["nonce"], "nonce-1")
        self.assertEqual(payload["proof"], g.proof_for("nonce-1"))

    def test_challenge_auth_failure_does_not_post(self):
        calls = []

        def fake_api(session, method, path, cookie, ua, domain, payload=None, timeout=None):
            calls.append(path)
            return {"code": -2, "message": "没有权限"}

        with mock.patch.object(g, "api_call", side_effect=fake_api):
            result = g.api_checkin(object(), "c=1", "UA", ["https://glados.cloud"])

        self.assertEqual(g.classify(result), "auth")
        self.assertEqual(calls, ["/api/user/checkin/challenge"])

    def test_short_ttl_is_rejected(self):
        with mock.patch.object(g, "api_call", return_value={"code": 0, "nonce": "n", "ttl": 100}):
            result = g.api_checkin(object(), "c=1", "UA", ["https://glados.cloud"])
        self.assertTrue(result.get("request_failed"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
