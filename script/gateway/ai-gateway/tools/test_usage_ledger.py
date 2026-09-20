import json
import os
from pathlib import Path
import tempfile
import unittest

from usage_ledger import Ledger


class UsageLedgerTests(unittest.TestCase):
    def event(self, **changes):
        value = dict(at='2026-09-16T01:00:00.000000001Z', region='tokyo', api_key_id='key-hmac-v1:fixture',
                     request_id='r1', purpose='business', effective_model='gpt-5.6-terra',
                     effective_reasoning_effort='low', attempt=True, success=True,
                     input_tokens=10, cache_hit_tokens=6, cache_miss_tokens=4, output_tokens=2)
        value.update(changes)
        return (json.dumps(value) + '\n').encode()

    def test_replay_rotation_restart_and_numeric_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); spool = root/'usage.jsonl'; db = root/'usage.sqlite'
            spool.write_bytes(self.event() + self.event(at='2026-09-16T01:00:00.000000002Z', success=False))
            ledger = Ledger(db)
            self.assertEqual(ledger.ingest(spool)['inserted'], 2)
            ledger.close()
            ledger = Ledger(db)
            self.assertEqual(ledger.ingest(spool)['inserted'], 0)
            os.rename(spool, root/'usage.jsonl.1')
            spool.write_bytes(self.event() + self.event(region='us', request_id='r2'))
            self.assertEqual(ledger.ingest(root/'usage.jsonl.1')['inserted'], 0)
            self.assertEqual(ledger.ingest(spool)['inserted'], 1)
            ledger.map_keys([dict(region='tokyo',key_hash='key-hmac-v1:fixture',api_key_id=141)])
            rows = ledger.daily(); tokyo = next(row for row in rows if row['region']=='tokyo')
            self.assertEqual((tokyo['requests'],tokyo['events'],tokyo['attempts'],tokyo['input_tokens'],tokyo['failures'],tokyo['api_key_id']), (1,2,2,20,1,141))
            self.assertIsNone(next(row for row in rows if row['region']=='us')['api_key_id'])
            self.assertEqual(db.stat().st_mode & 0o777, 0o600)
            ledger.close()

    def test_partial_tail_invalid_event_and_cache_accounting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); spool = root/'usage.jsonl'; ledger=Ledger(root/'ledger.sqlite')
            cached=self.event(request_id='cache',attempt=False,response_cache_hit=True,input_tokens=0,cache_hit_tokens=0,cache_miss_tokens=0,output_tokens=0)
            spool.write_bytes(self.event()+cached[:-4])
            self.assertEqual(ledger.ingest(spool),dict(read=1,inserted=1,partial_tail=True))
            with spool.open('ab') as output:output.write(cached[-4:])
            self.assertEqual(ledger.ingest(spool)['inserted'],1)
            row=ledger.daily()[0]
            self.assertEqual((row['attempts'],row['input_tokens'],row['response_cache_hits']), (1,10,1))
            with spool.open('ab') as output:output.write(self.event(attempt=False))
            with self.assertRaises(ValueError):ledger.ingest(spool)
            self.assertEqual(ledger.daily()[0]['events'],2)
            ledger.close()

    def test_does_not_persist_arbitrary_fields_or_accept_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);spool=root/'usage.jsonl';ledger=Ledger(root/'ledger.sqlite')
            spool.write_bytes(self.event(prompt='PRIVATE BODY MUST NOT PERSIST',authorization='PRIVATE KEY MUST NOT PERSIST'))
            ledger.ingest(spool)
            raw=ledger.db.execute('SELECT payload FROM events').fetchone()[0]
            self.assertNotIn('PRIVATE',raw)
            spool.write_bytes(self.event())
            with self.assertRaises(ValueError):ledger.ingest(spool)
            ledger.close()


if __name__=='__main__':unittest.main()
