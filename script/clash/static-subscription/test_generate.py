"""Offline structure and publication checks using synthetic subscriptions."""

import contextlib
import copy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import yaml

import generate as subject


HEADER = "upload=10; download=20; total=1000; expire=0"


def ss(name, plugin=False):
    node = {"name": name, "type": "ss", "server": "proxy.example.invalid", "port": 443,
            "cipher": "chacha20-ietf-poly1305", "password": "synthetic-test-password", "udp": True}
    if plugin:
        node.update({"plugin": "obfs", "plugin-opts": {"mode": "tls", "host": "cover.example.invalid"},
                     "udp-over-tcp": True, "udp-over-tcp-version": 2})
    return node


def subscriptions():
    base = {
        "mode": "rule", "ipv6": False, "dns": {"enable": False},
        "proxies": [*(ss(f"BASE-SS-{i:02d}") for i in range(1, 6)), ss("EXTRA-SS-01"), ss("EXTRA-SS-02")],
        "proxy-groups": [
            {"name": "Auto", "type": "url-test", "hidden": True, "include-all-proxies": True,
             "filter": "^BASE-SS-(01|02)$", "empty-fallback": "REJECT",
             "url": "https://example.invalid/check", "interval": 300},
            {"name": "PROXY", "type": "select", "default-selected": "Auto", "proxies": ["Auto"],
             "include-all-proxies": True, "filter": "^BASE-SS-[0-9]+$"},
        ],
        "rules": ["DOMAIN,service.example.invalid,PROXY", "MATCH,PROXY"],
    }
    extra = {"proxies": [ss("SOURCE-01", True), ss("SOURCE-02", True), ss("SOURCE-UNSELECTED", True)]}
    return base, extra


