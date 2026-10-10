#!/usr/bin/env python3
"""Exercise only the private candidate; keep all credentials in its private ops directory."""
import argparse
import base64
from decimal import Decimal
import fcntl
import hashlib
import json
import os
import secrets
import socket
import struct
import subprocess
import time
import urllib.error
import urllib.request

from candidate_ops import ROOT, candidate_sql, compose, event
from candidate_migrate import BASE, POOLS, api, all_items, equal_totals, key_inventory, roster, sql_json
from customer_passwords import customer_password

STATE = ROOT / 'ops' / 'acceptance-state.json'
REPORT = ROOT / 'ops' / 'acceptance-report.json'
GPT_MODEL = 'gpt-5.6-luna'


def request(method, path, body=None, token=None, timeout=180):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path, method=method, headers=headers,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    data = response.read(32 * 1024 * 1024)
    try:
        parsed = json.loads(data)
    except ValueError:
        parsed = None
    return response.code, parsed, data


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def native(method, path, body=None, token=None):
    code, result, raw = request(method, path, body, token)
    if code != 200 or not isinstance(result, dict) or result.get('code', 0) != 0:
        (ROOT / 'ops' / 'acceptance-error.bin').write_bytes(raw)
        raise RuntimeError('candidate panel {} {} returned {}'.format(method, path, code))
    return result.get('data', result)


