#!/usr/bin/env python3
"""Run bounded, local-only Guard and Auto replay reviews.

The source event remains the actual production observation. Results written by
this module are explicitly offline analysis metadata: they never change the
captured outcome, routing, quarantine state, or any business/tool execution.
Only configured loopback/private HTTP endpoints are accepted. Request and
response bodies are read from the immutable source record for the replay call,
but are never copied into the analysis database or ordinary worker output.
"""
from collections import Counter
from datetime import datetime, timezone
import http.client
import ipaddress
import json
import os
from pathlib import Path
import socket
import stat
from urllib.parse import urlsplit


MAX_REPLAY_BODY = 8 << 20
MAX_MESSAGE_CHARS = 2 << 20
MAX_RESPONSE_BYTES = 1 << 20


def ensure_schema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS semantic_reviews (
            region TEXT NOT NULL, event_id TEXT NOT NULL, source_path TEXT NOT NULL,
            source_sha TEXT NOT NULL, plane TEXT NOT NULL DEFAULT 'offline_analysis',
            state TEXT NOT NULL, guard_state TEXT NOT NULL, guard_decision TEXT,
            guard_risk_level TEXT, guard_categories TEXT, guard_reason_codes TEXT,
            guard_http_status INTEGER, auto_state TEXT NOT NULL, auto_model TEXT,
            auto_effort TEXT, auto_action TEXT, auto_reason TEXT,
            auto_classification TEXT, auto_http_status INTEGER, attempts INTEGER NOT NULL DEFAULT 0,
            error_code TEXT, reviewed_at TEXT,
            PRIMARY KEY(region,event_id)
        );
        CREATE INDEX IF NOT EXISTS semantic_reviews_state ON semantic_reviews(state,reviewed_at);
    ''')
    columns = {row[1] for row in db.execute('PRAGMA table_info(review_jobs)')}
    for name, definition in (
        ('attempts', 'INTEGER NOT NULL DEFAULT 0'),
        ('claimed_at', 'TEXT'),
        ('last_error', 'TEXT'),
    ):
        if name not in columns:
            db.execute('ALTER TABLE review_jobs ADD COLUMN ' + name + ' ' + definition)


def _local_url(url):
    """Reject public endpoints so a config typo cannot export captured text."""
    if not isinstance(url, str) or not url:
        raise ValueError('semantic_endpoint_required')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('semantic_endpoint_must_be_private_http')
    host = parsed.hostname.lower().rstrip('.')
    if host == 'localhost':
        return parsed
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError('semantic_endpoint_host_must_be_private_ip')
    if not (address.is_private or address.is_loopback or address.is_link_local):
        raise ValueError('semantic_endpoint_host_must_be_private_ip')
    return parsed


def _auth_headers(path, header='Authorization'):
    """Read a dedicated offline-review token without putting it in config/DB."""
    if not path:
        return {}
    if header not in ('Authorization', 'X-API-Key'):
        raise ValueError('semantic_auth_header_invalid')
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError('semantic_auth_file_invalid')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise ValueError('semantic_auth_file_unavailable') from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size < 1 or info.st_size > 4096 or (stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError('semantic_auth_file_invalid')
        raw = os.read(fd, 4097).decode('utf-8').strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError('semantic_auth_file_invalid') from exc
    finally:
        os.close(fd)
    if not raw or '\r' in raw or '\n' in raw:
        raise ValueError('semantic_auth_file_invalid')
    if header == 'Authorization' and not raw.lower().startswith('bearer '):
        raw = 'Bearer ' + raw
    return {header: raw}


def _post(url, payload, timeout, headers=None):
    parsed = _local_url(url)
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    if len(body) > MAX_REPLAY_BODY:
        raise ValueError('semantic_replay_payload_too_large')
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    connection = http.client.HTTPSConnection(host, port, timeout=timeout) if parsed.scheme == 'https' else http.client.HTTPConnection(host, port, timeout=timeout)
    path = parsed.path or '/'
    if parsed.query:
        path += '?' + parsed.query
    try:
        request_headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if headers:
            request_headers.update(headers)
        connection.request('POST', path, body=body, headers=request_headers)
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        status = response.status
    finally:
        connection.close()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError('semantic_response_too_large')
    try:
        decoded = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        decoded = {}
    return status, decoded if isinstance(decoded, dict) else {}


def _text(value, limit=MAX_MESSAGE_CHARS):
    if isinstance(value, str):
        return value[:limit]
    if value is None:
        return ''
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    except (TypeError, ValueError):
        text = str(value)
    return text[:limit]


def _append_message(messages, role, value):
    if isinstance(value, list):
        for item in value:
            _append_message(messages, role, item)
        return
    if isinstance(value, dict):
        # Preserve text parts and tool results while avoiding a second copy of
        # the complete provider envelope in the Guard request.
        if isinstance(value.get('text'), str):
            messages.append({'role': role, 'content': value['text'][:MAX_MESSAGE_CHARS]})
            return
        if isinstance(value.get('content'), (str, list, dict)):
            _append_message(messages, value.get('role', role), value['content'])
            return
        if value.get('type') in ('function_call', 'tool_use', 'function_call_output', 'tool_result'):
            messages.append({'role': 'tool' if value['type'].endswith(('output', 'result')) else 'assistant', 'content': _text(value)})
            return
    text = _text(value)
    if text:
        messages.append({'role': role, 'content': text})


def _request_parts(request):
    messages = []
    if isinstance(request, dict) and request.get('type') == 'response.create' and isinstance(request.get('response'), dict):
        request = request['response']
    if isinstance(request, dict):
        if 'instructions' in request:
            _append_message(messages, 'system', request['instructions'])
        if 'system' in request:
            _append_message(messages, 'system', request['system'])
        if 'messages' in request:
            for item in request['messages'] if isinstance(request['messages'], list) else [request['messages']]:
                if isinstance(item, dict):
                    _append_message(messages, item.get('role', 'user'), item.get('content', item))
                else:
                    _append_message(messages, 'user', item)
        if 'input' in request:
            _append_message(messages, 'user', request['input'])
        if 'prompt' in request:
            _append_message(messages, 'user', request['prompt'])
        if not messages:
            _append_message(messages, 'user', request)
    elif request is not None:
        _append_message(messages, 'user', request)
    return messages


def _response_parts(response):
    messages = []
    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, dict):
            if value.get('_capture_transport') == 'sse':
                walk(value.get('data'))
                return
            if isinstance(value.get('response'), dict):
                walk(value['response'])
                return
            if isinstance(value.get('choices'), list):
                for choice in value['choices']:
                    if not isinstance(choice, dict):
                        continue
                    item = choice.get('message', choice.get('delta', choice.get('text')))
                    if isinstance(item, dict):
                        _append_message(messages, item.get('role', 'assistant'), item.get('content', item))
                    elif item is not None:
                        _append_message(messages, 'assistant', item)
                return
            if 'output' in value:
                _append_message(messages, 'assistant', value['output'])
                return
            if value.get('type') in ('error', 'response.failed', 'response.incomplete'):
                _append_message(messages, 'assistant', value)
                return
            if 'content' in value or 'message' in value:
                _append_message(messages, value.get('role', 'assistant'), value.get('content', value.get('message')))
    walk(response)
    return messages


def _event_messages(event):
    messages = _request_parts(event.get('request'))
    messages.extend(_response_parts(event.get('response')))
    return messages or [{'role': 'user', 'content': '[empty captured request]'}]


def _tools(request):
    if not isinstance(request, dict) or not isinstance(request.get('tools'), list):
        return []
    result = []
    for item in request['tools'][:32]:
        if isinstance(item, dict):
            function = item.get('function')
            name = item.get('name') or (function.get('name') if isinstance(function, dict) else None)
            result.append({'name': str(name or 'tool')[:256], 'schema': _text(item)[:MAX_MESSAGE_CHARS]})
    return result


def _request_body(event):
    request = event.get('request')
    if isinstance(request, (dict, list)):
        return request
    return {'messages': _event_messages(event)}


def guard_payload(event):
    request = event.get('request') if isinstance(event.get('request'), dict) else {}
    attachments = request.get('attachments', []) if isinstance(request, dict) else []
    if not isinstance(attachments, list):
        attachments = []
    return {
        'request_id': str(event.get('id', '')),
        'protocol': str(event.get('protocol', 'unknown')),
        'provider': str(event.get('provider', 'openai')),
        'model': str(event.get('model') or request.get('model') or 'auto')[:256],
        'region': str(event.get('region', '')),
        'session_hash': str(event.get('root_session_hash') or event.get('session_hash') or ''),
        'messages': _event_messages(event),
        'tools': _tools(request),
        'attachments': [item for item in attachments[:16] if isinstance(item, dict)],
        'metadata': {'plane': 'offline_analysis', 'ingress': str(event.get('ingress', '')), 'client': str(event.get('client', ''))},
    }


def auto_payload(event):
    request = event.get('request')
    return {
        'protocol': str(event.get('protocol', 'responses')),
        'provider': str(event.get('provider', 'openai')),
        # Route preview is the Auto policy surface. Always use its public
        # model name; the original requested model remains in the captured
        # body and is stripped by the same normalizer as a live request.
        'model': 'auto',
        'body': _request_body(event),
        'turn': 1,
        'new_task_epoch': False,
        'tool_loop': bool(_tools(request)),
        'hard_capability_failure': False,
        'stream_active': False,
        'session_id': str(event.get('root_session_hash') or event.get('session_hash') or ''),
    }


def _json_field(value):
    return json.dumps(value if isinstance(value, (list, dict)) else [], ensure_ascii=False, separators=(',', ':'))


def _guard_result(status, body):
    decision = body.get('decision') if isinstance(body.get('decision'), str) else None
    if status < 200 or status >= 300:
        return {'state': 'unavailable' if status in (502, 503, 504) else 'http_error', 'decision': decision,
                'risk_level': None, 'categories': [], 'reason_codes': [], 'http_status': status, 'error': body.get('error', 'guard_http_error')}
    if decision not in ('allow', 'block', 'unavailable'):
        return {'state': 'invalid', 'decision': None, 'risk_level': None, 'categories': [], 'reason_codes': [], 'http_status': status, 'error': 'invalid_guard_decision'}
    return {'state': 'complete', 'decision': decision, 'risk_level': body.get('risk_level'),
            'categories': body.get('categories', []) if isinstance(body.get('categories'), list) else [],
            'reason_codes': body.get('reason_codes', []) if isinstance(body.get('reason_codes'), list) else [], 'http_status': status}


def _auto_result(status, body):
    if status < 200 or status >= 300:
        return {'state': 'blocked' if status == 403 else ('unavailable' if status in (502, 503, 504) else 'http_error'), 'model': None, 'effort': None, 'action': None, 'reason': body.get('error'), 'classification': {}, 'http_status': status}
    model = body.get('effective_model')
    if not isinstance(model, str) or not model:
        return {'state': 'invalid', 'model': None, 'effort': None, 'action': None, 'reason': None, 'classification': {}, 'http_status': status}
    return {'state': 'complete', 'model': model[:256], 'effort': body.get('effective_reasoning_effort'), 'action': body.get('action'), 'reason': body.get('reason'), 'classification': body.get('classification', {}) if isinstance(body.get('classification'), dict) else {}, 'http_status': status}


def _event_headers(event, headers=None):
    """Preserve the observed client identity on an offline Auto replay.

    Credentials remain supplied separately by the restricted auth file; an
    event never supplies or reconstructs an Authorization header.
    """
    result = dict(headers or {})
    user_agent = event.get('user_agent')
    if isinstance(user_agent, str) and user_agent:
        result['User-Agent'] = user_agent[:512]
    return result


def review_event(event, guard_url, auto_url, timeout, guard_headers=None, auto_headers=None):
    result = {'guard': None, 'auto': None}
    try:
        if guard_headers:
            result['guard'] = _guard_result(*_post(guard_url, guard_payload(event), timeout, guard_headers))
        else:
            result['guard'] = _guard_result(*_post(guard_url, guard_payload(event), timeout))
    except (OSError, ValueError, socket.error, http.client.HTTPException) as exc:
        result['guard'] = {'state': 'unavailable', 'decision': None, 'risk_level': None, 'categories': [], 'reason_codes': [], 'http_status': None, 'error': type(exc).__name__}
    try:
        if auto_headers:
            result['auto'] = _auto_result(*_post(auto_url, auto_payload(event), timeout, _event_headers(event, auto_headers)))
        else:
            # Keep the no-auth call shape compatible with lightweight local
            # test doubles. Regional previews always use a dedicated auth
            # file, so the observed UA is attached on the real path above.
            result['auto'] = _auto_result(*_post(auto_url, auto_payload(event), timeout))
    except (OSError, ValueError, socket.error, http.client.HTTPException) as exc:
        result['auto'] = {'state': 'unavailable', 'model': None, 'effort': None, 'action': None, 'reason': None, 'classification': {}, 'http_status': None, 'error': type(exc).__name__}
    # A model/Guard block is a valid offline observation and must be retained
    # as complete analysis. Transport failure and an unavailable decision are
    # the only retryable states.
    guard_terminal = result['guard']['state'] == 'complete'
    auto_terminal = result['auto']['state'] in ('complete', 'blocked')
    result['state'] = 'complete' if guard_terminal and auto_terminal else 'unavailable'
    return result


def _write_review(db, job, review, attempts, now):
    guard, auto = review['guard'], review['auto']
    error = guard.get('error') or auto.get('error')
    db.execute('''INSERT INTO semantic_reviews
      (region,event_id,source_path,source_sha,plane,state,guard_state,guard_decision,guard_risk_level,guard_categories,guard_reason_codes,guard_http_status,
       auto_state,auto_model,auto_effort,auto_action,auto_reason,auto_classification,auto_http_status,attempts,error_code,reviewed_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(region,event_id) DO UPDATE SET source_path=excluded.source_path,source_sha=excluded.source_sha,plane=excluded.plane,state=excluded.state,
       guard_state=excluded.guard_state,guard_decision=excluded.guard_decision,guard_risk_level=excluded.guard_risk_level,guard_categories=excluded.guard_categories,
       guard_reason_codes=excluded.guard_reason_codes,guard_http_status=excluded.guard_http_status,auto_state=excluded.auto_state,auto_model=excluded.auto_model,
       auto_effort=excluded.auto_effort,auto_action=excluded.auto_action,auto_reason=excluded.auto_reason,auto_classification=excluded.auto_classification,
       auto_http_status=excluded.auto_http_status,attempts=excluded.attempts,error_code=excluded.error_code,reviewed_at=excluded.reviewed_at''',
      (job['region'], job['event_id'], job['source_path'], job['sha'], 'offline_analysis', review['state'], guard['state'], guard.get('decision'), guard.get('risk_level'),
       _json_field(guard.get('categories')), _json_field(guard.get('reason_codes')), guard.get('http_status'), auto['state'], auto.get('model'), auto.get('effort'), auto.get('action'),
       auto.get('reason'), json.dumps(auto.get('classification', {}), ensure_ascii=False, separators=(',', ':')), auto.get('http_status'), attempts, error, now.isoformat()))


def _region_config(config, region):
    """Resolve one region without ever falling back to another region's endpoint."""
    regions = config.get('regions')
    if regions is None:
        return config
    if not isinstance(regions, dict):
        return None
    override = regions.get(region)
    if not isinstance(override, dict):
        return None
    resolved = {key: value for key, value in config.items() if key != 'regions'}
    resolved.update(override)
    return resolved


def run(db, config, now=None):
    """Process a small queue slice. Disabled/missing endpoints stay pending."""
    ensure_schema(db)
    config = config if isinstance(config, dict) else {}
    if not config.get('enabled'):
        pending = db.execute("SELECT COUNT(*) FROM review_jobs WHERE state='pending'").fetchone()[0]
        return {'status': 'disabled', 'processed': 0, 'pending': pending, 'complete': 0, 'unavailable': 0}
    if config.get('regions') is None and (not config.get('guard_url') or not config.get('auto_url')):
        pending = db.execute("SELECT COUNT(*) FROM review_jobs WHERE state='pending'").fetchone()[0]
        return {'status': 'pending_local_worker', 'processed': 0, 'pending': pending, 'complete': 0, 'unavailable': 0}
    timeout = min(max(float(config.get('timeout_seconds', 3)), 0.1), 30.0)
    limit = min(max(int(config.get('max_jobs', 20)), 1), 1000)
    now = now or datetime.now(timezone.utc)
    # A killed timer must not strand a queue item forever. The global rolling
    # lock prevents a concurrent worker, while this age check recovers a stale
    # claim from a previous process.
    stale_before = (now.timestamp() - max(timeout * 4, 60))
    stale_rows = db.execute("SELECT region,event_id,claimed_at FROM review_jobs WHERE state='running'").fetchall()
    for region, event_id, claimed_at in stale_rows:
        try:
            stale = datetime.fromisoformat(claimed_at).timestamp() < stale_before
        except (TypeError, ValueError):
            stale = True
        if stale:
            db.execute("UPDATE review_jobs SET state='pending',last_error='worker_restart',claimed_at=NULL WHERE region=? AND event_id=?", (region, event_id))
    db.commit()
    jobs = db.execute("SELECT region,event_id,source_path,sha,attempts FROM review_jobs WHERE state='pending' ORDER BY at,event_id LIMIT ?", (limit,)).fetchall()
    counts = Counter()
    auth_error = None
    for row in jobs:
        job = {'region': row[0], 'event_id': row[1], 'source_path': row[2], 'sha': row[3]}
        attempts = int(row[4] or 0) + 1
        db.execute("UPDATE review_jobs SET state='running',attempts=?,claimed_at=? WHERE region=? AND event_id=?", (attempts, now.isoformat(), row[0], row[1]))
        db.commit()
        region_config = _region_config(config, job['region'])
        if not region_config or not region_config.get('guard_url') or not region_config.get('auto_url'):
            db.execute("UPDATE review_jobs SET state='pending',last_error='semantic_region_not_configured',claimed_at=NULL WHERE region=? AND event_id=?", (row[0], row[1]))
            counts['unavailable'] += 1
            continue
        try:
            guard_headers = _auth_headers(region_config.get('guard_auth_file', ''), region_config.get('guard_auth_header', 'Authorization'))
            auto_headers = _auth_headers(region_config.get('auto_auth_file', ''), region_config.get('auto_auth_header', 'Authorization'))
        except (OSError, ValueError, TypeError):
            db.execute("UPDATE review_jobs SET state='pending',last_error='semantic_auth_unavailable',claimed_at=NULL WHERE region=? AND event_id=?", (row[0], row[1]))
            counts['unavailable'] += 1
            auth_error = 'semantic_auth_unavailable'
            continue
        try:
            import rolling
            event, digest = rolling.read_record(Path(job['source_path']))
            if digest != job['sha'] or event.get('id') != job['event_id']:
                raise ValueError('source_changed')
        except (OSError, ValueError, KeyError, TypeError):
            db.execute("UPDATE review_jobs SET state='failed',last_error='source_validation_failed' WHERE region=? AND event_id=?", (row[0], row[1]))
            db.execute('''INSERT OR REPLACE INTO semantic_reviews
                (region,event_id,source_path,source_sha,plane,state,guard_state,auto_state,attempts,error_code,reviewed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (row[0], row[1], row[2], row[3], 'offline_analysis', 'failed', 'not_run', 'not_run', attempts, 'source_validation_failed', now.isoformat()))
            counts['failed'] += 1
            continue
        review = review_event(event, region_config['guard_url'], region_config['auto_url'], timeout, guard_headers, auto_headers)
        _write_review(db, job, review, attempts, now)
        if review['state'] == 'complete':
            db.execute("UPDATE review_jobs SET state='complete',last_error=NULL,claimed_at=NULL WHERE region=? AND event_id=?", (row[0], row[1]))
            counts['complete'] += 1
        else:
            db.execute("UPDATE review_jobs SET state='pending',last_error=?,claimed_at=NULL WHERE region=? AND event_id=?", (str(review['guard'].get('error') or review['auto'].get('error') or 'semantic_unavailable')[:128], row[0], row[1]))
            counts['unavailable'] += 1
        db.commit()
    pending = db.execute("SELECT COUNT(*) FROM review_jobs WHERE state IN ('pending','running')").fetchone()[0]
    result = dict(counts)
    status = 'degraded_local' if counts['failed'] else ('complete_local' if pending == 0 and jobs else ('pending_local_worker' if counts['unavailable'] or pending else 'idle'))
    result.update({'status': status,
                   'processed': len(jobs), 'pending': pending})
    if auth_error:
        result['auth_error'] = auth_error
    return result


def main():
    raise SystemExit('use rolling.py with semantic.enabled=true')


if __name__ == '__main__':
    main()
