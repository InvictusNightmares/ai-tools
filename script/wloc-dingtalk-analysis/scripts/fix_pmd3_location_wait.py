#!/usr/bin/env python3
"""Reversible fix for pymobiledevice3 11.50.0 DVT wait and transport selection.

Run with the Python interpreter that owns the pymobiledevice3 installation.
Only the exact inspected source is accepted; upgrades require a fresh review.
"""

import argparse
import hashlib
import importlib.metadata
import os
from pathlib import Path
import tempfile


VERSION = "11.50.0"
ORIGINAL_SHA256 = "bc91bb5933245e223464353aa6557f98e5a3733a420c2597696319db8dd24728"
MODULE_PATH = "pymobiledevice3/cli/developer/dvt/simulate_location.py"
OLD_IMPORT = "from pymobiledevice3.cli.cli_common import OSUTILS, ServiceProviderDep, async_command"
WAIT_ONLY_IMPORT = "from pymobiledevice3.cli.cli_common import ServiceProviderDep, async_command"
NEW_IMPORT = "from pymobiledevice3.cli.cli_common import RSDServiceProviderDep, async_command"
OLD_PARAMETER = "service_provider: ServiceProviderDep"
NEW_PARAMETER = "service_provider: RSDServiceProviderDep"
OLD_WAIT = "        OSUTILS.wait_return()"
NEW_WAIT = (
    '        print("Simulation session open. Press Ctrl+C to stop.", flush=True)\n'
    "        # Keep the DVT reader and in-process tunnel running while waiting.\n"
    "        await asyncio.Event().wait()"
)


def digest(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


def original_source(source: str) -> str:
    if digest(source) == ORIGINAL_SHA256:
        return source
    restored = source.removeprefix("import asyncio\n").replace(NEW_IMPORT, OLD_IMPORT)
    restored = restored.replace(WAIT_ONLY_IMPORT, OLD_IMPORT)
    restored = restored.replace(NEW_PARAMETER, OLD_PARAMETER).replace(NEW_WAIT, OLD_WAIT)
    if digest(restored) != ORIGINAL_SHA256:
        raise ValueError("Source differs from the verified 11.50.0 file; refusing to modify it.")
    if source not in (patched_source(restored), wait_only_source(restored)):
        raise ValueError("Partial or unexpected patch; refusing to modify it.")
    return restored


def wait_only_source(original: str) -> str:
    """Recognize the exact preliminary patch so it can be upgraded or restored."""
    if digest(original) != ORIGINAL_SHA256:
        raise ValueError("Expected the verified original source.")
    return "import asyncio\n" + original.replace(OLD_IMPORT, WAIT_ONLY_IMPORT).replace(OLD_WAIT, NEW_WAIT)


def patched_source(original: str) -> str:
    return wait_only_source(original).replace(WAIT_ONLY_IMPORT, NEW_IMPORT).replace(OLD_PARAMETER, NEW_PARAMETER)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="Exit 0 if fixed, 1 if the fix is needed.")
    action.add_argument("--apply", action="store_true", help="Apply the verified fix to this interpreter's package.")
    action.add_argument("--restore", action="store_true", help="Restore the exact original package source.")
    args = parser.parse_args()
    try:
        package = importlib.metadata.distribution("pymobiledevice3")
        if package.version != VERSION:
            raise ValueError(f"Expected pymobiledevice3 {VERSION}, found {package.version}; review before patching.")
        target = Path(package.locate_file(MODULE_PATH))
        source = target.read_text()
        original = original_source(source)
        fixed = patched_source(original)
        if args.check:
            print("Fixed: asynchronous wait and direct RSD selection." if source == fixed else "Fix needed: DVT wait and/or transport selection.")
            return 0 if source == fixed else 1
        replacement = original if args.restore else fixed
        if replacement == source:
            print("Already in the requested state.")
            return 0
        compile(replacement, str(target), "exec")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(replacement)
            temporary.chmod(target.stat().st_mode & 0o777)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(f"{'Restored' if args.restore else 'Fixed'}: {target}")
        return 0
    except (importlib.metadata.PackageNotFoundError, OSError, ValueError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
