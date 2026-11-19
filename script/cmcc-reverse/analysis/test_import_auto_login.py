#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线测试：autoLogin 模板解密与 HAR/flow 解析。"""

import base64
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import import_auto_login as m  # noqa: E402


def encrypt(plain):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    data = plain.encode()
    pad = 16 - len(data) % 16
    enc = Cipher(algorithms.AES(m.REQ_KEY), modes.CBC(m.REQ_IV)).encryptor()
    return enc.update(data + bytes([pad]) * pad) + enc.finalize()


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.template = {
            "tel": "99999999999",
            "xk": "a" * 72,
            "reqBody": {"cellNum": "synthetic"},
            "packageName": "com.jsmcc.TEST",
        }

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
