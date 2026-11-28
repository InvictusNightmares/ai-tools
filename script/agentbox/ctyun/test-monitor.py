#!/usr/bin/env python3
"""Unit tests for the agentbox-ctyun keepalive watchdog."""

import datetime as dt
import importlib.util
import json
import pathlib
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).with_name("monitor.py")
SPEC = importlib.util.spec_from_file_location("ctyun_monitor", MODULE_PATH)
assert SPEC and SPEC.loader
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)


class CtyunMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ctyun-monitor-test-")
        self.health = pathlib.Path(self.tmp.name) / "health.json"
        self.now = dt.datetime(2026, 11, 28, 4, 0, 0, tzinfo=dt.timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def write_health(self, state: str, delta_seconds: int):
        ts = self.now - dt.timedelta(seconds=delta_seconds)
        self.health.write_text(json.dumps({"State": state, "Time": ts.isoformat()}), encoding="utf-8")

    def test_healthy_stays_quiet(self):
        self.write_health("connected", 30)
        verdict = monitor.evaluate("agentbox-ctyun", self.health, self.now, 240, lambda _: (True, "running:healthy"))
        self.assertTrue(verdict["ok"])
        sent = []
        action, state = monitor.decide_and_act(
            verdict, {"status": "healthy", "reason": None, "last_alert_ts": 0},
            self.now, 3600, "agentbox", lambda t, m: sent.append((t, m)) or "mid-1",
        )
        self.assertEqual(action, "healthy_quiet")
        self.assertEqual(sent, [])
        self.assertEqual(state["status"], "healthy")

    def test_stale_health_alerts_once_then_cools_down_and_recovers(self):
        self.write_health("connected", 400)
        verdict = monitor.evaluate("agentbox-ctyun", self.health, self.now, 240, lambda _: (True, "running:healthy"))
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["reason_key"], "health=health_stale")
        sent = []
        sender = lambda t, m: sent.append((t, m)) or f"mid-{len(sent)}"

        action1, state1 = monitor.decide_and_act(
            verdict, {"status": "healthy", "reason": None, "reason_key": None, "last_alert_ts": 0},
            self.now, 3600, "agentbox", sender,
        )
        self.assertEqual(action1, "alert_sent")
        self.assertEqual(len(sent), 1)
        self.assertEqual(state1["status"], "alerting")
        self.assertEqual(state1["reason_key"], "health=health_stale")

        # 5 minutes later, re-evaluating produces a larger age (700s vs 400s) -> must STILL suppress by cooldown
        later = self.now + dt.timedelta(minutes=5)
        verdict_later = monitor.evaluate("agentbox-ctyun", self.health, later, 240, lambda _: (True, "running:healthy"))
        self.assertNotEqual(verdict_later["reason"], verdict["reason"])
        self.assertEqual(verdict_later["reason_key"], "health=health_stale")
        action2, state2 = monitor.decide_and_act(verdict_later, state1, later, 3600, "agentbox", sender)
        self.assertEqual(action2, "suppressed_cooldown")
        self.assertEqual(len(sent), 1)

        # If a different root cause appears during cooldown (e.g. container exits), alert immediately
        escalated = monitor.evaluate("agentbox-ctyun", self.health, later, 240, lambda _: (False, "container_not_running:false"))
        self.assertEqual(escalated["reason_key"], "container=container_not_running:false; health=health_stale")
        action_esc, state_esc = monitor.decide_and_act(escalated, state2, later, 3600, "agentbox", sender)
        self.assertEqual(action_esc, "alert_sent")
        self.assertEqual(len(sent), 2)

        # After cooldown expires on original state -> re-alerts
        after_cd = self.now + dt.timedelta(seconds=3601)
        verdict_after = monitor.evaluate("agentbox-ctyun", self.health, after_cd, 240, lambda _: (True, "running:healthy"))
        action3, state3 = monitor.decide_and_act(verdict_after, state2, after_cd, 3600, "agentbox", sender)
        self.assertEqual(action3, "alert_sent")
        self.assertEqual(len(sent), 3)

        # Recovery -> sends one recovery notice and resets state
        self.write_health("connected", 10)
        ok_verdict = monitor.evaluate("agentbox-ctyun", self.health, self.now, 240, lambda _: (True, "running:healthy"))
        action4, state4 = monitor.decide_and_act(ok_verdict, state3, after_cd, 3600, "agentbox", sender)
        self.assertEqual(action4, "recovered_notified")
        self.assertEqual(len(sent), 4)
        self.assertIn("恢复", sent[-1][0])
        self.assertEqual(state4["status"], "healthy")

    def test_unhealthy_container_or_retrying_state_triggers_alert(self):
        self.write_health("retrying", 5)
        verdict = monitor.evaluate("agentbox-ctyun", self.health, self.now, 240, lambda _: (False, "container_unhealthy:unhealthy"))
        self.assertFalse(verdict["ok"])
        self.assertIn("container=container_unhealthy:unhealthy", verdict["reason"])
        self.assertIn("health=keepalive_state_retrying", verdict["reason"])

    def test_future_timestamp_rejected_and_deduped(self):
        self.write_health("connected", -500)
        verdict1 = monitor.evaluate("agentbox-ctyun", self.health, self.now, 240, lambda _: (True, "running:healthy"))
        self.assertFalse(verdict1["ok"])
        self.assertIn("health_future_timestamp", verdict1["reason"])
        self.assertEqual(verdict1["reason_key"], "health=health_future_timestamp")
        sent = []
        sender = lambda t, m: sent.append((t, m)) or f"mid-{len(sent)}"
        a1, st1 = monitor.decide_and_act(verdict1, {"status": "healthy", "reason": None, "reason_key": None, "last_alert_ts": 0}, self.now, 3600, "agentbox", sender)
        self.assertEqual(a1, "alert_sent")
        later = self.now + dt.timedelta(seconds=60)
        verdict2 = monitor.evaluate("agentbox-ctyun", self.health, later, 240, lambda _: (True, "running:healthy"))
        self.assertNotEqual(verdict2["reason"], verdict1["reason"])
        a2, _ = monitor.decide_and_act(verdict2, st1, later, 3600, "agentbox", sender)
        self.assertEqual(a2, "suppressed_cooldown")
        self.assertEqual(len(sent), 1)

    def test_non_dict_health_json_handled_cleanly(self):
        self.health.write_text("[]", encoding="utf-8")
        verdict = monitor.evaluate("agentbox-ctyun", self.health, self.now, 240, lambda _: (True, "running:healthy"))
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["reason_key"], "health=health_file_schema_invalid")

    def test_dry_run_never_sends(self):
        self.write_health("login-required", 10)
        verdict = monitor.evaluate("agentbox-ctyun", self.health, self.now, 240, lambda _: (True, "running:healthy"))
        sent = []
        action, _ = monitor.decide_and_act(
            verdict, {"status": "healthy", "reason": None, "last_alert_ts": 0},
            self.now, 3600, "agentbox", lambda t, m: sent.append((t, m)) or "mid", dry_run=True,
        )
        self.assertEqual(action, "alert_sent")
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
