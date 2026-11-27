#!/usr/bin/env python3
"""Offline regression tests for the split domain/ipcidr provider updater's publication guard."""

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
        self.domain_target = self.root / "config/clash/rule-providers/johnshall-shadowrocket-ad-domain.txt"
        self.ip_target = self.root / "config/clash/rule-providers/johnshall-shadowrocket-ad-ip.txt"
        self.domain_target.parent.mkdir(parents=True)
        self.previous_domain = b"# Last successful domain provider\n+.previous.example\n"
        self.previous_ip = b"# Last successful ip provider\n192.0.2.1/32\n"
        self.domain_target.write_bytes(self.previous_domain)
        self.ip_target.write_bytes(self.previous_ip)
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
        self.assertEqual(self.domain_target.read_bytes(), self.previous_domain)
        self.assertEqual(self.ip_target.read_bytes(), self.previous_ip)

    def test_october_27_counts_publish_and_check_without_overwriting(self):
        # Real upstream counts: 49,956 raw domains + 128 IPs, 29 duplicates.
        self.write_source(domains=49927, ips=128, duplicates=29)
        self.assert_rejected_without_overwrite(self.run_updater("--check"), "Providers are stale")
        result = self.run_updater()
        self.assertEqual(result.returncode, 0, result.stderr)
        domain_provider = self.domain_target.read_text()
        ip_provider = self.ip_target.read_text()
        domain_rules = [line for line in domain_provider.splitlines() if line and not line.startswith("#")]
        ip_rules = [line for line in ip_provider.splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(domain_rules), 49927)
        self.assertEqual(len(set(domain_rules)), len(domain_rules))
        self.assertEqual(len(ip_rules), 128)
        self.assertEqual(len(set(ip_rules)), len(ip_rules))
        self.assertEqual(domain_rules[0], "+.ad-00000.fixture.example")
        self.assertEqual(domain_rules[-1], "+.ad-49926.fixture.example")
        self.assertEqual(ip_rules[0], "192.0.2.0/32")
        self.assertEqual(ip_rules[-1], "192.0.2.127/32")
        self.assertIn(f"# Source commit: {SOURCE_COMMIT}\n", domain_provider)
        self.assertIn(f"# Source commit: {SOURCE_COMMIT}\n", ip_provider)
        for text in (domain_provider, ip_provider):
            self.assertNotIn(",Reject", text)
            self.assertNotIn("DOMAIN-SUFFIX,", text)
            self.assertNotIn("IP-CIDR,", text)
        checked = self.run_updater("--check")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(self.domain_target.read_text(), domain_provider)
        self.assertEqual(self.ip_target.read_text(), ip_provider)

        # Removing or changing either provider makes --check fail.
        self.ip_target.write_bytes(self.previous_ip)
        stale = self.run_updater("--check")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("Providers are stale", stale.stderr)

    def test_october_26_incomplete_upstream_preserves_previous_providers(self):
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

    def test_unsupported_or_leading_dot_rules_preserve_previous_providers(self):
        self.write_source(domains=50001, ips=128, extra="DOMAIN-KEYWORD,ad,Reject\n")
        self.assert_rejected_without_overwrite(self.run_updater(), "Unsupported source rule")
        self.write_source(domains=50001, ips=128, extra="DOMAIN-SUFFIX,.leading-dot.example,Reject\n")
        self.assert_rejected_without_overwrite(self.run_updater(), "Unsupported source rule")


if __name__ == "__main__":
    unittest.main(verbosity=2)
