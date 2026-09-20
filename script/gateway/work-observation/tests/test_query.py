from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
import analyze
import query


class Query(unittest.TestCase):
    def test_region_key_filter_is_read_only_and_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'index.sqlite'
            db = analyze.connect(path)
            for region in ('tokyo', 'us'):
                for index in range(2):
                    analyze.ingest(db, {'schema': analyze.SCHEMA, 'id': str(index),
                        'at': '2026-09-17T08:00:00Z', 'region': region, 'ingress': 'fixture',
                        'kind': 'http_exchange', 'protocol': 'responses', 'outcome': 'completed',
                        'version': 'fixture', 'key_hash': 'key', 'agent_hash': 'agent'+str(index),
                        'request': {'input': 'BODY_MUST_NOT_APPEAR'}})
            db.commit()
            result = query.query(path, {'region': 'tokyo', 'key_hash': 'key'}, limit=1)
            self.assertEqual(len(result['events']), 1)
            self.assertTrue(result['has_more'])
            self.assertEqual(result['events'][0]['region'], 'tokyo')
            self.assertNotIn('BODY_MUST_NOT_APPEAR', str(result))
            child = query.query(path, {'region': 'tokyo', 'key_hash': 'key', 'agent_hash': 'agent0'})
            self.assertEqual(len(child['events']), 1)
            self.assertEqual(child['events'][0]['id'], '0')
            empty = query.query(path, {'region': "tokyo' OR 1=1 --"})
            self.assertFalse(empty['events'])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 4)
            with self.assertRaises(ValueError):
                query.query(path, {'key_hash': 'key'})
            db.close()


if __name__ == '__main__':
    unittest.main()
