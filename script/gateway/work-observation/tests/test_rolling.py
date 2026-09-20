import fcntl
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
import rolling as r


class Rolling(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = self.root / 'store'
        self.store.mkdir()
        (self.store / 'events').mkdir()
        self.analysis = self.root / 'analysis'
        self.now = datetime(2026, 9, 17, 10, tzinfo=timezone.utc)
        self.config = {'analysis_dir': str(self.analysis), 'analysis_bytes': 2 << 30,
            'max_events': 100, 'max_seconds': 20, 'review_queue_limit': 100,
            'stores': [{'store_dir': str(self.store), 'status_file': str(self.store / 'status.json'), 'region': 'tokyo', 'ingress': '4000'}]}
        self.status()

    def tearDown(self):
        self.tmp.cleanup()

    def status(self):
        (self.store / 'status.json').write_text(json.dumps({'started_at': 'fixture',
            'updated_at': self.now.isoformat(), 'capture_enabled': True}))

    def record(self, identity='r1', **overrides):
        event = {'schema': 'work-observation-v1', 'content_policy': 'literal_text_attachment_metadata',
            'id': identity, 'at': self.now.isoformat(), 'region': 'tokyo', 'ingress': '4000',
            'kind': 'http_exchange', 'protocol': 'responses', 'outcome': 'completed', 'version': 'fixture',
            'client': 'codex', 'request': {'model': 'synthetic', 'input': 'RAW_BODY_NOT_IN_METADATA_DB'}}
        event.update(overrides)
        raw = json.dumps(event, separators=(',', ':'))
        text = '{"sha256":"' + hashlib.sha256(raw.encode()).hexdigest() + '","event":' + raw + '}\n'
        path = self.store / 'events' / event['at'][:10] / (identity + '.json')
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
        return path

    def db(self):
        return r.analyze.connect(self.analysis / 'index.sqlite')

    def test_incremental_idempotent_no_body_copies_and_unknown_quality(self):
        self.record()
        first = r.tick(self.config, self.now)
        second = r.tick(self.config, self.now, force=True)
        self.assertEqual(first['review_pending'], 1)
        self.assertEqual(second['recent']['events'], 1)
        self.assertEqual(second['recent']['evidence_quality'], {'unknown': 1})
        self.assertEqual(second['recent']['cost_unknown_events'], 1)
        self.assertEqual(second['body_copies_created'], 0)
        db = self.db()
        try:
            self.assertNotIn('RAW_BODY_NOT_IN_METADATA_DB', ''.join(db.iterdump()))
        finally:
            db.close()

    def test_late_written_earlier_event_not_skipped_by_time_watermark(self):
        self.record()
        r.tick(self.config, self.now)
        self.record('late', at=(self.now - timedelta(hours=2)).isoformat())
        result = r.tick(self.config, self.now + timedelta(hours=1), force=True)
        self.assertEqual(result['review_pending'], 2)
        db = self.db()
        try:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 2)
        finally:
            db.close()

    def test_corrupt_record_visible_and_corrected_record_retried(self):
        path = self.record()
        original = path.read_text()
        path.write_text(original.replace('synthetic', 'tampered'))
        result = r.tick(self.config, self.now)
        self.assertEqual(result['invalid_sources'], 1)
        self.assertEqual(result['review_pending'], 0)
        self.assertEqual(result['status'], 'degraded')
        path.write_text(original)
        fixed = r.tick(self.config, self.now, force=True)
        self.assertEqual(fixed['invalid_sources'], 0)
        self.assertEqual(fixed['review_pending'], 1)

    def test_forged_ingress_or_simulation_not_actuals(self):
        self.record('spoofed', ingress='4001')
        self.record('simulated', plane='simulation')
        result = r.tick(self.config, self.now)
        self.assertEqual(result['invalid_sources'], 2)
        self.assertEqual(result['recent']['events'], 0)

    def test_bounded_queue_deferred_without_losing_source_references(self):
        self.config['review_queue_limit'] = 1
        self.record('a')
        self.record('b')
        result = r.tick(self.config, self.now)
        self.assertEqual(result['review_pending'], 1)
        self.assertEqual(result['review_deferred'], 1)
        db = self.db()
        try:
            db.execute("UPDATE review_jobs SET state='complete'")
            db.commit()
        finally:
            db.close()
        result = r.tick(self.config, self.now, force=True)
        self.assertEqual(result['review_pending'], 1)
        self.assertEqual(result['review_deferred'], 0)

    def test_budget_catchup_next_tick_and_expiry(self):
        self.config['max_events'] = 1
        self.record('a')
        self.record('b')
        one = r.tick(self.config, self.now)
        two = r.tick(self.config, self.now + timedelta(minutes=5))
        self.assertEqual(one['review_pending'], 1)
        self.assertEqual(two['review_pending'], 2)
        expired = r.tick(self.config, self.now + timedelta(days=30), force=True)
        self.assertEqual(expired['review_pending'], 0)
        self.assertEqual(expired['pruned']['events'], 2)

    def test_hourly_daily_cadence_and_concurrent_worker_lock(self):
        self.record()
        r.tick(self.config, self.now)
        second = r.tick(self.config, self.now + timedelta(minutes=5))
        self.assertNotIn('incremental', second)
        with (self.analysis / 'worker.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(r.tick(self.config, self.now)['status'], 'already_running')

    def test_time_bounded_scan_resumes_past_known_prefix_and_revisits_late_files(self):
        for n in range(9):self.record(f'known{n}')
        r.tick(self.config,self.now)
        self.record('new-tail')
        db=self.db()
        try:
            # Force four entries per tick, including already-indexed entries.
            for _ in range(5):
                with patch.object(r.time,'monotonic',side_effect=range(100)):
                    r.ingest_batch(db,self.config['stores'],self.now,100,5)
                db.commit()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],10)
            self.record('late-old-time',at=(self.now-timedelta(hours=2)).isoformat())
            for _ in range(8):
                with patch.object(r.time,'monotonic',side_effect=range(100)):
                    r.ingest_batch(db,self.config['stores'],self.now,100,5)
                db.commit()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],11)
        finally:db.close()

    def test_symlink_record_does_not_follow_external_file(self):
        target = self.root / 'unrelated'
        target.write_text('unrelated local content')
        part = self.store / 'events' / '2026-09-17'
        part.mkdir()
        (part / 'bad.json').symlink_to(target)
        result = r.tick(self.config, self.now)
        self.assertEqual(result['invalid_sources'], 1)
        self.assertEqual(target.read_text(), 'unrelated local content')


if __name__ == '__main__':
    unittest.main()
