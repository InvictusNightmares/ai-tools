import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('usage_override', Path(__file__).parents[1]/'deploy/acceptance/run-usage-override.py')
override=importlib.util.module_from_spec(spec)
spec.loader.exec_module(override)


class OverrideTests(unittest.TestCase):
    def test_fixed_us_runner_rejects_api_upgrade_tamper_and_extra_files(self):
        for failure in (None,'upgrade','tamper','extra','component','region'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                home=Path(directory);root=home/'instance';root.mkdir()
                release=home/'releases/base';(release/'tools').mkdir(parents=True)
                bundle=home/'bundle';(bundle/'tools').mkdir(parents=True)
                for name in override.FILES:
                    (bundle/name).write_text('fixture')
                    if name.startswith('tools/'):(release/name).write_text('fixture')
                metadata={'release_id':'base','source_sha256':'source','operations_contract':'independent-usage-health-v1'}
                (release/'release.json').write_text(json.dumps(metadata))
                pointer={'release_id':'base','path':str(release)}
                (root/'current-release.json').write_text(json.dumps(pointer))
                manifest={'schema':'gateway-usage-override-v1','region':'us','base_release_id':'base','base_source_sha256':'source',
                          'files':{name:override.digest(bundle/name) for name in override.FILES}}
                if failure=='upgrade':
                    metadata['source_sha256']='new';(release/'release.json').write_text(json.dumps(metadata))
                if failure=='tamper':(bundle/'tools/usage_sync.py').write_text('tampered')
                if failure=='extra':(bundle/'extra.py').write_text('unlisted')
                if failure=='component':(release/'tools/gateway_ops.py').write_text('changed')
                if failure=='region':manifest['region']='tokyo'
                (bundle/'manifest.json').write_text(json.dumps(manifest))
                with patch.object(override,'RELEASES',home/'releases'):
                    if failure:
                        with self.assertRaises(ValueError):override.command(root,bundle)
                    else:
                        command=override.command(root,bundle)
                        self.assertEqual(command[1],'-B')
                        self.assertEqual(command[command.index('--region')+1],'us')
                        self.assertIn('--usage-only',command)
                self.assertEqual(json.loads((root/'current-release.json').read_text()),pointer)


if __name__=='__main__':unittest.main()