def record(name, result):
    with (ROOT / 'ops' / 'acceptance-report.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        report = json.loads(REPORT.read_text()) if REPORT.exists() else {}
        report[name] = result
        temporary = REPORT.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        os.replace(str(temporary), str(REPORT))
    event('acceptance_' + name, **result)


def login(email, password):
    result = native('POST', '/api/v1/auth/login', {'email': email, 'password': password})
    check('access_token' in result, 'login did not return an access token')
    return result['access_token']


def state():
    return json.loads(STATE.read_text())


def metadata():
    migration = json.loads((ROOT / 'ops' / 'migration-state.json').read_text())
    accounts = []
    for aid in [a[0] for a in POOLS.values()] + migration['deepseek_accounts']:
        account = api('GET', '/api/v1/admin/accounts/{}'.format(aid))
        credentials = account.get('credentials') or {}
        accounts.append({k: account.get(k) for k in ['id', 'name', 'platform', 'status', 'schedulable', 'group_ids']})
        accounts[-1]['model_mapping'] = credentials.get('model_mapping')
        accounts[-1]['model_allowlist'] = credentials.get('model_allowlist')
        accounts[-1]['base_url'] = credentials.get('base_url')
        accounts[-1]['credential_fields'] = sorted(credentials)
    print(json.dumps({'accounts': accounts, 'groups': migration['groups']}, ensure_ascii=False), flush=True)


def panel():
    migration = json.loads((ROOT / 'ops' / 'migration-state.json').read_text())
    rows = roster()
    # Sample customers across resource groups without embedding a delivery roster.
    groups = list(dict.fromkeys(row['resource_group'] for row in rows))[:4]
    samples = [next(row for row in rows if row['resource_group'] == group) for group in groups]
    results = []
    for row in samples:
        key_id, uid = int(row['api_key_id']), migration['users'][row['api_key_id']]
        email = row['login_email']
        token = login(email, customer_password(email))
        profile = native('GET', '/api/v1/user/profile', token=token)
        check(profile['id'] == uid and profile['email'] == email, 'profile identity mismatch')
        keys = native('GET', '/api/v1/keys?page_size=100', token=token)
        items = keys if isinstance(keys, list) else keys['items']
        check({k['id'] for k in items} == {key_id}, 'user sees unexpected active keys')
        groups = native('GET', '/api/v1/groups/available', token=token)
        check({g['id'] for g in groups} == {migration['groups'][row['resource_group']]}, 'user sees unexpected available groups')
        usage = native('GET', '/api/v1/usage?page_size=10', token=token)
        expected = int(candidate_sql('SELECT count(*) FROM usage_logs WHERE user_id={};'.format(uid)))
        check(usage['total'] == expected and all(u['user_id'] == uid for u in usage['items']), 'personal usage differs from database')
        other = next(int(r['api_key_id']) for r in rows if r['api_key_id'] != row['api_key_id'])
        forbidden_key = request('GET', '/api/v1/keys/{}'.format(other), token=token)[0]
        forbidden_usage = request('GET', '/api/v1/usage?api_key_id={}'.format(other), token=token)[0]
        forbidden_admin = request('GET', '/api/v1/admin/users', token=token)[0]
        check(forbidden_key in (403, 404) and forbidden_usage in (403, 404) and forbidden_admin == 403, 'personal data isolation check failed')
        results.append({'key_id': key_id, 'login': True, 'historical_requests': expected,
                        'only_own_key_and_group': True, 'cross_user_key_status': forbidden_key,
                        'cross_user_usage_status': forbidden_usage, 'admin_status': forbidden_admin})
    record('personal_panel', {'passed': True, 'samples': results})


def prepare():
    check((ROOT / 'ops' / 'migration-verification.json').exists(), 'migration verification must precede runtime QA')
    if STATE.exists():
        event('acceptance_user_exists', user_id=state()['user_id'])
        return
    migration = json.loads((ROOT / 'ops' / 'migration-state.json').read_text())
    email = 'candidate-acceptance-20261009@invalid.test'
    check(not any(u['email'] == email for u in all_items('users')), 'untracked QA user already exists')
    password = secrets.token_urlsafe(24)
    user = api('POST', '/api/v1/admin/users', {'email': email, 'password': password,
               'username': '隔离验收账号', 'notes': 'Candidate QA only; disable before production cutover',
               'role': 'user', 'balance': 10, 'concurrency': 2, 'rpm_limit': 0,
               'allowed_groups': list(migration['groups'].values()), 'restrict_public_groups': True})
    qa = {'user_id': user['id'], 'email': email, 'password': password, 'keys': {}, 'groups': migration['groups']}
    STATE.write_text(json.dumps(qa))
    token = login(email, password)
    for name, gid in migration['groups'].items():
        key = native('POST', '/api/v1/keys', {'name': 'candidate-qa-' + name, 'group_id': gid}, token)
        qa['keys'][name] = {'id': key['id'], 'key': key['key']}
        STATE.write_text(json.dumps(qa))
    key = native('POST', '/api/v1/keys', {'name': 'candidate-qa-shared-quota', 'group_id': migration['groups']['ecube-A']}, token)
    qa['keys']['second'] = {'id': key['id'], 'key': key['key']}
    STATE.write_text(json.dumps(qa))
    api('PUT', '/api/v1/admin/users/{}/platform-quotas'.format(user['id']), {'quotas': [{'platform': 'openai', 'weekly_limit_usd': 3}]})
    record('qa_prepared', {'user_id': user['id'], 'test_keys': len(qa['keys']), 'isolated_from_74_people': True})


def call(key_name, model, protocol='responses', expected_status=200):
    qa = state()
    key = qa['keys'][key_name]
    before = int(candidate_sql('SELECT coalesce(max(id),0) FROM usage_logs WHERE user_id={};'.format(qa['user_id'])))
    if protocol == 'responses':
        path = '/v1/responses'
        payload = {'model': model, 'stream': True, 'store': False, 'instructions': 'Reply briefly.',
                   'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': 'Reply with exactly OK.'}]}]}
    elif protocol == 'messages':
        path = '/v1/messages'
        payload = {'model': model, 'max_tokens': 32, 'stream': True,
                   'messages': [{'role': 'user', 'content': 'Reply with exactly OK.'}]}
    else:
        path = '/v1/chat/completions'
        payload = {'model': model, 'stream': False, 'max_tokens': 64,
                   'messages': [{'role': 'user', 'content': 'Reply with exactly OK.'}]}
    code, result, raw = request('POST', path, payload, key['key'])
    info = {'group': key_name, 'model': model, 'protocol': protocol, 'http_status': code}
    if code != expected_status:
        (ROOT / 'ops' / 'acceptance-error.bin').write_bytes(raw)
        if isinstance(result, dict):
            error = result.get('error') or {}
            info['error_type'] = error.get('type') if isinstance(error, dict) else 'non-object'
            info['error_code'] = error.get('code') if isinstance(error, dict) else None
        record('call_failure', info)
        raise RuntimeError('candidate runtime response status differs from expectation')
    if code == 200:
        if protocol == 'responses':
            check(b'response.completed' in raw, 'Responses stream has no completed event')
        elif protocol == 'messages':
            check(b'message_stop' in raw, 'Messages stream has no terminal event')
        else:
            check(isinstance(result, dict) and bool(result.get('choices')), 'Chat response has no choices')
        usage = []
        for _ in range(15):
            usage = sql_json('SELECT coalesce(json_agg(t),\'[]\') FROM (SELECT l.id,l.api_key_id,l.account_id,a.platform,l.model,l.total_cost,l.actual_cost FROM usage_logs l JOIN accounts a ON a.id=l.account_id WHERE l.user_id={} AND l.id>{} ORDER BY l.id) t;'.format(qa['user_id'], before))
            if usage:
                break
            time.sleep(1)
        check(len(usage) == 1 and usage[0]['api_key_id'] == key['id'], 'successful request did not produce exactly one usage record')
        info['usage'] = usage[0]
    else:
        error = (result or {}).get('error') or {}
        info['error_type'] = error.get('type') if isinstance(error, dict) else None
        info['error_code'] = error.get('code') if isinstance(error, dict) else None
    event('acceptance_call', **info)
    return info


