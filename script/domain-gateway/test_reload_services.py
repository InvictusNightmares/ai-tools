import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import reload_services as module


class ReloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "loaded"
        self.config = {"state_file": str(self.state), "panel_container": "panel",
                       "gateway_container": "gateway"}
        self.digest = patch.object(module, "certificate_digest", return_value="new")
        self.digest.start()
        self.addCleanup(self.digest.stop)
        self.acme = patch.object(module, "wait_for_acme")
        self.acme.start()
        self.addCleanup(self.acme.stop)
        self.panel = patch.object(module, "wait_for_panel")
        self.panel.start()
        self.addCleanup(self.panel.stop)

    def test_failed_gateway_validation_keeps_running_panel_and_previous_state(self):
        self.state.write_text("old\n")
        with patch.object(module, "command", side_effect=subprocess.CalledProcessError(1, "check")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                module.reload_locked(self.config)
        self.assertEqual(self.state.read_text(), "old\n")
        self.assertFalse(any("restart" in call.args[0] for call in run.call_args_list))

    def test_partial_reload_is_retried_after_failure(self):
        self.state.write_text("old\n")
        with patch.object(module, "command", side_effect=[b"", b"", subprocess.CalledProcessError(1, "reload")]):
            with self.assertRaises(subprocess.CalledProcessError):
                module.reload_locked(self.config)
        self.assertEqual(self.state.read_text(), "old\n")
        with patch.object(module, "command", return_value=b""):
            self.assertEqual(module.reload_locked(self.config), "reloaded")
            self.assertEqual(module.reload_locked(self.config), "unchanged")

    def test_changed_installation_is_not_marked_as_loaded(self):
        self.state.write_text("old\n")
        with patch.object(module, "certificate_digest", side_effect=["new", "new", "newer"]), patch.object(module, "command", return_value=b""):
            with self.assertRaises(module.ConfigError):
                module.reload_locked(self.config)
        self.assertEqual(self.state.read_text(), "old\n")

    def test_force_reloads_unchanged_certificate(self):
        self.state.write_text("new\n")
        with patch.object(module, "command", return_value=b"") as run:
            self.assertEqual(module.reload_locked(self.config, force=True), "reloaded")
        self.assertTrue(any("restart" in call.args[0] for call in run.call_args_list))

    def test_live_acme_defers_restart(self):
        with patch.object(module, "wait_for_acme", side_effect=TimeoutError("busy")), patch.object(module, "command") as run:
            with self.assertRaises(TimeoutError):
                module.reload_locked(self.config)
        run.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_docker_process_query_includes_required_pid_column(self):
        with patch.object(module, "command", return_value=b"PID COMMAND\n12 /app/x-ui\n13 bin/xray-linux -c config.json\n") as run:
            # Use the real readiness function, not the per-test mocked one.
            self.panel.stop()
            module.wait_for_panel("panel", timeout=1)
        self.assertEqual(run.call_args.args[0][-1], "pid,args")


class CertificateValidationTests(unittest.TestCase):
    def test_zero_exit_status_does_not_accept_hostname_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            cert = Path(directory) / "fullchain.pem"
            key = Path(directory) / "key.pem"
            cert.write_text("fixture")
            key.write_text("fixture")
            key.chmod(0o600)
            config = {"certificate": str(cert), "private_key": str(key),
                      "domains": ["service.example.com"]}
            with patch.object(module, "command", side_effect=[b"Certificate will not expire", b"Hostname service.example.com does NOT match certificate"]):
                with self.assertRaises(module.ConfigError):
                    module.certificate_digest(config)


if __name__ == "__main__":
    unittest.main()
