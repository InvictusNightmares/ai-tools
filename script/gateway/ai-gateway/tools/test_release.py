import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import release
from source_manifest import manifest
import importlib.util
import collections

spec = importlib.util.spec_from_file_location('deploy_release', Path(__file__).with_name('deploy-release.py'))
deploy_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy_release)


class ReleaseTests(unittest.TestCase):
    def test_guard_only_failed_upgrade_undrains_unchanged_auto_before_rollback_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'instance';old=base/'old';new=base/'new'
            for path in (root/'deployment',root/'state',root/'secrets',old/'deployment',new/'deployment'):path.mkdir(parents=True)
            (root/'deployment/runtime.env').write_text('')
            (root/'deployment/nginx.conf').write_text('server_name _; old ingress')
            (root/'deployment/compose.yaml').write_text('old compose')
            (new/'deployment/compose.yaml').write_text('new compose')
            (root/'secrets/cache-secret').write_text('fixture')
            pointer={'path':str(old),'release_id':'old'};(root/'current-release.json').write_text(json.dumps(pointer))
            metadata=lambda path:{'release_id':path.name,'binaries':{'auto-server':'unchanged','preflight-api':path.name}}
            app=deploy_release.Deployment('tokyo',1);app.root=root
            state={'draining':False}
            def command(args):
                if 'inspect' in args:return json.dumps([{'Id':'existing'}])
                if 'config' in args:return json.dumps({'services':{'ingress':{},'auto':{},'guard':{}}})
                return ''
            def request(port,path,data=None,admin=False):
                if path=='/_gateway/drain':state['draining']=data['draining']
            def ready():
                if state['draining']:raise RuntimeError('unchanged_auto_still_draining')
            with patch.object(deploy_release,'validate',side_effect=metadata),patch.object(deploy_release,'render_ingress',side_effect=lambda rel,*args:'server_name _; '+rel.name+' ingress'),patch.object(deploy_release,'run',side_effect=command),patch.object(app,'ready',side_effect=ready),patch.object(app,'protected',return_value={}),patch.object(app,'drain',side_effect=lambda:state.update(draining=True)),patch.object(app,'request',side_effect=request),patch.object(app,'rewrite_ingress',side_effect=lambda text:(root/'deployment/nginx.conf').write_text(text)),patch.object(app,'activate_components',side_effect=RuntimeError('guard_activation_failed')),patch('builtins.print'):
                with self.assertRaises(SystemExit):app.activate(new)
            result=json.loads(next((root/'backups').glob('*/result.json')).read_text())
            self.assertEqual(result['rollback'],'restored')
            self.assertFalse(state['draining'])
            self.assertEqual((root/'deployment/nginx.conf').read_text(),'server_name _; old ingress')
            self.assertEqual(json.loads((root/'current-release.json').read_text()),pointer)

    def test_activation_failure_distinguishes_restored_and_failed_rollback(self):
        for rollback_fails in (False,True):
            with tempfile.TemporaryDirectory() as directory:
                base=Path(directory);root=base/'instance';old=base/'old';new=base/'new'
                for path in (root/'deployment',root/'state',root/'secrets',old/'deployment',new/'deployment'):path.mkdir(parents=True)
                (root/'deployment/runtime.env').write_text('')
                (root/'deployment/nginx.conf').write_text('server_name _; old ingress')
                (root/'deployment/compose.yaml').write_text('old compose')
                (new/'deployment/compose.yaml').write_text('new compose')
                (root/'state/session.json').write_text('preserve active user state')
                (root/'secrets/cache-secret').write_text('fixture')
                pointer={'path':str(old),'release_id':'old'};(root/'current-release.json').write_text(json.dumps(pointer))
                metadata=lambda path:{'release_id':path.name,'binaries':{name:path.name for name in release.BINARIES}}
                app=deploy_release.Deployment('tokyo',1);app.root=root
                def command(args):
                    if 'inspect' in args:return json.dumps([{'Id':'existing'}])
                    if 'config' in args:return json.dumps({'services':{'ingress':{},'auto':{},'guard':{}}})
                    if 'up' in args and rollback_fails:raise RuntimeError('injected_rollback_failure')
                    return ''
                writes=[]
                def rewrite(text):writes.append(text);(root/'deployment/nginx.conf').write_text(text)
                with patch.object(deploy_release,'validate',side_effect=metadata),patch.object(deploy_release,'render_ingress',side_effect=lambda rel,*args:'server_name _; old ingress' if rel==old else 'server_name _; new ingress'),patch.object(deploy_release,'run',side_effect=command),patch.object(app,'ready'),patch.object(app,'protected',return_value={}),patch.object(app,'drain'),patch.object(app,'request'),patch.object(app,'rewrite_ingress',side_effect=rewrite),patch.object(app,'activate_components',side_effect=RuntimeError('injected_activation_failure')),patch('builtins.print'):
                    with self.assertRaises(SystemExit):app.activate(new)
                result=json.loads(next((root/'backups').glob('*/result.json')).read_text())
                self.assertEqual(result['status'],'failed')
                self.assertEqual(result['rollback'],'failed' if rollback_fails else 'restored')
                self.assertEqual(json.loads((root/'current-release.json').read_text()),pointer)
                self.assertEqual((root/'state/session.json').read_text(),'preserve active user state')
                self.assertEqual((root/'deployment/compose.yaml').read_text(),'old compose')
                if rollback_fails:self.assertIn('return 503;',writes[-1])
                else:self.assertEqual(writes[-1],'server_name _; old ingress')

    @patch('release.platform.system', return_value='Darwin')
    def test_contract_and_state_compatibility_rejected_before_activation(self, _):
        for field,value in [('guard_contract','unknown'),('compatible_state_schemas',[]),('state_schema','future-state')]:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);self.fixture(root)
                data=json.loads((root/'release.json').read_text());data[field]=value
                (root/'release.json').write_text(json.dumps(data));self.checksums(root)
                with self.assertRaises(ValueError):release.validate(root)

    def test_render_ingress_supports_initial_metadata_and_rejects_port_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);deployment=root/'deployment';deployment.mkdir()
            (deployment/'nginx.conf.template').write_text('listen @BIND_ADDRESS@:@PORT@; auto @AUTO_PORT@; upstream @UPSTREAM_AUTHORITY@;')
            endpoint={'region':'tokyo','port':4004,'bind_address':'192.168.64.16'}
            (deployment/'endpoint.json').write_text(json.dumps(endpoint))
            (deployment/'runtime.env').write_text('ACCEPTANCE_AUTO_PORT=8093\nACCEPTANCE_GUARD_PORT=8013\n')
            self.assertEqual(deploy_release.render_ingress(root,root,'tokyo'),'listen 192.168.64.16:4004; auto 8093; upstream 106.14.254.110:9881;')
            endpoint['port']=4000;(deployment/'endpoint.json').write_text(json.dumps(endpoint))
            with self.assertRaises(ValueError):deploy_release.render_ingress(root,root,'tokyo')

    def test_disk_and_missing_secret_fail_before_drain_or_docker(self):
        for missing in (False,True):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);(root/'deployment').mkdir();(root/'state').mkdir()
                (root/'deployment/runtime.env').write_text('')
                app=deploy_release.Deployment('tokyo',1);app.root=root
                disk=collections.namedtuple('Disk','total used free')(1<<40,0,1<<40 if missing else 1)
                with patch.object(deploy_release,'validate',return_value={}),patch.object(deploy_release.shutil,'disk_usage',return_value=disk),patch.object(deploy_release,'run') as command,patch.object(app,'drain') as drain:
                    with self.assertRaises((RuntimeError,FileNotFoundError)):app.activate(root)
                    command.assert_not_called();drain.assert_not_called()

    def fixture(self, root):
        (root / 'bin').mkdir()
        header = b'\x7fELF\x02' + b'\0' * 13 + b'\x3e\x00'
        for name in release.BINARIES: (root / 'bin' / name).write_bytes(header)
        data = {'schema': release.SCHEMA, 'platform': 'linux/amd64', 'config_schema': 'gateway-config-v1',
                'state_schema': 'session-json-v1', 'release_id': 'test', 'source_sha256': 'source',
                'guard_contract': 'credential-redaction-v1', 'compatible_state_schemas': ['session-json-v1'],
                'binaries': {name: release.sha(root / 'bin' / name) for name in release.BINARIES}}
        (root / 'release.json').write_text(json.dumps(data))
        self.checksums(root)

    def checksums(self, root):
        (root / 'SHA256SUMS').write_text(''.join(release.sha(p) + '  ' + p.relative_to(root).as_posix() + '\n'
            for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS'))

    @patch('release.platform.system', return_value='Darwin')
    def test_checksums_reject_mutation_and_extra_file(self, _):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            self.assertEqual(release.validate(root)['release_id'], 'test')
            (root / 'extra').write_text('untracked')
            with self.assertRaises(ValueError): release.validate(root)
            (root / 'extra').unlink()
            (root / 'bin/auto-server').write_bytes(b'changed')
            with self.assertRaises(ValueError): release.validate(root)

    @patch('release.platform.system', return_value='Darwin')
    def test_rejects_wrong_platform_and_path_escape(self, _):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            data = json.loads((root / 'release.json').read_text()); data['platform'] = 'linux/arm64'
            (root / 'release.json').write_text(json.dumps(data)); self.checksums(root)
            with self.assertRaises(ValueError): release.validate(root)
            data['platform'] = 'linux/amd64'; (root / 'release.json').write_text(json.dumps(data)); self.checksums(root)
            with (root / 'SHA256SUMS').open('a') as output: output.write('0' * 64 + '  ../outside\n')
            with self.assertRaises(ValueError): release.validate(root)

    def test_source_manifest_detects_added_deleted_changed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'auto').mkdir(); (root / 'auto/a.go').write_text('a')
            first = manifest(root)
            (root / 'auto/a.go').write_text('b'); self.assertNotEqual(first, manifest(root))
            (root / 'auto/a.go').write_text('a'); (root / 'auto/b.go').write_text('b'); self.assertNotEqual(first, manifest(root))
            (root / 'auto/a.go').unlink(); self.assertNotEqual(first, manifest(root))

    def test_component_change_does_not_rebuild_unrelated_binary(self):
        source = {'files': [{'path': p, 'sha256': 'before'} for p in
                           ['auto/http.go', 'auto/http_test.go', 'guard/preflight.go', 'service/lifecycle.go', 'go.mod']]}
        guard = release.component_digest(source, 'preflight-api')
        auto = release.component_digest(source, 'auto-server')
        source['files'][0]['sha256'] = 'after'
        self.assertEqual(guard, release.component_digest(source, 'preflight-api'))
        self.assertNotEqual(auto, release.component_digest(source, 'auto-server'))
        source['files'][3]['sha256'] = 'shared-library-change'
        self.assertNotEqual(guard, release.component_digest(source, 'preflight-api'))

    def test_config_comparison_preserves_runtime_changes(self):
        first = {'services': {'auto': {'environment': {'REGION': 'us'}, 'volumes': [
            {'target': '/app/auto-server', 'source': '/release/one/bin/auto-server'},
            {'target': '/state', 'source': '/instance/state'}]}}}
        second = json.loads(json.dumps(first))
        second['services']['auto']['volumes'][0]['source'] = '/release/two/bin/auto-server'
        self.assertEqual(deploy_release.component_config(first, 'auto'), deploy_release.component_config(second, 'auto'))
        second['services']['auto']['environment']['REGION'] = 'tokyo'
        self.assertNotEqual(deploy_release.component_config(first, 'auto'), deploy_release.component_config(second, 'auto'))

    def test_noop_and_guard_only_upgrade_undrain_unchanged_auto(self):
        for changed in ([], ['guard']):
            app = deploy_release.Deployment('tokyo', 1)
            state = {'draining': True}
            def request(port, path, data=None, admin=False):
                self.assertTrue(admin)
                self.assertEqual(path, '/_gateway/drain')
                state['draining'] = data['draining']
            def ready():
                self.assertFalse(state['draining'])
            app.request, app.ready = request, ready
            with patch.object(deploy_release, 'run') as run:
                app.activate_components(changed)
                self.assertEqual(run.call_count, int(bool(changed)))


if __name__ == '__main__': unittest.main()