def smoke():
    results = []
    for name, (aid, _) in POOLS.items():
        item = call(name, GPT_MODEL)
        check(item['usage']['account_id'] == aid and item['usage']['platform'] == 'openai', 'GPT resource isolation mismatch')
        results.append(item)
    for model in ['deepseek-flash', 'deepseek-v4-pro']:
        item = call('ecube-A', model, 'chat')
        check(item['usage']['platform'] == 'deepseek' and item['usage']['actual_cost'] > 0, 'DeepSeek native routing or billing failed')
        results.append(item)
    record('routing_smoke', {'passed': True, 'calls': results})


def quota_snapshot():
    uid = state()['user_id']
    return sql_json("SELECT row_to_json(t) FROM (SELECT q.weekly_usage_usd::text AS usage,q.weekly_limit_usd::text AS limit_usd,q.weekly_window_start,(q.weekly_window_start AT TIME ZONE 'Asia/Shanghai')::text AS week_local,u.balance::text AS balance FROM user_platform_quotas q JOIN users u ON u.id=q.user_id WHERE q.user_id={} AND q.platform='openai' AND q.deleted_at IS NULL) t;".format(uid))


def set_quota(limit_usd):
    api('PUT', '/api/v1/admin/users/{}/platform-quotas'.format(state()['user_id']),
        {'quotas': [{'platform': 'openai', 'weekly_limit_usd': limit_usd}]})


def delete_quota_cache():
    # Redis credentials are already in this candidate container's environment.
    result = subprocess.run(['docker', 'exec', 'sub2api-next-redis', 'redis-cli', 'DEL',
                             'billing:user_platform_quota:{}:openai'.format(state()['user_id'])],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=15)
    check(result.returncode == 0, 'could not clear the isolated QA quota cache')


def limits():
    qa = state()
    before = quota_snapshot()
    check(Decimal(before['usage']) > 0, 'successful GPT smoke requests are required before quota tests')
    set_quota(0.0000000001)
    first = call('ecube-A', GPT_MODEL, expected_status=429)
    second = call('second', GPT_MODEL, expected_status=429)
    ds = []
    for model in ['deepseek-flash', 'deepseek-v4-pro']:
        ds.append(call('ecube-A', model, 'chat'))
    after = quota_snapshot()
    check(Decimal(before['usage']) == Decimal(after['usage']), 'DeepSeek changed the GPT weekly counter')
    check(Decimal(after['balance']) < Decimal(before['balance']), 'DeepSeek did not deduct internal balance')
    record('quota_isolation', {'passed': True, 'two_keys_share_limit': [first, second],
                              'deepseek_while_gpt_exhausted': ds, 'gpt_counter_unchanged': True,
                              'deepseek_wallet_debit': str(Decimal(before['balance']) - Decimal(after['balance']))})

    # Clear one QA cache entry to test persisted enforcement, then restart only B.
    delete_quota_cache()
    cold = call('second', GPT_MODEL, expected_status=429)
    compose('restart', 'app')
    for _ in range(60):
        try:
            if request('GET', '/health', timeout=2)[0] == 200:
                break
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    restarted = call('second', GPT_MODEL, expected_status=429)
    record('quota_persistence', {'passed': True, 'cold_cache': cold['http_status'], 'after_candidate_restart': restarted['http_status']})

    # A prior-week row exercises native rollover without touching any server clock.
    candidate_sql("UPDATE user_platform_quotas SET weekly_usage_usd=300,weekly_window_start=(date_trunc('week',now() AT TIME ZONE 'Asia/Shanghai')-interval '7 days') AT TIME ZONE 'Asia/Shanghai' WHERE user_id={} AND platform='openai' AND deleted_at IS NULL;".format(qa['user_id']))
    set_quota(300)
    reset_call = call('second', GPT_MODEL)
    reset = quota_snapshot()
    expected = candidate_sql("SELECT date_trunc('week',now() AT TIME ZONE 'Asia/Shanghai')::text;").strip()
    check(reset['week_local'] == expected and Decimal(reset['usage']) < 1, 'native natural-week rollover failed')
    record('weekly_rollover', {'passed': True, 'week_start_asia_shanghai': reset['week_local'], 'new_usage': reset['usage'], 'request': reset_call})

    wallet()


