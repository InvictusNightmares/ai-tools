import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
import rolling
import semantic


class Semantic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = self.root / 'store'
        (self.store / 'events' / '2026-09-17').mkdir(parents=True)
        self.analysis = self.root / 'analysis'
        self.now = datetime(2026, 9, 17, 10, tzinfo=timezone.utc)
        (self.store / 'status.json').write_text(json.dumps({'started_at': 'fixture', 'updated_at': self.now.isoformat(), 'capture_enabled': True}))
        self.config = {'analysis_dir': str(self.analysis), 'analysis_bytes': 2 << 30, 'max_events': 100,
            'max_seconds': 20, 'review_queue_limit': 100, 'stores': [{'store_dir': str(self.store),
            'status_file': str(self.store / 'status.json'), 'region': 'tokyo', 'ingress': '4000'}],
            'semantic': {'enabled': True, 'guard_url': 'http://127.0.0.1:8011/guard',
                         'auto_url': 'http://127.0.0.1:8011/auto', 'timeout_seconds': 2, 'max_jobs': 20}}

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, identity='r1'):
        event = {'schema': 'work-observation-v1', 'content_policy': 'literal_text_attachment_metadata', 'id': identity,
                 'at': self.now.isoformat(), 'region': 'tokyo', 'ingress': '4000', 'kind': 'http_exchange',
                 'protocol': 'responses', 'outcome': 'completed', 'version': 'fixture', 'client': 'codex',
                 'user_agent': 'codex-cli/0.154.0 fixture',
                 'request': {'model': 'auto', 'input': [{'role': 'user', 'content': 'read the changed file and summarize it'}]},
                 'response': {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'The file changed two lines.'}]}]}}
        raw = json.dumps(event, separators=(',', ':'))
        path = self.store / 'events' / '2026-09-17' / (identity + '.json')
        path.write_text('{"sha256":"' + hashlib.sha256(raw.encode()).hexdigest() + '","event":' + raw + '}\n')

    def test_local_worker_records_both_decisions_without_body_copy(self):
        self.record()
        def post(url, payload, timeout):
            if url.endswith('/guard'):
                self.assertEqual(payload['metadata']['plane'], 'offline_analysis')
                return 200, {'decision': 'allow', 'risk_level': 'low', 'categories': [], 'reason_codes': ['synthetic_allow']}
            self.assertEqual(payload['model'], 'auto')
            return 200, {'object': 'auto.route', 'effective_model': 'deepseek-v4-pro', 'effective_reasoning_effort': 'medium',
                          'action': 'route', 'reason': 'synthetic_route', 'classification': {'Intent': 'coding'}}
        with patch.object(semantic, '_post', side_effect=post) as mock_post:
            result = rolling.tick(self.config, self.now)
        self.assertEqual(result['semantic_review'], 'complete_local')
        self.assertEqual(result['review_pending'], 0)
        self.assertEqual(result['semantic_reviewed'], 1)
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            row = db.execute('SELECT state,plane,guard_decision,auto_model,auto_state,auto_classification FROM semantic_reviews').fetchone()
            self.assertEqual(row[:5], ('complete', 'offline_analysis', 'allow', 'deepseek-v4-pro', 'complete'))
            self.assertIn('coding', row[5])
            self.assertNotIn('read the changed file', ''.join(db.iterdump()))
        finally:
            db.close()
        # Rebuild the input independently to assert both request and response
        # roles without retaining a copy of the body in the analysis DB.
        event, _ = rolling.read_record(self.store / 'events' / '2026-09-17' / 'r1.json')
        guard = semantic.guard_payload(event)
        self.assertEqual(guard['messages'][0]['role'], 'user')
        self.assertIn('read the changed file', guard['messages'][0]['content'])
        self.assertTrue(any(item['role'] == 'assistant' for item in guard['messages']))
        self.assertEqual([call.args[0] for call in mock_post.call_args_list], [self.config['semantic']['guard_url'], self.config['semantic']['auto_url']])

    def test_endpoint_must_be_private(self):
        with self.assertRaises(ValueError):
            semantic._local_url('https://example.com/guard')

    def test_auth_file_is_sent_only_as_header(self):
        self.record()
        token = self.root / 'offline-auto.token'
        token.write_text('synthetic-review-token\n')
        token.chmod(0o600)
        self.config['semantic']['auto_auth_file'] = str(token)
        seen = []
        def post(url, payload, timeout, headers=None):
            seen.append((url, headers or {}))
            if url.endswith('/guard'):
                return 200, {'decision': 'allow', 'risk_level': 'low'}
            return 200, {'effective_model': 'deepseek-v4-pro', 'classification': {}}
        with patch.object(semantic, '_post', side_effect=post):
            result = rolling.tick(self.config, self.now)
        self.assertEqual(result['semantic_review'], 'complete_local')
        self.assertEqual(seen[0][1], {})
        self.assertEqual(seen[1][1], {'Authorization': 'Bearer synthetic-review-token', 'User-Agent': 'codex-cli/0.154.0 fixture'})

    def test_region_specific_endpoints_do_not_fall_back(self):
        self.record()
        self.config['semantic']['regions'] = {
            'tokyo': {
                'guard_url': 'http://127.0.0.1:8013/tokyo-guard',
                'auto_url': 'http://127.0.0.1:8095/tokyo-auto',
            },
        }
        seen = []
        def post(url, payload, timeout, headers=None):
            seen.append(url)
            if url.endswith('guard'):
                return 200, {'decision': 'allow', 'risk_level': 'low'}
            return 200, {'effective_model': 'deepseek-flash', 'classification': {}}
        with patch.object(semantic, '_post', side_effect=post):
            result = rolling.tick(self.config, self.now)
        self.assertEqual(result['semantic_review'], 'complete_local')
        self.assertEqual(seen, [self.config['semantic']['regions']['tokyo']['guard_url'], self.config['semantic']['regions']['tokyo']['auto_url']])

    def test_unconfigured_region_stays_pending_without_cross_region_call(self):
        self.record()
        self.config['semantic']['regions'] = {
            'us': {
                'guard_url': 'http://127.0.0.1:8014/us-guard',
                'auto_url': 'http://127.0.0.1:8096/us-auto',
            },
        }
        with patch.object(semantic, '_post') as post:
            result = rolling.tick(self.config, self.now)
        self.assertEqual(result['semantic_review'], 'pending_local_worker')
        self.assertEqual(result['review_pending'], 1)
        post.assert_not_called()

    def test_invalid_auth_file_keeps_queue_pending(self):
        self.record()
        token = self.root / 'offline-auto.token'
        token.write_text('too-open')
        token.chmod(0o644)
        self.config['semantic']['auto_auth_file'] = str(token)
        result = rolling.tick(self.config, self.now)
        self.assertEqual(result['semantic_review'], 'pending_local_worker')
        self.assertEqual(result['review_pending'], 1)
        self.assertEqual(result['semantic_auth_error'], 'semantic_auth_unavailable')

    def test_unavailable_is_retryable_and_does_not_claim_complete(self):
        self.record()
        with patch.object(semantic, '_post', side_effect=OSError('synthetic_down')):
            result = rolling.tick(self.config, self.now)
        self.assertEqual(result['semantic_review'], 'pending_local_worker')
        self.assertEqual(result['review_pending'], 1)
        self.assertFalse(result['complete_analysis_claim'])
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            self.assertEqual(db.execute('SELECT state,guard_state,auto_state FROM semantic_reviews').fetchone(), ('unavailable', 'unavailable', 'unavailable'))
            self.assertEqual(db.execute("SELECT state FROM review_jobs").fetchone()[0], 'pending')
        finally:
            db.close()

    def test_block_is_recorded_as_a_terminal_offline_observation(self):
        self.record()
        def post(url, payload, timeout):
            if url.endswith('/guard'):
                return 200, {'decision': 'block', 'risk_level': 'medium', 'categories': ['Controversial'], 'reason_codes': ['synthetic_review']}
            return 403, {'error': 'preflight_blocked'}
        with patch.object(semantic, '_post', side_effect=post):
            result = rolling.tick(self.config, self.now)
        self.assertEqual(result['semantic_review'], 'complete_local')
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            self.assertEqual(db.execute('SELECT state,guard_decision,auto_state FROM semantic_reviews').fetchone(), ('complete', 'block', 'blocked'))
        finally:
            db.close()

    def test_stale_running_claim_is_requeued(self):
        self.record()
        with patch.object(semantic, '_post', side_effect=OSError('synthetic_down')):
            first = rolling.tick(self.config, self.now)
        self.assertEqual(first['review_pending'], 1)
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            db.execute("UPDATE review_jobs SET state='running',claimed_at=?", ('2026-09-17T00:00:00+00:00',))
            db.commit()
        finally:
            db.close()
        def post(url, payload, timeout):
            if url.endswith('/guard'):
                return 200, {'decision': 'allow', 'risk_level': 'low'}
            return 200, {'effective_model': 'deepseek-v4-pro', 'classification': {}}
        with patch.object(semantic, '_post', side_effect=post):
            recovered = rolling.tick(self.config, self.now)
        self.assertEqual(recovered['review_pending'], 0)
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            self.assertEqual(db.execute('SELECT state,attempts,last_error FROM review_jobs').fetchone(), ('complete', 2, None))
        finally:
            db.close()

    def test_semantic_metadata_follows_thirty_day_retention(self):
        self.record()
        def post(url, payload, timeout):
            if url.endswith('/guard'):
                return 200, {'decision': 'allow', 'risk_level': 'low'}
            return 200, {'effective_model': 'deepseek-v4-pro', 'classification': {}}
        with patch.object(semantic, '_post', side_effect=post):
            rolling.tick(self.config, self.now)
        expired = rolling.tick(self.config, self.now + timedelta(days=30), force=True)
        self.assertEqual(expired['pruned']['semantic_reviews'], 1)
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM semantic_reviews').fetchone()[0], 0)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
