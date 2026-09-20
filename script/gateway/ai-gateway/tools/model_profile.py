#!/usr/bin/env python3
"""Run bounded file-tool coding tasks against an isolated fixed-model endpoint.

The operator supplies a private historical source copy and trusted build commands.
Models never receive a shell tool, signing material, credentials, or other repos.
Raw transcripts remain private; summaries expose hashes and execution metadata only.
"""
import argparse
import atexit
import base64
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import queue
import shlex
import subprocess
import threading
import time
import urllib.error
import urllib.request


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Workspace:
    def __init__(self, config, evidence):
        self.config = config
        self.root = Path(config['workspace']).resolve()
        self.evidence = evidence
        self.builds = []
        if not self.root.is_dir() or not (self.root / 'EVALUATION_SCOPE.md').is_file():
            raise ValueError('private_evaluation_copy_required')
        if not config.get('read_globs') or not config.get('write_globs'):
            raise ValueError('explicit_file_scope_required')

    def path(self, name, write=False):
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or not path.parts:
            raise ValueError('relative_scoped_path_required')
        target = self.root / path
        if any(part.startswith('.') or part in ('node_modules', 'oh_modules', 'build', 'vendor') for part in path.parts):
            raise ValueError('private_or_generated_path')
        for parent in [target, *target.parents]:
            if parent == self.root:
                break
            if parent.is_symlink():
                raise ValueError('symlink_rejected')
        if not target.resolve().is_relative_to(self.root):
            raise ValueError('path_escape')
        patterns = self.config['write_globs' if write else 'read_globs']
        if not any(fnmatch.fnmatch(path.as_posix(), pattern) for pattern in patterns):
            raise ValueError('outside_declared_file_scope')
        return target

    def files(self):
        result = []
        for path in self.root.rglob('*'):
            if not path.is_file():
                continue
            name = path.relative_to(self.root).as_posix()
            try:
                self.path(name)
            except ValueError:
                continue
            result.append(name)
        return sorted(result)

    def snapshot(self):
        return {name: digest(self.path(name).read_bytes()) for name in self.files()}

    def execute(self, name, args):
        if name == 'list_files':
            pattern = args.get('pattern', '*')
            return [p for p in self.files() if fnmatch.fnmatch(p, pattern)][:800]
        if name == 'read_file':
            path = self.path(args['path'])
            if path.stat().st_size > 256000:
                raise ValueError('file_too_large')
            lines = path.read_text().splitlines()
            start = max(1, int(args.get('start_line', 1)))
            count = max(1, min(240, int(args.get('line_count', 160))))
            return {'total_lines': len(lines), 'lines': [{'number': i + 1, 'text': line} for i, line in enumerate(lines) if start - 1 <= i < start - 1 + count]}
        if name == 'search_text':
            needle = args['text']
            if not isinstance(needle, str) or not needle or len(needle) > 200:
                raise ValueError('invalid_search')
            hits = []
            for file in self.files():
                if self.path(file).stat().st_size > 256000:
                    continue
                try:
                    lines = self.path(file).read_text().splitlines()
                except UnicodeDecodeError:
                    continue
                for i, line in enumerate(lines):
                    if needle in line:
                        hits.append({'path': file, 'line': i + 1, 'text': line[:600]})
                        if len(hits) == 100:
                            return hits
            return hits
        if name in ('replace_text', 'write_file'):
            path = self.path(args['path'], write=True)
            if name == 'replace_text':
                text = path.read_text()
                old, new = args['old_text'], args['new_text']
                if not old or text.count(old) != 1:
                    raise ValueError('replacement_requires_one_exact_match')
                value = text.replace(old, new, 1)
            else:
                value = args['content']
            if not isinstance(value, str) or len(value.encode()) > 256000:
                raise ValueError('invalid_file_content')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
            return {'written': args['path'], 'sha256': digest(path.read_bytes())}
        if name == 'run_checks':
            if len(self.builds) >= 4:
                raise ValueError('check_budget_exhausted')
            results = []
            for index, command in enumerate(self.config.get('checks', [])):
                if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
                    raise ValueError('invalid_operator_check')
                started = time.monotonic()
                try:
                    run = subprocess.run(command, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
                    raw, status = run.stdout, run.returncode
                except subprocess.TimeoutExpired as error:
                    raw, status = error.stdout or b'', 124
                path = self.evidence / ('check-%d-%d.log' % (len(self.builds), index))
                path.write_bytes(raw)
                results.append({'argv': command, 'exit_code': status, 'seconds': round(time.monotonic() - started, 3), 'log_sha256': digest(raw), 'tail': raw.decode(errors='replace')[-10000:]})
            self.builds.append(results)
            return results
        raise ValueError('tool_not_available')


def tool(name, description, properties, required):
    return {'type': 'function', 'function': {'name': name, 'description': description, 'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}}}


S = {'type': 'string'}
TOOLS = [
    tool('list_files', 'List allowed project source files.', {'pattern': S}, []),
    tool('read_file', 'Read numbered project source lines.', {'path': S, 'start_line': {'type': 'integer'}, 'line_count': {'type': 'integer'}}, ['path']),
    tool('search_text', 'Find a literal text in allowed source files.', {'text': S}, ['text']),
    tool('replace_text', 'Replace one exact source occurrence.', {'path': S, 'old_text': S, 'new_text': S}, ['path', 'old_text', 'new_text']),
    tool('write_file', 'Write an allowed source file.', {'path': S, 'content': S}, ['path', 'content']),
    tool('run_checks', 'Run only the operator-defined offline build and behavior checks.', {}, []),
]


class SSHRelay:
    """One exec session per run; never replay a request after uncertain delivery."""

    def __init__(self, args):
        script = '''import base64,json,pathlib,urllib.request,urllib.error,sys
key=pathlib.Path(KEY_PATH).read_text().strip()
client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
print("PROFILE_READY",flush=True)
while True:
 line=sys.stdin.readline((64<<20)+1)
 if not line:break
 if len(line)>(64<<20) or not line.endswith("\\n"):raise RuntimeError("request_too_large")
 wire=json.loads(line);headers=wire["headers"];headers["Authorization"]="Bearer "+key
 req=urllib.request.Request(ENDPOINT,data=base64.b64decode(wire["body"]),headers=headers)
 try:
  with client.open(req,timeout=300) as response:status=response.status;data=response.read(120001)
 except urllib.error.HTTPError as error:status=error.code;data=error.read(120001)
 if len(data)>120000:raise RuntimeError("response_too_large")
 print("PROFILE_RESPONSE="+json.dumps({"status":status,"body":base64.b64encode(data).decode()}),flush=True)
'''.replace('KEY_PATH', repr(args.key_file)).replace('ENDPOINT', repr(args.endpoint))
        self.process = subprocess.Popen(
            ['ssh', '-T', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=10',
             '-o', 'ServerAliveCountMax=2', args.ssh, 'python3 -u -c ' + shlex.quote(script)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1)
        self.lines = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        atexit.register(self.close)
        if self._line(40) != 'PROFILE_READY':
            self.close()
            raise RuntimeError('private_relay_not_ready')

    def _read(self):
        try:
            for line in self.process.stdout:
                self.lines.put(line.rstrip('\n'))
        finally:
            self.lines.put(None)

    def _line(self, timeout):
        try:
            line = self.lines.get(timeout=timeout)
        except queue.Empty:
            self.close()
            raise RuntimeError('private_relay_timeout') from None
        if line is None:
            raise RuntimeError('private_relay_closed')
        return line

    def request(self, raw, headers):
        try:
            self.process.stdin.write(json.dumps({'headers': headers, 'body': base64.b64encode(raw).decode()}) + '\n')
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            raise RuntimeError('private_relay_closed') from None
        line = self._line(330)
        if not line.startswith('PROFILE_RESPONSE='):
            raise RuntimeError('private_relay_invalid_response')
        wire = json.loads(line[len('PROFILE_RESPONSE='):])
        return wire['status'], base64.b64decode(wire['body'])

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


def request(args, payload, sequence):
    raw = json.dumps(payload, ensure_ascii=False).encode()
    headers = {'Content-Type': 'application/json', 'User-Agent': 'ai-gateway-model-profile/1', 'X-Gateway-Session-ID': args.session, 'X-Request-ID': args.session + '-' + str(sequence)}
    if args.ssh:
        # Only framed request data crosses stdin; the Key stays on the host.
        if not hasattr(args, '_relay'):
            args._relay = SSHRelay(args)
        return args._relay.request(raw, headers)
    headers['Authorization'] = 'Bearer ' + Path(args.key_file).read_text().strip()
    req = urllib.request.Request(args.endpoint, data=raw, headers=headers)
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with client.open(req, timeout=300) as response:
            return response.status, response.read(120001)
    except urllib.error.HTTPError as error:
        return error.code, error.read(120001)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--endpoint', required=True)
    ap.add_argument('--key-file', required=True)
    ap.add_argument('--ssh', choices=['qiyuan-gpu'])
    ap.add_argument('--session', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--max-turns', type=int, default=24)
    args = ap.parse_args()
    from urllib.parse import urlparse
    u = urlparse(args.endpoint)
    if u.scheme != 'http' or u.hostname not in ('127.0.0.1', '::1') or u.path != '/v1/chat/completions' or u.username or u.query or u.fragment or not 1 <= args.max_turns <= 40:
        raise ValueError('isolated_loopback_endpoint_required')
    os.umask(0o077)
    args.output.mkdir(mode=0o700)
    config = json.loads(args.config.read_text())
    workspace = Workspace(config, args.output)
    initial = workspace.snapshot()
    messages = [{'role': 'system', 'content': 'You are implementing one authorized coding task in a private historical project copy. Use only the provided file tools. Follow project instructions. Keep the edit minimal, do not change dependencies or build configuration. Run the prescribed checks before concluding. You cannot install, publish, access credentials, or access other workspaces.'}, {'role': 'user', 'content': config['prompt']}]
    records, failure, completed = [], None, False
    started = time.monotonic()
    try:
        for turn in range(args.max_turns):
            if time.monotonic() - started > 1800:
                failure = 'time_limit'
                break
            status, raw = request(args, {'model': 'auto', 'messages': messages, 'tools': TOOLS, 'stream': False, 'max_tokens': 8192}, turn)
            (args.output / ('response-%d.json' % turn)).write_bytes(raw)
            if status != 200:
                failure = 'http_' + str(status)
                break
            reply = json.loads(raw)
            message = reply['choices'][0]['message']
            records.append({'turn': turn, 'response_model': reply.get('model'), 'usage': reply.get('usage'), 'response_sha256': digest(raw)})
            messages.append(message)
            calls = message.get('tool_calls') or []
            if not calls:
                completed = True
                break
            for call in calls:
                try:
                    if call['function']['name'] == 'run_checks' and len(workspace.builds) >= 3:
                        raise ValueError('model_check_budget_exhausted')
                    result = workspace.execute(call['function']['name'], json.loads(call['function']['arguments']))
                except (ValueError, KeyError, OSError, UnicodeError) as error:
                    result = {'error_type': type(error).__name__, 'message': str(error)[:200]}
                messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(result, ensure_ascii=False)})
        if not completed and failure is None:
            failure = 'turn_limit'
    except Exception as error:
        safe_errors = {'private_relay_not_ready', 'private_relay_timeout', 'private_relay_closed', 'private_relay_invalid_response'}
        failure = str(error) if isinstance(error, RuntimeError) and str(error) in safe_errors else type(error).__name__
    finally:
        if hasattr(args, '_relay'):
            args._relay.close()
    final_checks = workspace.execute('run_checks', {})
    final = workspace.snapshot()
    changed = sorted(name for name in set(initial) | set(final) if initial.get(name) != final.get(name))
    (args.output / 'transcript.json').write_text(json.dumps(messages, ensure_ascii=False, indent=2))
    summary = {'scope': 'fixed-model real coding task; not natural Auto selection or device UI', 'candidate': args.candidate, 'task': config['task'], 'source_commit': config.get('source_commit'), 'completed': completed, 'failure': failure, 'seconds': round(time.monotonic()-started, 3), 'changed_files': changed, 'file_sha256': {name: final.get(name) for name in changed}, 'checks': [{k: v for k, v in item.items() if k != 'tail'} for item in final_checks], 'requests': records, 'quality_review_pending': True}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ('task', 'candidate', 'completed', 'failure', 'changed_files')}), flush=True)


if __name__ == '__main__':
    main()