def wallet():
    qa = state()
    before = quota_snapshot()
    # The native user-update route ignores its legacy balance field; use the balance endpoint.
    api('POST', '/api/v1/admin/users/{}/balance'.format(qa['user_id']),
        {'balance': float(before['balance']), 'operation': 'subtract', 'notes': 'Candidate empty-wallet acceptance'})
    check(Decimal(quota_snapshot()['balance']) == 0, 'native balance adjustment did not set the QA wallet to zero')
    zero = call('ecube-A', 'deepseek-flash', 'chat', expected_status=403)
    api('POST', '/api/v1/admin/users/{}/balance'.format(qa['user_id']),
        {'balance': 10, 'operation': 'set', 'notes': 'Candidate wallet recovery acceptance'})
    restored = call('ecube-A', 'deepseek-flash', 'chat')
    record('wallet', {'passed': True, 'empty_balance_status': zero['http_status'], 'after_refill_status': restored['http_status']})


def protocols():
    results = [call('ecube-A', GPT_MODEL, 'chat'), call('ecube-A', GPT_MODEL, 'messages'),
               call('ecube-A', 'deepseek-flash', 'responses'), call('ecube-A', 'deepseek-v4-pro', 'responses')]
    record('http_protocols', {'passed': True, 'calls': results})


def websocket(quota_gate=False):
    """Small RFC6455 client for localhost acceptance, with no extra host packages."""
    qa = state()
    nonce = base64.b64encode(os.urandom(16)).decode()
    expected_accept = base64.b64encode(hashlib.sha1((nonce + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
    before = int(candidate_sql('SELECT coalesce(max(id),0) FROM usage_logs WHERE user_id={};'.format(qa['user_id'])))
    with socket.create_connection(('127.0.0.1', 18080), timeout=90) as sock:
        headers = ['GET /v1/responses HTTP/1.1', 'Host: 127.0.0.1:18080', 'Upgrade: websocket',
                   'Connection: Upgrade', 'Sec-WebSocket-Version: 13', 'Sec-WebSocket-Key: ' + nonce,
                   'Authorization: Bearer ' + qa['keys']['ecube-A']['key']]
        sock.sendall(('\r\n'.join(headers) + '\r\n\r\n').encode())
        stream = sock.makefile('rb')
        status_line = stream.readline().decode().strip()
        response_headers = {}
        while True:
            line = stream.readline().decode().strip()
            if not line:
                break
            name, value = line.split(':', 1)
            response_headers[name.lower()] = value.strip()
        check(' 101 ' in status_line and response_headers.get('sec-websocket-accept') == expected_accept, 'candidate WebSocket upgrade failed: ' + status_line)

        def send(payload, opcode=1):
            mask = os.urandom(4)
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            n = len(data)
            prefix = bytes([0x80 | opcode, 0x80 | n]) if n < 126 else bytes([0x80 | opcode, 0xfe]) + struct.pack('!H', n)
            sock.sendall(prefix + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(data)))

        def next_event():
            chunks = []
            for _ in range(1000):
                prefix = stream.read(2)
                check(len(prefix) == 2, 'WebSocket closed without a terminal event')
                first, second = prefix
                n = second & 0x7f
                if n == 126:
                    n = struct.unpack('!H', stream.read(2))[0]
                elif n == 127:
                    n = struct.unpack('!Q', stream.read(8))[0]
                check(n <= 1024 * 1024, 'unexpectedly large WebSocket frame')
                mask = stream.read(4) if second & 0x80 else None
                data = stream.read(n)
                if mask:
                    data = bytes(value ^ mask[i % 4] for i, value in enumerate(data))
                opcode = first & 0x0f
                if opcode == 9:
                    send(data, 10)
                    continue
                if opcode == 8:
                    return {'type': 'closed', 'code': struct.unpack('!H', data[:2])[0] if len(data) >= 2 else None,
                            'reason': data[2:].decode('utf-8', errors='replace')}
                if opcode in (0, 1):
                    chunks.append(data)
                    if first & 0x80:
                        return json.loads(b''.join(chunks))
            raise RuntimeError('WebSocket event frame bound exceeded')

        completed, rejected = 0, False
        for turn in range(2):
            payload = {'type': 'response.create', 'model': GPT_MODEL, 'store': False,
                       'instructions': 'Reply briefly.',
                       'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': 'Reply with exactly OK.'}]}]}
            if turn:
                del payload['model']
                if quota_gate:
                    set_quota(0.0000000001)
            send(payload)
            for _ in range(1000):
                response = next_event()
                kind = response.get('type')
                if kind in ('error', 'response.failed', 'closed'):
                    if quota_gate and turn and 'quota' in json.dumps(response).lower():
                        rejected = True
                        break
                    (ROOT / 'ops' / 'websocket-error.json').write_text(json.dumps(response))
                    raise RuntimeError('WebSocket request did not complete; terminal event=' + str(kind))
                if kind == 'response.completed':
                    completed += 1
                    break
        if not rejected:
            send(struct.pack('!H', 1000), 8)
    time.sleep(2)
    usage = sql_json('SELECT coalesce(json_agg(t),\'[]\') FROM (SELECT account_id,api_key_id,actual_cost FROM usage_logs WHERE user_id={} AND id>{} ORDER BY id) t;'.format(qa['user_id'], before))
    expected_turns = 1 if quota_gate else 2
    if quota_gate and (completed != expected_turns or not rejected):
        record('websocket_quota', {'passed': False, 'completed_turns': completed,
                                   'second_turn_quota_blocked': rejected, 'usage': usage})
    check(completed == expected_turns and len(usage) == expected_turns and all(u['account_id'] == 51 for u in usage), 'WebSocket billing or group routing mismatch')
    check(not quota_gate or rejected, 'existing WebSocket bypassed the personal quota')
    record('websocket_quota' if quota_gate else 'websocket', {'passed': True, 'completed_turns': completed,
           'second_turn_model_omitted': True, 'second_turn_quota_blocked': rejected, 'usage': usage})


