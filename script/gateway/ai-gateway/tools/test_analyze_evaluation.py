import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


class EvaluationIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.fixture = {"cases": [{"id": "task", "split": "history_holdout", "protocol": "chat",
            "expected_task": "coding", "reviewer_complexity": "bounded", "expected_new_task": False}]}
        self.rows = [{"case_id": "task", "split": "history_holdout", "protocol": "chat", "language": lang,
            "primary": "primary", "reviewer": "reviewer", "ok": True, "latency_ms": 100,
            "business_upstream_called": False, "classification_calls": [],
            "classification": {"Assessment": {"complexity": "bounded", "task_labels": ["coding"],
                "new_task": False}, "EffectiveReasoningEffort": "low"}} for lang in ("zh", "en", "mixed")]

    def run_report(self, rows):
        with tempfile.TemporaryDirectory() as root:
            root = pathlib.Path(root)
            (root / "fixture.json").write_text(json.dumps(self.fixture))
            (root / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
            result = subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("analyze-evaluation.py")),
                "--cases", str(root / "fixture.json"), "--results", str(root / "results.jsonl"),
                "--out", str(root / "out.json")], capture_output=True, text=True)
            output = root / "out.json"
            return result.returncode, json.loads(output.read_text()) if output.exists() else None

    def test_history_split_and_boundaries_are_not_omitted(self):
        code, report = self.run_report(self.rows)
        self.assertEqual(code, 0)
        split = report["trials"][0]["splits"]["history_holdout"]
        self.assertEqual(split["consistent_groups"], 1)
        self.assertEqual(split["languages"]["zh"]["task_boundary_matches"], 1)

    def test_missing_samples_cannot_be_excluded_from_denominator(self):
        code, report = self.run_report(self.rows[:2])
        self.assertEqual(code, 1)
        trial = report["trials"][0]
        self.assertFalse(trial["complete"])
        self.assertEqual(trial["splits"]["history_holdout"]["consistency_percent"], 0)
        self.assertEqual(trial["missing_samples"], [{"case_id": "task", "language": "mixed"}])

    def test_duplicates_cannot_inflate_consistency(self):
        code, report = self.run_report(self.rows[:1] * 3)
        self.assertEqual(code, 2)
        self.assertIsNone(report)

    def test_effort_disagreement_counts_as_inconsistent(self):
        self.rows[1]["classification"]["EffectiveReasoningEffort"] = "medium"
        code, report = self.run_report(self.rows)
        self.assertEqual(code, 0)
        self.assertEqual(report["trials"][0]["splits"]["history_holdout"]["consistent_groups"], 0)

    def test_mislabeled_or_unknown_samples_are_rejected(self):
        for field, value in (("split", "holdout"), ("case_id", "other"), ("protocol", "responses")):
            with self.subTest(field=field):
                changed = [dict(row) for row in self.rows]
                changed[0][field] = value
                code, report = self.run_report(changed)
                self.assertEqual(code, 2)
                self.assertIsNone(report)


if __name__ == "__main__":
    unittest.main()
