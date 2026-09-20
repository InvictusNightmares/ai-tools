import importlib.util
from pathlib import Path
from datetime import datetime, timezone
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('analyze',Path(__file__).parents[1]/'tools/analyze.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


class Analysis(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=a.connect(Path(self.tmp.name)/'analysis.db')
        self.event={'schema':a.SCHEMA,'id':'r1','at':'2026-09-17T08:00:00Z','region':'tokyo',
            'ingress':'4000','kind':'http_exchange','protocol':'responses','outcome':'completed',
            'version':'test','client':'codex','request':{'model':'synthetic','input':'DO_NOT_STORE_BODY'},
            'status':200,'key_hash':'key-a','session_hash':'session-a','association':'verified_session'}
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def summary(self):
        return a.report(self.db,datetime(2026,9,17,9,tzinfo=timezone.utc))
    def test_http_success_not_task_success_or_zero_cost(self):
        a.ingest(self.db,self.event);r=self.summary()
        self.assertEqual(r['evidence_quality'],{'unknown':1});self.assertEqual(r['cost_unknown_events'],1)
        self.assertEqual(r['usage_unknown_events'],1);self.assertIsNone(r['first_byte_p95_ms'])
        self.assertNotIn('DO_NOT_STORE_BODY',''.join(self.db.iterdump()))
    def test_idempotent_and_later_cost_enrichment(self):
        self.assertEqual(a.ingest(self.db,self.event),1);self.assertEqual(a.ingest(self.db,self.event),0)
        enriched={**self.event,'billing':{'match':'verified','currency':'USD','cost_usd':.07}}
        self.assertEqual(a.ingest(self.db,enriched),1);a.ingest(self.db,self.event)
        r=self.summary();self.assertEqual(r['events'],1);self.assertEqual(r['known_cost_usd'],.07)
        self.assertEqual(r['cost_unknown_events'],0)
    def test_final_stream_usage_not_sum_of_snapshots(self):
        e={**self.event,'response':[{'usage':{'input_tokens':9,'output_tokens':1}},
           {'response':{'usage':{'input_tokens':9,'output_tokens':4}}}]}
        a.ingest(self.db,e);r=self.summary()
        self.assertEqual(r['input_tokens_known'],9);self.assertEqual(r['output_tokens_known'],4)
    def test_sse_envelope_usage_and_ws_observation_are_not_false_failures(self):
        event={**self.event,'kind':'websocket_message','outcome':'observed','duration_ms':-1,'first_byte_ms':-1,
            'response':[{'_capture_transport':'sse','data':{'response':{'usage':{'input_tokens':8,'output_tokens':3}}}},
                        {'_capture_transport':'sse','data':'[DONE]'}]}
        a.ingest(self.db,event);r=self.summary()
        self.assertEqual(r['input_tokens_known'],8);self.assertEqual(r['output_tokens_known'],3)
        self.assertFalse(r['investigation_candidates']);self.assertEqual(r['latency_samples'],0)
    def test_http_200_api_failure_is_visible_without_treating_quoted_error_as_failure(self):
        e={**self.event,'response':[{'_capture_transport':'sse','data':{'type':'response.failed','response':{'error':{'code':'fixture'}}}}]}
        a.ingest(self.db,e);self.assertEqual(self.summary()['outcomes'],{'model_error':1})
        self.assertIsNone(a.api_failure({'output':[{'content':'{"error":{"code":"quoted"}}'}]}))
    def test_anthropic_input_and_output_usage_across_separate_events(self):
        response=[{'_capture_transport':'sse','data':{'type':'message_start','message':{'usage':{'input_tokens':4000,'output_tokens':0}}}},
                  {'_capture_transport':'sse','data':{'type':'message_delta','usage':{'output_tokens':30}}},
                  {'_capture_transport':'sse','data':{'type':'message_stop'}}]
        self.assertEqual(a.usage(response),(4000,30))
    def test_ws_provisional_usage_not_double_counted_as_another_call(self):
        for n,kind in enumerate(('response.created','response.completed')):
            a.ingest(self.db,{**self.event,'id':'ws'+str(n),'kind':'websocket_message','outcome':'observed',
                'response':{'type':kind,'response':{'usage':{'input_tokens':4000,'output_tokens':30}}}})
        self.assertEqual(self.summary()['input_tokens_known'],4000)
        self.assertEqual(self.summary()['output_tokens_known'],30)
    def test_requested_reported_model_and_ws_connection_latency_separate(self):
        a.ingest(self.db,{**self.event,'duration_ms':100,'first_byte_ms':20,
            'response':{'object':'response','id':'resp_fixture','model':'reported-fixture'}})
        a.ingest(self.db,{**self.event,'id':'wsconn','kind':'websocket_connection','duration_ms':600000,'first_byte_ms':10})
        report=self.summary()
        self.assertEqual(report['total_p95_ms'],100)
        self.assertEqual(report['latency_samples'],1)
        self.assertEqual(report['latency_by_event_kind']['websocket_connection']['total_p95_ms'],600000)
        self.assertEqual(report['reported_models']['reported-fixture'],1)
        self.assertEqual(report['requested_models']['synthetic'],2)
        self.assertEqual(a.response_metadata({'_capture_transport':'sse','data':{'response':{'object':'response','id':'r','model':'m'}}}),('r','m'))
    def test_conversation_partition_stable_and_unknown_unsplit(self):
        self.assertEqual(a.partition(self.event),a.partition({**self.event,'id':'r2'}))
        self.assertEqual(a.partition({**self.event,'association':'client_claimed'}),'unassigned')
    def test_simulation_never_contaminates_actuals(self):
        with self.assertRaises(ValueError):a.ingest(self.db,{**self.event,'plane':'simulation'})
        self.assertEqual(self.summary()['events'],0)
    def test_gap_and_cancel_produce_evidence_not_auto_change(self):
        a.ingest(self.db,{**self.event,'outcome':'canceled','missing':['queue_full']})
        r=self.summary();self.assertEqual(r['events_with_missing_capture'],1)
        self.assertEqual(r['investigation_candidates'][0]['id'],'r1')
    def test_report_nearest_rank_and_bounded_fault_evidence(self):
        for n in range(120):
            a.ingest(self.db,{**self.event,'id':f'r{n:03}','first_byte_ms':n+1,
                'duration_ms':n+1,'outcome':'canceled','missing':['fixture']})
        report=self.summary()
        self.assertEqual(report['first_byte_p95_ms'],114)
        self.assertEqual(report['total_p95_ms'],114)
        self.assertEqual(report['events_with_missing_capture'],120)
        self.assertEqual(len(report['investigation_candidates']),100)
        self.assertEqual(report['investigation_candidates'][0]['id'],'r020')
        self.assertEqual(report['verified_conversations'],1)
        self.assertEqual(report['report_version'],2)
    def test_report_two_samples_does_not_report_minimum_as_p95(self):
        for n in (1,100):
            a.ingest(self.db,{**self.event,'id':str(n),'duration_ms':n})
        self.assertEqual(self.summary()['total_p95_ms'],100)


if __name__=='__main__':unittest.main()
