from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import shlex
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from model_profile import SSHRelay, Workspace


class WorkspaceBoundaries(unittest.TestCase):
    def test_model_tools_stay_inside_declared_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, evidence = root / 'source', root / 'evidence'
            source.mkdir()
            evidence.mkdir()
            (source / 'EVALUATION_SCOPE.md').write_text('private fixture')
            (source / 'src').mkdir()
            (source / 'src/main.kt').write_text('fun value() = 1\n')
            (source / 'build.gradle').write_text('operator owned')
            (root / 'outside.kt').write_text('do not read')
            (source / 'src/linked.kt').symlink_to(root / 'outside.kt')
            config = {'workspace': str(source), 'read_globs': ['src/*.kt', '*.md', 'build.gradle'], 'write_globs': ['src/*.kt'], 'checks': []}
            w = Workspace(config, evidence)
            self.assertEqual(w.execute('read_file', {'path': 'src/main.kt'})['lines'][0]['text'], 'fun value() = 1')
            for name in ['../outside.kt', str(root / 'outside.kt'), 'src/linked.kt', 'src/../../outside.kt', '.env', 'src/.private.kt', 'build/generated.kt']:
                with self.assertRaises(ValueError):
                    w.execute('read_file', {'path': name})
            with self.assertRaises(ValueError):
                w.execute('write_file', {'path': 'build.gradle', 'content': 'modified'})
            with self.assertRaises(ValueError):
                w.execute('shell', {'command': 'anything'})
            with self.assertRaises(ValueError):
                w.execute('replace_text', {'path': 'src/main.kt', 'old_text': '', 'new_text': 'invalid'})
            w.execute('replace_text', {'path': 'src/main.kt', 'old_text': '= 1', 'new_text': '= 2'})
            self.assertEqual((source / 'src/main.kt').read_text(), 'fun value() = 2\n')
            self.assertNotIn('src/linked.kt', w.files())
            self.assertEqual((source / 'build.gradle').read_text(), 'operator owned')

    def test_checks_use_only_operator_argv_and_retain_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'EVALUATION_SCOPE.md').write_text('private fixture')
            evidence = root / 'results'
            evidence.mkdir()
            w = Workspace({'workspace': str(root), 'read_globs': ['*.md'], 'write_globs': ['src/*.kt'], 'checks': [['/usr/bin/true']]}, evidence)
            result = w.execute('run_checks', {'command': '/usr/bin/false'})
            self.assertEqual(result[0]['exit_code'], 0)
            self.assertEqual(result[0]['argv'], ['/usr/bin/true'])
            self.assertTrue((evidence / 'check-0-0.log').exists())
            for _ in range(3):
                w.execute('run_checks', {})
            with self.assertRaises(ValueError):
                w.execute('run_checks', {})


class RelayTransport(unittest.TestCase):
    def test_one_exec_session_preserves_multiple_bodies_and_http_errors(self):
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                seen.append((raw, self.headers.get('Authorization'), self.headers.get('User-Agent')))
                self.send_response(503 if len(seen) == 1 else 200)
                self.end_headers()
                self.wfile.write(json.dumps({'received': len(raw)}).encode())

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        actual_popen = subprocess.Popen
        commands = []

        def local_exec(command, **kwargs):
            commands.append(command)
            parts = shlex.split(command[-1])
            self.assertEqual(parts[:3], ['python3', '-u', '-c'])
            return actual_popen([sys.executable, *parts[1:]], **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / 'key'
            key.write_text('synthetic-relay-test-key')
            args = SimpleNamespace(ssh='qiyuan-gpu', key_file=str(key), endpoint='http://127.0.0.1:' + str(server.server_port) + '/v1/chat/completions')
            with patch('model_profile.subprocess.Popen', side_effect=local_exec):
                relay = SSHRelay(args)
                try:
                    bodies = [b'{"first":true}', json.dumps({'source': '合成源码\n' * 20000}, ensure_ascii=False).encode()]
                    for body, expected in zip(bodies, [503, 200]):
                        status, response = relay.request(body, {'Content-Type': 'application/json', 'User-Agent': 'profile-test/1'})
                        self.assertEqual(status, expected)
                        self.assertEqual(json.loads(response)['received'], len(body))
                    self.assertEqual([row[0] for row in seen], bodies)
                    self.assertTrue(all(row[1:] == ('Bearer synthetic-relay-test-key', 'profile-test/1') for row in seen))
                    self.assertEqual(len(commands), 1)
                    self.assertNotIn('synthetic-relay-test-key', commands[0][-1])
                finally:
                    relay.close()

    def test_lost_response_never_reconnects_or_replays(self):
        actual_popen = subprocess.Popen
        commands = []

        def disconnected_exec(command, **kwargs):
            commands.append(command)
            script = 'import sys; print("PROFILE_READY",flush=True); sys.stdin.readline()'
            return actual_popen([sys.executable, '-u', '-c', script], **kwargs)

        args = SimpleNamespace(ssh='qiyuan-gpu', key_file='/unused/private-key', endpoint='http://127.0.0.1:1/v1/chat/completions')
        with patch('model_profile.subprocess.Popen', side_effect=disconnected_exec):
            relay = SSHRelay(args)
            try:
                with self.assertRaisesRegex(RuntimeError, 'private_relay_closed'):
                    relay.request(b'{}', {})
                self.assertEqual(len(commands), 1)
            finally:
                relay.close()


if __name__ == '__main__':
    unittest.main()
