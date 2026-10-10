"""Credential-source checks use only fictional accounts and temporary files."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import candidate_accept as accept
import candidate_migrate as migrate
import candidate_monitor_v2 as monitor
import customer_passwords as passwords


EMAIL = 'customer@example.invalid'
PASSWORD = 'fictional-credential-for-tests'


class CustomerPasswordFileTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.path = self.directory / 'passwords.json'
        self.path.write_text(json.dumps({EMAIL: PASSWORD}))
        self.path.chmod(0o600)

    def test_private_file_and_explicit_path_override(self):
        with patch.dict(os.environ, {passwords.PATH_ENV: '/missing/operator-file.json'}):
            self.assertEqual(passwords.customer_password(EMAIL, self.path), PASSWORD)
        self.path.chmod(0o400)
        self.assertEqual(passwords.customer_password(EMAIL, self.path), PASSWORD)

    def test_environment_override(self):
        with patch.dict(os.environ, {passwords.PATH_ENV: str(self.path)}):
            self.assertEqual(passwords.customer_password(EMAIL), PASSWORD)

    def test_missing_file_does_not_derive_a_password(self):
        self.path.unlink()
        with self.assertRaisesRegex(passwords.CustomerPasswordError, 'is missing'):
            passwords.customer_password(EMAIL, self.path)

    def test_relative_or_empty_path_rejected(self):
        for path in ('passwords.json', ''):
            with self.subTest(path=path), self.assertRaisesRegex(
                    passwords.CustomerPasswordError, 'absolute path'):
                passwords.customer_password(EMAIL, path)

    def test_symlink_and_redirected_parent_rejected(self):
        link = self.directory / 'linked.json'
        link.symlink_to(self.path)
        parent = self.directory / 'linked-directory'
        parent.symlink_to(self.directory, target_is_directory=True)
        for path in (link, parent / self.path.name):
            with self.subTest(path=path.name), self.assertRaisesRegex(
                    passwords.CustomerPasswordError, 'symlinks'):
                passwords.customer_password(EMAIL, path)

    def test_non_regular_file_rejected_without_opening_it(self):
        with self.assertRaisesRegex(passwords.CustomerPasswordError, 'regular file'):
            passwords.customer_password(EMAIL, self.directory)

    def test_other_operator_owner_rejected(self):
        different_uid = os.geteuid() + 1
        with patch.object(passwords.os, 'geteuid', return_value=different_uid), \
                self.assertRaisesRegex(passwords.CustomerPasswordError, 'owned by this operator'):
            passwords.customer_password(EMAIL, self.path)

    def test_group_or_other_access_rejected(self):
        for mode in (0o640, 0o604, 0o620, 0o601):
            self.path.chmod(mode)
            with self.subTest(mode=mode), self.assertRaisesRegex(
                    passwords.CustomerPasswordError, 'group or other permissions'):
                passwords.customer_password(EMAIL, self.path)

    def test_read_failure_is_safe(self):
        with patch.object(passwords.os, 'open', side_effect=PermissionError('private detail')), \
                self.assertRaisesRegex(passwords.CustomerPasswordError, 'cannot be read safely') as error:
            passwords.customer_password(EMAIL, self.path)
        self.assertNotIn('private detail', str(error.exception))
        self.assertTrue(error.exception.__suppress_context__)

    def test_invalid_missing_or_short_values_never_appear_in_errors(self):
        examples = [
            ('{' + PASSWORD, 'valid UTF-8 JSON'),
            (json.dumps([]), 'email-to-password object'),
            (json.dumps({EMAIL: 'tiny'}), 'shorter than six'),
            (json.dumps({EMAIL: 123456}), 'invalid email-to-password entry'),
            (json.dumps({'other@example.invalid': PASSWORD}), 'no entry'),
            ('{"customer@example.invalid":"first-fictional",'
             '"customer@example.invalid":"second-fictional"}', 'duplicate entries'),
        ]
        for content, reason in examples:
            self.path.write_text(content)
            with self.subTest(reason=reason), self.assertRaisesRegex(
                    passwords.CustomerPasswordError, reason) as error:
                passwords.customer_password(EMAIL, self.path)
            self.assertNotIn(EMAIL, str(error.exception))
            self.assertNotIn(PASSWORD, str(error.exception))
            self.assertTrue(error.exception.__suppress_context__)

    def test_oversized_file_rejected(self):
        self.path.write_bytes(b' ' * (passwords.MAX_BYTES + 1))
        with self.assertRaisesRegex(passwords.CustomerPasswordError, 'size limit'):
            passwords.customer_password(EMAIL, self.path)


class CreationAndLoginSourceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'ops').mkdir()
        (self.root / 'ops' / 'migration-baseline.json').write_text('{}')
        (self.root / 'ops' / 'migration-state.json').write_text(
            json.dumps({'users': {'100': 5}, 'groups': {'fixture': 700}}))
        self.row = dict(login_email=EMAIL, api_key_id='100', resource_group='fixture')

    def test_new_user_missing_password_fails_before_any_api_write(self):
        with patch.multiple(migrate, ROOT=self.root), \
                patch.object(migrate, 'roster', return_value=[self.row]), \
                patch.object(migrate, 'all_items', return_value=[]), \
                patch.object(migrate, 'api') as api, \
                patch.object(migrate, 'customer_password',
                             side_effect=passwords.CustomerPasswordError('private file missing')):
            with self.assertRaises(passwords.CustomerPasswordError):
                migrate.configure()
            api.assert_not_called()

    def test_existing_user_configuration_does_not_request_password(self):
        with patch.multiple(migrate, ROOT=self.root), \
                patch.object(migrate, 'roster', return_value=[self.row]), \
                patch.object(migrate, 'all_items', side_effect=[
                    [{'email': EMAIL}], RuntimeError('reached group configuration')]), \
                patch.object(migrate, 'customer_password') as private:
            with self.assertRaisesRegex(RuntimeError, 'reached group configuration'):
                migrate.configure()
            private.assert_not_called()

    def test_initial_login_uses_exact_supplied_password(self):
        with patch.multiple(accept, ROOT=self.root), \
                patch.object(accept, 'roster', return_value=[self.row]), \
                patch.object(accept, 'customer_password', return_value=PASSWORD), \
                patch.object(accept, 'request', return_value=(200, {
                    'code': 0, 'data': {'access_token': 'fictional-session'}}, b'')) as request, \
                patch.object(accept, 'native', side_effect=[{'id': 5}, {
                    'platform_quotas': [{'platform': 'openai', 'weekly_limit_usd': 300}]}]), \
                patch.object(accept, 'record') as record, patch.object(accept.time, 'sleep'):
            accept.login_all()
            self.assertEqual(request.call_args[0][2], {'email': EMAIL, 'password': PASSWORD})
            self.assertNotIn(PASSWORD, repr(record.call_args))

    def test_missing_password_never_attempts_initial_login(self):
        with patch.multiple(accept, ROOT=self.root), \
                patch.object(accept, 'roster', return_value=[self.row]), \
                patch.object(accept, 'customer_password',
                             side_effect=passwords.CustomerPasswordError('private file missing')), \
                patch.object(accept, 'request') as request:
            with self.assertRaises(passwords.CustomerPasswordError):
                accept.login_all()
            request.assert_not_called()

    def test_every_customer_creation_or_initial_login_path_uses_private_source(self):
        expected = {'candidate_migrate.py': ['configure'],
                    'candidate_accept.py': ['panel', 'login_all'],
                    'candidate_monitor_v2.py': ['verify'],
                    'candidate_portal.py': ['verify'],
                    'cutover_accept_server.py': ['portal']}
        directory = Path(__file__).resolve().parent
        for filename, names in expected.items():
            tree = ast.parse((directory / filename).read_text())
            functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
            for name in names:
                with self.subTest(filename=filename, function=name):
                    calls = [node for node in ast.walk(functions[name]) if isinstance(node, ast.Call)]
                    self.assertTrue(any(isinstance(call.func, ast.Name)
                                        and call.func.id == 'customer_password' for call in calls))
                    # Email/name splitting must never reconstruct a login password.
                    self.assertFalse(any(isinstance(call.func, ast.Attribute)
                                         and call.func.attr in ('split', 'partition') for call in calls))

    def test_cutover_rpc_imports_helper_only_after_entering_ops_directory(self):
        source = Path(__file__).resolve().parent
        ops = self.root / 'ops'
        cutover = ops / 'cutover'
        cutover.mkdir()
        for filename in ('cutover_accept_server.py', 'cutover_control.py', 'cutover_merge.py'):
            shutil.copyfile(str(source / filename), str(cutover / filename))
        shutil.copyfile(str(source / 'customer_passwords.py'), str(ops / 'customer_passwords.py'))
        # Match deployment: RPC scripts in ops/cutover, candidate dependencies
        # one level up in ops. Isolated Python cannot fall back to this checkout.
        code = """import pathlib, sys, types
