#!/usr/bin/env python3
"""Exercise the generated installer's Alpine root handoff using dummy files.

Usage: python3 test-alpine-root-handoff.py /path/to/staged/reinstall.sh
No installer, network, privileged command, or real disk is used.
"""

import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


def root_handoff(installer):
    function = installer.split("mod_initrd_alpine() {", 1)[1].split(
        "\nmod_initrd() {", 1
    )[0]
    match = re.search(
        r"(?m)^        for dir in /configs[^\n]*; do\n.*?^        done$",
        function,
        re.DOTALL,
    )
    if not match:
        raise ValueError("The pinned Alpine directory handoff was not found")
    # This code is in an unquoted installer heredoc: its escaped variables
    # become ordinary runtime variables in Alpine's generated /init.
    return match.group(0).replace("\\$", "$")


class AlpineRootHandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agentbox-handoff-")
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.initrd = self.base / "initrd"
        self.sysroot = self.base / "sysroot"
        self.initrd.mkdir()
        self.sysroot.mkdir()
        for name in ("configs", "custom_drivers", "proxy-bootstrap"):
            directory = self.initrd / name
            directory.mkdir(mode=0o700)
            (directory / "fixture").write_text("dummy data only\n")
            (directory / "fixture").chmod(0o600)
        binary = self.initrd / "proxy-bootstrap" / "mihomo"
        binary.write_text("dummy executable, never run\n")
        binary.chmod(0o700)

        # Relocate the absolute initramfs input names to the disposable fixture.
        # The actual cp/rm body is executed unchanged from the staged artifact.
        hook = root_handoff(INSTALLER)
        first, body = hook.split("\n", 1)
        first = re.sub(
            r"(?<= )/([a-z_-]+)", r'"$initrd_root/\1"', first
        )
        script = 'set -eu\numask 077\ninitrd_root=$1\nsysroot=$2\n'
        script += first + "\n" + body
        subprocess.run(
            [shutil.which("sh") or "/bin/sh", "-c", script, "handoff",
             str(self.initrd), str(self.sysroot)],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_proxy_bundle_survives_root_switch(self):
        copied = self.sysroot / "proxy-bootstrap" / "fixture"
        self.assertTrue(copied.is_file(), "proxy-bootstrap lost at switch_root")
        self.assertEqual(copied.read_text(), "dummy data only\n")
        self.assertFalse((self.initrd / "proxy-bootstrap").exists())

    def test_existing_configuration_and_drivers_still_survive(self):
        for name in ("configs", "custom_drivers"):
            self.assertEqual(
                (self.sysroot / name / "fixture").read_text(), "dummy data only\n"
            )

    def test_private_permissions_and_executable_survive(self):
        bundle = self.sysroot / "proxy-bootstrap"
        for path, mode in ((bundle, 0o700), (bundle / "fixture", 0o600),
                           (bundle / "mihomo", 0o700)):
            self.assertTrue(path.exists(), f"Missing carried file: {path.name}")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    INSTALLER = pathlib.Path(sys.argv.pop()).read_text(encoding="utf-8")
    unittest.main()