def quota_supplement():
    try:
        set_quota(0.0000000001)
        cross_group = call('dpad-A', GPT_MODEL, expected_status=429)
        record('cross_group_quota', {'passed': True, 'different_group_status': cross_group['http_status']})
        set_quota(300)
        websocket(quota_gate=True)
    finally:
        set_quota(300)


def websocket_blocked():
    qa = state()
    before = int(candidate_sql('SELECT count(*) FROM usage_logs WHERE user_id={};'.format(qa['user_id'])))
    config = json.loads((ROOT / 'compose.json').read_text())['services']['app']['environment']
    check(config.get('GATEWAY_OPENAI_WS_ENABLED') == 'false' and config.get('GATEWAY_OPENAI_WS_MODE_ROUTER_V2_ENABLED') == 'false', 'candidate WS switches are not disabled')
    try:
        websocket()
    except RuntimeError as exc:
        check('terminal event=closed' in str(exc), 'unexpected WebSocket disabled result')
        response = json.loads((ROOT / 'ops' / 'websocket-error.json').read_text())
        check(response['code'] == 1013 and response.get('reason') == 'no available account', 'unexpected WebSocket close code or reason')
    else:
        raise RuntimeError('candidate WebSocket still permits model calls')
    after = int(candidate_sql('SELECT count(*) FROM usage_logs WHERE user_id={};'.format(qa['user_id'])))
    check(after == before, 'blocked WebSocket produced a billable request')
    record('websocket_disabled', {'passed': True, 'close_code': response['code'], 'billable_requests': 0,
                                  'required_client_transport': 'HTTP/SSE'})


