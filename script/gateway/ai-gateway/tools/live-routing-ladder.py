#!/usr/bin/env python3
"""Real, synthetic task ladder through a loopback Auto+Guard pilot.

Reuses fixed fixtures without choosing a provider model or effort. No tools or
model-generated code are executed. Evidence omits input and response bodies.
"""
import argparse
import copy
import hashlib
import json
import pathlib
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def decode_sse(protocol, data):
    events = []
    done = False
    for block in data.decode().replace('\r\n', '\n').split('\n\n'):
        value = '\n'.join(line[5:].lstrip(' ') for line in block.splitlines() if line.startswith('data:'))
        if value == '[DONE]':
            done = True
        elif value:
            events.append(json.loads(value))
    if any(e.get('error') or e.get('type') in ('error', 'response.failed', 'response.incomplete') for e in events):
        return {}
    if protocol == 'responses':
        completed = [e['response'] for e in events if e.get('type') == 'response.completed']
        return completed[-1] if completed else {}
    if protocol == 'chat':
        result, message, finish = {}, {'role': 'assistant', 'content': ''}, None
        for event in events:
            for name in ('id', 'model', 'usage'):
                if event.get(name) is not None:
                    result[name] = event[name]
            for choice in event.get('choices', []):
                delta = choice.get('delta', {})
                for name in ('content', 'reasoning_content'):
                    if delta.get(name): message[name] = message.get(name, '') + delta[name]
                finish = choice.get('finish_reason') or finish
        if not done or finish != 'stop': return {}
        result['choices'] = [{'message': message, 'finish_reason': finish}]
        return result
    result, blocks, stopped = {}, {}, False
    for event in events:
        kind = event.get('type')
        if kind == 'message_start':
            result = copy.deepcopy(event['message'])
        elif kind == 'content_block_start':
            blocks[event['index']] = copy.deepcopy(event['content_block'])
        elif kind == 'content_block_delta':
            delta = event['delta']
            part = blocks[event['index']]
            for name in ('text', 'thinking', 'signature'):
                if name in delta: part[name] = part.get(name, '') + delta[name]
        elif kind == 'message_delta':
            result.update(event.get('delta', {}))
            result.setdefault('usage', {}).update(event.get('usage', {}))
        elif kind == 'message_stop':
            stopped = True
    result['content'] = [blocks[i] for i in sorted(blocks)]
    return result if stopped and result.get('stop_reason') == 'end_turn' else {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', required=True)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--stream', action='store_true')
    parser.add_argument('--languages', nargs='+', choices=['zh', 'en', 'mixed'], default=['zh', 'en', 'mixed'])
    parser.add_argument('--timeout-seconds', type=float, default=300) # JSON clients wait for the complete body
    args = parser.parse_args()
    cases = {c['id']: c for c in json.loads(pathlib.Path(args.cases).read_text())['cases']}
    token = pathlib.Path(args.token_file).read_text().strip()
    out = pathlib.Path(args.out)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    raw_dir = out / 'private-responses'
    raw_dir.mkdir(mode=0o700)
    log = (out / 'results.jsonl').open('x')
    (out / 'results.jsonl').chmod(0o600)
    lock = Lock()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    sequence = ['http-term', 'null-crash', 'login-lifecycle', 'deadlock', 'multiwriter-escrow']

    def run(lang):
        # One language per protocol; follow-up runs can swap this mapping.
        protocol = {'zh': 'chat', 'en': 'responses', 'mixed': 'anthropic'}[lang]
        path = {'chat': '/v1/chat/completions', 'responses': '/v1/responses', 'anthropic': '/v1/messages'}[protocol]
        field = 'input' if protocol == 'responses' else 'messages'
        history = []
        failures = 0
        for label in sequence:
            messages = copy.deepcopy(cases[label]['variants'][lang]['messages'])
            history.extend(messages)
            payload = {'model': 'claude-opus-5' if protocol == 'anthropic' else 'auto',
                       field: history, 'stream': args.stream,
                       'max_output_tokens' if protocol == 'responses' else 'max_tokens': 8192}
            req = urllib.request.Request('http://127.0.0.1:8092' + path,
                json.dumps(payload, ensure_ascii=False).encode(),
                {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
                 'anthropic-version': '2023-06-01', 'X-Gateway-Session-ID': ('ladder-stream-' if args.stream else 'ladder-buffered-') + lang})
            started = time.monotonic()
            status, data, headers = 0, b'', {}
            try:
                with opener.open(req, timeout=args.timeout_seconds) as response:
                    status, data, headers = response.status, response.read(), response.headers
            except urllib.error.HTTPError as error:
                status, data, headers = error.code, error.read(), error.headers
            except OSError:
                pass
            try:
                response = decode_sse(protocol, data) if args.stream and status == 200 else json.loads(data)
            except (ValueError, UnicodeDecodeError):
                response = {}
            complete = bool(response.get('id') and response.get('model'))
            if protocol == 'responses':
                complete = complete and response.get('status') == 'completed'
                if complete: history.extend(response['output'])
            elif protocol == 'chat':
                complete = complete and bool(response.get('choices')) and response['choices'][0].get('finish_reason') == 'stop'
                if complete: history.append(response['choices'][0]['message'])
            else:
                complete = complete and response.get('stop_reason') == 'end_turn'
                if complete: history.append({'role': 'assistant', 'content': response['content']})
            row = {'case': label + '-' + lang, 'protocol': protocol, 'status': status,
                   'ok': status == 200 and complete, 'stream': args.stream, 'model': response.get('model'),
                   'response_id': response.get('id'), 'request_id': headers.get('X-Gateway-Request-ID'),
                   'latency_ms': round((time.monotonic() - started)*1000),
                   'response_sha256': hashlib.sha256(data).hexdigest(), 'usage': response.get('usage')}
            raw = raw_dir / (label + '-' + lang + '.json')
            raw.write_bytes(data)
            raw.chmod(0o600)
            with lock:
                log.write(json.dumps(row, ensure_ascii=False) + '\n')
                log.flush()
                print(json.dumps({k: row[k] for k in ('case', 'status', 'ok', 'model', 'latency_ms')}), flush=True)
            failures += not row['ok']
        return failures

    with ThreadPoolExecutor(max_workers=2) as pool:
        failures = sum(pool.map(run, args.languages))
    log.close()
    print(json.dumps({'requests': len(args.languages) * len(sequence), 'failures': failures, 'scope': 'synthetic_multi_turn_route_and_effort_not_artifact_quality'}), flush=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
