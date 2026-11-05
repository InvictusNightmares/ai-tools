#!/usr/bin/env python3
"""Device-free regression checks against the installed DVT command handlers."""

import asyncio
import importlib.metadata
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import AsyncMock, patch

import fix_pmd3_location_wait as fix


async def probe(command: str) -> None:
    from pymobiledevice3.cli.developer.dvt import simulate_location as cli

    provider = AsyncMock()
    simulation = AsyncMock()
    simulation.__aenter__.return_value = simulation
    with patch.object(cli, "DvtProvider", return_value=provider), patch.object(
        cli, "LocationSimulation", return_value=simulation
    ):
        if command == "set":
            operation = cli.dvt_simulate_location_set.__wrapped__(object(), 39.9087, 116.3975)
        else:
            operation = cli.dvt_simulate_location_play.__wrapped__(object(), Path("unused.gpx"), 0, False)
        task = asyncio.create_task(operation)
        # Models another tunnel callback on the same loop. The original sigwait
        # prevents this callback from ever running, so the parent times out.
        await asyncio.sleep(0.05)
        assert not task.done(), "Simulation must keep its session open."
        if command == "set":
            simulation.set.assert_awaited_once_with(39.9087, 116.3975)
        else:
            simulation.play_gpx_file.assert_awaited_once_with(
                "unused.gpx", disable_sleep=False, timing_randomness_range=0
            )
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        provider.__aexit__.assert_awaited_once()
        simulation.__aexit__.assert_awaited_once()
        print("RESPONSIVE_AND_CLEANED_UP")


def routing_probe() -> None:
    from typer.testing import CliRunner
    from pymobiledevice3.cli import cli_common
    from pymobiledevice3.cli.developer.dvt import simulate_location as cli
    from pymobiledevice3.remote import userspace_tunnel

    provider = AsyncMock()
    simulation = AsyncMock()
    simulation.__aenter__.return_value = simulation

    async def schedule_cancellation(*args):
        task = asyncio.current_task()
        asyncio.get_running_loop().call_later(0.05, task.cancel)

    simulation.set.side_effect = schedule_cancellation
    with patch.object(cli_common, "_resolve_target_serial", return_value=None), patch.object(
        cli_common, "default_transport_preference", return_value="userspace"
    ), patch.object(
        cli_common, "_usbmux_service_provider",
        side_effect=AssertionError("DVT location must select RSD before invoking the command"),
    ), patch.object(
        userspace_tunnel, "establish_userspace_rsd", new_callable=AsyncMock
    ) as tunnel, patch.object(cli, "DvtProvider", return_value=provider), patch.object(
        cli, "LocationSimulation", return_value=simulation
    ):
        result = CliRunner().invoke(cli.cli, ["set", "--", "39.9087", "116.3975"])
        assert result.exit_code == 130, (result.output, repr(result.exception))
        tunnel.assert_awaited_once()
        simulation.set.assert_awaited_once_with(39.9087, 116.3975)
        provider.__aexit__.assert_awaited_once()
        print("RESPONSIVE_AND_CLEANED_UP")


class SimulationWaitTests(unittest.TestCase):
    def check_command(self, command: str) -> None:
        try:
            result = subprocess.run(
                [sys.executable, __file__, "--probe", command],
                capture_output=True, text=True, timeout=5,
            )
        except subprocess.TimeoutExpired:
            self.fail(f"{command} blocked the event loop; tunnel callbacks and cancellation cannot run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESPONSIVE_AND_CLEANED_UP", result.stdout)

    def test_set_keeps_event_loop_responsive_and_closes_on_cancellation(self):
        self.check_command("set")

    def test_play_keeps_event_loop_responsive_and_closes_on_cancellation(self):
        self.check_command("play")

    def test_default_cli_selects_rsd_without_legacy_retry(self):
        self.check_command("routing")

    def test_patch_can_be_reapplied_and_reversed_exactly(self):
        package = importlib.metadata.distribution("pymobiledevice3")
        original = fix.original_source(Path(package.locate_file(fix.MODULE_PATH)).read_text())
        patched = fix.patched_source(original)
        self.assertEqual(fix.original_source(patched), original)
        self.assertEqual(fix.patched_source(fix.original_source(patched)), patched)
        self.assertEqual(fix.digest(original), fix.ORIGINAL_SHA256)

    def test_unrecognized_source_is_rejected(self):
        with self.assertRaises(ValueError):
            fix.original_source("# a different package version\n")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--probe":
        if sys.argv[2] == "routing":
            routing_probe()
        else:
            asyncio.run(probe(sys.argv[2]))
    else:
        unittest.main()
