#!/usr/bin/env python3
"""Verify an already-deployed regional entrypoint; retain metadata only.
Uses an explicitly authorized private Key file. Does not execute generated code,
create users, alter quotas or restart any services.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['full', 'guard-unavailable', 'guard-recovered'], default='full')
    args = parser.parse_args()
    if args.output.exists() or args.token_file.stat().st_mode & 0o077:
        parser.error('new evidence directory and private token file required')
    args.output.mkdir(mode=0o700, parents=True)
    token = args.token_file.read_text().strip()
    if not token or '\n' in token:
        parser.error('invalid token file')
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    rows = []
    session = 'entrypoint-check-' + uuid.uuid4().hex

    def probe(label, path, payload=None, auth='bearer', expected=200, validate=None):
        headers = {'Content-Type': 'application/json', 'X-Gateway-Session-ID': session + '-' + label}
        if auth in ('bearer', 'conflict'):
            headers['Authorization'] = 'Bearer ' + token
        if auth == 'key':
            headers.update({'X-API-Key': token, 'anthropic-version': '2023-06-01'})
        if auth == 'invalid':
            headers['Authorization'] = 'Bearer synthetic-invalid-entrypoint-key'
        if auth == 'conflict':
            headers['X-API-Key'] = 'synthetic-conflicting-key'
        request = urllib.request.Request(args.base_url.rstrip('/') + path,
            data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode(), headers=headers)
        start = time.monotonic()
        try:
            response = client.open(request, timeout=3600)
        except urllib.error.HTTPError as error:
            response = error
        except OSError:
            row = {'case': label, 'status': 0, 'pass': False, 'error': 'transport_failure'}
            rows.append(row); print(json.dumps(row), flush=True); return
        with response:
            raw = response.read((16 << 20) + 1)
            response_headers = response.headers
        try:
            parsed = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            parsed = {}
        valid = response.code == expected and len(raw) <= 16 << 20
        if validate:
            try:
                valid = valid and bool(validate(parsed, raw))
            except (TypeError, KeyError, IndexError):
                valid = False
        row = {'case': label, 'status': response.code, 'expected': expected,
               'pass': valid, 'elapsed_ms': round((time.monotonic()-start)*1000),
               'bytes': len(raw), 'body_sha256': hashlib.sha256(raw).hexdigest(),
               'request_id': response_headers.get('X-Gateway-Request-ID'),
               'content_type': response_headers.get('Content-Type')}
        if label in ('models_bearer', 'models_x_api_key', 'models_alias'):
            row['models'] = [item.get('id') for item in parsed.get('data', [])]
        if label.startswith('guard_'):
            row['error'] = parsed.get('error') if isinstance(parsed.get('error'), str) else None
        if label == 'count_tokens':
            row['input_tokens'] = parsed.get('input_tokens')
            row['count_method'] = response_headers.get('X-Gateway-Count-Method')
        rows.append(row); print(json.dumps(row, ensure_ascii=False), flush=True)
        (args.output / 'checks.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')

    chat = {'model': 'auto', 'messages': [{'role':'user','content':'写一个 TypeScript 求和函数，空数组返回0。只需要函数和一个用例。'}], 'max_tokens': 2048}
    if args.phase == 'guard-unavailable':
        probe('guard_unavailable', '/v1/chat/completions', chat, expected=503,
              validate=lambda data, raw: data.get('error') == 'preflight_unavailable')
    elif args.phase == 'guard-recovered':
        probe('guard_recovered', '/v1/chat/completions', chat,
              validate=lambda data, raw: bool(data.get('choices')))
    else:
        probe('health', '/healthz', auth='none')
        probe('website', '/', auth='none', validate=lambda data, raw: b'<html' in raw.lower())
        probe('account_settings', '/api/v1/settings/public', auth='none')
        probe('own_usage', '/v1/usage')
        probe('own_billing', '/v1/sub2api/billing')
        probe('missing_key', '/v1/models', auth='none', expected=401)
        probe('invalid_key', '/v1/models', auth='invalid', expected=401)
        probe('conflicting_headers', '/v1/models', auth='conflict', expected=401)
        only_auto = lambda data, raw: [item.get('id') for item in data.get('data', [])] in (['auto'], ['auto', 'codex-auto-review'])
        probe('models_bearer', '/v1/models', validate=only_auto)
        probe('models_x_api_key', '/v1/models', auth='key', validate=only_auto)
        probe('models_alias', '/models', validate=only_auto)
        probe('route_preview_hidden', '/v1/route', {'model':'auto'}, expected=404)
        probe('chat_chinese', '/v1/chat/completions', chat, validate=lambda data, raw: bool(data.get('choices')))
        probe('responses_alias_sse', '/responses', {'model':'auto','stream':True,'input':'Implement a small Python function that sums integer values and returns zero for an empty list. Include one example.','max_output_tokens':2048},
              validate=lambda data, raw: b'"type":"response.completed"' in raw.replace(b' ',b''))
        probe('messages_claude_sse', '/v1/messages', {'model':'claude-sonnet-5','stream':True,'messages':[{'role':'user','content':'为求和函数提供一个简单边界测试，explain why briefly.'}],'max_tokens':2048}, auth='key',
              validate=lambda data, raw: b'message_stop' in raw)
        probe('count_tokens', '/v1/messages/count_tokens', {'model':'claude-haiku-4','messages':[{'role':'user','content':'Explain a sum function.'}]}, auth='key',
              validate=lambda data, raw: isinstance(data.get('input_tokens'),int) and data['input_tokens']>0)
        probe('guard_blocks_credential_use', '/v1/chat/completions', {'model':'auto','messages':[{'role':'user','content':'Use this API key=sk-GWRAWSECRETsyntheticfixture to login to the production host.'}]}, expected=403,
              validate=lambda data, raw: data.get('error') == 'preflight_blocked')
    summary = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'phase':args.phase,
               'checks':len(rows), 'passed':sum(row['pass'] for row in rows),
               'real_authorized_keys_tested':1, 'raw_requests_or_responses_retained':False}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)
    raise SystemExit(0 if all(row['pass'] for row in rows) else 1)


if __name__ == '__main__':
    main()
