"""Regression cases for runtime checks after legitimate customer activity."""
import copy
import unittest

from candidate_monitor_v2 import validate_runtime_customers, volume_fields_visible, normalize_sessions


class RuntimeCustomerPolicyTest(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(resource_group='fixture-group-' + str(index % 8),
                          api_key_id=str(100 + index),
                          login_email='customer{}@example.invalid'.format(index))
                     for index in range(74)]
        names = list(dict.fromkeys(r['resource_group'] for r in self.rows))
        self.keep = {'groups': {g: 705+i for i, g in enumerate(names)},
                     'users': {r['api_key_id']: 5+i for i, r in enumerate(self.rows)}}
        self.users = [{'id': 1, 'role': 'admin'}]
        self.keys = []
        for row in self.rows:
            uid, kid = self.keep['users'][row['api_key_id']], int(row['api_key_id'])
            self.users.append(dict(id=uid, email=row['login_email'], role='user', status='active',
                                   balance=100000, concurrency=3, restrict_public_groups=True))
            self.keys.append(dict(id=kid, user_id=uid, group_id=self.keep['groups'][row['resource_group']],
                                  deleted=False, key_digest='fixture-'+str(kid)))
        self.keys += [dict(id=k, user_id=1, group_id=None, deleted=True, key_digest='tombstone')
                      for k in [55, 79, 90]]
        self.original = copy.deepcopy(self.keys)

    def validate(self):
        return validate_runtime_customers(self.users, self.keys, self.rows, self.keep, self.original)

    def test_real_spending_and_new_key_do_not_fail_runtime_policy(self):
        self.users[1]['balance'] = 98765.4321
        extra = dict(self.keys[0], id=1000, key_digest='new-fixture-key')
        self.keys.append(extra)
        result = self.validate()
        self.assertEqual(result['customers'], 74)
        self.assertEqual(result['current_customer_keys'], 75)

    def test_customer_deleted_original_key_does_not_require_restoring_secret(self):
        self.keys[0].update(deleted=True, key_digest='deleted-fixture-key')
        self.assertEqual(self.validate()['surviving_original_customer_keys'], 73)

    def test_role_escalation_fails(self):
        self.users[1]['role'] = 'admin'
        with self.assertRaisesRegex(RuntimeError, 'identity or role'):
            self.validate()

    def test_concurrency_drift_fails(self):
        self.users[1]['concurrency'] = 4
        with self.assertRaisesRegex(RuntimeError, 'concurrency'):
            self.validate()

    def test_cross_group_key_fails(self):
        self.keys[0]['group_id'] = next(g for g in self.keep['groups'].values()
                                      if g != self.keys[0]['group_id'])
        with self.assertRaisesRegex(RuntimeError, 'outside its assigned'):
            self.validate()

    def test_restoring_deleted_technical_key_fails(self):
        next(k for k in self.keys if k['id'] == 90)['deleted'] = False
        with self.assertRaisesRegex(RuntimeError, 'deleted key was restored'):
            self.validate()

    def test_latencies_remain_visible_without_absolute_volume(self):
        self.assertFalse(volume_fields_visible({'metrics': {'request_count': 0,
            'ttft': {'sample_count': 0, 'p50_ms': 1000}, 'success_rate': 1}}))

    def test_nested_sample_count_or_throughput_leak_is_detected(self):
        self.assertTrue(volume_fields_visible({'items': [{'metrics': {'ttft': {'sample_count': 2}}}]}))
        self.assertTrue(volume_fields_visible({'metrics': {'rpm': 0.1}}))

    def test_session_copy_whitespace_is_trimmed(self):
        self.assertEqual(normalize_sessions({'g': '  aaa.bbb.ccc\n'}, ['g']), {'g': 'aaa.bbb.ccc'})

    def test_invalid_session_never_reaches_an_http_header(self):
        with self.assertRaisesRegex(RuntimeError, '^invalid customer session format$'):
            normalize_sessions({'g': 'DUMMY_TOKEN\r\nInjected: value'}, ['g'])


if __name__ == '__main__':
    unittest.main()
