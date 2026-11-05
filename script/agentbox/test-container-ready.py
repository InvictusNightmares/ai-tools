#!/usr/bin/env python3
"""Regressions for partial Docker network loss after an unavailable bind address."""

import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock


spec = importlib.util.spec_from_file_location(
    "container_ready", Path(__file__).with_name("ensure-container-ready.py"))
ready = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ready)


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.container = {
            "State": {"Running": True, "Error": ""},
            "HostConfig": {"RestartPolicy": {"Name": "unless-stopped"},
                           "PortBindings": {"8080/tcp": [{"HostIp": "192.0.2.1", "HostPort": "8080"}]}},
            "NetworkSettings": {
                "Networks": {"internal": {"EndpointID": "internal-endpoint"},
                             "outbound": {"EndpointID": "outbound-endpoint"}},
                "Ports": {"8080/tcp": [{"HostIp": "192.0.2.1", "HostPort": "8080"}]},
            },
        }
        self.docker = Mock(networks={"internal": {}, "outbound": {}})
        self.docker.inspect.side_effect = lambda: copy.deepcopy(self.container)
        self.docker.addresses_ready.return_value = True
        self.docker.reachable.return_value = True

        def connect(network):
            self.container["NetworkSettings"]["Networks"][network] = {"EndpointID": "restored"}
            if network == "outbound":
                self.container["NetworkSettings"]["Ports"] = copy.deepcopy(
                    self.container["HostConfig"]["PortBindings"])
        self.docker.connect.side_effect = connect
        self.docker.start.side_effect = lambda: self.container["State"].update(Running=True)

    def test_running_process_with_missing_outbound_network_is_repaired(self):
        # The old guard returned success immediately because Running was true.
        del self.container["NetworkSettings"]["Networks"]["outbound"]
        self.container["NetworkSettings"]["Ports"] = {"8080/tcp": None}
        self.assertTrue(ready.reconcile_once(self.docker))
        self.docker.connect.assert_called_once_with("outbound")
        self.docker.start.assert_not_called()
        self.docker.reachable.assert_called_once()

    def test_failed_bind_recovers_network_before_start(self):
        self.container["State"].update(
            Running=False, Error="failed to bind host port: cannot assign requested address")
        del self.container["NetworkSettings"]["Networks"]["outbound"]
        self.assertTrue(ready.reconcile_once(self.docker))
        actions = [call[0] for call in self.docker.mock_calls]
        self.assertLess(actions.index("connect"), actions.index("start"))

    def test_missing_bind_address_waits_without_mutation(self):
        self.docker.addresses_ready.return_value = False
        self.assertFalse(ready.reconcile_once(self.docker))
        self.docker.connect.assert_not_called()
        self.docker.start.assert_not_called()

    def test_intentional_stop_is_preserved(self):
        self.container["State"]["Running"] = False
        self.assertTrue(ready.reconcile_once(self.docker))
        self.docker.connect.assert_not_called()
        self.docker.start.assert_not_called()

    def test_missing_published_binding_cannot_report_success(self):
        self.container["NetworkSettings"]["Ports"] = {"8080/tcp": None}
        self.assertFalse(ready.reconcile_once(self.docker))

    def test_inaccessible_proxy_cannot_report_success(self):
        self.docker.reachable.return_value = False
        self.assertFalse(ready.reconcile_once(self.docker))

    def test_healthy_container_is_not_restarted(self):
        self.assertTrue(ready.reconcile_once(self.docker))
        self.docker.connect.assert_not_called()
        self.docker.start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