def images():
    qa = state()
    code, result, raw = request('POST', '/v1/images/generations',
                               {'model': 'gpt-image-2.5-flare', 'prompt': 'A small plain blue circle on a white background.',
                                'n': 1, 'size': '1024x1024', 'quality': 'low', 'response_format': 'b64_json'},
                               qa['keys']['ecube-A']['key'], timeout=180)
    if code != 200:
        (ROOT / 'ops' / 'image-error.bin').write_bytes(raw)
    check(code == 200 and isinstance(result, dict) and bool(result.get('data')), 'candidate image request failed with HTTP {}'.format(code))
    check(bool(result['data'][0].get('b64_json') or result['data'][0].get('url')), 'image response contains no image')
    time.sleep(2)
    usage = sql_json('SELECT row_to_json(t) FROM (SELECT account_id,api_key_id,actual_cost,image_count,model FROM usage_logs WHERE user_id={} ORDER BY id DESC LIMIT 1) t;'.format(qa['user_id']))
    check(usage['account_id'] == 51 and usage['image_count'] == 1 and usage['actual_cost'] > 0, 'image billing or group routing mismatch')
    record('images', {'passed': True, 'http_status': code, 'usage': usage})


def cleanup():
    qa = state()
    api('PUT', '/api/v1/admin/users/{}'.format(qa['user_id']), {'status': 'disabled'})
    result = api('GET', '/api/v1/admin/users/{}'.format(qa['user_id']))
    check(result['status'] == 'disabled', 'QA user remains active')
    record('qa_disabled', {'passed': True, 'user_id': qa['user_id']})


def login_all():
    migration = json.loads((ROOT / 'ops' / 'migration-state.json').read_text())
    for index, row in enumerate(roster(), 1):
        # Native login is limited to 20/minute; retry only that explicit response.
        email = row['login_email']
        password = customer_password(email)
        for attempt in range(3):
            code, result, raw = request('POST', '/api/v1/auth/login', {'email': email, 'password': password})
            if code != 429:
                break
            time.sleep(30)
        check(code == 200 and isinstance(result, dict) and result.get('code') == 0, 'personal login failed for key {}'.format(row['api_key_id']))
        token = result['data']['access_token']
        profile = native('GET', '/api/v1/user/profile', token=token)
        check(profile['id'] == migration['users'][row['api_key_id']], 'personal login returned the wrong identity')
        quota = native('GET', '/api/v1/user/platform-quotas', token=token)['platform_quotas']
        check(len(quota) == 1 and quota[0]['platform'] == 'openai' and quota[0]['weekly_limit_usd'] == 300, 'personal quota display mismatch')
        if index % 10 == 0 or index == 74:
            event('personal_logins_verified', count=index)
        time.sleep(3.3)
    record('all_logins', {'passed': True, 'count': 74, 'credential_source': 'operator-private-file', 'gpt_weekly_limit_usd': 300})


def final_audit():
    migration = json.loads((ROOT / 'ops' / 'migration-state.json').read_text())
    baseline = json.loads((ROOT / 'ops' / 'migration-baseline.json').read_text())
    current = {k['id']: k for k in key_inventory()}
    for original in baseline['keys']:
        key = current[original['id']]
        check(key['key_digest'] == original['key_digest'] and key['deleted'] == original['deleted'], 'original key value or deletion state changed')
        if original['id'] in (55, 79, 90):
            check(key == original, 'excluded key metadata changed')
    key_ids = ','.join(str(k['id']) for k in baseline['keys'])
    totals = sql_json('SELECT json_agg(t) FROM (SELECT api_key_id,count(*) AS requests,sum(input_tokens)::text AS input_tokens,sum(output_tokens)::text AS output_tokens,sum(cache_creation_tokens)::text AS cache_creation_tokens,sum(cache_read_tokens)::text AS cache_read_tokens,sum(total_cost)::text AS total_cost,sum(actual_cost)::text AS actual_cost FROM usage_logs WHERE api_key_id IN ({}) GROUP BY api_key_id ORDER BY api_key_id) t;'.format(key_ids))
    check(equal_totals(baseline['usage_totals'], totals), 'original key history changed during isolated QA')
    users = ','.join(str(u) for u in migration['users'].values())
    real_users = sql_json("SELECT json_agg(t) FROM (SELECT u.id,u.balance,u.status,q.weekly_limit_usd,q.weekly_usage_usd FROM users u JOIN user_platform_quotas q ON q.user_id=u.id AND q.platform='openai' AND q.deleted_at IS NULL WHERE u.id IN ({})) t;".format(users))
    check(len(real_users) == 74 and all(u['balance'] == 100000 and u['status'] == 'active' and u['weekly_limit_usd'] == 300 and u['weekly_usage_usd'] == 0 for u in real_users), 'real personal user initialization changed during QA')
    native_credentials = int(candidate_sql("SELECT count(*) FROM accounts WHERE id IN ({}) AND length(credentials->>'api_key')>0;".format(','.join(str(a) for a in migration['deepseek_accounts']))))
    check(native_credentials == 2, 'native DeepSeek credentials missing')
    refresh_count = int(candidate_sql("SELECT count(*) FROM accounts WHERE type='oauth' AND credentials ? 'refresh_token';"))
    check(refresh_count == 0, 'candidate contains shared OAuth refresh credentials')
    record('final_audit', {'passed': True, 'historical_requests_preserved': sum(r['requests'] for r in totals),
                          'original_key_values_preserved': len(baseline['keys']), 'personal_users': 74,
                          'personal_weekly_usage_zero': True, 'personal_initial_balance_100000': True,
                          'native_deepseek_credentials': native_credentials, 'candidate_oauth_refresh_tokens': refresh_count})


