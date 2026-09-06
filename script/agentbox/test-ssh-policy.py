#!/usr/bin/env python3
"""Check the finalizer's policy against the installer's OpenSSH include.

Usage: python3 test-ssh-policy.py [path/to/finalize-debian.sh]
Runs sshd -T against temporary files; never starts or changes a server.
"""

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


class SshPolicyTest(unittest.TestCase):
    def test_installer_include_cannot_enable_password_login(self):
        sshd = shutil.which("sshd") or "/usr/sbin/sshd"
        match = re.search(
            r"cat >(/etc/ssh/sshd_config\.d/[^\s]+) <<'EOF'\n(.*?)\nEOF",
            FINALIZER,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "No managed SSH policy was found")
        with tempfile.TemporaryDirectory(prefix="agentbox-ssh-policy-") as tmp:
            root = pathlib.Path(tmp)
            includes = root / "sshd_config.d"
            includes.mkdir()
            # This file is left by the real Debian installer. OpenSSH applies
            # the first setting read across the sorted include files.
            (includes / "01-permitrootlogin.conf").write_text(
                "PermitRootLogin yes\n"
            )
            (includes / pathlib.Path(match[1]).name).write_text(match[2] + "\n")
            config = root / "sshd_config"
            config.write_text(f'Include "{includes}/*.conf"\nUsePAM no\n')
            host_key = root / "host_key"
            subprocess.run(
                ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(host_key)],
                check=True,
                capture_output=True,
            )
            result = subprocess.run(
                [sshd, "-T", "-f", str(config), "-h", str(host_key)],
                check=True,
                capture_output=True,
                text=True,
            )
            effective = set(result.stdout.splitlines())
            for setting in (
                "permitrootlogin without-password",
                "authenticationmethods publickey",
                "passwordauthentication no",
                "kbdinteractiveauthentication no",
                "pubkeyauthentication yes",
                "allowusers root",
            ):
                with self.subTest(setting=setting):
                    keyword = setting.split()[0]
                    actual = [line for line in effective if line.startswith(keyword + " ")]
                    self.assertTrue(setting in effective, f"Expected {setting}; got {actual}")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        raise SystemExit(__doc__)
    source = (
        pathlib.Path(sys.argv.pop())
        if len(sys.argv) == 2
        else pathlib.Path(__file__).with_name("finalize-debian.sh")
    )
    FINALIZER = source.read_text(encoding="utf-8")
    unittest.main()
