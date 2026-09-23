import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import threading
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
        event, source_digest = rolling.read_record(self.store / 'events' / '2026-09-17' / 'r1.json')
        guard = semantic.guard_payload(event)
        self.assertEqual(guard['messages'][0]['role'], 'user')
        self.assertIn('read the changed file', guard['messages'][0]['content'])
        self.assertTrue(any(item['role'] == 'assistant' for item in guard['messages']))
        self.assertEqual([call.args[0] for call in mock_post.call_args_list], [self.config['semantic']['guard_url'], self.config['semantic']['auto_url']])

    def test_bounded_semantic_batch_continues_on_next_timer_tick(self):
        for identity in ('r1', 'r2', 'r3'):
            self.record(identity)
        self.config['semantic']['max_jobs'] = 2

        def post(url, payload, timeout):
            if url.endswith('/guard'):
                return 200, {'decision': 'allow', 'risk_level': 'low'}
            return 200, {'effective_model': 'deepseek-flash', 'classification': {}}

        with patch.object(semantic, '_post', side_effect=post):
            first = rolling.tick(self.config, self.now)
            second = rolling.tick(self.config, self.now + timedelta(minutes=5))

        self.assertEqual(first['semantic_processed'], 2)
        self.assertEqual(first['semantic_complete'], 2)
        self.assertEqual(first['semantic_pending'], 1)
        self.assertEqual(second['semantic_processed'], 1)
        self.assertEqual(second['semantic_complete'], 1)
        self.assertEqual(second['semantic_pending'], 0)

    def test_job_workers_overlap_without_parallel_sqlite_writes(self):
        for identity in ('r1', 'r2', 'r3', 'r4'):
            self.record(identity)
        self.config['semantic']['max_jobs'] = 4
        self.config['semantic']['max_workers'] = 2
        lock = threading.Lock()
        barrier = threading.Barrier(2)
        active = 0
        peak = 0
        barrier_broken = False

        def review(*args, **kwargs):
            nonlocal active, peak, barrier_broken
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                try:
                    barrier.wait(timeout=2)
                except threading.BrokenBarrierError:
                    barrier_broken = True
                    raise
                return {
                    'guard': {'state': 'complete', 'decision': 'allow', 'risk_level': 'low',
                              'categories': [], 'reason_codes': [], 'http_status': 200},
                    'auto': {'state': 'complete', 'model': 'deepseek-flash', 'effort': 'medium',
                             'action': 'route', 'reason': None, 'classification': {}, 'http_status': 200},
                    'state': 'complete',
                }
            finally:
                with lock:
                    active -= 1

        with patch.object(semantic, 'review_event', side_effect=review):
            result = rolling.tick(self.config, self.now)
        self.assertFalse(barrier_broken)
        self.assertGreaterEqual(peak, 2)
        self.assertLessEqual(peak, 2)
        self.assertEqual(result['semantic_processed'], 4)
        self.assertEqual(result['semantic_complete'], 4)
        self.assertEqual(result['semantic_pending'], 0)
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM review_jobs WHERE state='complete'").fetchone()[0], 4)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE state='complete'").fetchone()[0], 4)
        finally:
            db.close()

    def test_worker_exception_returns_retryable_pending_row(self):
        for identity in ('r1', 'r2'):
            self.record(identity)
        self.config['semantic']['max_jobs'] = 2
        self.config['semantic']['max_workers'] = 2
        with patch.object(semantic, 'review_event', side_effect=RuntimeError('should_not_leak')):
            result = rolling.tick(self.config, self.now)
        self.assertEqual(result['semantic_processed'], 2)
        self.assertEqual(result['semantic_complete'], 0)
        self.assertEqual(result['semantic_unavailable'], 2)
        self.assertEqual(result['semantic_pending'], 2)
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM review_jobs WHERE state='pending'").fetchone()[0], 2)
            rows = db.execute("SELECT state,guard_state,auto_state,error_code FROM semantic_reviews ORDER BY event_id").fetchall()
            self.assertEqual(rows, [('unavailable', 'unavailable', 'unavailable', 'semantic_worker_exception')] * 2)
        finally:
            db.close()

    def test_pending_jobs_interleave_regions(self):
        db = rolling.analyze.connect(self.analysis / 'fairness.sqlite')
        try:
            rolling.setup(db)
            for region in ('tokyo', 'us'):
                for index in range(3):
                    event = {
                        'schema': 'work-observation-v1',
                        'content_policy': 'literal_text_attachment_metadata',
                        'id': f'{region}-{index}',
                        'at': f'2026-09-17T10:0{index}:00+00:00',
                        'region': region, 'ingress': '4000' if region == 'tokyo' else '4001',
                        'kind': 'http_exchange', 'protocol': 'chat', 'outcome': 'completed',
                        'version': 'fixture', 'client': 'codex',
                        'request': {'messages': [{'role': 'user', 'content': 'x'}]},
                        'response': {},
                    }
                    rolling.analyze.ingest(db, event)
                    db.execute(
                        'INSERT INTO review_jobs(region,event_id,source_path,sha,at) VALUES(?,?,?,?,?)',
                        (region, event['id'], '/tmp/source', 'sha', event['at']),
                    )
            db.commit()
            rows = semantic._pending_jobs(db, 4)
            self.assertEqual([(row[0], row[1]) for row in rows], [
                ('tokyo', 'tokyo-0'), ('us', 'us-0'), ('tokyo', 'tokyo-1'), ('us', 'us-1'),
            ])
        finally:
            db.close()

    def test_pending_jobs_prioritize_single_stage_retry_without_starving_new_work(self):
        db = rolling.analyze.connect(self.analysis / 'retry-priority.sqlite')
        try:
            rolling.setup(db)
            for region in ('tokyo', 'us'):
                event = {
                    'schema': 'work-observation-v1',
                    'content_policy': 'literal_text_attachment_metadata',
                    'id': f'{region}-retry',
                    'at': '2026-09-17T10:00:00+00:00',
                    'region': region, 'ingress': '4000' if region == 'tokyo' else '4001',
                    'kind': 'http_exchange', 'protocol': 'chat', 'outcome': 'completed',
                    'version': 'fixture', 'client': 'codex',
                    'request': {'messages': [{'role': 'user', 'content': 'retry'}]},
                    'response': {},
                }
                rolling.analyze.ingest(db, event)
                db.execute(
                    'INSERT INTO review_jobs(region,event_id,source_path,sha,at,attempts) VALUES(?,?,?,?,?,?)',
                    (region, event['id'], '/tmp/source', 'sha', event['at'], 1),
                )
                db.execute('''INSERT INTO semantic_reviews
                    (region,event_id,source_path,source_sha,plane,state,guard_state,auto_state,reviewed_at)
                    VALUES(?,?,?,?,?,?,?,?,?)''',
                    (region, event['id'], '/tmp/source', 'sha', 'offline_analysis', 'unavailable',
                     'complete', 'unavailable', event['at']),
                )
                fresh = dict(event)
                fresh['id'] = f'{region}-fresh'
                fresh['at'] = '2026-09-17T10:01:00+00:00'
                rolling.analyze.ingest(db, fresh)
                db.execute(
                    'INSERT INTO review_jobs(region,event_id,source_path,sha,at,attempts) VALUES(?,?,?,?,?,?)',
                    (region, fresh['id'], '/tmp/source', 'sha', fresh['at'], 0),
                )
            db.commit()
            rows = semantic._pending_jobs(db, 2)
            self.assertEqual([(row[0], row[1]) for row in rows], [
                ('tokyo', 'tokyo-retry'), ('us', 'us-retry'),
            ])
            db.execute("UPDATE review_jobs SET attempts=3 WHERE event_id LIKE '%retry'")
            db.commit()
            rows = semantic._pending_jobs(db, 2)
            self.assertEqual([(row[0], row[1]) for row in rows], [
                ('tokyo', 'tokyo-fresh'), ('us', 'us-fresh'),
            ])
        finally:
            db.close()

    def test_auto_payload_is_bounded_request_only_and_keeps_system_tail(self):
        old_marker = 'OLD_REQUEST_CONTEXT_SHOULD_BE_DROPPED'
        response_marker = 'RESPONSE_TRANSCRIPT_MUST_NOT_BE_REPLAYED'
        event = {
            'protocol': 'responses',
            'provider': 'openai',
            'request': {
                'instructions': 'SYSTEM_POLICY ' + ('s' * 2000),
                'input': [
                    {'role': 'user', 'content': f'{old_marker}-{index}-' + ('x' * (70 << 10))}
                    for index in range(16)
                ],
                'tools': [{
                    'type': 'function', 'name': 'large_tool',
                    'description': 'd' * (100 << 10),
                    'parameters': {'type': 'object', 'properties': {
                        'value': {'type': 'string', 'description': 'p' * (100 << 10)},
                    }},
                }],
            },
            'response': {'output': [{'type': 'message', 'content': response_marker}]},
        }
        payload = semantic.auto_payload(event)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        body = payload['body']

        self.assertEqual(payload['protocol'], 'responses')
        self.assertIn('input', body)
        self.assertIn('instructions', body)
        self.assertNotIn('messages', body)
        self.assertNotIn(response_marker, encoded)
        self.assertNotIn(f'{old_marker}-0-', encoded)
        self.assertIn(f'{old_marker}-15-', encoded)
        self.assertTrue(payload['metadata']['truncated'])
        self.assertEqual(payload['metadata']['source'], 'request')
        self.assertLessEqual(len(json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')),
                             semantic.AUTO_MAX_REPLAY_BYTES)
        # The compact tool schema stays structured JSON rather than becoming
        # an invalid string suffix after byte clipping.
        tool = body['tools'][0]
        self.assertIsInstance(tool['parameters'], dict)
        json.loads(json.dumps(body, ensure_ascii=False))

    def test_auto_payload_uses_protocol_native_envelopes_and_tool_shapes(self):
        cases = {
            'chat': ({
                'stream': True,
                'response_format': {'type': 'json_object'},
                'messages': [{'role': 'system', 'content': 'chat system'}, {'role': 'user', 'content': 'hello'}],
                'tools': [{'type': 'function', 'function': {'name': 'lookup', 'parameters': {'type': 'object'}}}],
            }, lambda body: self.assertIn('messages', body)),
            'responses': ({
                'stream': True,
                'text': {'format': {'type': 'json_schema', 'name': 'result', 'schema': {'type': 'object'}}},
                'instructions': 'responses system',
                'input': [{'role': 'user', 'content': 'hello'}],
                'tools': [{'type': 'function', 'name': 'lookup', 'parameters': {'type': 'object'}}],
            }, lambda body: self.assertIn('input', body)),
            'anthropic': ({
                'stream': True,
                'output_config': {'format': {'type': 'json_schema', 'schema': {'type': 'object'}}},
                'system': 'anthropic system',
                'messages': [{'role': 'user', 'content': 'hello'}],
                'tools': [{'name': 'lookup', 'input_schema': {'type': 'object'}}],
            }, lambda body: self.assertIn('messages', body)),
        }
        for protocol, (request, shape_assertion) in cases.items():
            with self.subTest(protocol=protocol):
                payload = semantic.auto_payload({
                    'protocol': protocol,
                    'request': request,
                    'response': {'output': 'RESPONSE_MUST_NOT_ENTER_NORMAL_REPLAY'},
                })
                shape_assertion(payload['body'])
                self.assertEqual(payload['protocol'], protocol)
                self.assertIs(payload['body']['stream'], True)
                self.assertIs(payload['stream_active'], True)
                self.assertNotIn('RESPONSE_MUST_NOT_ENTER_NORMAL_REPLAY', json.dumps(payload, ensure_ascii=False))
                json.loads(json.dumps(payload['body'], ensure_ascii=False))
                self.assertTrue(payload['body'].get('tools'))

        self.assertEqual(semantic.auto_payload({'protocol': 'chat', 'request': cases['chat'][0]})['body']['response_format']['type'], 'json_object')
        self.assertEqual(semantic.auto_payload({'protocol': 'responses', 'request': cases['responses'][0]})['body']['text']['format']['type'], 'json_schema')
        self.assertEqual(semantic.auto_payload({'protocol': 'anthropic', 'request': cases['anthropic'][0]})['body']['output_config']['format']['type'], 'json_schema')

        chat_tool = semantic.auto_payload({'protocol': 'chat', 'request': cases['chat'][0]})['body']['tools'][0]
        responses_tool = semantic.auto_payload({'protocol': 'responses', 'request': cases['responses'][0]})['body']['tools'][0]
        anthropic_tool = semantic.auto_payload({'protocol': 'anthropic', 'request': cases['anthropic'][0]})['body']['tools'][0]
        self.assertIn('function', chat_tool)
        self.assertIn('parameters', responses_tool)
        self.assertIn('input_schema', anthropic_tool)

    def test_auto_payload_marks_legacy_response_fallback_only_when_request_has_no_parts(self):
        payload = semantic.auto_payload({
            'protocol': 'other',
            'request': {},
            'response': {'output': [{'type': 'message', 'content': 'legacy response context'}]},
        })
        self.assertEqual(payload['metadata']['source'], 'event_messages_fallback')
        self.assertIn('legacy response context', json.dumps(payload, ensure_ascii=False))

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
            self.assertEqual(db.execute('SELECT state,guard_state,auto_state FROM semantic_reviews').fetchone(), ('unavailable', 'unavailable', 'not_run'))
            self.assertEqual(db.execute("SELECT state FROM review_jobs").fetchone()[0], 'pending')
        finally:
            db.close()

    def test_block_is_recorded_as_a_terminal_offline_observation(self):
        self.record()
        calls = []
        def post(url, payload, timeout):
            calls.append(url)
            if url.endswith('/guard'):
                return 200, {'decision': 'block', 'risk_level': 'medium', 'categories': ['Controversial'], 'reason_codes': ['synthetic_review']}
            self.fail('Auto must not run after a Guard block')
        with patch.object(semantic, '_post', side_effect=post):
            result = rolling.tick(self.config, self.now)
        self.assertEqual(result['semantic_review'], 'complete_local')
        self.assertEqual(calls, [self.config['semantic']['guard_url']])
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            self.assertEqual(db.execute('SELECT state,guard_decision,auto_state FROM semantic_reviews').fetchone(), ('complete', 'block', 'not_run'))
        finally:
            db.close()

    def test_guard_unavailable_does_not_run_auto(self):
        self.record()
        calls = []

        def post(url, payload, timeout):
            calls.append(url)
            if url.endswith('/guard'):
                return 503, {'error': 'preflight_unavailable'}
            self.fail('Auto must not run when Guard has no conclusion')

        with patch.object(semantic, '_post', side_effect=post):
            result = rolling.tick(self.config, self.now)
        self.assertEqual(result['semantic_review'], 'pending_local_worker')
        self.assertEqual(calls, [self.config['semantic']['guard_url']])
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            self.assertEqual(db.execute('SELECT state,guard_state,guard_decision,auto_state FROM semantic_reviews').fetchone(),
                             ('unavailable', 'unavailable', None, 'not_run'))
        finally:
            db.close()

    def test_retry_limit_moves_unavailable_job_to_deferred(self):
        self.record()
        self.config['semantic']['max_attempts'] = 2
        with patch.object(semantic, '_post', side_effect=OSError('synthetic_down')):
            first = rolling.tick(self.config, self.now)
            second = rolling.tick(self.config, self.now + timedelta(minutes=5))
        self.assertEqual(first['semantic_unavailable'], 1)
        self.assertEqual(first['semantic_deferred'], 0)
        self.assertEqual(second['semantic_unavailable'], 1)
        self.assertEqual(second['semantic_deferred'], 1)
        self.assertEqual(second['semantic_pending'], 0)
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            self.assertEqual(db.execute('SELECT state,attempts,last_error FROM review_jobs').fetchone(),
                             ('deferred', 2, 'retry_limit_exceeded'))
        finally:
            db.close()

    def test_previously_exhausted_pending_jobs_are_reported_as_deferred(self):
        self.record()
        with patch.object(semantic, '_post', side_effect=OSError('synthetic_down')):
            rolling.tick(self.config, self.now)
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            db.execute("UPDATE review_jobs SET attempts=3 WHERE state='pending'")
            db.commit()
        finally:
            db.close()
        result = rolling.tick(self.config, self.now + timedelta(minutes=5))
        self.assertEqual(result['semantic_deferred'], 1)
        self.assertEqual(result['semantic_pending'], 0)
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            self.assertEqual(db.execute('SELECT state,last_error FROM review_jobs').fetchone(),
                             ('deferred', 'retry_limit_exceeded'))
        finally:
            db.close()

    def test_retry_reuses_fresh_guard_result_when_auto_was_unavailable(self):
        self.record()
        calls = []

        def post(url, payload, timeout, *args):
            calls.append(url)
            if url.endswith('/guard'):
                return 200, {'decision': 'allow', 'risk_level': 'low', 'reason_codes': ['first_pass']}
            if calls.count(self.config['semantic']['auto_url']) == 1:
                raise OSError('synthetic_auto_down')
            return 200, {'effective_model': 'deepseek-flash', 'classification': {'Intent': 'coding'}}

        with patch.object(semantic, '_post', side_effect=post):
            first = rolling.tick(self.config, self.now)
            second = rolling.tick(self.config, self.now + timedelta(minutes=5))
        self.assertEqual(first['semantic_unavailable'], 1)
        self.assertEqual(second['semantic_complete'], 1)
        self.assertEqual(second.get('semantic_guard_reused'), 1)
        self.assertEqual(calls, [self.config['semantic']['guard_url'], self.config['semantic']['auto_url'], self.config['semantic']['auto_url']])
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            row = db.execute('''SELECT guard_decision,auto_model,guard_reviewed_at,auto_reviewed_at,
                       guard_result_version,auto_result_version FROM semantic_reviews''').fetchone()
            self.assertEqual(row[0:2], ('allow', 'deepseek-flash'))
            self.assertEqual(row[2], self.now.isoformat())
            self.assertEqual(row[3], (self.now + timedelta(minutes=5)).isoformat())
            self.assertTrue(row[4].startswith(semantic.SEMANTIC_RESULT_VERSION + ':'))
            self.assertTrue(row[5].startswith(semantic.SEMANTIC_RESULT_VERSION + ':'))
        finally:
            db.close()

    def test_retry_does_not_run_auto_after_guard_later_blocks(self):
        self.record()
        calls = []

        def post(url, payload, timeout, *args):
            calls.append(url)
            if url.endswith('/guard') and calls.count(self.config['semantic']['guard_url']) == 1:
                raise OSError('synthetic_guard_down')
            if url.endswith('/guard'):
                return 200, {'decision': 'block', 'risk_level': 'medium'}
            return 200, {'effective_model': 'deepseek-flash', 'classification': {'Intent': 'coding'}}

        with patch.object(semantic, '_post', side_effect=post):
            first = rolling.tick(self.config, self.now)
            second = rolling.tick(self.config, self.now + timedelta(minutes=5))
        self.assertEqual(first['semantic_unavailable'], 1)
        self.assertEqual(second['semantic_complete'], 1)
        self.assertEqual(second.get('semantic_auto_reused') or 0, 0)
        self.assertEqual(calls, [self.config['semantic']['guard_url'], self.config['semantic']['guard_url']])
        db = rolling.analyze.connect(self.analysis / 'index.sqlite')
        try:
            row = db.execute('''SELECT guard_decision,auto_model,guard_reviewed_at,auto_reviewed_at,
                       guard_result_version,auto_result_version FROM semantic_reviews''').fetchone()
            self.assertEqual(row[0:2], ('block', None))
            self.assertEqual(row[2], (self.now + timedelta(minutes=5)).isoformat())
            self.assertEqual(row[3], (self.now + timedelta(minutes=5)).isoformat())
        finally:
            db.close()

    def test_stage_reuse_expires_and_endpoint_change_invalidates_it(self):
        self.record()
        calls = []

        def post(url, payload, timeout, *args):
            calls.append(url)
            if url.endswith('/guard'):
                return 200, {'decision': 'allow', 'risk_level': 'low'}
            if calls.count(self.config['semantic']['auto_url']) == 1:
                raise OSError('synthetic_auto_down')
            return 200, {'effective_model': 'deepseek-flash', 'classification': {}}

        with patch.object(semantic, '_post', side_effect=post):
            rolling.tick(self.config, self.now)
            # The one-hour default is deliberately exceeded, so both stages
            # must be called again instead of treating the old Guard result as
            # a current policy conclusion.
            rolling.tick(self.config, self.now + timedelta(seconds=semantic.DEFAULT_STAGE_REUSE_TTL_SECONDS + 1))
        self.assertEqual(calls, [self.config['semantic']['guard_url'], self.config['semantic']['auto_url'],
                                 self.config['semantic']['guard_url'], self.config['semantic']['auto_url']])

        # A changed private endpoint has a different stage version even inside
        # the TTL.  This prevents a preview replacement from inheriting a
        # result produced by the previous endpoint.  Exercise this directly
        # with metadata-only prior state so it does not depend on queue timing.
        event, source_digest = rolling.read_record(self.store / 'events' / '2026-09-17' / 'r1.json')
        old_guard = self.config['semantic']['guard_url']
        auto_url = self.config['semantic']['auto_url']
        prior = {
            'source_sha': source_digest,
            'guard_state': 'complete', 'guard_decision': 'allow', 'guard_risk_level': 'low',
            'guard_categories': '[]', 'guard_reason_codes': '[]', 'guard_http_status': 200,
            'auto_state': 'complete', 'auto_model': 'deepseek-flash', 'auto_effort': 'medium',
            'auto_action': 'route', 'auto_reason': None, 'auto_classification': '{}',
            'auto_http_status': 200, 'guard_reviewed_at': self.now.isoformat(),
            'auto_reviewed_at': self.now.isoformat(),
            'guard_result_version': semantic._stage_result_version('guard', old_guard),
            'auto_result_version': semantic._stage_result_version('auto', auto_url),
        }
        changed_guard = 'http://127.0.0.1:8011/guard-v2'
        direct_calls = []

        def direct_post(url, payload, timeout, *args):
            direct_calls.append(url)
            return 200, ({'decision': 'block', 'risk_level': 'medium'} if 'guard' in url
                         else {'effective_model': 'deepseek-flash', 'classification': {}})

        with patch.object(semantic, '_post', side_effect=direct_post):
            semantic.review_event(event, changed_guard, auto_url, 2, prior=prior,
                                  source_sha=prior['source_sha'], now=self.now + timedelta(minutes=5))
        self.assertEqual(direct_calls, [changed_guard])

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