def native_features():
    settings = api('GET', '/api/v1/admin/settings')
    flags = {key: settings.get(key) for key in
             ['ops_monitoring_enabled', 'ops_realtime_monitoring_enabled', 'channel_monitor_enabled']}
    check(all(value is True for value in flags.values()), 'native management feature flag remains disabled')
    advanced = api('GET', '/api/v1/admin/ops/advanced-settings')
    check(advanced['aggregation']['aggregation_enabled'], 'native ops aggregation disabled')
    check(advanced['data_retention']['cleanup_enabled'], 'native ops retention disabled')
    check(advanced['auto_refresh_enabled'], 'native ops dashboard auto refresh disabled')
    logging = api('GET', '/api/v1/admin/ops/runtime/logging')
    check(logging['request_retention_days'] == 0, 'historical usage retention must remain unlimited')
    email = api('GET', '/api/v1/admin/ops/email-notification/config')
    check(not email['alert']['enabled'] and not email['report']['enabled'], 'unexpected outbound notifications')
    endpoints = ['dashboard/overview', 'dashboard/throughput-trend', 'concurrency',
                 'realtime-traffic', 'account-availability', 'alert-rules', 'alert-events',
                 'request-errors', 'upstream-errors', 'system-logs', 'system-logs/health']
    for endpoint in endpoints:
        api('GET', '/api/v1/admin/ops/' + endpoint)
    metrics = sql_json("SELECT json_build_object('metrics_rows',count(*),'latest_metric_at',max(created_at),'recent_metrics',count(*) FILTER (WHERE created_at>now()-interval '5 minutes')) FROM ops_system_metrics;")
    check(metrics['recent_metrics'] > 0, 'native metrics collector has not persisted recent data')
    containers = json.loads(subprocess.check_output(['docker', 'inspect', 'sub2api', 'sub2api-next'], universal_newlines=True))
    candidate = containers[1]
    env = dict(item.split('=', 1) for item in candidate['Config']['Env'])
    check(all(env.get(key) == 'true' for key in ['OPS_ENABLED', 'DASHBOARD_AGGREGATION_ENABLED', 'USAGE_CLEANUP_ENABLED']),
          'native worker environment remains disabled')
    check(env.get('TOKEN_REFRESH_ENABLED') == 'false' and env.get('GATEWAY_OPENAI_WS_FORCE_HTTP') == 'true',
          'preview credential isolation or approved HTTP/SSE restriction changed')
    record('native_features', {'passed': True, 'flags': flags, 'ops_read_endpoints_passed': endpoints,
                              'ops_aggregation': True, 'ops_retention': True, 'dashboard_aggregation': True,
                              'dashboard_auto_refresh': True, 'usage_cleanup_service': True,
                              'request_history_retention_days': 0, 'email_sending': False,
                              'metrics': metrics, 'candidate_health': candidate['State'].get('Health', {}).get('Status'),
                              'production_health': containers[0]['State'].get('Health', {}).get('Status'),
                              'gpt_transport': 'HTTP/SSE', 'shared_oauth_refresh': False})


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['metadata', 'panel', 'prepare', 'smoke', 'limits', 'wallet', 'protocols', 'websocket', 'images', 'cleanup', 'login_all', 'final_audit', 'quota_supplement', 'websocket_blocked', 'native_features'])
    args = parser.parse_args()
    for attempt in range(30):
        try:
            if request('GET', '/health', timeout=2)[0] == 200:
                break
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    else:
        raise RuntimeError('candidate is not healthy; acceptance did not start')
    globals()[args.phase]()


if __name__ == '__main__':
    main()
