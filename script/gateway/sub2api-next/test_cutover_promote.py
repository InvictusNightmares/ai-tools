import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cutover_promote as promote


class ActivationRenderingTest(unittest.TestCase):
    def test_activation_renders_postgres_exception_and_weekly_reset(self):
        ids = list(range(1, 9))
        source = [{'id': i, 'credentials': {'access_token': 'test-access', 'refresh_token': 'test-refresh',
                   'chatgpt_account_id': 'upstream-' + str(i)}} for i in ids]
        identities = [{'id': i, 'account_identity': 'upstream-' + str(i)} for i in ids]
        queries = []

        def database(name, query, source=False):
            queries.append(query)
            return json.dumps(accounts) if query.startswith('SELECT json_agg(json_build_object') else ''

        accounts = source
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ops = root / 'ops' / 'cutover'
            ops.mkdir(parents=True)
            for name in ('final-a-dump.json', 'final-b-dump.json', 'final-restore.json', 'final-core.json', 'final-v2.json'):
                (ops / name).write_text(json.dumps({'freeze_id': 'test-freeze', 'phase': 'local_snapshot_completed'}))
            with patch.multiple(promote, ROOT=root, OPS=ops), \
                    patch.object(promote, 'stopped'), \
                    patch.object(promote, 'state', return_value={'stage': 'frozen', 'freeze_id': 'test-freeze'}), \
                    patch.object(promote, 'value', side_effect=[True, ids, identities, {'usage_max_id': 100, 'usage_totals': []}]), \
                    patch.object(promote, 'sql', side_effect=database), \
                    patch.object(promote, 'run'), patch.object(promote, 'save'), patch.object(promote, 'report'):
                promote.customize()
        activation = next(q for q in queries if q.startswith('BEGIN;'))
        self.assertIn("RAISE EXCEPTION '%',msg", activation)
        self.assertIn('weekly_usage_usd=0', activation)
        self.assertIn("date_trunc('week',now())", activation)


if __name__ == '__main__':
    unittest.main()
