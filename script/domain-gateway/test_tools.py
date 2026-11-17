import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import ssl
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import acme
from common import ConfigError, load_private, write_new_private
import render
import verify


class PrivateFilesTest(unittest.TestCase):
    def test_refuses_shared_config_and_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text("{}")
            path.chmod(0o644)
            with self.assertRaises(ConfigError):
                load_private(path)
            path.chmod(0o600)
            self.assertEqual(load_private(path), {})
            with self.assertRaises(FileExistsError):
                write_new_private(path, "replacement")
            self.assertEqual(path.read_text(), "{}")

    def test_refuses_symlink_and_tracked_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "original"
            target.write_text("preserve")
            link = Path(folder) / "link"
            link.symlink_to(target)
            with self.assertRaises(ConfigError):
                write_new_private(link, "replacement")
            self.assertEqual(target.read_text(), "preserve")
        with self.assertRaises(ConfigError):
            write_new_private(Path(__file__).parent / "must-not-create.json", "secret")


class RenderSafetyTest(unittest.TestCase):
    def test_private_gateway_rejects_public_bind(self):
        for address in ["0.0.0.0", "203.0.113.8", "127.0.0.1", "::"]:
            with self.subTest(address=address), self.assertRaises(ConfigError):
                render.value_for("PRIVATE_BIND_IP", {"PRIVATE_BIND_IP": address})

    def test_rejects_config_injection_and_invalid_domain(self):
        for value in ["backend;include_secret", "backend\ninclude_secret", "backend#comment", "$(command)"]:
            with self.subTest(value=value), self.assertRaises(ConfigError):
                render.value_for("RAW_BACKEND", {"RAW_BACKEND": value})
        with self.assertRaises(ConfigError):
            render.value_for("SNI_ROUTES", {"TLS_PORT": 19001, "WEB_DOMAINS": ["*.example.net"]})

    def test_port_collision_and_missing_fields_fail_before_output(self):
        with self.assertRaises(ConfigError):
            render.render("private-nginx.conf.template", {"HTTP_PORT": 19001, "HTTPS_PORT": 19001})
        with self.assertRaises(ConfigError):
            render.render("private-vhost.conf.template", {})


class AcmeSafetyTest(unittest.TestCase):
    def config(self, folder):
        return {
            "acme_command": [sys.executable, str(Path(folder) / "fake.py")],
            "home": str(Path(folder) / "acme-home"),
            "server": "zerossl", "validation": "http",
            "domains": ["private.example.net"], "email": "operator@example.net",
            "webroot": str(Path(folder) / "webroot"),
            "key_file": str(Path(folder) / "key"),
            "fullchain_file": str(Path(folder) / "chain"),
            "reload_command": [str(Path(folder) / "reload script"), "literal;argument"],
            "log_file": str(Path(folder) / "operation.log"),
        }

    def test_dry_run_never_executes_or_prints_private_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            config = self.config(folder)
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(config));path.chmod(0o600)
            fake = Path(folder) / "fake.py"
            marker = Path(folder) / "executed"
            fake.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n")
            result = subprocess.run([sys.executable, str(Path(acme.__file__)), "issue", "--config", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(marker.exists())
            self.assertNotIn("private.example.net", result.stdout + result.stderr)
            self.assertNotIn("operator@example.net", result.stdout + result.stderr)

    def test_client_failure_is_recorded_only_in_private_log(self):
        with tempfile.TemporaryDirectory() as folder:
            config = self.config(folder)
            (Path(folder) / "fake.py").write_text("print('private-diagnostic-value')\nraise SystemExit(7)\n")
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(config));path.chmod(0o600)
            result = subprocess.run([sys.executable, str(Path(acme.__file__)), "issue", "--config", str(path), "--apply"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("private-diagnostic-value", result.stdout + result.stderr)
            log = Path(config["log_file"])
            self.assertIn("private-diagnostic-value", log.read_text())
            self.assertEqual(stat.S_IMODE(log.stat().st_mode), 0o600)

    def test_test_ca_cannot_reuse_production_home(self):
        with tempfile.TemporaryDirectory() as folder:
            config = self.config(folder)
            config.update(server="letsencrypt_test", config_home=config["home"])
            with self.assertRaises(ConfigError):
                acme.arguments(config, "issue")

    def test_reload_argv_is_quoted_and_key_cannot_overwrite_chain(self):
        with tempfile.TemporaryDirectory() as folder:
            config = self.config(folder)
            command = acme.arguments(config, "install")
            self.assertEqual(shlex.split(command[command.index("--reloadcmd") + 1]), config["reload_command"])
            config["fullchain_file"] = config["key_file"]
            with self.assertRaises(ConfigError):
                acme.arguments(config, "install")

    def test_dns_file_is_parsed_without_shell_evaluation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "dns.env"
            path.write_text("CF_Token='$(unsafe_command)'\nCF_Zone_ID='" + "a" * 32 + "'\n")
            path.chmod(0o600)
            with self.assertRaises(ConfigError):
                acme.dns_environment({"validation": "dns", "dns_env_file": str(path)})


class VerifySafetyTest(unittest.TestCase):
    def test_bad_tls_does_not_fall_back_or_leak_url(self):
        with patch.object(verify.http.client, "HTTPSConnection") as factory:
            factory.return_value.connect.side_effect = ssl.SSLCertVerificationError("private.example.net /private-path")
            result = verify.check({"label": "panel", "url": "https://private.example.net/private-path", "status": 200})
            self.assertFalse(result["ok"])
            self.assertNotIn("private.example.net", json.dumps(result))
            self.assertNotIn("private-path", json.dumps(result))
            self.assertTrue(factory.call_args.kwargs["context"].check_hostname)
            self.assertEqual(factory.call_args.kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
            factory.return_value.request.assert_not_called()

    def test_redirect_is_checked_without_following(self):
        with patch.object(verify.http.client, "HTTPSConnection") as factory:
            connection = factory.return_value
            connection.sock.getpeercert.return_value = {"notAfter": "fixture-expiry"}
            response = connection.getresponse.return_value
            response.status = 302
            response.read.return_value = b""
            result = verify.check({"label": "login", "url": "https://private.example.net/", "status": 302})
            self.assertTrue(result["ok"])
            self.assertEqual(connection.request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
