import csv
import hashlib
import hmac
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from usage_ledger import Ledger
import usage_sync


class UsageSyncTests(unittest.TestCase):
    def test_regional_targets_keep_tokyo_and_use_new_west_database(self):
        for region, container, database in [('tokyo','sub2api-postgres','sub2api'), ('us','sub2api-next-postgres','sub2api_next')]:
            with self.subTest(region=region):
                with patch.object(usage_sync, 'ssh', return_value='') as remote:
                    usage_sync.psql(region, 'SELECT 1;')
                command = remote.call_args.args[1]
                self.assertIn(container + ' psql', command)
                self.assertIn('-d gateway_usage', command)
                with patch('sys.stdin',io.StringIO(json.dumps(dict(region=region,secret='fixture')))), patch('sys.stdout',io.StringIO()), patch('subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout='[]')) as query:
                    exec(usage_sync.KEYMAP_HELPER,{})
                args = query.call_args.args[0]
                self.assertEqual(args[3],container)
                self.assertEqual(args[args.index('-d')+1],database)
                with self.assertRaises(ValueError):
                    usage_sync.psql(region, 'DELETE FROM api_keys;', database)

    def test_replay_restores_exported_history_and_old_mapping_only_for_region(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'secrets').mkdir();(root/'secrets/cache-secret').write_text('fixture')
            ledger=Ledger(root/'ops/usage-ledger.sqlite');spool=root/'usage.jsonl'
            base=dict(at='2026-09-16T00:00:00Z',region='us',api_key_id='key-hmac-v1:old',request_id='fixture',purpose='business',effective_model='model',attempt=True,success=True,input_tokens=12)
            spool.write_text(json.dumps(base)+'\n'+json.dumps(dict(base,region='synthetic'))+'\n')
            ledger.ingest(spool)
            old_mapping=dict(region='us',key_hash='key-hmac-v1:old',api_key_id=10)
            ledger.map_keys([old_mapping]);ledger.db.execute("UPDATE events SET exported=1 WHERE region='us'");ledger.db.commit();ledger.close()
            with patch.object(usage_sync,'ssh',return_value='[]'),patch.object(usage_sync,'initialize') as initialize,patch.object(usage_sync,'psql') as database:
                result=usage_sync.run('us',root,initialize_db=True,replay_all=True)
                initialize.assert_called_once_with('us')
                self.assertEqual(result['exported'],1)
                self.assertEqual(result['remaining'],0)
                script=database.call_args.args[1]
                self.assertIn('key-hmac-v1:old',script)
                self.assertNotIn('synthetic',script)
                self.assertEqual(result['key_mappings'],1)
                again=usage_sync.run('us',root)
                self.assertEqual(again['exported'],0)
            ledger=Ledger(root/'ops/usage-ledger.sqlite')
            self.assertEqual(ledger.db.execute("SELECT exported FROM events WHERE region='synthetic'").fetchone()[0],0)
            ledger.close()

    def test_replay_requires_explicit_initialization(self):
        with self.assertRaises(ValueError):
            usage_sync.run('us',Path('/nonexistent'),replay_all=True)

    def test_export_ack_failure_preserves_replay_and_copy_framing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); ledger=Ledger(root/'ledger.sqlite'); spool=root/'usage.jsonl'
            spool.write_text(json.dumps(dict(at='2026-09-16T00:00:00Z',region='tokyo',api_key_id='key-hmac-v1:test',request_id='fixture',
                purpose='business',effective_model='gpt-5.6-luna',attempt=True,success=True,input_tokens=12,output_tokens=2))+'\n')
            ledger.ingest(spool)
            with patch.object(usage_sync,'psql',side_effect=RuntimeError('lost_ack')):
                with self.assertRaises(RuntimeError):usage_sync.export_batch('tokyo',ledger,[])
            self.assertEqual(ledger.db.execute('SELECT exported FROM events').fetchone()[0],0)
            def check(region,script):
                self.assertEqual(region,'tokyo')
                self.assertEqual(sum(line=='\\.' for line in script.splitlines()),2)
                self.assertNotIn('    \\.',script)
                self.assertIn('ON CONFLICT DO NOTHING',script)
                self.assertIn('COMMIT;',script)
            with patch.object(usage_sync,'psql',side_effect=check):
                self.assertEqual(usage_sync.export_batch('tokyo',ledger,[]),1)
                self.assertEqual(usage_sync.export_batch('tokyo',ledger,[]),0)
            ledger.close()

    def test_regional_helper_only_returns_hmac_mapping(self):
        source=dict(secret='private-fixture-secret',region='tokyo')
        out=io.StringIO()
        with patch('sys.stdin',io.StringIO(json.dumps(source))),patch('sys.stdout',out),patch('subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout='[{"id":141,"key":"private-fixture-key"}]')):
            exec(usage_sync.KEYMAP_HELPER,{})
        output=out.getvalue();self.assertNotIn('private-fixture',output)
        expected=hmac.new(source['secret'].encode(),b'sub2api-identity-v1\x00tokyo\x00private-fixture-key',hashlib.sha256).hexdigest()
        self.assertEqual(json.loads(output),[dict(region='tokyo',key_hash='key-hmac-v1:'+expected,api_key_id=141)])

    def test_exporter_cannot_target_business_database(self):
        with self.assertRaises(ValueError):usage_sync.psql('tokyo','SELECT 1','sub2api')

    def test_bastion_zero_exit_does_not_hide_remote_failure(self):
        for output in ('Traceback: synthetic failure\n__GATEWAY_REMOTE_EXIT__:1\n','unconfirmed output'):
            with patch('subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout=output)):
                with self.assertRaises(RuntimeError):usage_sync.ssh('tokyo','true','')
        with patch('subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout='{"ok":true}\n__GATEWAY_REMOTE_EXIT__:0\n')):
            self.assertEqual(usage_sync.ssh('tokyo','true',''),' {"ok":true}'.lstrip())


if __name__=='__main__':unittest.main()
