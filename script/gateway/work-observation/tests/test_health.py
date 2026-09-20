import importlib.util
from pathlib import Path
from datetime import datetime, timezone
import unittest

spec=importlib.util.spec_from_file_location('health',Path(__file__).parents[1]/'tools/health.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)


class Health(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,9,17,10,tzinfo=timezone.utc)
        self.status={'started_at':'boot-a','updated_at':self.now.isoformat(),'capture_enabled':True,
            'captured':100,'written':99,'dropped':1,'queue_limit_bytes':1000,'queued_bytes':0}
    def test_count_new_loss_not_historical_loss(self):
        r=h.evaluate(self.status,{**self.status,'dropped':0},self.now,10<<30)
        self.assertEqual(r['issues'][0],{'reason':'dropped','new_count':1})
        self.assertFalse(r['complete_capture_claim'])
        r=h.evaluate(self.status,self.status,self.now,10<<30)
        self.assertEqual(r['status'],'ok');self.assertIsNone(r['complete_capture_claim'])
    def test_restart_not_negative_delta(self):
        r=h.evaluate({**self.status,'started_at':'boot-b','captured':2,'written':2,'dropped':0},self.status,self.now,10<<30)
        self.assertTrue(r['process_changed']);self.assertEqual(r['delta']['captured'],2)
    def test_queue_disk_stale_are_visible(self):
        r=h.evaluate({**self.status,'queued_bytes':900,'updated_at':'2026-09-17T09:00:00Z'},self.status,self.now,100)
        self.assertEqual({i['reason'] for i in r['issues']},{'queue_pressure','stale_status','filesystem_low_space'})
    def test_disabled_never_claims_complete(self):
        r=h.evaluate({**self.status,'capture_enabled':False},self.status,self.now,10<<30)
        self.assertFalse(r['complete_capture_claim'])
    def test_startup_failure_counts_uncaptured_forwarded_requests(self):
        status={**self.status,'capture_enabled':False,'capture_unavailable':'capture_store_unavailable',
                'unavailable_bypassed_requests':7}
        result=h.evaluate(status,{},self.now,10<<30)
        self.assertEqual(result['issues'][0]['new_bypassed_requests'],7)
        self.assertEqual(result['status'],'degraded')


if __name__=='__main__':unittest.main()
