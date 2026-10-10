"""Regression checks for the West personal-account migration and empty SSH errors."""
import contextlib
import csv
import io
import subprocess
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sub2api_daily_person_token_usage as usage


def row(key, person, owner="", **overrides):
    result = dict.fromkeys(usage.USAGE_COLUMNS, "0")
    result.update(
        usage_date="2026-10-09", api_key_id=str(key), person_name=person,
        person_user_id=str(owner), key_name="我的新密钥", models="gpt-example",
        request_count="2", input_tokens="10", output_tokens="4",
        total_tokens="14", total_tokens_with_image="14", actual_cost="0.125",
    )
    result.update(overrides)
    return result


def csv_text(rows=()):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=usage.USAGE_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


class QueryBoundaryTests(unittest.TestCase):
    def query(self, stdout, returncode=0):
        completed = subprocess.CompletedProcess([], returncode, stdout, "")
        with patch.object(usage.subprocess, "run", return_value=completed):
            return usage.query_server(usage.SERVERS["west"], "SELECT 1", 10)[1]

    def test_empty_stdout_is_not_zero_usage(self):
        with self.assertRaisesRegex(RuntimeError, "CSV 表头"):
            self.query("")

    def test_bastion_exit_zero_with_docker_error_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "CSV 表头"):
            self.query("Error response from daemon: No such container: sub2api-postgres\n")

    def test_incomplete_header_is_rejected_even_without_rows(self):
        with self.assertRaisesRegex(RuntimeError, "CSV 表头"):
            self.query("usage_date,api_key_id\n")

    def test_genuine_empty_day_with_full_header_is_valid(self):
        self.assertEqual(self.query(csv_text()), [])

    def test_valid_rows_preserve_identity_and_exact_cost(self):
        original = row(105, "杨涛涛", 58, key_name="代码,测试")
        self.assertEqual(self.query(csv_text([original])), [original])

    def test_truncated_row_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "CSV 行不完整"):
            self.query(csv_text() + "2026-10-09,105\n")

    def test_extra_field_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "CSV 行不完整"):
            self.query(csv_text([row(105, "杨涛涛", 58)]).rstrip() + ",extra\n")

    def test_nonzero_exit_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "退出码 1"):
            self.query(csv_text(), returncode=1)


