#!/usr/bin/env python3

import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest


SCRIPT_PATH = pathlib.Path(__file__).with_name("merge-adapter-env.py")


def run_cli(*arguments):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)] + list(arguments),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


class MergeAdapterEnvironmentTest(unittest.TestCase):
    def test_merges_reviewed_runtime_values_and_preserves_api_key(self):
        api_key = "PRIVATE_API_KEY_SENTINEL"
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            base = root / "adapter.env"
            overlay = root / "runtime.env"
            output = root / "merged.env"
            base.write_text(
                "# existing deployment\n"
                "FIGMA_ADAPTER_API_KEY=%s\n"
                "FIGMA_ADAPTER_PORT=18090\n"
                "FIGMA_COOKIE_FILE=/opt/figma/.cookie\n"
                "UNRELATED_EXISTING_SETTING=preserved\n" % api_key,
                encoding="utf-8",
            )
            overlay.write_text(
                'FIGMA_USER_ID="user-1"\n'
                'FIGMA_FILE_KEY="file-1"\n'
                'FIGMA_THREAD_ID="thread-1"\n'
                'FIGMA_ATTACHMENT_GUID="12:1000034"\n'
                'FIGMA_FOUNDRY_ORIGIN_HOST='
                '"test-v3-figmaiframepreview.figma.site"\n'
                'FIGMA_FOUNDRY_SYNC_TEMPLATE_FILE='
                '"/opt/figma/foundry-sync.json"\n'
                'FIGMA_REQUEST_TEMPLATE_FILE="/opt/figma/template.json"\n',
                encoding="utf-8",
            )

            result = run_cli(
                "--base",
                str(base),
                "--overlay",
                str(overlay),
                "--output",
                str(output),
                "--set",
                "FIGMA_ADAPTER_PORT=18091",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")
            self.assertNotIn(api_key, result.stdout)
            self.assertNotIn(api_key, result.stderr)
            merged = output.read_text(encoding="utf-8")
            self.assertIn("FIGMA_ADAPTER_API_KEY=%s\n" % api_key, merged)
            self.assertIn("FIGMA_ADAPTER_PORT=18091\n", merged)
            self.assertIn(
                "FIGMA_COOKIE_FILE=/opt/figma/.cookie\n",
                merged,
            )
            self.assertIn("UNRELATED_EXISTING_SETTING=preserved\n", merged)
            self.assertIn('FIGMA_USER_ID="user-1"\n', merged)
            self.assertIn(
                (
                    'FIGMA_FOUNDRY_ORIGIN_HOST='
                    '"test-v3-figmaiframepreview.figma.site"\n'
                ),
                merged,
            )
            self.assertIn(
                (
                    'FIGMA_FOUNDRY_SYNC_TEMPLATE_FILE='
                    '"/opt/figma/foundry-sync.json"\n'
                ),
                merged,
            )
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    def test_can_replace_the_base_file_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory) / "adapter.env"
            base.write_text(
                "FIGMA_ADAPTER_API_KEY=test-key\n"
                "FIGMA_ADAPTER_PORT=18090\n",
                encoding="utf-8",
            )
            base.chmod(0o644)
            original_owner = (base.stat().st_uid, base.stat().st_gid)

            result = run_cli(
                "--base",
                str(base),
                "--output",
                str(base),
                "--set",
                "FIGMA_ADAPTER_PORT=18091",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "FIGMA_ADAPTER_PORT=18091\n",
                base.read_text(encoding="utf-8"),
            )
            self.assertEqual(stat.S_IMODE(base.stat().st_mode), 0o600)
            self.assertEqual(
                (base.stat().st_uid, base.stat().st_gid),
                original_owner,
            )

    def test_rejects_api_key_from_overlay_without_echoing_it(self):
        secret = "OVERLAY_SECRET_SENTINEL"
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            base = root / "base.env"
            overlay = root / "overlay.env"
            output = root / "output.env"
            base.write_text(
                "FIGMA_ADAPTER_API_KEY=base-key\n",
                encoding="utf-8",
            )
            overlay.write_text(
                "FIGMA_ADAPTER_API_KEY=%s\n" % secret,
                encoding="utf-8",
            )

            result = run_cli(
                "--base",
                str(base),
                "--overlay",
                str(overlay),
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertNotIn(secret, result.stdout)
            self.assertNotIn(secret, result.stderr)

    def test_rejects_unknown_overlay_and_set_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            base = root / "base.env"
            overlay = root / "overlay.env"
            output = root / "output.env"
            base.write_text(
                "FIGMA_ADAPTER_API_KEY=base-key\n",
                encoding="utf-8",
            )
            overlay.write_text(
                "UNREVIEWED_RUNTIME_SETTING=value\n",
                encoding="utf-8",
            )

            overlay_result = run_cli(
                "--base",
                str(base),
                "--overlay",
                str(overlay),
                "--output",
                str(output),
            )
            set_result = run_cli(
                "--base",
                str(base),
                "--output",
                str(output),
                "--set",
                "UNREVIEWED_RUNTIME_SETTING=value",
            )

            self.assertEqual(overlay_result.returncode, 2)
            self.assertEqual(set_result.returncode, 2)
            self.assertFalse(output.exists())

    def test_rejects_a_base_without_a_nonempty_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            base = root / "base.env"
            output = root / "output.env"
            base.write_text(
                'FIGMA_ADAPTER_API_KEY=""\n',
                encoding="utf-8",
            )

            result = run_cli(
                "--base",
                str(base),
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
