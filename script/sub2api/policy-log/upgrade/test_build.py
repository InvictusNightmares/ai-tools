import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location("policy_builder",Path(__file__).with_name("build.py"))
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
installer_spec=importlib.util.spec_from_file_location("policy_installer",Path(__file__).with_name("install_node.py"))
installer=importlib.util.module_from_spec(installer_spec)
installer_spec.loader.exec_module(installer)


class MergeTests(unittest.TestCase):
    def test_each_node_receives_package_without_peer_dependency(self):
        import tarfile
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            binary = home / 'binary'
            binary.mkdir()
            (binary / 'sub2api').write_bytes(b'verified binary fixture')
            (binary / 'release.json').write_text('{}')
            for failed_node in (None, 'qiyuan-us'):
                calls = []
                def send(args, **kwargs):
                    self.assertIn('stdin', kwargs, 'each node receives its own package via SSH')
                    node = args[-2]
                    with tarfile.open(fileobj=kwargs['stdin'], mode='r:gz') as archive:
                        self.assertEqual(archive.extractfile('sub2api').read(), b'verified binary fixture')
                    calls.append(node)
                    if node == failed_node:
                        raise RuntimeError('fixture node unavailable')
                with patch.object(builder, 'run', side_effect=send):
                    if failed_node:
                        with self.assertRaises(RuntimeError):
                            builder.stage(home, {'status':'ready','releases':[]}, binary, {})
                    else:
                        builder.stage(home, {'status':'ready','releases':[]}, binary, {})
                self.assertEqual(calls, ['qiyuan-us', 'qiyuan-tokyo'])

    def test_incomplete_catalog_refresh_keeps_previously_delivered_artifacts(self):
        import io
        import subprocess
        import sys
        import tarfile
        receiver=next(v for v in builder.stage.__code__.co_consts if isinstance(v,str) and 'latest binary not staged' in v)
        for status in ('building','failed'):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'node';root.mkdir()
                for sha in ('a'*64,'b'*64):
                    dest=root/'releases'/sha;dest.mkdir(parents=True);(dest/'sub2api').write_bytes(b'previously verified artifact')
                catalog={'status':status,'releases':[{'version':'old','sha256':'a'*64}]}
                stream=io.BytesIO()
                with tarfile.open(fileobj=stream,mode='w:gz') as tar:
                    data=json.dumps(catalog).encode();entry=tarfile.TarInfo('catalog.json');entry.size=len(data);tar.addfile(entry,io.BytesIO(data))
                script=receiver.replace('/opt/sub2api-deploy/policy-releases',str(root))
                subprocess.run([sys.executable,'-c',script],input=stream.getvalue(),check=True,capture_output=True)
                self.assertTrue((root/'releases'/('b'*64)/'sub2api').exists())

    def test_verified_cache_does_not_require_github_tag_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = home/f'releases/0.2.1+policy-log.{builder.REVISION}'
            result.mkdir(parents=True)
            (result/'sub2api').write_bytes(b'verified fixture')
            meta = {'patch_sha256':'b'*64, 'upstream_version':'0.2.1', 'upstream_commit':'a'*40}
            record = {'version':f'0.2.1+policy-log.{builder.REVISION}', 'patch_sha256':'b'*64,
                      'upstream_commit':'a'*40, 'sha256':builder.digest(result/'sub2api'),
                      'persistent_update_verified':True}
            (result/'release.json').write_text(json.dumps(record))
            with patch.object(builder, 'validate_bundle', return_value=meta), patch.object(builder, 'official_tag_commit', side_effect=RuntimeError('GitHub unavailable')) as lookup:
                actual, path = builder.prepare(home, home/'bundle', {'tag_name':'v0.2.1'})
                self.assertEqual(actual, record)
                self.assertEqual(path, result)
                lookup.assert_not_called()

    def test_release_detection_uses_published_latest_not_newer_tags(self):
        release = {'tag_name':'v0.2.1','draft':False,'prerelease':False}
        with patch.object(builder, 'fetch', return_value=release):
            self.assertEqual(builder.latest_official_release(), release)

    def test_rate_limited_release_detection_uses_official_redirect(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.geturl.return_value = 'https://github.com/Wei-Shaw/sub2api/releases/tag/v0.2.1'
        error = builder.urllib.error.HTTPError('api',403,'rate limit',{},None)
        with patch.object(builder.urllib.request, 'urlopen') as open_url, patch.object(builder, 'fetch', side_effect=error):
            open_url.return_value.__enter__.return_value = response
            self.assertEqual(builder.latest_official_release()['tag_name'], 'v0.2.1')

    def test_release_detection_rejects_foreign_or_prerelease_redirect(self):
        from unittest.mock import MagicMock
        for url in ['https://example.com/releases/tag/v0.2.2',
                    'https://github.com/Wei-Shaw/sub2api/releases/tag/v0.2.3-beta']:
            response = MagicMock()
            response.geturl.return_value = url
            error = builder.urllib.error.HTTPError('api',429,'rate limit',{},None)
            with patch.object(builder.urllib.request, 'urlopen') as open_url, patch.object(builder, 'fetch', side_effect=error):
                open_url.return_value.__enter__.return_value = response
                with self.assertRaises(RuntimeError): builder.latest_official_release()

    def test_blocked_release_message_preserves_version_and_cause(self):
        error = builder.CompatibilityError('database schema changed', '数据库结构变化，等待兼容性验证')
        message = builder.failure_message({'tag_name':'v0.2.2'}, error)
        self.assertIn('v0.2.2', message)
        self.assertIn('数据库结构变化', message)
        self.assertNotIn('database schema changed', message)

    def test_migration_runner_change_is_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root/'backend/internal/repository/migrations_runner.go'
            runner.parent.mkdir(parents=True)
            runner.write_text('old locking behavior')
            before = builder.migration_fingerprint(root)
            runner.write_text('new locking behavior')
            self.assertNotEqual(before, builder.migration_fingerprint(root))

    def test_nonoverlapping_upstream_change_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            base,custom,target=[Path(tmp)/n for n in ('base','custom','target')]
            for p in (base,custom,target):p.mkdir()
            (base/'x').write_text('original\n'+ '\n'*10+'old\n')
            (custom/'x').write_text('policy\n'+ '\n'*10+'old\n')
            (target/'x').write_text('original\n'+ '\n'*10+'new-upstream\n')
            builder.merge_custom(base,custom,target)
            self.assertEqual((target/'x').read_text(),'policy\n'+ '\n'*10+'new-upstream\n')

    def test_conflict_does_not_replace_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            base,custom,target=[Path(tmp)/n for n in ('base','custom','target')]
            for p in (base,custom,target):p.mkdir()
            for p,value in ((base,'original'),(custom,'policy'),(target,'upstream')):(p/'x').write_text(value+'\n')
            with self.assertRaises(RuntimeError):builder.merge_custom(base,custom,target)
            self.assertEqual((target/'x').read_text(),'upstream\n')

    def test_deleted_integration_and_new_collision_stop_build(self):
        for mode in ('deleted','collision'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                base,custom,target=[Path(tmp)/n for n in ('base','custom','target')]
                for p in (base,custom,target):p.mkdir()
                (custom/'x').write_text('policy')
                ((base if mode=='deleted' else target)/'x').write_text('upstream')
                with self.assertRaises(RuntimeError):builder.merge_custom(base,custom,target)

    def test_migration_change_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); migrations=root/'backend/migrations';migrations.mkdir(parents=True)
            (migrations/'001.sql').write_text('CREATE TABLE original;')
            before=builder.migration_fingerprint(root)
            (migrations/'002.sql').write_text('ALTER TABLE original DROP COLUMN old;')
            self.assertNotEqual(before,builder.migration_fingerprint(root))

    def test_compose_changes_only_application_and_retry_is_stable(self):
        text='services:\n  sub2api:\n    image: original:latest\n    volumes:\n      - ./data:/app/data\n    environment:\n      - AUTO_SETUP=true\n  sub2api-proxy:\n    image: nginx:stable\n    depends_on:\n      sub2api:\n        condition: service_healthy\n  postgres:\n    image: postgres:18-alpine\n'
        changed=installer.replacement_compose(text,'original@sha256:abc')
        self.assertIn('command: ["/app/data/policy-updates/runtime/sub2api"]',changed)
        self.assertIn('./policy-releases:/app/policy-releases:ro',changed)
        self.assertEqual(changed.split('  postgres:',1)[1],text.split('  postgres:',1)[1])
        self.assertEqual(changed.split('  sub2api-proxy:',1)[1],text.split('  sub2api-proxy:',1)[1])
        self.assertEqual(installer.replacement_compose(changed,'original@sha256:abc',True),changed)

    def test_runtime_directory_symlink_is_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);deploy=root/'deploy';deploy.mkdir();outside=root/'outside';outside.mkdir()
            (deploy/'data').symlink_to(outside,target_is_directory=True)
            source=root/'new';source.write_bytes(b'new')
            with patch.object(installer,'DEPLOY',deploy):
                with self.assertRaises(OSError):installer.install_runtime(source)
            self.assertEqual(list(outside.iterdir()),[])


if __name__=='__main__':unittest.main()
