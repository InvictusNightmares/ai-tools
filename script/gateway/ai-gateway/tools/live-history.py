#!/usr/bin/env python3
"""Exercise real pilot tool rounds; never executes model-proposed tools or code.

Only a loopback pilot is accepted. The token stays in memory, raw provider
responses stay in the private output directory, and evidence contains metadata.
"""
import argparse
import copy
import hashlib
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:8092')
    ap.add_argument('--cases', required=True)
    ap.add_argument('--token-file', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--parallel', type=int, default=2)
    args = ap.parse_args()
    if urllib.parse.urlsplit(args.base).hostname not in ('127.0.0.1', '::1'):
        ap.error('only an isolated loopback pilot is supported')
    token = pathlib.Path(args.token_file).read_text().strip()
    out = pathlib.Path(args.out)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    raw_dir = out / 'private-responses'
    raw_dir.mkdir(mode=0o700)
    cases = {c['id']: c for c in json.loads(pathlib.Path(args.cases).read_text())['cases']}
    log = (out / 'results.jsonl').open('x')
    (out / 'results.jsonl').chmod(0o600)
    lock = Lock()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    paths = {'chat': '/v1/chat/completions', 'responses': '/v1/responses', 'anthropic': '/v1/messages'}

    def record(row):
        with lock:
            log.write(json.dumps(row, ensure_ascii=False) + '\n')
            log.flush()
            print(json.dumps({k: row[k] for k in ('case', 'status', 'ok', 'model', 'latency_ms')}, ensure_ascii=False), flush=True)

    def send(protocol, payload, session, label):
        start = time.monotonic()
        body = json.dumps(payload, ensure_ascii=False).encode()
        req = urllib.request.Request(args.base + paths[protocol], body, {
            'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
            'X-Gateway-Session-ID': session, 'anthropic-version': '2023-06-01'})
        status, data, headers = 0, b'', {}
        try:
            with opener.open(req, timeout=180) as response:
                status, headers, data = response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            status, headers, data = error.code, error.headers, error.read()
        except OSError:
            pass
        try:
            parsed = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            parsed = {}
        complete = bool(parsed.get('id') and parsed.get('model'))
        if protocol == 'chat':
            complete = complete and bool(parsed.get('choices')) and parsed['choices'][0].get('finish_reason') in ('stop', 'tool_calls')
        elif protocol == 'responses':
            complete = complete and parsed.get('status') == 'completed'
        else:
            complete = complete and parsed.get('stop_reason') in ('end_turn', 'tool_use', 'stop_sequence')
        row = {'case': label, 'protocol': protocol, 'requested_model': payload['model'], 'status': status,
               'ok': status == 200 and complete, 'model': parsed.get('model'),
               'response_id': parsed.get('id'), 'request_id': headers.get('X-Gateway-Request-ID'),
               'latency_ms': round((time.monotonic() - start) * 1000),
               'response_sha256': hashlib.sha256(data).hexdigest(), 'usage': parsed.get('usage')}
        if status != 200:
            # Never copy an upstream error body to public evidence.
            row['error'] = 'http_failure' if status else 'transport_failure'
        raw_file = raw_dir / (label + '.json')
        raw_file.write_bytes(data)
        raw_file.chmod(0o600)
        record(row)
        if not row['ok']:
            raise RuntimeError('request_not_completed')
        return parsed

    def assistant_items(protocol, response):
        if protocol == 'responses':
            return response['output']
        if protocol == 'chat':
            return [response['choices'][0]['message']]
        return [{'role': 'assistant', 'content': response['content']}]

    def user_text(body, protocol):
        history = body['input' if protocol == 'responses' else 'messages']
        content = history[-1]['content']
        if isinstance(content, str):
            return content
        return '\n'.join(p.get('text', '') for p in content if p['type'] in ('text', 'input_text'))

    def tool_output(body, protocol):
        history = body['input' if protocol == 'responses' else 'messages']
        for item in reversed(history):
            if item.get('type') == 'function_call_output':
                return item['output']
            if item.get('role') == 'tool':
                return item['content']
            content = item.get('content')
            if isinstance(content, list):
                for part in content:
                    if part.get('type') == 'tool_result':
                        return part['content']
        raise RuntimeError('fixture_tool_output_missing')

    def tool_results(protocol, response, content):
        if protocol == 'chat':
            calls = response['choices'][0]['message'].get('tool_calls', [])
            return [{'role': 'tool', 'tool_call_id': c['id'], 'content': content} for c in calls]
        if protocol == 'responses':
            return [{'type': 'function_call_output', 'call_id': c['call_id'], 'output': content}
                    for c in response['output'] if c['type'] == 'function_call']
        parts = [{'type': 'tool_result', 'tool_use_id': c['id'], 'content': content}
                 for c in response['content'] if c['type'] == 'tool_use']
        return [{'role': 'user', 'content': parts}] if parts else []

    def workflow(item):
        prefix, lang = item
        initial = cases[prefix + '-start']
        protocol = initial['protocol']
        body = copy.deepcopy(initial['variants'][lang])
        body['model'] = {'zh': 'claude-opus-5', 'en': 'claude-sonnet-5', 'mixed': 'claude-haiku-4'}[lang] if protocol == 'anthropic' else 'auto'
        body['stream'] = False
        body['max_output_tokens' if protocol == 'responses' else 'max_tokens'] = 2048
        field = 'input' if protocol == 'responses' else 'messages'
        session = 'history-' + prefix + '-' + lang
        label = prefix + '-' + lang
        # A real model-generated tool call and ID, followed by a fixture result.
        # No suggested shell command is executed.
        body['tool_choice'] = ({'type': 'tool', 'name': 'Read'} if protocol == 'anthropic' else
                               {'type': 'function', 'name': 'Read'} if protocol == 'responses' else
                               {'type': 'function', 'function': {'name': 'Read'}})
        response = send(protocol, body, session, label + '-start')
        results = tool_results(protocol, response, tool_output(cases[prefix + '-tool_result']['variants'][lang], protocol))
        if not results:
            record({'case': label + '-tool_contract', 'status': 200, 'ok': False, 'model': response.get('model'), 'latency_ms': 0})
            raise RuntimeError('tool_contract_missing')
        body[field].extend(assistant_items(protocol, response))
        body[field].extend(results)
        body['tool_choice'] = {'type': 'none'} if protocol == 'anthropic' else 'none'
        response = send(protocol, body, session, label + '-tool_result')
        body[field].extend(assistant_items(protocol, response))
        for phase in ('correction', 'new_task'):
            body[field].append({'role': 'user', 'content': user_text(cases[prefix + '-' + phase]['variants'][lang], protocol)})
            response = send(protocol, body, session, label + '-' + phase)
            body[field].extend(assistant_items(protocol, response))

    jobs = [(prefix, lang) for prefix in ('logout', 'startup', 'release', 'reminder') for lang in ('zh', 'en', 'mixed')]
    failed = 0
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        for result in pool.map(run_workflow_safely, [(workflow, item) for item in jobs]):
            failed += not result
    log.close()
    print(json.dumps({'workflows': len(jobs), 'failed_workflows': failed, 'scope': 'real_guard_auto_business_with_reconstructed_tool_results_not_full_client_or_artifact_acceptance'}), flush=True)
    return int(failed > 0)


def run_workflow_safely(args):
    workflow, item = args
    try:
        workflow(item)
        return True
    except Exception as error:
        # Type only: no raw URL, credentials, prompt or provider error text.
        print(json.dumps({'workflow': '-'.join(item), 'failure_type': type(error).__name__}), flush=True)
        return False


if __name__ == '__main__':
    raise SystemExit(main())
