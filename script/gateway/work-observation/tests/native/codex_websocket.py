"""Native Codex WebSocket to an isolated deterministic provider, through observe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import tempfile
import threading
import time

from websockets.sync.server import serve
from websockets.exceptions import ConnectionClosed
from collector_adapter import GatewayFixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(tempfile.mkdtemp(prefix='observation-codex-ws-'))
    profile = root / 'profile'
    profile.mkdir()
    (root / 'fixture.txt').write_text('WS_TOOL_MARKER_431\n')
    requests = []
    canceled_started = threading.Event()

    def provider(connection):
        try:
            for message in connection:
                body = json.loads(message)
                requests.append({'type': body.get('type'), 'sha256': hashlib.sha256(message.encode()).hexdigest(),
                                 'previous_response': bool(body.get('previous_response_id'))})
                if body.get('type') != 'response.create':
                    continue
                params = body.get('response') if isinstance(body.get('response'), dict) else body
                index = len(requests)
                rid = 'resp_ws_fixture_' + str(index)
                items = params.get('input', [])
                text = json.dumps(items)
                last = next((json.dumps(item) for item in reversed(items) if item.get('role') == 'user'), '')
                if 'WS_CANCEL_TRIGGER' in last:
                    canceled_started.set()
                    # The native client closes/abandons the active WS turn.
                    try:
                        connection.recv(timeout=15)
                    except (ConnectionClosed, TimeoutError):
                        return
                    continue
                if 'WS_READ_TOOL' in last and not any(item.get('type') == 'function_call_output' for item in items):
                    output = [{'id': 'fc_ws_'+str(index), 'type': 'function_call', 'call_id': 'call_ws_'+str(index),
                               'name': 'exec_command', 'arguments': json.dumps({'cmd': 'cat '+str(root/'fixture.txt'), 'max_output_tokens': 1000}), 'status': 'completed'}]
                else:
                    output = [{'id': 'msg_'+rid, 'type': 'message', 'role': 'assistant', 'status': 'completed',
                               'content': [{'type': 'output_text', 'text': 'WS_MEMORY_892 WS_TOOL_MARKER_431', 'annotations': [], 'logprobs': []}]}]
                if params.get('generate') is False:
                    output = []
                response = {'id': rid, 'object': 'response', 'created_at': int(time.time()), 'model': 'auto',
                            'status': 'completed', 'output': output, 'usage': {'input_tokens': 20, 'output_tokens': 6, 'total_tokens': 26}}
                connection.send(json.dumps({'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}}))
                for index, item in enumerate(output):
                    connection.send(json.dumps({'type': 'response.output_item.added', 'output_index': index, 'item': item}))
                    connection.send(json.dumps({'type': 'response.output_item.done', 'output_index': index, 'item': item}))
                connection.send(json.dumps({'type': 'response.completed', 'response': response}))
        except ConnectionClosed:
            pass

    origin = serve(provider, '127.0.0.1', 0, max_size=16 << 20, close_timeout=1)
    threading.Thread(target=origin.serve_forever, daemon=True).start()
    proxy = GatewayFixture(root, args.binary, 'http://127.0.0.1:'+str(origin.socket.getsockname()[1]))
    env = {**os.environ, 'CODEX_HOME': str(profile), 'OBSERVATION_FIXTURE_KEY': 'synthetic-ws-fixture'}
    options = {'model': 'auto', 'model_provider': 'observation',
               'model_providers.observation.name': 'Isolated observation fixture',
               'model_providers.observation.base_url': proxy.base+'/v1',
               'model_providers.observation.env_key': 'OBSERVATION_FIXTURE_KEY',
               'model_providers.observation.wire_api': 'responses',
               'model_providers.observation.supports_websockets': True,
               'model_providers.observation.request_max_retries': 0,
               'model_providers.observation.stream_max_retries': 0, 'web_search': 'disabled'}
    cmd = ['codex']
    for key, value in options.items():
        cmd += ['-c', key+'='+json.dumps(value)]
    cmd += ['app-server', '--stdio']
    error_log = (root/'stderr.log').open('w')
    process = subprocess.Popen(cmd, cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=error_log, text=True, bufsize=1, start_new_session=True)
    incoming = queue.Queue()
    events = []
    seq = 0

    def read():
        for line in process.stdout:
            try: incoming.put(json.loads(line))
            except ValueError: pass
    threading.Thread(target=read, daemon=True).start()

    def next_event(deadline):
        row = incoming.get(timeout=max(.1, deadline-time.monotonic()))
        events.append(row)
        return row

    def rpc(method, params):
        nonlocal seq
        seq += 1
        process.stdin.write(json.dumps({'id': seq, 'method': method, 'params': params})+'\n')
        process.stdin.flush()
        deadline = time.monotonic()+40
        while time.monotonic() < deadline:
            row = next_event(deadline)
            if row.get('id') == seq:
                if 'error' in row: raise RuntimeError('native_rpc_error')
                return row['result']
        raise TimeoutError('native_rpc_timeout')

    def finish(thread_id, start):
        deadline = time.monotonic()+50
        while time.monotonic() < deadline:
            for row in events[start:]:
                if row.get('method') == 'turn/completed' and row['params']['threadId'] == thread_id:
                    return row['params']['turn'], events[start:]
            next_event(deadline)
        raise TimeoutError('native_turn_timeout')

    def turn(thread_id, text):
        start = len(events)
        rpc('turn/start', {'threadId': thread_id, 'input': [{'type': 'text', 'text': text, 'text_elements': []}]})
        return finish(thread_id, start)

    def answer(rows):
        return '\n'.join(row.get('params', {}).get('item', {}).get('text', '')
                         for row in rows if row.get('method') == 'item/completed')

    checks = {}
    failure = None
    try:
        rpc('initialize', {'clientInfo': {'name': 'observation_native_ws', 'version': '1'}, 'capabilities': {'experimentalApi': True, 'requestAttestation': False}})
        process.stdin.write('{"method":"initialized","params":{}}\n');process.stdin.flush()
        tid = rpc('thread/start', {'model': 'auto', 'modelProvider': 'observation', 'cwd': str(root),
                                  'ephemeral': True, 'sandbox': 'read-only', 'approvalPolicy': 'never'})['thread']['id']
        result, rows = turn(tid, 'Remember WS_MEMORY_892. Reply with that marker. No tools.')
        checks['native_ws_first_turn'] = result['status'] == 'completed' and 'WS_MEMORY_892' in answer(rows)
        result, rows = turn(tid, 'WS_READ_TOOL: Read fixture.txt with exec_command, then return its exact marker.')
        checks['native_ws_tool_continuation'] = result['status'] == 'completed' and 'WS_TOOL_MARKER_431' in answer(rows) and any(r.get('params', {}).get('item', {}).get('type') == 'commandExecution' for r in rows)
        result, rows = turn(tid, 'Return the original remembered marker. No tools.')
        checks['native_ws_followup'] = result['status'] == 'completed' and 'WS_MEMORY_892' in answer(rows)
        start = len(events)
        active = rpc('turn/start', {'threadId': tid, 'input': [{'type': 'text', 'text': 'WS_CANCEL_TRIGGER: Continue until interrupted. No tools.', 'text_elements': []}]})
        if not canceled_started.wait(15): raise TimeoutError('cancel_request_not_observed')
        rpc('turn/interrupt', {'threadId': tid, 'turnId': active['turn']['id']})
        result, _ = finish(tid, start)
        checks['native_ws_cancel'] = result['status'] == 'interrupted'
        result, rows = turn(tid, 'Return WS_MEMORY_892 after cancellation. No tools.')
        checks['native_ws_resume'] = result['status'] == 'completed' and 'WS_MEMORY_892' in answer(rows)
        checks['actual_websocket_messages'] = len(requests) >= 5
    except Exception as error:
        failure = type(error).__name__
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL);process.wait()
        error_log.close()
        (root/'events.json').write_text(json.dumps(events))
        proxy.close()
        origin.shutdown()
        result = {'scope': 'native Codex WS through collector to synthetic provider', 'checks': checks,
                  'passed': bool(checks) and all(checks.values()) and failure is None, 'error_type': failure,
                  'websocket_requests': len(requests), 'production_changed': False}
        (root/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result));print('RESULT_ROOT='+str(root))


if __name__ == '__main__':
    main()
