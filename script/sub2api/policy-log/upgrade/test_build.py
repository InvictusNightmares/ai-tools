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
