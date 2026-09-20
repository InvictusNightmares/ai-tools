import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import datetime
import threading

from gateway_ops import histogram_p95,log_maintenance,rotate,run,run_usage,read_usage_status,atomic_json
from usage_ledger import Ledger


class GatewayOpsTests(unittest.TestCase):
    def test_health_does_not_wait_for_blocked_exporter(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);started=threading.Event();release=threading.Event()
            def blocked(*args):
                started.set()
                if not release.wait(5):raise TimeoutError('fixture_timeout')
                return {'remaining':0}
            status={'alerts':[],'components':{}}
            with patch('gateway_ops.usage_sync.run',side_effect=blocked),patch('gateway_ops.inspect',return_value=status),patch('gateway_ops.log_maintenance',return_value={}),patch('builtins.print'):
                worker=threading.Thread(target=run_usage,args=(root,'tokyo'));worker.start()
                try:
                    self.assertTrue(started.wait(2))
                    began=time.monotonic();observed=run(root,'tokyo')
                    self.assertLess(time.monotonic()-began,1)
                    self.assertTrue(worker.is_alive())
                    self.assertEqual(observed['usage_sync']['status'],'running')
                    self.assertIn('usage_export_pending',[row['code'] for row in observed['alerts']])
                finally:release.set();worker.join(5)
            self.assertFalse(read_usage_status(root/'ops')[1])

    def test_usage_status_warns_missing_stale_failed_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            ops=Path(directory)
            self.assertTrue(read_usage_status(ops)[1])
            now=datetime.datetime.now(datetime.timezone.utc)
            for status,stamp,pending in [('completed',now,False),('running',now,False),('failed',now,True),('running',now-datetime.timedelta(seconds=181),True)]:
                atomic_json(ops/'usage-status.json',{'status':status,'remaining':0,'last_completed_at':stamp.isoformat()})
                self.assertEqual(read_usage_status(ops)[1],pending)
            (ops/'usage-status.json').write_text('{broken')
            self.assertTrue(read_usage_status(ops)[1])

    def test_export_failure_retains_last_completion_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'ops').mkdir()
            stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
            atomic_json(root/'ops/usage-status.json',{'status':'completed','last_completed_at':stamp})
            with patch('gateway_ops.usage_sync.run',side_effect=OSError('private detail')),patch('builtins.print'):
                result=run_usage(root,'us')
            self.assertEqual(result['last_completed_at'],stamp)
            self.assertEqual(result['error_type'],'OSError')
            self.assertNotIn('private detail',json.dumps(result))
            self.assertTrue(read_usage_status(root/'ops')[1])
            with patch('gateway_ops.usage_sync.run',return_value={'remaining':0}),patch('builtins.print'):
                run_usage(root,'us')
            self.assertFalse(read_usage_status(root/'ops')[1])

    def test_histogram_window_and_restart(self):
        old={'lat_count':100,'lat_bucket{le="100"}':80,'lat_bucket{le="300"}':100}
        now={'lat_count':120,'lat_bucket{le="100"}':90,'lat_bucket{le="300"}':120}
        self.assertEqual(histogram_p95(now,old,'lat'),300)
        self.assertIsNone(histogram_p95(old,now,'lat'))

    def test_rotation_keeps_bytes_owner_and_new_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'usage.jsonl';content=b'{"n":1}\n'*5;path.write_bytes(content)
            self.assertTrue(rotate(path,1,False));self.assertEqual(path.read_bytes(),content)
            self.assertTrue(rotate(path,1,True));self.assertEqual(path.read_bytes(),b'')
            archived=[p for p in path.parent.glob('usage.jsonl.*') if not p.name.endswith('.lock')]
            self.assertEqual(len(archived),1);self.assertEqual(archived[0].read_bytes(),content)
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            path.unlink();path.symlink_to(archived[0])
            with self.assertRaises(ValueError):rotate(path,1,True)

    def test_retention_retains_unexported_usage_and_default_retains_all(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'logs/auto';folder.mkdir(parents=True);(root/'ops').mkdir()
            active=folder/'usage.jsonl';active.write_text('')
            archive=folder/'usage.jsonl.20260101T000000.1'
            row=dict(at='2026-01-01T00:00:00Z',region='tokyo',api_key_id='key-hmac-v1:test',effective_model='fixture',attempt=True,success=True)
            archive.write_text(json.dumps(row)+'\n');os.utime(archive,(time.time()-100*86400,)*2)
            ledger=Ledger(root/'ops/usage-ledger.sqlite');ledger.ingest(archive)
            log_maintenance(root,'tokyo',True,30);self.assertTrue(archive.exists())
            with ledger.db:ledger.db.execute('UPDATE events SET exported=1')
            ledger.close()
            log_maintenance(root,'tokyo',True,None);self.assertTrue(archive.exists())
            result=log_maintenance(root,'tokyo',True,30);self.assertFalse(archive.exists());self.assertEqual(result['deleted'],1)


if __name__=='__main__':unittest.main()
