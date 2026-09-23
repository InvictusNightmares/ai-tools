import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import analyze
import rolling
import review_dashboard


class ReviewDashboard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = self.root / "tokyo"
        (self.store / "events" / "2026-09-20").mkdir(parents=True)
        self.analysis = self.root / "analysis"
        self.db_path = self.analysis / "index.sqlite"
        self.event_id = "evt-1"
        self._write_event()
        db = analyze.connect(self.db_path)
        try:
            rolling.setup(db)
            event, digest = rolling.read_record(self.event_path)
            analyze.ingest(db, event)
            db.execute(
                "INSERT INTO review_jobs(region,event_id,source_path,sha,at,state) VALUES(?,?,?,?,?,?)",
                ("tokyo", self.event_id, str(self.event_path), digest, event["at"], "complete"),
            )
            db.execute(
                """INSERT INTO semantic_reviews
                (region,event_id,source_path,source_sha,plane,state,guard_state,guard_decision,
                 guard_risk_level,guard_categories,guard_reason_codes,guard_http_status,
                 auto_state,auto_model,auto_effort,auto_action,auto_reason,auto_classification,
                 auto_http_status,attempts,error_code,reviewed_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("tokyo", self.event_id, str(self.event_path), digest, "offline_analysis", "complete",
                 "complete", "allow", "low", '["safe"]', '["none"]', 200, "complete",
                 "deepseek-flash", "medium", "route", "routine", '{"task":"simple"}', 200,
                 1, None, event["at"]),
            )
            db.commit()
        finally:
            db.close()
        (self.analysis / "tick.json").write_text(json.dumps({
            "run_id": "20260920-120000", "at": "2026-09-20T12:00:00+00:00", "status": "ok",
            "scanned": 1, "review_jobs_added": 1, "semantic_reviewed": 1,
        }))
        (self.analysis / "diagnostic-200.json").write_text(json.dumps({
            "schema": "work-observation-diagnostic-v1",
            "set_id": "diagnostic-200-test",
            "created_at": "2026-09-20T12:00:00+00:00",
            "counts": {"total": 1, "by_region": {"tokyo": 1}, "by_bucket": {"normal_allow": 1}},
            "rows": [{
                "rank": 1, "region": "tokyo", "event_id": self.event_id,
                "selection_bucket": "normal_allow", "selection_reason": "测试",
                "features": {"message_count": 2, "flags": []},
            }],
        }), encoding="utf-8")
        self.store_api = review_dashboard.ReviewStore(
            self.db_path, self.analysis / "review-labels.sqlite", {"tokyo": self.store}
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _write_event(self):
        event = {
            "schema": "work-observation-v1", "content_policy": "literal_text_attachment_metadata",
            "id": self.event_id, "at": "2026-09-20T12:00:00+00:00", "region": "tokyo", "ingress": "4000",
            "kind": "http_exchange", "protocol": "responses", "outcome": "completed", "version": "fixture",
            "client": "codex", "request": {"model": "auto", "input": "PRIVATE_BODY_SHOULD_NOT_ENTER_INDEX"},
            "response": {"object": "response", "id": "resp-1", "model": "deepseek-flash",
                         "output": [{"role": "assistant", "content": "done"}]},
        }
        raw = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(raw.encode()).hexdigest()
        self.event_path = self.store / "events" / "2026-09-20" / f"{self.event_id}.json"
        self.event_path.write_text(json.dumps({"sha256": digest, "event": event}, ensure_ascii=False, separators=(",", ":")) + "\n")

    def test_store_exposes_gray_lane_and_keeps_body_out_of_index(self):
        summary = self.store_api.summary()
        self.assertEqual(summary["formal_lanes"], {"tokyo": "4000", "us": "4001"})
        self.assertEqual(summary["gray_lanes"], {"tokyo": "4004", "us": "4005"})
        self.assertEqual(summary["latest_run"]["run_id"], "20260920-120000")
        row = self.store_api.get_review("tokyo", self.event_id)
        self.assertEqual(row["formal_ingress"], "4000")
        self.assertEqual(row["gray_ingress"], "4004")
        self.assertEqual(row["guard"]["decision"], "allow")
        self.assertEqual(row["auto"]["model"], "deepseek-flash")
        self.assertIn("PRIVATE_BODY_SHOULD_NOT_ENTER_INDEX", row["messages"][0]["content"])
        with sqlite3.connect(self.db_path) as db:
            self.assertNotIn("PRIVATE_BODY_SHOULD_NOT_ENTER_INDEX", "".join(db.iterdump()))

    def test_label_round_trip_is_separate(self):
        updated = self.store_api.save_label("tokyo", self.event_id, {
            "status": "reviewed", "guard_label": "correct_allow", "auto_label": "good_choice",
            "notes": "人工确认", "reviewer": "local",
        })
        self.assertEqual(updated["human"]["guard_label"], "correct_allow")
        self.assertEqual(updated["human"]["auto_label"], "good_choice")
        self.assertEqual(self.store_api.summary()["human_labels"], 1)

    def test_review_views_are_separate_and_paginated(self):
        # The same source can be inspected through three operator questions:
        # Guard exceptions for humans, every attempted Auto result, and jobs
        # still waiting for the semantic worker.
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE semantic_reviews SET guard_decision='block' WHERE region='tokyo' AND event_id=?", (self.event_id,))
            db.commit()

        review = self.store_api.list_reviews(view="review", limit=1, offset=0)
        self.assertEqual(review["total"], 1)
        self.assertEqual(review["page"], 1)
        self.assertEqual(review["pages"], 1)
        self.assertEqual(review["start"], 1)
        self.assertEqual(review["end"], 1)
        self.assertEqual(review["reviews"][0]["guard"]["decision"], "block")
        self.assertEqual(review["reviews"][0]["auto"]["offline_status"], "selected")
        self.assertEqual(review["reviews"][0]["auto"]["online_status"], "not_run_guard_block")

        auto = self.store_api.list_reviews(view="auto", limit=1, offset=0, query="deepseek-flash")
        self.assertEqual(auto["total"], 1)
        self.assertEqual(auto["reviews"][0]["auto"]["model"], "deepseek-flash")
        self.assertEqual(auto["reviews"][0]["auto"]["offline_label"], "离线已选模型")

        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE review_jobs SET state='pending' WHERE region='tokyo' AND event_id=?", (self.event_id,))
            db.commit()
        backlog = self.store_api.list_reviews(view="backlog", limit=1, offset=0)
        self.assertEqual(backlog["total"], 1)
        self.assertEqual(backlog["reviews"][0]["status"], "pending")

    def test_technical_results_are_separate_from_guard_review_and_auto_selection(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE semantic_reviews SET guard_state='unavailable', guard_decision=NULL, auto_state='unavailable', auto_model=NULL WHERE region='tokyo' AND event_id=?", (self.event_id,))
            db.commit()

        self.assertEqual(self.store_api.list_reviews(view="review")["total"], 0)
        self.assertEqual(self.store_api.list_reviews(view="auto")["total"], 0)
        technical = self.store_api.list_reviews(view="technical")
        self.assertEqual(technical["total"], 1)
        row = technical["reviews"][0]
        self.assertTrue(row["analysis"]["technical_issue"])
        self.assertEqual(row["auto"]["offline_status"], "technical_failure")
        self.assertEqual(row["production"]["auto"], "not_run_guard_unavailable")
        summary = self.store_api.summary()
        self.assertEqual(summary["guard_review_total"], 0)
        self.assertEqual(summary["technical_total"], 1)

    def test_guard_allow_stays_out_of_review_but_in_auto_and_capture_time_is_stable(self):
        # Guard allow is intentionally excluded from the human exception queue,
        # while the Auto overview still includes the same attempted result.
        review = self.store_api.list_reviews(view="review")
        self.assertEqual(review["total"], 0)
        auto = self.store_api.list_reviews(view="auto")
        self.assertEqual(auto["total"], 1)
        self.assertEqual(auto["reviews"][0]["guard"]["decision"], "allow")
        self.assertEqual(auto["reviews"][0]["at"], "2026-09-20T12:00:00+00:00")

        # A later semantic write must not move the row to another page by
        # changing its original capture ordering key.
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE semantic_reviews SET reviewed_at=? WHERE region=? AND event_id=?",
                ("2026-09-21T12:00:00+00:00", "tokyo", self.event_id),
            )
            db.commit()
        stable = self.store_api.list_reviews(view="auto")
        self.assertEqual(stable["reviews"][0]["at"], "2026-09-20T12:00:00+00:00")

    def test_review_queue_removes_processed_blocks_but_can_show_them_explicitly(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE semantic_reviews SET guard_decision='block' WHERE region='tokyo' AND event_id=?",
                (self.event_id,),
            )
            db.commit()

        self.assertEqual(self.store_api.list_reviews(view="review")["total"], 1)
        self.store_api.save_label("tokyo", self.event_id, {
            "status": "reviewed",
            "guard_label": "correct_block",
            "auto_label": "good_choice",
            "notes": "已复核",
        })

        # The default queue is work still requiring a human decision.  A
        # reviewer can opt into the historical, already processed blocks.
        self.assertEqual(self.store_api.list_reviews(view="review")["total"], 0)
        reviewed = self.store_api.list_reviews(view="review", human_status="reviewed")
        self.assertEqual(reviewed["total"], 1)
        self.assertEqual(reviewed["reviews"][0]["human_status"], "reviewed")
        self.assertEqual(self.store_api.summary()["guard_block_total"], 1)
        self.assertEqual(self.store_api.summary()["guard_review_total"], 0)

    def test_invalid_view_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store_api.list_reviews(view="everything")
        with self.assertRaises(ValueError):
            self.store_api.list_reviews(view="review", human_status="broken")

    def test_diagnostic_view_is_manifest_scoped_and_body_free(self):
        result = self.store_api.list_reviews(view="diagnostic", limit=1, page=1)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["diagnostic_set"]["set_id"], "diagnostic-200-test")
        row = result["reviews"][0]
        self.assertEqual(row["diagnostic"]["selection_bucket"], "normal_allow")
        self.assertNotIn("source_path", row["diagnostic"])
        self.assertNotIn("PRIVATE_BODY_SHOULD_NOT_ENTER_INDEX", json.dumps(row["diagnostic"]))
        summary = self.store_api.summary()
        self.assertTrue(summary["diagnostic_set"]["available"])
        html = (ROOT / "review" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-view="diagnostic"', html)
        self.assertIn('view-count-diagnostic', html)

    def test_http_surface_is_standalone_and_has_no_login(self):
        static_root = ROOT / "review"
        try:
            server = review_dashboard.ThreadingHTTPServer(("127.0.0.1", 0), review_dashboard.DashboardHandler)
        except PermissionError:
            self.skipTest("sandbox disallows local listener; API store tests still cover the data path")
        server.review_store = self.store_api
        server.static_root = static_root
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(base + "/api/health") as response:
                self.assertEqual(response.status, 200)
            with urlopen(base + "/healthz") as response:
                self.assertEqual(response.status, 200)
            with urlopen(base + "/api/summary") as response:
                payload = json.load(response)
                self.assertEqual(payload["gray_lanes"]["us"], "4005")
            with urlopen(base + f"/api/reviews?view=auto&limit=1&page=1&q=deepseek-flash") as response:
                payload = json.load(response)
                self.assertEqual(payload["view"], "auto")
                self.assertEqual(payload["total"], 1)
                self.assertEqual(payload["page"], 1)
                self.assertEqual(payload["pages"], 1)
            with urlopen(base + "/api/reviews?view=review&human_status=all&limit=1&page=1") as response:
                payload = json.load(response)
                self.assertEqual(payload["human_status"], "all")
            with urlopen(base + "/") as response:
                self.assertIn("Auto", response.read().decode("utf-8"))
            request = Request(base + f"/api/reviews/tokyo/{self.event_id}/label", data=json.dumps({
                "status": "reviewed", "guard_label": "uncertain", "auto_label": "uncertain",
                "notes": "HTTP label", "reviewer": "local",
            }).encode(), headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request) as response:
                self.assertEqual(response.status, 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_review_page_has_explicit_human_filter_and_page_jump_controls(self):
        html = (ROOT / "review" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "review" / "app.js").read_text(encoding="utf-8")
        for element_id in ("human-status-filter", "page-first", "page-last", "page-input", "page-go", "page-size"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn("human_status", js)
        self.assertIn("clearSelection()", js)
        self.assertIn("保存并下一条", js + html)
        self.assertIn("selectNeighbor", js)


if __name__ == "__main__":
    unittest.main()