class Fixture(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory(prefix="static-subscription-test-")
        self.addCleanup(work.cleanup)
        self.root = Path(work.name).resolve()
        self.settings = subject.Settings(
            base_url="https://base.example.invalid/private",
            extra_url="https://extra.example.invalid/private",
            nodes={"SOURCE-01": "EXTRA-SS-01", "SOURCE-02": "EXTRA-SS-02"},
            output_dir=self.root / "published",
            required_base_nodes=[f"BASE-SS-{i:02d}" for i in range(1, 6)],
            max_stale_seconds=3600,
        )
        self.base, self.extra = subscriptions()

    def publish(self, now=1000):
        with subject.publish_lock(self.settings):
            subject.publish(b"previous subscription\n", subject.userinfo(HEADER, now), self.settings, now)
        return subject.current_target(self.settings.output_dir)

    def config(self, **overrides):
        data = {"base_url": self.settings.base_url, "extra_url": self.settings.extra_url,
                "nodes": self.settings.nodes, "output_dir": str(self.settings.output_dir),
                "required_base_nodes": self.settings.required_base_nodes}
        data.update(overrides)
        path = self.root / "private.yaml"
        path.write_text(yaml.safe_dump(data))
        path.chmod(0o600)
        return path


class MergeTests(Fixture):
    def test_replaces_incomplete_nodes_preserving_base_rules_and_auto(self):
        original_base, original_extra = copy.deepcopy(self.base), copy.deepcopy(self.extra)
        merged = subject.merge(self.base, self.extra, self.settings)
        self.assertEqual(len(merged["proxies"]), 7)
        self.assertEqual(merged["proxies"][:5], self.base["proxies"][:5])
        for index, node in enumerate(merged["proxies"][5:]):
            expected = dict(self.extra["proxies"][index], name=f"EXTRA-SS-{index + 1:02d}")
            self.assertEqual(node, expected)
        for key in ("rules", "mode", "dns", "ipv6"):
            self.assertEqual(merged[key], self.base[key])
        self.assertEqual(merged["proxy-groups"][0], self.base["proxy-groups"][0])
        self.assertEqual(self.base, original_base)
        self.assertEqual(self.extra, original_extra)
        proxy = merged["proxy-groups"][1]
        self.assertEqual(proxy["proxies"], ["Auto"])
        self.assertEqual(proxy["default-selected"], "Auto")
        for node in merged["proxies"]:
            self.assertEqual(sum(bool(re.search(p, node["name"])) for p in proxy["filter"].split("`")), 1)
        self.assertEqual(subject.merge(merged, self.extra, self.settings), merged)

    def test_appends_missing_nodes_but_never_imports_unselected_nodes(self):
        self.base["proxies"] = self.base["proxies"][:5]
        result = subject.merge(self.base, self.extra, self.settings)
        self.assertEqual([node["name"] for node in result["proxies"]][-2:], ["EXTRA-SS-01", "EXTRA-SS-02"])
        self.assertEqual(len(result["proxies"]), 7)

    def test_partial_dynamic_filter_does_not_duplicate_members(self):
        group = self.base["proxy-groups"][1]
        group["filter"] += "`^EXTRA-SS-01$"
        group["proxies"].extend(["EXTRA-SS-01", "EXTRA-SS-02"])
        result = subject.merge(self.base, self.extra, self.settings)["proxy-groups"][1]
        self.assertEqual(result["proxies"], ["Auto"])
        for name in self.settings.nodes.values():
            self.assertEqual(sum(bool(re.search(p, name)) for p in result["filter"].split("`")), 1)

    def test_explicit_group_adds_each_selected_node_once(self):
        group = self.base["proxy-groups"][1]
        group.pop("include-all-proxies")
        group["proxies"].extend(["BASE-SS-01", "EXTRA-SS-01"])
        result = subject.merge(self.base, self.extra, self.settings)["proxy-groups"][1]
        self.assertEqual(result["proxies"], ["Auto", "BASE-SS-01", "EXTRA-SS-01", "EXTRA-SS-02"])

    def test_unfiltered_dynamic_group_needs_no_new_filter(self):
        self.base["proxy-groups"][1].pop("filter")
        result = subject.merge(self.base, self.extra, self.settings)
        self.assertNotIn("filter", result["proxy-groups"][1])

    def test_protected_group_cannot_gain_new_members(self):
        for change in ({"filter": ".*"}, {"proxies": ["EXTRA-SS-01"]}):
            with self.subTest(change=change):
                base = copy.deepcopy(self.base)
                base["proxy-groups"][0].update(change)
                with self.assertRaisesRegex(subject.Failure, "protected group"):
                    subject.merge(base, self.extra, self.settings)

    def test_destination_exclusions_are_rejected_in_both_group_modes(self):
        for dynamic in (True, False):
            for exclusion in ({"exclude-filter": "^EXTRA"}, {"exclude-type": "Http|sHaDoWsOcKs"}):
                with self.subTest(dynamic=dynamic, exclusion=exclusion):
                    base = copy.deepcopy(self.base)
                    base["proxy-groups"][1].update(exclusion, **{"include-all-proxies": dynamic})
                    with self.assertRaisesRegex(subject.Failure, "exclusions"):
                        subject.merge(base, self.extra, self.settings)

    def test_missing_required_or_selected_nodes_fail(self):
        for which in ("base", "extra"):
            with self.subTest(which=which):
                base, extra = copy.deepcopy(self.base), copy.deepcopy(self.extra)
                (base if which == "base" else extra)["proxies"].pop(0)
                with self.assertRaises(subject.Failure):
                    subject.merge(base, extra, self.settings)

    def test_duplicate_node_or_group_names_fail(self):
        for which, key in (("base", "proxies"), ("extra", "proxies"), ("base", "proxy-groups")):
            with self.subTest(which=which, key=key):
                base, extra = copy.deepcopy(self.base), copy.deepcopy(self.extra)
                doc = base if which == "base" else extra
                doc[key].append(copy.deepcopy(doc[key][0]))
                with self.assertRaisesRegex(subject.Failure, "duplicate"):
                    subject.merge(base, extra, self.settings)

    def test_selected_node_parameters_and_chain_are_checked(self):
        for change in ({"plugin": None}, {"password": ""}, {"port": True}, {"port": 65536},
                       {"plugin-opts": {"mode": "tls"}}, {"dialer-proxy": "MISSING-GROUP"}):
            with self.subTest(change=change):
                extra = copy.deepcopy(self.extra)
                extra["proxies"][0].update(change)
                with self.assertRaises(subject.Failure):
                    subject.merge(self.base, extra, self.settings)

    def test_policy_name_collision_and_missing_rules_fail(self):
        for target in ("Auto", "DIRECT"):
            with self.subTest(target=target):
                settings = replace(self.settings, nodes={"SOURCE-01": target})
                with self.assertRaisesRegex(subject.Failure, "collides"):
                    subject.merge(self.base, self.extra, settings)
        self.base["rules"] = []
        with self.assertRaisesRegex(subject.Failure, "rules"):
            subject.merge(self.base, self.extra, self.settings)


class ReferenceTests(Fixture):
    def test_unknown_group_policy_and_provider_are_rejected(self):
        for change in ({"proxies": ["MISSING"]}, {"use": ["MISSING"]}):
            with self.subTest(change=change):
                base = copy.deepcopy(self.base)
                base["proxy-groups"][1].update(change)
                with self.assertRaisesRegex(subject.Failure, "group references"):
                    subject.validate_references(base)

    def test_invalid_rule_or_unknown_target_is_rejected(self):
        for rule in (42, "INVALID", "MATCH,MISSING", "DOMAIN,example.invalid,MISSING"):
            with self.subTest(rule=rule):
                self.base["rules"] = [rule]
                with self.assertRaises(subject.Failure):
                    subject.validate_references(self.base)

    def test_provider_references_are_checked_without_downloading(self):
        self.base["proxy-providers"] = {"SOURCE": {"type": "http", "url": "https://example.invalid/proxies"}}
        self.base["proxy-groups"][1]["use"] = ["SOURCE"]
        self.base["rule-providers"] = {"FILTER": {"type": "http", "url": "https://example.invalid/rules"}}
        self.base["rules"].insert(0, "RULE-SET,FILTER,PROXY,no-resolve")
        with patch.object(subject, "fetch", side_effect=AssertionError("unexpected download")):
            subject.validate_references(self.base)
        self.base["rule-providers"] = {}
        with self.assertRaisesRegex(subject.Failure, "unknown rule provider"):
            subject.validate_references(self.base)

    def test_rule_flags_and_nested_conditions_keep_policy_references(self):
        self.base["rules"] = ["GEOIP,CN,DIRECT,no-resolve", "DST-PORT,443,PROXY",
                              "AND,((NETWORK,TCP),(DST-PORT,443)),PROXY", "MATCH,PROXY"]
        subject.validate_references(self.base)

    def test_sub_rule_targets_are_checked_against_sub_rules(self):
        self.base["sub-rules"] = {"FILTER": ["MATCH,PROXY"]}
        self.base["rules"].insert(0, "SUB-RULE,(NETWORK,TCP),FILTER")
        subject.validate_references(self.base)
        self.base["sub-rules"]["FILTER"] = ["MATCH,MISSING"]
        with self.assertRaisesRegex(subject.Failure, "unknown policy"):
            subject.validate_references(self.base)

    def test_node_group_name_collision_is_rejected(self):
        self.base["proxies"][0]["name"] = "Auto"
        with self.assertRaisesRegex(subject.Failure, "collides"):
            subject.validate_references(self.base)


class MetadataTests(unittest.TestCase):
    def test_valid_and_unlimited_metadata(self):
        self.assertEqual(subject.userinfo(HEADER, 1000), {"upload": 10, "download": 20, "total": 1000, "expire": 0})
        self.assertEqual(subject.userinfo("upload=10;download=20;total=0", 1000)["expire"], 0)

    def test_expired_or_exhausted_metadata_revokes(self):
        for header in ("upload=1; download=0; total=0; expire=1000", "upload=10; download=20; total=30"):
            with self.subTest(header=header), self.assertRaises(subject.Revoked):
                subject.userinfo(header, 1000)

    def test_missing_duplicate_or_injected_metadata_is_rejected(self):
        for header in ("", "upload=1;download=2", HEADER + ";upload=1", HEADER + '\"; injected=1',
                       "upload=-1;download=2;total=0"):
            with self.subTest(header=header), self.assertRaises(subject.Failure):
                subject.userinfo(header, 1000)


class SettingsTests(Fixture):
    def test_private_config_loads(self):
        settings = subject.Settings.load(self.config())
        self.assertEqual(settings.nodes, self.settings.nodes)
        self.assertEqual(settings.output_dir, self.settings.output_dir)

    def test_public_permissions_and_symlink_config_are_rejected(self):
        path = self.config()
        path.chmod(0o644)
        with self.assertRaisesRegex(subject.Failure, "chmod 600"):
            subject.Settings.load(path)
        path.chmod(0o600)
        link = self.root / "linked.yaml"
        link.symlink_to(path)
        with self.assertRaisesRegex(subject.Failure, "regular private file"):
            subject.Settings.load(link)

    def test_config_and_output_cannot_be_in_git_checkout(self):
        checkout = self.root / "checkout"
        checkout.mkdir()
        (checkout / ".git").write_text("gitdir: synthetic-worktree\n")
        private = checkout / "private.yaml"
        private.write_bytes(self.config().read_bytes())
        private.chmod(0o600)
        with self.assertRaisesRegex(subject.Failure, "Git checkout"):
            subject.Settings.load(private)
        with self.assertRaisesRegex(subject.Failure, "Git checkout"):
            subject.Settings.load(self.config(output_dir=str(checkout / "data")))

    def test_invalid_settings_fail_before_fetching(self):
        cases = ({"base_url": "http://base.example.invalid/private"}, {"extra_url": 42},
                 {"unknown": "value"}, {"nodes": {"A": "SAME", "B": "SAME"}},
                 {"required_base_nodes": []}, {"required_base_nodes": ["EXTRA-SS-01"]},
                 {"max_stale_seconds": 0}, {"nginx_reload_command": ["true"]}, {"reader_gid": -1})
        for change in cases:
            with self.subTest(change=change), self.assertRaises(subject.Failure):
                subject.Settings.load(self.config(**change))


class PublicationTests(Fixture):
    def test_atomic_publication_keeps_only_new_generation(self):
        previous = self.publish()
        root = self.settings.output_dir
        with subject.publish_lock(self.settings):
            subject.publish(b"new subscription\n", subject.userinfo(HEADER, 1100), self.settings, 1100)
        current = subject.current_target(root)
        self.assertNotEqual(current, previous)
        self.assertEqual((root / "current/subscription.yaml").read_bytes(), b"new subscription\n")
        self.assertFalse((root / previous).exists())
        self.assertEqual(len(list(root.glob("generation-*"))), 1)
        self.assertEqual((root / "current/headers.conf").read_text(),
                         f'add_header Subscription-Userinfo "{HEADER}" always;\n')
        self.assertEqual(stat.S_IMODE((root / "current/subscription.yaml").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)

    def test_reader_group_gets_read_only_access(self):
        self.settings = replace(self.settings, reader_gid=os.getgid())
        self.publish()
        root = self.settings.output_dir
        self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o750)
        self.assertEqual(stat.S_IMODE((root / "current/subscription.yaml").stat().st_mode), 0o640)
        self.assertEqual((root / "current/subscription.yaml").stat().st_gid, os.getgid())

    def test_nginx_check_or_reload_failure_rolls_back(self):
        previous = self.publish()
        settings = replace(self.settings, nginx_check_command=("nginx", "-t"),
                           nginx_reload_command=("nginx", "-s", "reload"))
        for step in (0, 1):
            with self.subTest(step=step):
                results = [None] * step + [subject.Failure("synthetic command failure")]
                with patch.object(subject, "run_command", side_effect=results), subject.publish_lock(settings):
                    with self.assertRaises(subject.Failure):
                        subject.publish(b"new subscription", subject.userinfo(HEADER, 1000), settings, 1000)
                self.assertEqual(subject.current_target(settings.output_dir), previous)
                self.assertEqual((settings.output_dir / "current/subscription.yaml").read_bytes(), b"previous subscription\n")
                self.assertEqual(len(list(settings.output_dir.glob("generation-*"))), 1)

    def test_failed_first_publication_leaves_no_current(self):
        settings = replace(self.settings, nginx_check_command=("nginx", "-t"),
                           nginx_reload_command=("nginx", "-s", "reload"))
        with patch.object(subject, "run_command", side_effect=subject.Failure("failed")), subject.publish_lock(settings):
            with self.assertRaises(subject.Failure):
                subject.publish(b"new subscription", subject.userinfo(HEADER, 1000), settings, 1000)
        self.assertIsNone(subject.current_target(settings.output_dir))
        self.assertEqual(list(settings.output_dir.glob("generation-*")), [])

    def test_generation_permission_failure_removes_unpublished_directory(self):
        previous = self.publish()
        with subject.publish_lock(self.settings), patch.object(subject, "permissions", side_effect=OSError):
            with self.assertRaises(OSError):
                subject.publish(b"new subscription", subject.userinfo(HEADER, 1000), self.settings, 1000)
        self.assertEqual(subject.current_target(self.settings.output_dir), previous)
        self.assertEqual(len(list(self.settings.output_dir.glob("generation-*"))), 1)

    def test_stale_or_revoked_file_is_withdrawn_but_nginx_include_remains(self):
        for now, revoked in ((4600, False), (1001, True)):
            with self.subTest(now=now, revoked=revoked):
                self.publish()
                self.assertTrue(subject.withdraw_if_expired(self.settings, now, revoked))
                self.assertFalse((self.settings.output_dir / "current/subscription.yaml").exists())
                self.assertTrue((self.settings.output_dir / "current/headers.conf").is_file())

    def test_unexpired_failure_keeps_previous_file(self):
        self.publish()
        self.assertFalse(subject.withdraw_if_expired(self.settings, 4599))
        self.assertTrue((self.settings.output_dir / "current/subscription.yaml").is_file())

    def test_upstream_expiry_is_stricter_than_maximum_age(self):
        with subject.publish_lock(self.settings):
            subject.publish(b"previous", subject.userinfo(HEADER.replace("expire=0", "expire=1200"), 1000),
                            self.settings, 1000)
        self.assertTrue(subject.withdraw_if_expired(self.settings, 1200))

    def test_unmanaged_symlink_cannot_redirect_cleanup(self):
        root = self.settings.output_dir
        root.mkdir()
        (root / "current").symlink_to(self.root)
        sentinel = self.root / "keep.txt"
        sentinel.write_text("unrelated")
        with self.assertRaisesRegex(subject.Failure, "not managed"):
            subject.publish(b"new", subject.userinfo(HEADER, 1000), self.settings, 1000)
        self.assertEqual(sentinel.read_text(), "unrelated")

    def test_lock_rejects_concurrent_publishers(self):
        with subject.publish_lock(self.settings):
            with self.assertRaisesRegex(subject.Failure, "already running"):
                with subject.publish_lock(self.settings):
                    self.fail("second writer acquired the lock")


class PipelineTests(Fixture):
    def test_dry_run_validates_without_publishing_or_reloading(self):
        with patch.object(subject, "fetch", side_effect=[(self.base, HEADER), (self.extra, "")]), \
             patch.object(subject, "run_command") as command, patch.object(subject, "publish") as publish:
            result = subject.generate(self.settings, dry_run=True)
        self.assertEqual(result, {"status": "validated", "nodes": 7, "selected_nodes": 2, "traffic_source": "base_only"})
        command.assert_not_called()
        publish.assert_not_called()
        self.assertFalse(self.settings.output_dir.exists())

    def test_validation_failure_does_not_overwrite_previous(self):
        previous = self.publish()
        self.base["rules"] = ["MATCH,MISSING"]
        with patch.object(subject, "fetch", side_effect=[(self.base, HEADER), (self.extra, "")]):
            with self.assertRaisesRegex(subject.Failure, "unknown policy"):
                subject.generate(self.settings)
        self.assertEqual(subject.current_target(self.settings.output_dir), previous)

    def test_cli_publishes_without_any_external_executable(self):
        config = self.config()
        output = io.StringIO()
        with patch.dict(os.environ, {"PATH": ""}), \
             patch.object(subject, "fetch", side_effect=[(self.base, HEADER), (self.extra, "")]), \
             patch.object(subject.subprocess, "run", side_effect=AssertionError("unexpected child process")), \
             contextlib.redirect_stdout(output):
            self.assertEqual(subject.main(["--config", str(config)]), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "published")
        result = yaml.safe_load((self.settings.output_dir / "current/subscription.yaml").read_bytes())
        self.assertEqual(len(result["proxies"]), 7)
        self.assertEqual(result["proxies"][5]["plugin"], "obfs")
        self.assertEqual(result["rules"], self.base["rules"])
        self.assertEqual(result["proxy-groups"][0], self.base["proxy-groups"][0])

    def test_rechecks_expiration_after_validation(self):
        header = HEADER.replace("expire=0", "expire=1001")
        with patch.object(subject, "fetch", side_effect=[(self.base, header), (self.extra, "")]), \
             patch.object(subject.time, "time", side_effect=[1000, 1001]):
            with self.assertRaises(subject.Revoked):
                subject.generate(self.settings, dry_run=True)

    def test_main_withdraws_on_stale_operational_errors_and_redacts_logs(self):
        for error in (subject.Failure("upstream unavailable"), OSError("private-path-secret")):
            with self.subTest(error=type(error).__name__):
                self.publish()
                output = io.StringIO()
                with patch.object(subject.Settings, "load", return_value=self.settings), \
                     patch.object(subject, "generate", side_effect=error), \
                     patch.object(subject.time, "time", return_value=4600), contextlib.redirect_stderr(output):
                    self.assertEqual(subject.main(["--config", str(self.root / "private.yaml")]), 1)
                self.assertIn("withdrawn", output.getvalue())
                self.assertNotIn("private-path-secret", output.getvalue())
                self.assertFalse((self.settings.output_dir / "current/subscription.yaml").exists())

    def test_child_process_output_never_appears_in_errors(self):
        command = [sys.executable, "-c", "import sys; print('synthetic-private-token'); sys.exit(2)"]
        with self.assertRaises(subject.Failure) as error:
            subject.run_command(command, 10, "nginx check")
        self.assertNotIn("synthetic-private-token", str(error.exception))

    def test_base_access_denial_revokes_but_extra_denial_does_not(self):
        for label in ("base", "extra"):
            with self.subTest(label=label):
                error = urllib.error.HTTPError("https://example.invalid/private-token", 403, "denied", {}, None)
                with patch.object(subject.urllib.request.OpenerDirector, "open", side_effect=error):
                    with self.assertRaises(subject.Failure) as raised:
                        subject.fetch("https://example.invalid/private-token", self.settings, label)
                self.assertEqual(isinstance(raised.exception, subject.Revoked), label == "base")
                self.assertNotIn("private-token", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