class IdentityTests(unittest.TestCase):
    def report(self, west=(), tokyo=(), mapping=None):
        results = {
            "west": (usage.SERVERS["west"], list(west)),
            "tokyo": (usage.SERVERS["tokyo"], list(tokyo)),
        }
        return usage.build_reports(results, mapping or {}, set(usage.ALWAYS_EXCLUDED_GROUPS))

    def test_new_and_existing_keys_share_one_account_without_csv_updates(self):
        result = self.report([row(61, "杨涛涛", 58), row(105, "杨涛涛", 58)])
        self.assertEqual(result["unmapped"], [])
        self.assertEqual(result["name_mismatches"], [])
        self.assertEqual(len(result["per_person"]), 1)
        person = result["per_person"][0]
        self.assertEqual((person["business_group"], person["key_count"]), ("研发", 2))
        self.assertEqual(person["actual_cost"], Decimal("0.250"))
        self.assertEqual(person["total_tokens"], 28)
        self.assertEqual(len(result["key_daily"]), 2)

    def test_renamed_key_uses_ledger_owner_not_key_label_or_stale_mapping(self):
        result = self.report(
            [row(61, "杨涛涛", 58, key_name="张成")],
            mapping={("west", "61"): {"person_name": "旧名字", "business_group": "研发Codex"}},
        )
        self.assertEqual(result["per_person"][0]["person_name"], "杨涛涛")
        self.assertEqual(result["name_mismatches"], [])

    def test_different_accounts_with_same_name_are_not_merged(self):
        result = self.report([row(101, "同名用户", 11), row(102, "同名用户", 12)])
        self.assertEqual(len(result["per_person"]), 2)
        west = next(r for r in result["summary"] if r["server"] == "美西")
        self.assertEqual(west["person_count"], 2)

    def test_tokyo_keeps_existing_mapping_and_name_merge(self):
        mapping = {("tokyo", str(k)): {"person_name": "甲", "business_group": "产品"} for k in [10, 11]}
        result = self.report(tokyo=[row(10, "甲"), row(11, "甲")], mapping=mapping)
        self.assertEqual(len(result["per_person"]), 1)
        self.assertEqual(result["per_person"][0]["business_group"], "产品")
        self.assertEqual(result["per_person"][0]["key_count"], 2)

    def test_unique_name_still_merges_across_regions(self):
        result = self.report(
            [row(105, "杨涛涛", 58)], [row(5, "杨涛涛")],
            {("tokyo", "5"): {"person_name": "杨涛涛", "business_group": "研发Codex"}},
        )
        self.assertEqual(len(result["per_person"]), 1)
        self.assertEqual(result["per_person"][0]["key_count"], 2)
        self.assertEqual(set(result["per_person"][0]["servers"].split("、")), {"美西", "东京"})

    def test_ambiguous_cross_region_name_does_not_join_two_accounts(self):
        result = self.report(
            [row(101, "同名用户", 11), row(102, "同名用户", 12)], [row(5, "同名用户")],
            {("tokyo", "5"): {"person_name": "同名用户", "business_group": "研发Codex"}},
        )
        self.assertEqual(len(result["per_person"]), 3)
        self.assertEqual(sum(r["total_tokens"] for r in result["per_person"]), 42)

    def test_legacy_administrator_claude_key_remains_excluded(self):
        result = self.report(
            [row(79, "历史人员")],
            mapping={("west", "79"): {"person_name": "历史人员", "business_group": "研发Claude"}},
        )
        self.assertEqual(result["per_person"], [])
        self.assertEqual(result["excluded_group_usage"]["total_tokens"], 14)

    def test_totals_reconcile_between_key_person_group_and_server(self):
        result = self.report([row(61, "杨涛涛", 58), row(105, "杨涛涛", 58), row(106, "杨顺祥", 45)])
        for section in ["key_daily", "per_person", "per_group", "summary"]:
            self.assertEqual(sum(r["total_tokens"] for r in result[section]), 42)
            self.assertEqual(sum(r["actual_cost"] for r in result[section]), Decimal("0.375"))


class EmailFailureTests(unittest.TestCase):
    def test_query_failure_never_renders_or_sends_mail(self):
        import email_daily_report as mail

        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                start_date="2026-10-09", end_date="2026-10-09", timezone="Asia/Shanghai",
                config_file=Path(directory) / "unused", test_recipient=None, test=False,
                mapping_file=Path(directory) / "unused", timeout_seconds=10,
                work_dir=Path(directory), dry_run=False,
            )
            with contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                stack.enter_context(patch.object(mail, "parse_args", return_value=args))
                stack.enter_context(patch.object(mail, "load_email_config", return_value=object()))
                stack.enter_context(patch.object(mail, "load_group_mapping", return_value={}))
                query = stack.enter_context(patch.object(mail, "_query_with_retry", side_effect=RuntimeError("invalid CSV")))
                render = stack.enter_context(patch.object(mail, "render_report_images"))
                send = stack.enter_context(patch.object(mail, "send_email"))
                self.assertEqual(mail.main(), 1)
                self.assertEqual(query.call_count, 2)
                render.assert_not_called()
                send.assert_not_called()
                west_sql = next(c.args[1] for c in query.call_args_list if c.args[0].key == "west")
                tokyo_sql = next(c.args[1] for c in query.call_args_list if c.args[0].key == "tokyo")
                self.assertIn("u.id = ul.user_id", west_sql)
                self.assertNotIn("JOIN public.users", tokyo_sql)
                self.assertIn("END NOT IN ('张成')", west_sql)
                self.assertIn("NOT IN ('张成')", tokyo_sql)


if __name__ == "__main__":
    unittest.main()
