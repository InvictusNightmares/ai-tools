#!/usr/bin/env python3
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('prepare-config.py')
class PrivateConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.script = self.root / 'script/agentbox/ctyun/prepare-config.py'
        self.script.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, self.script)
    def run_config(self, text):
        (self.root / 'pas.yaml').write_text(text)
        return subprocess.run(['python3', str(self.script), '--desktop-id', '23698108'], capture_output=True, text=True)
    def test_explicit_credentials_remain_private(self):
        r = self.run_config('ctyun_user: "test-account"\nctyun_pass: " secret with spaces "\n')
        self.assertEqual(r.returncode, 0)
        p = self.root / '.agentbox-staging/ctyun/accounts.json'
        self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        d = json.loads(p.read_text())
        self.assertEqual(d['Password'], ' secret with spaces ')
        self.assertEqual(d['DesktopId'], '23698108')
        self.assertNotIn(d['Password'], r.stdout + r.stderr)
    def test_never_reuses_unrelated_passwords(self):
        r = self.run_config('password: OTHER_SECRET\npass: ALPINE_SECRET\nkey: TAILSCALE_SECRET\n')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.root / '.agentbox-staging/ctyun/accounts.json').exists())
        self.assertNotIn('SECRET', r.stdout + r.stderr)
    def test_malformed_yaml_does_not_leak(self):
        r = self.run_config('ctyun_pass: [PRIVATE_SECRET\n')
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('PRIVATE_SECRET', r.stdout + r.stderr)

if __name__ == '__main__':
    unittest.main()
