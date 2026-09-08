import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

spec=importlib.util.spec_from_file_location('pull_transport',Path(__file__).with_name('pull_transport.py'))
transport=importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class PullTransportTests(unittest.TestCase):
    def test_nginx_change_is_restricted_and_idempotent(self):
        original='events {}\nhttp {\n    server {\n        location / {\n            proxy_pass http://backend;\n        }\n    }\n}\n'
        actual=transport.nginx_config(original)
        self.assertEqual(actual.replace(transport.NGINX_LOCATION,''),original)
        self.assertIn('allow 8.216.44.189;\n            deny all;',actual)
        self.assertEqual(transport.nginx_config(actual),actual)
        with self.assertRaises(RuntimeError):
            transport.nginx_config(actual.replace('allow 8.216.44.189;','allow all;'))

    def test_transport_secret_only_uses_captured_output_and_stdin(self):
        secret='fixture-secret'; calls=[]
        def run(args,**kwargs):
            calls.append((args,kwargs))
            return SimpleNamespace(stdout=json.dumps({'password':secret,'cipher_sha256':'a'*64,'cipher_size':64}))
        transport.stage_tokyo({'status':'ready'},{'sha256':'b'*64},'receiver',run)
        self.assertTrue(calls[0][1]['capture_output'])
        self.assertEqual(json.loads(calls[1][1]['input'])['password'],secret)
        self.assertTrue(all(secret not in ' '.join(args) for args,_ in calls))
        self.assertEqual(len(calls),3)

    def run_download(self,tamper):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp); work=tmp/'work';work.mkdir(); commands=tmp/'bin';commands.mkdir()
            original=b'complete verified archive fixture\n'*32
            (tmp/'plain').write_bytes(original)
            password='random-fixture-without-real-credentials';(tmp/'password').write_text(password+'\n')
            subprocess.run(['openssl','enc','-aes-256-cbc','-md','sha256','-salt','-pass','file:'+str(tmp/'password'),'-in',str(tmp/'plain'),'-out',str(tmp/'cipher')],check=True,capture_output=True)
            cipher=(tmp/'cipher').read_bytes()
            control={'password':password,'cipher_sha256':hashlib.sha256(cipher).hexdigest(),'cipher_size':len(cipher),
                     'receiver':'import sys,hashlib; data=sys.stdin.buffer.read(); assert hashlib.sha256(data).hexdigest()=='+repr(hashlib.sha256(original).hexdigest())+'; print("receiver verified")'}
            if tamper:(tmp/'cipher').write_bytes(b'wrong'+cipher[5:])
            curl=commands/'curl'
            curl.write_text('#!'+sys.executable+'\nimport pathlib,sys\npathlib.Path(sys.argv[sys.argv.index("--output")+1]).write_bytes(pathlib.Path('+repr(str(tmp/'cipher'))+').read_bytes())\n')
            curl.chmod(0o755)
            script=transport.DOWNLOADER.replace('/opt/sub2api-deploy/policy-releases',str(work))
            result=subprocess.run([sys.executable,'-c',script],input=json.dumps(control),text=True,capture_output=True,env={**os.environ,'PATH':str(commands)+os.pathsep+os.environ['PATH']})
            self.assertEqual(list(work.iterdir()),[])
            return result

    def test_encrypted_round_trip_runs_verifier_only_after_integrity_checks(self):
        result=self.run_download(False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('receiver verified',result.stdout)

    def test_tampered_download_never_reaches_verifier(self):
        result=self.run_download(True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('encrypted download checksum mismatch',result.stderr)
        self.assertNotIn('receiver verified',result.stdout)


if __name__=='__main__':unittest.main()
