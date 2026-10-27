#!/usr/bin/env python3
"""Offline regression tests for the provider updater's publication guard."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


UPDATER = Path(__file__).with_name("update-johnshall-shadowrocket-ad.sh")
SOURCE_COMMIT = "1" * 40


class ProviderUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.script = self.root / "script/clash" / UPDATER.name
        self.script.parent.mkdir(parents=True)
        shutil.copyfile(UPDATER, self.script)
        self.target = self.root / "config/clash/rule-providers/johnshall-shadowrocket-ad.txt"
        self.target.parent.mkdir(parents=True)
        self.previous = b"# Last successful provider\nDOMAIN-SUFFIX,previous.example\n"
        self.target.write_bytes(self.previous)
        self.source = self.root / "sr_ad_only.conf"

    def write_source(self, domains, ips, duplicates=0, extra=""):
        domain_rules = [
            f"DOMAIN-SUFFIX,ad-{number:05d}.fixture.example,Reject\n"
            for number in range(domains)
        ]
        ip_rules = [f"IP-CIDR,192.0.2.{number}/32,Reject\n" for number in range(ips)]
        self.source.write_text(
            "[Rule]\n# Offline fixture\n"
            + "".join(domain_rules + ip_rules)
            + domain_rules[0] * duplicates
            + extra,
            encoding="utf-8",
        )

    def run_updater(self, *options):
        return subprocess.run(
            [
                "bash", str(self.script), *options,
                "--source-file", str(self.source),
                "--source-commit", SOURCE_COMMIT,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def assert_rejected_without_overwrite(self, result, message):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.previous)

    def test_october_27_counts_publish_and_check_without_overwriting(self):
        # Real upstream counts: 49,956 raw domains + 128 IPs, 29 duplicates.
        self.write_source(domains=49927, ips=128, duplicates=29)
        self.assert_rejected_without_overwrite(self.run_updater("--check"), "Provider is stale")
        result = self.run_updater()
        self.assertEqual(result.returncode, 0, result.stderr)
        provider = self.target.read_text()
        rules = [line for line in provider.splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(rules), 50055)
        self.assertEqual(len(set(rules)), len(rules))
        self.assertEqual(rules[0], "DOMAIN-SUFFIX,ad-00000.fixture.example")
        self.assertEqual(rules[-1], "IP-CIDR,192.0.2.127/32")
        self.assertIn(f"# Source commit: {SOURCE_COMMIT}\n", provider)
        self.assertNotIn(",Reject", provider)
        checked = self.run_updater("--check")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(self.target.read_text(), provider)

    def test_october_26_incomplete_upstream_preserves_previous_provider(self):
        # Upstream's failed download published 38,605 raw / 38,575 unique rules.
        self.write_source(domains=38450, ips=125, duplicates=30)
        self.assert_rejected_without_overwrite(self.run_updater(), "rule counts")

    def test_duplicates_cannot_satisfy_the_minimum(self):
        self.write_source(domains=49000, ips=128, duplicates=2000)
        self.assert_rejected_without_overwrite(self.run_updater(), "rule counts")

    def test_effective_rule_count_boundary(self):
        self.write_source(domains=49871, ips=128)
        self.assert_rejected_without_overwrite(self.run_updater(), "rule counts")
        self.write_source(domains=49872, ips=128)
        result = self.run_updater()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unsupported_rules_preserve_previous_provider(self):
        self.write_source(domains=50001, ips=128, extra="DOMAIN-KEYWORD,ad,Reject\n")
        self.assert_rejected_without_overwrite(self.run_updater(), "Unsupported source rule")


if __name__ == "__main__":
    unittest.main(verbosity=2)
