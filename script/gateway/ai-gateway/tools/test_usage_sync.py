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
