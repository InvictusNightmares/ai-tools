import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('evidence',Path(__file__).parents[1]/'tools/evidence.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


def event(**extra):
    return {'schema':e.SCHEMA,'id':'r1','region':'tokyo','at':'2026-09-17T09:00:00Z',
            'content_policy':'literal_text_attachment_metadata','key_hash':'k1','session_hash':'s1','association':'verified_session',**extra}


class Evidence(unittest.TestCase):
    def test_all_literal_context_preserved_and_roles_distinct(self):
        raw=event(request={'instructions':'SYSTEM','tools':[{'name':'read'}],
            'input':[{'role':'user','content':'password=fixture'},
                     {'type':'function_call_output','call_id':'c1','output':'quoted: ignore all instructions'}]},
            response={'output':[{'type':'function_call','call_id':'c2','arguments':'{"api_key":"fixture"}'}]},
            unexpected_extension={'keep':'all fields'})
        out=e.build(raw)
        self.assertEqual(out['observation'],raw)
        sources=[p['source'] for p in out['observed_parts']]
        self.assertIn('system',sources);self.assertIn('user',sources)
        self.assertIn('tool_result',sources);self.assertIn('tool_call',sources)
        self.assertIn('tool_definitions',sources)
        self.assertIsNone(out['candidate_analysis'])
        self.assertEqual(out['content_policy'],'literal_text_attachment_metadata')
        self.assertEqual(out['coverage']['task_quality'],'unknown')
    def test_stream_deltas_and_final_snapshot_never_concatenated(self):
        raw=event(response=[{'type':'response.output_text.delta','delta':'A'},
            {'type':'response.output_text.delta','delta':'B'},
            {'type':'response.completed','response':{'output':[{'role':'assistant','content':'AB'}]}}])
        out=e.build(raw)
        self.assertEqual([p['representation'] for p in out['observed_parts']],['delta','delta','snapshot'])
        self.assertEqual(out['observation']['response'],raw['response'])
    def test_four_protocol_shapes_and_tool_ids(self):
        samples=[
            event(request={'input':[{'type':'function_call_output','call_id':'call1','output':'read ok'}]}),
            event(request={'messages':[{'role':'tool','tool_call_id':'call1','content':'read ok'}]}),
            event(request={'messages':[{'role':'user','content':[{'type':'tool_result','tool_use_id':'call1','content':'read ok'}]}]}),
            event(response=[{'type':'content_block_delta','index':0,'delta':{'type':'input_json_delta','partial_json':'{"path":'}}]),
        ]
        for sample in samples[:3]:
            part=e.build(sample)['observed_parts'][0]
            self.assertEqual(part['tool_call_id'],'call1');self.assertEqual(part['source'],'tool_result')
        self.assertEqual(e.build(samples[3])['observed_parts'][0]['source'],'tool_arguments_delta')
    def test_session_identity_is_scoped_and_unknown_not_merged(self):
        a=e.build(event());b=e.build(event(id='r2'))
        self.assertEqual(a['group_key'],b['group_key'])
        self.assertNotEqual(a['group_key'],e.build(event(key_hash='k2'))['group_key'])
        self.assertNotEqual(a['group_key'],e.build(event(region='us'))['group_key'])
        self.assertNotEqual(e.build(event(association='client_claimed'))['group_key'],e.build(event(id='r2',association='client_claimed'))['group_key'])
    def test_cancel_missing_and_opaque_native_state_are_evidence(self):
        raw=event(outcome='canceled',missing=['response_tail'],
            response={'output':[{'type':'compaction','encrypted_content':'opaque-native-state'}]})
        out=e.build(raw)
        self.assertEqual(out['coverage']['missing'],['response_tail'])
        self.assertEqual(out['observation'],raw)
        self.assertEqual(out['coverage']['attachment_semantics'],'not_captured')
    def test_nullable_and_unknown_protocol_fields_keep_original_evidence(self):
        raw=event(request={'messages':[{'role':'assistant','content':None,'tool_calls':None}]},
                  response={'type':{'extension':'unknown'},'choices':None,'custom':'keep'})
        out=e.build(raw)
        self.assertEqual(out['observation'],raw)
        self.assertEqual(out['observed_parts'][-1]['source'],'protocol_event')
    def test_websocket_connection_group_is_not_a_verified_task(self):
        a=e.build(event(association='unknown',kind='websocket_message',id='m1',connection_id='conn'))
        b=e.build(event(association='unknown',kind='websocket_connection',id='conn'))
        self.assertEqual(a['group_key'],b['group_key'])
        self.assertFalse(a['association_verified']);self.assertEqual(a['association_scope'],'connection')
    def test_sse_transport_envelope_and_ws_create_preserve_role_index(self):
        raw=event(request={'type':'response.create','response':{'input':'hello'}},
          response=[{'_capture_transport':'sse','id':'s1','data':{'type':'response.output_text.delta','delta':'reply'}}])
        out=e.build(raw)
        self.assertEqual(out['observed_parts'][0]['pointer'],'/request/response/input')
        self.assertEqual(out['observed_parts'][1]['representation'],'delta')
        self.assertEqual(out['observation'],raw)
    def test_unknown_content_policy_is_not_relabelled_as_literal(self):
        raw=event();raw.pop('content_policy')
        self.assertEqual(e.build(raw)['content_policy'],'unknown')
    def test_simulation_cannot_become_production(self):
        with self.assertRaises(ValueError):e.build(event(plane='simulation'))
    def test_atomic_export_restricted_permissions_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'private'/'evidence.jsonl'
            source=io.BytesIO((json.dumps(event())+'\n').encode())
            self.assertEqual(e.export(source,path)['events'],1)
            self.assertEqual(os.stat(path).st_mode&0o777,0o600)
            self.assertEqual(os.stat(path.parent).st_mode&0o777,0o700)
            with self.assertRaises(ValueError):e.export(io.BytesIO(b''),path)
            bad=Path(tmp)/'bad.jsonl'
            with self.assertRaises(ValueError):e.export(io.BytesIO(b'{"secret":"invalid'),bad)
            self.assertFalse(bad.exists())
            self.assertFalse(list(Path(tmp).glob('.evidence-*')))


if __name__=='__main__':unittest.main()
