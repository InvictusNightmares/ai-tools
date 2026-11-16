"""Offline capture regressions; every credential below is synthetic.

Run with the Python environment that has mitmproxy installed:
  python -m unittest discover -s capture -p 'test_*.py' -v
"""
from __future__ import annotations

import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from OpenSSL import SSL
from mitmproxy import connection, http, options, tls
from mitmproxy.addons import tlsconfig
from mitmproxy.net import tls as net_tls
from mitmproxy.proxy import context
from mitmproxy.proxy.mode_specs import ProxyMode


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cmcc-capture-test-")
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / "capture"
        source = Path(__file__).with_name("qwhd_capture.py")
        spec = importlib.util.spec_from_file_location("capture_under_test", source)
        self.capture = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"CMCC_CAPTURE_DIR": str(self.out)}):
            spec.loader.exec_module(self.capture)

    def flow(self, url, body=b"", headers=()):
        flow = http.HTTPFlow(
            connection.Client(peername=("127.0.0.1", 12345), sockname=("127.0.0.1", 8080)),
            connection.Server(address=("wx.10086.cn", 443)),
        )
        flow.request = http.Request.make("POST", url, body, http.Headers(headers))
        return flow

    def records(self):
        return [json.loads(p.read_text()) for p in (self.out / "flows").glob("*.json")]

    def test_native_auto_login_preserves_complete_paired_payloads(self):
        body = b"SYNTHETIC_ENCRYPTED_BODY:" + b"x" * 5000
        flow = self.flow(
            "https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin",
            body,
            [(b"cookie", b"JSESSIONID=SYNTHETIC_NATIVE_SESSION"),
             (b"x-sign", b"SYNTHETIC_SIGNATURE"), (b"x-test", b"first"), (b"x-test", b"second")],
        )
        console = io.StringIO()
        with contextlib.redirect_stdout(console):
            self.capture.request(flow)
            records = self.records()
            self.assertEqual(len(records), 1, "cold-start native login was not captured")
            self.assertIsNone(records[0]["response"])
            flow.response = http.Response.make(200, b"SYNTHETIC_ENCRYPTED_RESPONSE")
            self.capture.response(flow)
        records = self.records()
        self.assertEqual(len(records), 1, "request and response must update the same record")
        self.assertEqual(records[0]["kind"], "native-auto-login")
        self.assertEqual(base64.b64decode(records[0]["request"]["body_base64"]), body)
        self.assertIn(["x-sign", "SYNTHETIC_SIGNATURE"], records[0]["request"]["headers"])
        self.assertEqual(sum(k == "x-test" for k, _ in records[0]["request"]["headers"]), 2)
        self.assertEqual(records[0]["response"]["status_code"], 200)
        self.assertNotIn("SYNTHETIC_NATIVE_SESSION", console.getvalue())
        self.assertNotIn("SYNTHETIC_SIGNATURE", console.getvalue())
        self.assertNotIn("SYNTHETIC_ENCRYPTED_BODY", console.getvalue())

    def test_jiangsu_form_endpoint_is_captured(self):
        flow = self.flow(
            "https://wap.js.10086.cn/nact/action.do",
            b"reqUrl=act2510&method=doSign",
            [(b"content-type", b"application/x-www-form-urlencoded")],
        )
        self.capture.request(flow)
        self.assertTrue(self.capture.LOG.exists())
        self.assertEqual(self.records()[0]["kind"], "jiangsu-activity")

    def test_sf_login_keeps_redirect_cookie_pair_private_and_separate(self):
        flow = self.flow(
            "https://mcs-mimp-web.sf-express.com/mcs-mimp/share/app/redirect?token=SYNTHETIC_QUERY",
            b"SYNTHETIC_LOGIN_BODY",
            [(b"cookie", b"sessionId=SYNTHETIC_SESSION"),
             (b"cookie", b"_login_user_id_=SYNTHETIC_USER")],
        )
        console = io.StringIO()
        with contextlib.redirect_stdout(console):
            self.capture.request(flow)
            flow.response = http.Response.make(302, b"", http.Headers([
                (b"location", b"/superWelfare"),
                (b"set-cookie", b"sessionId=SYNTHETIC_NEW_SESSION; HttpOnly; Path=/"),
                (b"set-cookie", b"_login_user_id_=SYNTHETIC_USER; Path=/"),
            ]))
            self.capture.response(flow)
        files = list((self.out / "sf" / "flows").glob("*.json"))
        self.assertEqual(len(files), 1)
        record = json.loads(files[0].read_text())
        self.assertEqual(record["kind"], "sf-membership")
        self.assertEqual(record["request"]["text"], "SYNTHETIC_LOGIN_BODY")
        self.assertEqual(record["response"]["status_code"], 302)
        self.assertEqual(sum(k == "set-cookie" for k, _ in record["response"]["headers"]), 2)
        self.assertEqual(self.records(), [])
        self.assertFalse(self.capture.LOG.exists())
        self.assertTrue(self.capture.SF_LOG.exists())
        self.assertNotIn("SYNTHETIC", console.getvalue())
        for path in (self.out / "sf").rglob("*"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)

    def test_sf_capture_is_scoped_to_membership_origin_and_paths(self):
        for path in [
            "/mcs-mimp/commonPost/~memberNonactivity~integralSignV2Service~sign",
            "/mcs-mimp/share/weChat/redirect", "/share/app/login", "/superWelfare",
        ]:
            self.assertEqual(self.capture.capture_kind(self.flow(
                "https://mcs-mimp-web.sf-express.com" + path
            )), "sf-membership")
        for url in [
            "https://mcs-mimp-web.sf-express.com.attacker.example/mcs-mimp/share/app/login",
            "https://unrelated.sf-express.com/mcs-mimp/share/app/login",
            "https://mcs-mimp-web.sf-express.com/order/private",
            "https://mcs-mimp-web.sf-express.com/mcs-mimp-other/private",
        ]:
            self.assertIsNone(self.capture.capture_kind(self.flow(url)))

    def test_reload_recovers_sf_once_in_its_own_directory(self):
        flow = self.flow("https://mcs-mimp-web.sf-express.com/superWelfare")
        flow.response = http.Response.make(200, b"SYNTHETIC_PAGE")
        master = SimpleNamespace(view=SimpleNamespace(resolve=lambda spec: [flow]))
        with patch.object(self.capture, "ctx", SimpleNamespace(master=master)):
            self.capture.running()
            path = self.out / "sf" / "flows" / f"{flow.id}.json"
            original = path.read_bytes()
            flow.response = http.Response.make(200, b"DO_NOT_OVERWRITE")
            self.capture.running()
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(len(list(path.parent.glob("*.json"))), 1)
        self.assertEqual(self.records(), [])

    def test_sf_native_ticket_preserves_auth_and_response_in_private_sf_record(self):
        flow = self.flow(
            "https://native.sf-express.com/cx-app-member/member/app/user/universalSign",
            b'{"mobile":"SYNTHETIC_MOBILE","needReqTime":"1"}',
            [(b"authorization", b"Bearer SYNTHETIC_APP_TOKEN")],
        )
        response = b'{"sign":"SYNTHETIC_TICKET_' + b"x" * 5000 + b'"}'
        console = io.StringIO()
        with contextlib.redirect_stdout(console):
            self.capture.request(flow)
            flow.response = http.Response.make(200, response)
            self.capture.response(flow)
        files = list((self.out / "sf" / "flows").glob("*.json"))
        self.assertEqual(len(files), 1)
        record = json.loads(files[0].read_text())
        self.assertEqual(record["kind"], "sf-native-ticket")
        self.assertIn(["authorization", "Bearer SYNTHETIC_APP_TOKEN"], record["request"]["headers"])
        self.assertEqual(base64.b64decode(record["response"]["body_base64"]), response)
        self.assertEqual(stat.S_IMODE(files[0].stat().st_mode), 0o600)
        self.assertEqual(self.records(), [])
        self.assertFalse(self.capture.LOG.exists())
        self.assertTrue(self.capture.SF_LOG.exists())
        self.assertNotIn("SYNTHETIC", console.getvalue())

    def test_sf_native_ticket_filter_rejects_other_endpoints_and_lookalike_hosts(self):
        suffix = "/cx-app-member/member/app/user/universalSign"
        for origin in ["https://native.sf-express.com", "https://native.sf-express.com.cn"]:
            self.assertEqual(self.capture.capture_kind(self.flow(origin + suffix)), "sf-native-ticket")
            self.assertEqual(self.capture.capture_kind(self.flow(origin + "/gateway" + suffix)), "sf-native-ticket")
        for url in [
            "https://native.sf-express.com.attacker.example" + suffix,
            "https://native.sf-express.com.cn.attacker.example" + suffix,
            "https://notsf-express.com" + suffix,
            "https://native.sf-express.com" + suffix + "Other",
            "https://native.sf-express.com/cx-app-member/member/app/user/privateProfile",
        ]:
            self.assertIsNone(self.capture.capture_kind(self.flow(url)))

    def test_sf_wireguard_ip_destination_recovers_native_and_membership_records(self):
        flows = []
        for domain, path, kind in [
            ("native.sf-express.com", "/cx-app-member/member/app/user/universalSign", "sf-native-ticket"),
            ("mcs-mimp-web.sf-express.com", "/mcs-mimp/ifLogin", "sf-membership"),
        ]:
            flow = self.flow("https://198.18.0.42" + path, b"SYNTHETIC_BODY")
            flow.request.http_version = "HTTP/2.0"
            flow.request.host_header = domain
            flow.client_conn.sni = domain
            flow.client_conn.proxy_mode = ProxyMode.parse("wireguard")
            flow.response = http.Response.make(200, b'{"success":true}')
            flows.append((flow, domain, kind))
        master = SimpleNamespace(view=SimpleNamespace(resolve=lambda spec: [f for f, _, _ in flows]))
        with patch.object(self.capture, "ctx", SimpleNamespace(master=master)):
            self.capture.running()
        for flow, domain, kind in flows:
            record = json.loads((self.out / "sf" / "flows" / f"{flow.id}.json").read_text())
            self.assertEqual(record["kind"], kind)
            self.assertEqual(record["request"]["origin_host"], domain)
            self.assertEqual(record["transport"], "wireguard")
            self.assertIn("198.18.0.42", record["request"]["url"])
        inventory = json.loads((self.out / "host_inventory.json").read_text())["hosts"]
        self.assertIn("native.sf-express.com", inventory)
        self.assertNotIn("198.18.0.42", inventory)
        self.assertEqual(self.records(), [])

    def test_sf_wireguard_domain_recovery_requires_matching_authority_and_sni(self):
        path = "/cx-app-member/member/app/user/universalSign"
        for dest, authority, sni in [
            ("198.18.0.42", "native.sf-express.com", None),
            ("198.18.0.42", "native.sf-express.com", "unrelated.example"),
            ("198.18.0.42", "unrelated.example", "native.sf-express.com"),
            ("198.18.0.42", "native.sf-express.com.attacker.example", "native.sf-express.com.attacker.example"),
            ("unrelated.example", "native.sf-express.com", "native.sf-express.com"),
        ]:
            flow = self.flow("https://" + dest + path)
            flow.request.http_version = "HTTP/2.0"
            flow.request.host_header = authority
            flow.client_conn.sni = sni
            flow.client_conn.proxy_mode = ProxyMode.parse("wireguard")
            self.assertIsNone(self.capture.capture_kind(flow))

    def test_sf_response_cannot_replace_mobile_login_artifacts(self):
        self.capture.save_token("SYNTHETIC_MOBILE_TOKEN", "test")
        flow = self.flow("https://mcs-mimp-web.sf-express.com/mcs-mimp/share/app/login")
        flow.response = http.Response.make(200, b"{}", {
            "Set-Cookie": "QWHD_SESSION_TOKEN=SYNTHETIC_OTHER_TOKEN; Path=/"
        })
        self.capture.request(flow)
        self.capture.response(flow)
        self.assertEqual(self.capture.TOKEN.read_text().strip(), "SYNTHETIC_MOBILE_TOKEN")
        self.assertFalse(self.capture.APPTOKEN_BODY.exists())
        self.assertFalse(self.capture.APPTOKEN_RESP.exists())

    def test_native_token_exchange_outside_auto_login_is_captured(self):
        flow = self.flow(
            "https://client.app.coc.10086.cn/biz-orange/DN/syntheticTokenExchange",
            b"SYNTHETIC_ENCRYPTED_TOKEN_REQUEST",
            [(b"x-token", b"SYNTHETIC_SIGNATURE_TOKEN")],
        )
        self.capture.request(flow)
        records = self.records()
        self.assertEqual(len(records), 1, "native token exchanges must not be filtered out")
        self.assertEqual(records[0]["kind"], "native-api")

    def test_jiangsu_sso_is_exactly_scoped(self):
        for path in [
            "/vw/gateway/auth/auth/jtWx10086AuthLogin",
            "/hyl/content/provider-user/sso/china/mobile",
        ]:
            flow = self.flow("https://wap.js.10086.cn" + path, b"SYNTHETIC_LOGIN")
            self.assertEqual(self.capture.capture_kind(flow), "jiangsu-sso")
        for url in [
            "https://wap.js.10086.cn/hyl/content/provider-user/private-profile",
            "https://wap.js.10086.cn/vw/gateway/auth/auth/jtWx10086AuthLoginOther",
            "https://wap.js.10086.cn.attacker.example/hyl/content/provider-user/sso/china/mobile",
        ]:
            self.assertIsNone(self.capture.capture_kind(self.flow(url)))

    def test_reload_recovers_retained_flows_without_replaying_requests(self):
        saved = self.flow("https://wx.10086.cn/qwhdsso/appTokenLogin", b"first")
        self.capture.request(saved)
        original_file = self.out / "flows" / f"{saved.id}.json"
        original_contents = original_file.read_bytes()
        native = self.flow(
            "https://client.app.coc.10086.cn/biz-orange/DN/syntheticTokenExchange", b"second"
        )
        native.response = http.Response.make(200, b"SYNTHETIC_TOKEN_RESPONSE")
        unrelated = self.flow("https://example.org/private", b"UNRELATED_DATA")
        resolved = []

        def resolve(spec):
            resolved.append(spec)
            return [saved, native, unrelated]

        master = SimpleNamespace(view=SimpleNamespace(resolve=resolve))
        with patch.object(self.capture, "ctx", SimpleNamespace(master=master)):
            self.capture.running()
            self.capture.running()
        self.assertEqual(resolved, ["@all", "@all"])
        self.assertEqual(original_file.read_bytes(), original_contents)
        records = self.records()
        self.assertEqual(len(records), 2)
        recovered = next(r for r in records if r["id"] == native.id)
        self.assertEqual(recovered["response"]["text"], "SYNTHETIC_TOKEN_RESPONSE")

    def test_retained_inventory_contains_only_host_counts(self):
        flow = self.flow(
            "https://example.org/private?token=SYNTHETIC_QUERY_TOKEN",
            b"SYNTHETIC_PRIVATE_BODY",
            [(b"cookie", b"SYNTHETIC_PRIVATE_COOKIE")],
        )
        flow.response = http.Response.make(403, b"SYNTHETIC_PRIVATE_RESPONSE")
        view = SimpleNamespace(resolve=lambda spec: [flow])
        with patch.object(self.capture, "ctx", SimpleNamespace(master=SimpleNamespace(view=view))):
            self.capture.running()
        path = self.out / "host_inventory.json"
        self.assertTrue(path.exists())
        inventory = json.loads(path.read_text())
        self.assertEqual(inventory["hosts"]["example.org"]["flows"], 1)
        self.assertEqual(inventory["hosts"]["example.org"]["statuses"], {"403": 1})
        self.assertNotIn("SYNTHETIC", path.read_text())
        self.assertNotIn("/private", path.read_text())
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_sf_native_inventory_exposes_routes_without_credentials_or_payloads(self):
        identifier = "abcdef0123456789abcdef0123456789"
        flow = self.flow(
            f"https://native.sf-express.com/api/activity/{identifier}?sign=SYNTHETIC_SIGNATURE",
            b"SYNTHETIC_PRIVATE_BODY",
            [(b"authorization", b"Bearer SYNTHETIC_NATIVE_TOKEN")],
        )
        flow.response = http.Response.make(200, b"SYNTHETIC_PRIVATE_RESPONSE")
        view = SimpleNamespace(resolve=lambda spec: [flow])
        with patch.object(self.capture, "ctx", SimpleNamespace(master=SimpleNamespace(view=view))):
            self.capture.running()
        path = self.out / "host_inventory.json"
        inventory = json.loads(path.read_text())
        self.assertEqual(
            inventory["hosts"]["native.sf-express.com"]["paths"],
            {"/api/activity/<opaque>": 1},
        )
        self.assertNotIn("SYNTHETIC", path.read_text())
        self.assertNotIn(identifier, path.read_text())
        self.assertEqual(self.records(), [])
        self.assertEqual(list((self.out / "sf" / "flows").glob("*.json")), [])

    def test_sf_native_inventory_rejects_lookalike_domains_and_redacts_uuid_paths(self):
        identifier = "abcdef01-2345-6789-abcd-ef0123456789"
        native = self.flow(f"https://native.sf-express.com/api/{identifier}/13800000000")
        unrelated = self.flow("https://native.sf-express.com.attacker.example/private")
        view = SimpleNamespace(resolve=lambda spec: [native, unrelated])
        with patch.object(self.capture, "ctx", SimpleNamespace(master=SimpleNamespace(view=view))):
            self.capture.running()
        inventory = json.loads((self.out / "host_inventory.json").read_text())["hosts"]
        self.assertEqual(
            inventory["native.sf-express.com"]["paths"],
            {"/api/<opaque>/<number>": 1},
        )
        self.assertNotIn("paths", inventory["native.sf-express.com.attacker.example"])

    def test_unrelated_domain_cannot_overwrite_token(self):
        self.capture.save_token("SYNTHETIC_VALID_TOKEN", "test")
        flow = self.flow("https://10086.cn.attacker.example/qwhdsso/appTokenLogin")
        flow.response = http.Response.make(
            200, b"{}", {"Set-Cookie": "QWHD_SESSION_TOKEN=SYNTHETIC_INVALID_TOKEN; Path=/"}
        )
        self.capture.request(flow)
        self.capture.response(flow)
        self.assertEqual(self.capture.TOKEN.read_text().strip(), "SYNTHETIC_VALID_TOKEN")
        self.assertEqual(self.records(), [])

    def test_activity_path_inventory_omits_queries_and_identifiers(self):
        flow = self.flow(
            "https://wap.js.10086.cn/other/13800000000/index.html?token=SYNTHETIC_QUERY_TOKEN",
            b"SYNTHETIC_PRIVATE_BODY",
        )
        view = SimpleNamespace(resolve=lambda spec: [flow])
        with patch.object(self.capture, "ctx", SimpleNamespace(master=SimpleNamespace(view=view))):
            self.capture.running()
        path = self.out / "host_inventory.json"
        inventory = json.loads(path.read_text())
        self.assertEqual(
            inventory["hosts"]["wap.js.10086.cn"]["paths"],
            {"/other/<number>/index.html": 1},
        )
        self.assertNotIn("SYNTHETIC", path.read_text())
        self.assertNotIn("13800000000", path.read_text())
        self.assertEqual(self.records(), [])

    def test_multiple_cookie_headers_do_not_corrupt_token(self):
        flow = self.flow(
            "https://wx.10086.cn/qwhdhub/api/mark/mark31/markstatus",
            headers=[(b"cookie", b"QWHD_SESSION_TOKEN=SYNTHETIC_QWHD_TOKEN"),
                     (b"cookie", b"other=1")],
        )
        self.capture.request(flow)
        self.assertEqual(self.capture.TOKEN.read_text().strip(), "SYNTHETIC_QWHD_TOKEN")

    def test_login_requests_keep_independent_responses(self):
        first = self.flow("https://wx.10086.cn/qwhdsso/appTokenLogin?sid=synthetic-first", b"first")
        second = self.flow("https://wx.10086.cn/qwhdsso/appTokenLogin?sid=synthetic-second", b"second")
        self.capture.request(first)
        self.capture.request(second)
        second.response = http.Response.make(200, b"second-response")
        first.response = http.Response.make(200, b"first-response")
        self.capture.response(second)
        self.capture.response(first)
        pairs = {r["request"]["text"]: r["response"]["text"] for r in self.records()}
        self.assertEqual(pairs, {"first": "first-response", "second": "second-response"})

    def test_sensitive_files_are_private_with_permissive_umask(self):
        flow = self.flow(
            "https://wx.10086.cn/qwhdsso/appTokenLogin",
            b'{"token":"SYNTHETIC_APP_TOKEN"}',
            [(b"cookie", b"QWHD_SESSION_TOKEN=SYNTHETIC_QWHD_TOKEN")],
        )
        old_umask = os.umask(0o022)
        try:
            self.capture.request(flow)
        finally:
            os.umask(old_umask)
        files = [p for p in self.out.rglob("*") if p.is_file()]
        self.assertTrue(files)
        for path in files:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path.name)

    def tls_options(self):
        opts = options.Options()
        opts.add_option("tls_version_server_min", str, "TLS1_2", "test")
        opts.add_option("tls_version_server_max", str, "UNBOUNDED", "test")
        opts.add_option("tls_ecdh_curve_server", str | None, None, "test")
        opts.add_option("ciphers_server", str | None, None, "test")
        return opts

    def tls_data(self, host, opts, *, port=443, sni=None, is_dtls=False):
        client = connection.Client(peername=("127.0.0.1", 12345), sockname=("127.0.0.1", 8080))
        client.sni = sni or host
        server = connection.Server(address=(host, port), sni=sni or host)
        proxy_context = context.Context(client, opts)
        proxy_context.server = server
        return tls.TlsData(server, proxy_context, is_dtls=is_dtls)

    def test_legacy_tls_is_connection_scoped_and_preserves_verification(self):
        opts = self.tls_options()
        data = self.tls_data("client.app.coc.10086.cn", opts)
        plain = self.tls_data("unrelated.example", opts)
        fake_ctx = SimpleNamespace(options=opts)
        with patch.object(tlsconfig, "ctx", fake_ctx):
            self.capture.tls_start_server(data)
            tlsconfig.TlsConfig().tls_start_server(plain)
            original = data.ssl_conn
            tlsconfig.TlsConfig().tls_start_server(data)
        self.assertIs(data.ssl_conn, original)
        self.assertEqual(data.ssl_conn.get_verify_mode(), SSL.VERIFY_PEER)
        self.assertEqual(data.ssl_conn.get_servername(), b"client.app.coc.10086.cn")
        flags = SSL._lib.SSL_get_options(data.ssl_conn._ssl)
        self.assertTrue(flags & net_tls.OP_LEGACY_SERVER_CONNECT)
        self.assertTrue(flags & SSL.OP_NO_RENEGOTIATION)
        # The two connections share mitmproxy's cached context. A mutation to
        # that context would silently weaken subsequent unrelated connections.
        self.assertIs(data.ssl_conn.get_context(), plain.ssl_conn.get_context())
        plain_flags = SSL._lib.SSL_get_options(plain.ssl_conn._ssl)
        self.assertFalse(plain_flags & net_tls.OP_LEGACY_SERVER_CONNECT)

    def test_tls_compatibility_rejects_unrelated_hosts_ports_and_sni(self):
        opts = self.tls_options()
        for host, kwargs in [
            ("clientaccess.10086.cn", {}),
            ("client.app.coc.10086.cn.attacker.example", {}),
            ("client.app.coc.10086.cn", {"port": 8443}),
            ("client.app.coc.10086.cn", {"sni": "unrelated.example"}),
            ("client.app.coc.10086.cn", {"is_dtls": True}),
        ]:
            with self.subTest(host=host, **kwargs):
                data = self.tls_data(host, opts, **kwargs)
                self.capture.tls_start_server(data)
                self.assertIsNone(data.ssl_conn)


if __name__ == "__main__":
    unittest.main()
