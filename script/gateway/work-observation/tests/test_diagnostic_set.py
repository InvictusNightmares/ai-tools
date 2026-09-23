import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import analyze
import diagnostic_set
import rolling


class DiagnosticSet(unittest.TestCase):
    def test_builds_exact_body_free_balanced_set_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            analysis = root / "analysis" / "index.sqlite"
            stores = {}
            db = analyze.connect(analysis)
            try:
                rolling.setup(db)
                for region, ingress in (("tokyo", "4000"), ("us", "4001")):
                    store = root / region
                    event_dir = store / "events" / "2026-09-22"
                    event_dir.mkdir(parents=True)
                    stores[region] = store
                    for index in range(120):
                        event_id = f"{region}-{index:03d}"
                        outcome = "failed" if index % 17 == 0 else "completed"
                        request = {
                            "model": "auto",
                            "messages": [
                                {"role": "user", "content": f"PRIVATE_BODY_{event_id}"}
                            ],
                        }
                        if index % 11 == 0:
                            request["tools"] = [{"type": "function", "name": "read_file"}]
                        event = {
                            "schema": "work-observation-v1",
                            "content_policy": "literal_text_attachment_metadata",
                            "id": event_id,
                            "at": f"2026-09-22T00:{index // 60:02d}:{index % 60:02d}+00:00",
                            "region": region,
                            "ingress": ingress,
                            "kind": "http_exchange",
                            "protocol": "responses" if index % 3 else "chat_completions",
                            "outcome": outcome,
                            "version": "fixture",
                            "client": ("codex" if index % 4 else "other-client"),
                            "request": request,
                            "response": {
                                "object": "response",
                                "id": f"resp-{event_id}",
                                "model": "astra",
                                "output": [{"role": "assistant", "content": "done"}],
                            },
                        }
                        raw_event = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                        digest = hashlib.sha256(raw_event.encode()).hexdigest()
                        path = event_dir / f"{event_id}.json"
                        path.write_text(
                            json.dumps({"sha256": digest, "event": event}, ensure_ascii=False, separators=(",", ":"))
                            + "\n",
                            encoding="utf-8",
                        )
                        analyze.ingest(db, event)
                        db.execute(
                            "INSERT INTO review_jobs(region,event_id,source_path,sha,at,state) VALUES(?,?,?,?,?,?)",
                            (region, event_id, str(path), digest, event["at"], "complete"),
                        )
                        if index % 19 == 0:
                            db.execute(
                                """INSERT INTO semantic_reviews
                                (region,event_id,source_path,source_sha,plane,state,guard_state,guard_decision,auto_state,auto_model)
                                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                                (region, event_id, str(path), digest, "offline_analysis", "complete",
                                 "complete", "block", "not_run", None),
                            )
                        elif index % 23 == 0:
                            db.execute(
                                """INSERT INTO semantic_reviews
                                (region,event_id,source_path,source_sha,plane,state,guard_state,auto_state)
                                VALUES(?,?,?,?,?,?,?,?)""",
                                (region, event_id, str(path), digest, "offline_analysis", "unavailable",
                                 "unavailable", "not_run"),
                            )
                    db.commit()
            finally:
                db.close()

            first = diagnostic_set.build_manifest(
                analysis, {key: value for key, value in stores.items()},
                count=200, seed="test-seed",
            )
            second = diagnostic_set.build_manifest(
                analysis, {key: value for key, value in stores.items()},
                count=200, seed="test-seed",
            )
            self.assertEqual(first["schema"], diagnostic_set.SCHEMA)
            self.assertEqual(first["counts"]["total"], 200)
            self.assertEqual(first["counts"]["by_region"], {"tokyo": 100, "us": 100})
            self.assertEqual(first["rows"], second["rows"])
            self.assertEqual(len(first["rows"]), 200)
            serialized = json.dumps(first, ensure_ascii=False)
            self.assertNotIn("PRIVATE_BODY_", serialized)
            self.assertFalse(any("source_path" in row for row in first["rows"]))
            self.assertFalse(any("messages" in row for row in first["rows"]))
            self.assertTrue(first["selection"]["guard_auto_called"] is False)


if __name__ == "__main__":
    unittest.main()
