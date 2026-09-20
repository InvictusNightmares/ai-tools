import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('acceptance_prepare', ROOT/'deploy/acceptance/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class AcceptanceProfileTests(unittest.TestCase):
    def test_regions_render_isolated_endpoints(self):
        template = (ROOT/'deploy/acceptance/nginx.conf.template').read_text()
        for region, ports in [('tokyo', (4004, 8093, 8013, 9881)), ('us', (4005, 8094, 8014, 9880))]:
            with self.subTest(region=region):
                profile = prepare.deployment_profile(region)
                self.assertEqual((profile['port'], profile['auto_port'], profile['guard_port']), ports[:3])
                self.assertEqual(profile['root'].name, 'acceptance-'+region)
                rendered = prepare.render_nginx(template, '192.168.64.16', profile)
                self.assertIn(f'listen 192.168.64.16:{ports[0]};', rendered)
                self.assertIn(f'proxy_pass http://127.0.0.1:{ports[1]};', rendered)
                self.assertIn(f'server 106.14.254.110:{ports[3]};', rendered)
                self.assertNotIn('@', rendered)
                self.assertNotIn('106.14.254.110:'+str(9880 if region=='tokyo' else 9881), rendered)

    def test_unsupported_region_is_rejected(self):
        with self.assertRaises(KeyError):
            prepare.deployment_profile('unknown')


if __name__ == '__main__':
    unittest.main()
