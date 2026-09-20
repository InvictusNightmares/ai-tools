import argparse
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


DEPLOY = Path(__file__).parents[1] / "deploy"
sys.path.insert(0, str(DEPLOY))
spec = importlib.util.spec_from_file_location("short_window_watch", DEPLOY / "short_window_watch.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class WatchPolicy(unittest.TestCase):
    def args(self, root, max_5xx=-1):
        return argparse.Namespace(
            region="tokyo", seconds=1, interval=5, max_5xx=max_5xx,
            min_free_bytes=1 << 30, state_dir=str(root),
            access_log=str(root / "access.log"),
        )

    def test_truncation_is_reported_without_rolling_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = [
                {"capture_enabled": True, "truncated": 0, "dropped": 0,
                 "write_errors": 0, "projection_errors": 0,
                 "loss_persist_errors": 0, "queued_bytes": 0,
                 "queue_limit_bytes": 1000},
                {"capture_enabled": True, "truncated": 1, "dropped": 0,
                 "write_errors": 0, "projection_errors": 1,
                 "loss_persist_errors": 0, "queued_bytes": 0,
                 "queue_limit_bytes": 1000},
            ]
            args = self.args(root)
            with patch.object(watch, "read_manifest", return_value=(None, {"state": "enabled"})), \
                 patch.object(watch, "status", side_effect=status), \
                 patch.object(watch, "running", return_value=True), \
                 patch.object(watch, "collector_path_ready", return_value=True), \
                 patch.object(watch, "disable"), \
                 patch.object(watch, "rollback"), \
                 patch.object(watch, "access_log_state", return_value=(1, 0, 0)), \
                 patch.object(watch, "access_log_delta", return_value=(1, (1, 10, 1))), \
                 patch.object(watch.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(10 << 30, 1, 9 << 30)), \
                 patch.object(watch.time, "monotonic", side_effect=[0, 0, 0, 2]), \
                 patch.object(watch.time, "sleep"):
                result = watch.run(args)
            self.assertEqual(result, 0)
            record = next(root.glob("window-tokyo-*.json")).read_text()
            self.assertIn('"truncated_delta": 1', record)
            self.assertIn('"projection_errors_delta": 1', record)
            self.assertIn('"nginx_5xx": 1', record)
            self.assertIn('"failure": null', record)

    def test_fatal_drop_still_rolls_back_even_when_5xx_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.args(root)
            status = [
                {"capture_enabled": True, "truncated": 0, "dropped": 0,
                 "write_errors": 0, "projection_errors": 0,
                 "loss_persist_errors": 0, "queued_bytes": 0,
                 "queue_limit_bytes": 1000},
                {"capture_enabled": True, "truncated": 0, "dropped": 1,
                 "write_errors": 0, "projection_errors": 0,
                 "loss_persist_errors": 0, "queued_bytes": 0,
                 "queue_limit_bytes": 1000},
            ]
            with patch.object(watch, "read_manifest", return_value=(None, {"state": "enabled"})), \
                 patch.object(watch, "status", side_effect=status), \
                 patch.object(watch, "running", return_value=True), \
                 patch.object(watch, "collector_path_ready", return_value=True), \
                 patch.object(watch, "disable"), \
                 patch.object(watch, "rollback"), \
                 patch.object(watch, "access_log_state", return_value=(1, 0, 0)), \
                 patch.object(watch.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(10 << 30, 1, 9 << 30)), \
                 patch.object(watch.time, "monotonic", side_effect=[0, 0, 0]), \
                 patch.object(watch.time, "sleep"):
                watch.run(args)
            record = next(root.glob("window-tokyo-*.json")).read_text()
            self.assertIn('"failure": "collector_dropped"', record)
            self.assertIn('"rollback_attempted": true', record)

    def test_access_log_rotation_resets_cursor_instead_of_failing_watch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "access.log"
            path.write_text("rotated\n")
            delta, state = watch.access_log_delta(path, (999, 100, 0))
            self.assertEqual(delta, 0)
            self.assertEqual(state[0], path.stat().st_ino)
            self.assertEqual(state[1], path.stat().st_size)


if __name__ == "__main__":
    unittest.main()
