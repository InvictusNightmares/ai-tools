import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('install_operations',Path(__file__).parents[1]/'deploy/acceptance/install-operations.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class OperationsInstallTests(unittest.TestCase):
    def test_systemd_uses_verified_interpreter_and_rejects_old_or_unsafe_path(self):
        source=b'ExecStart=@GATEWAY_PYTHON@ /path/run-current.py %i'
        self.assertEqual(installer.render_unit(source,'/data/miniforge/bin/python3',(3,13)),b'ExecStart=/data/miniforge/bin/python3 /path/run-current.py %i')
        with self.assertRaises(ValueError):installer.render_unit(source,'/usr/bin/python3',(3,6))
        with self.assertRaises(ValueError):installer.render_unit(source,'/usr/bin/python3\nInjected=yes',(3,13))


if __name__=='__main__':unittest.main()