sys.path.insert(0, sys.argv[1])
import cutover_accept_server as server
assert 'customer_passwords' not in sys.modules
server.ROOT = pathlib.Path(sys.argv[2])
server.context = lambda: {'samples': []}
candidate = types.ModuleType('candidate_accept')
candidate.login = candidate.native = candidate.request = lambda *a, **kw: None
sys.modules['candidate_accept'] = candidate
assert server.portal() == {'passed': True, 'samples': []}
assert pathlib.Path(sys.modules['customer_passwords'].__file__).parent == server.ROOT / 'ops'
"""
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(cutover), str(self.root)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class MonitoringCredentialBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / 'ops').mkdir()
        (self.root / 'ops' / 'migration-baseline.json').write_text('{"keys": []}')
        self.state = self.root / 'monitor-state.json'
        self.state.write_text('{}')
        self.rows = [dict(api_key_id=str(100 + index), resource_group='group' + str(index % 8),
                          login_email='customer{}@example.invalid'.format(index)) for index in range(74)]
        self.keep = {'groups': {'group' + str(index): 700 + index for index in range(8)},
                     'users': {row['api_key_id']: 5 + index for index, row in enumerate(self.rows)}}
        self.tokens = {group: group + '.payload.signature' for group in self.keep['groups']}

    def admin_api(self, method, path):
        self.assertEqual(method, 'GET')
        if path.endswith('/settings'):
            return dict(channel_monitor_enabled=True, channel_monitor_mode='v2',
                        channel_monitor_hide_user_ranking=True, channel_monitor_hide_throughput=True)
        if path.endswith('/config'):
            return dict(enabled=True, refresh_interval_seconds=300, group_ids=list(self.keep['groups'].values()),
                        platforms=[dict(platform=name, enabled=True) for name in ('openai', 'deepseek')])
        if '/dimensions?' in path:
            return {'groups': [{'id': gid} for gid in self.keep['groups'].values()]}
        return {'metrics': {'ttft': {'sample_count': 1, 'p50_ms': 1},
                            'duration': {'sample_count': 1}}, 'coverage': {}}

    def customer_api(self, method, path, token=None):
        self.assertEqual(method, 'GET')
        group = next(name for name, value in self.tokens.items() if value == token)
        gid = self.keep['groups'][group]
        row = next(row for row in self.rows if row['resource_group'] == group)
        if path.endswith('/profile'):
            return {'id': self.keep['users'][row['api_key_id']], 'role': 'user'}
        if '/dimensions?' in path:
            return {'groups': [{'id': gid}], 'platforms': [{'value': name} for name in ('openai', 'deepseek')]}
        if '/models?' in path:
            return {'items': [{'model': name, 'platform': 'deepseek'}
                              for name in ('deepseek-flash', 'deepseek-v4-pro')]}
        if '/snapshot?' in path:
            return {'config': {}, 'metrics': {metric: {field: None for field in
                    ('p50_ms', 'p90_ms', 'p95_ms', 'avg_ms')} for metric in ('ttft', 'duration')}}
        return {'items': []}

    def verify(self, **options):
        quotas = [dict(user_id=uid, platform='openai', daily_limit_usd=None,
                       weekly_limit_usd=300, monthly_limit_usd=None) for uid in self.keep['users'].values()]
        allowed = [dict(user_id=self.keep['users'][row['api_key_id']],
                        group_id=self.keep['groups'][row['resource_group']]) for row in self.rows]
        with patch.multiple(monitor, ROOT=self.root, STATE=self.state), \
                patch.object(monitor, 'migration', return_value=self.keep), \
                patch.object(monitor, 'api', side_effect=self.admin_api), \
                patch.object(monitor, 'all_items', return_value=[]), \
                patch.object(monitor, 'roster', return_value=self.rows), \
                patch.object(monitor, 'user_snapshot', return_value=[]), \
                patch.object(monitor, 'key_inventory', return_value=[]), \
                patch.object(monitor, 'validate_runtime_customers', return_value={'customers': 74}), \
                patch.object(monitor, 'sql_json', side_effect=[quotas, 0, allowed]), \
                patch.object(monitor, 'certified_history', return_value={'usage_max_id': 0, 'usage_totals': []}), \
                patch.object(monitor, 'usage_totals', return_value=[]), \
                patch.object(monitor, 'native', side_effect=self.customer_api), \
                patch.object(monitor, 'record') as record:
            monitor.verify(**options)
            return record.call_args[0][1]

    def test_regular_verification_needs_no_password_or_customer_login(self):
        with patch.object(monitor, 'customer_password') as private, patch.object(monitor, 'login') as login:
            self.assertFalse(self.verify()['customer_api_verified'])
            private.assert_not_called()
            login.assert_not_called()

    def test_valid_sessions_never_fall_back_to_passwords(self):
        path = self.root / 'sessions.json'
        path.write_text(json.dumps(self.tokens))
        path.chmod(0o600)
        with patch.object(monitor, 'customer_password') as private, patch.object(monitor, 'login') as login:
            result = self.verify(sessions=str(path))
            self.assertTrue(result['customer_api_verified'])
            self.assertEqual(len(result['samples']), 8)
            private.assert_not_called()
            login.assert_not_called()

    def test_incomplete_sessions_fail_without_password_fallback(self):
        path = self.root / 'sessions.json'
        path.write_text(json.dumps({'group0': self.tokens['group0']}))
        path.chmod(0o600)
        with patch.object(monitor, 'customer_password') as private, patch.object(monitor, 'login') as login:
            with self.assertRaisesRegex(RuntimeError, 'session group coverage differs'):
                self.verify(sessions=str(path))
            private.assert_not_called()
            login.assert_not_called()

    def test_only_explicit_initial_logins_use_supplied_passwords(self):
        def login(email, password):
            self.assertEqual(password, PASSWORD)
            row = next(row for row in self.rows if row['login_email'] == email)
            return self.tokens[row['resource_group']]
        with patch.object(monitor, 'customer_password', return_value=PASSWORD) as private, \
                patch.object(monitor, 'login', side_effect=login):
            self.assertEqual(len(self.verify(initial_logins=True)['samples']), 8)
            self.assertEqual(private.call_count, 8)


if __name__ == '__main__':
    unittest.main()
