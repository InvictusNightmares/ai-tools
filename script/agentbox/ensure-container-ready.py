#!/usr/bin/env python3
"""Recover failed address binding and reconcile a container's declared networks.

Deployment identifiers are supplied by the private systemd unit. A running PID
alone is insufficient: Docker can lose one network after a failed port bind.
"""

import argparse
import json
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse


def command(args):
    return subprocess.run(args, text=True, capture_output=True, timeout=20)


class Docker:
    def __init__(self, container, compose, service):
        self.container = container
        result = command(["docker", "compose", "-f", compose, "config", "--format", "json"])
        if result.returncode:
            raise RuntimeError("Cannot read the declared container configuration")
        config = json.loads(result.stdout)
        spec = config["services"][service]
        if spec.get("container_name") != container:
            raise RuntimeError("Declared container identity does not match")
        self.networks = {}
        for key, options in spec.get("networks", {}).items():
            self.networks[config["networks"][key]["name"]] = options or {}
        if not self.networks:
            raise RuntimeError("No managed networks are declared")
        self.aliases = [container, service]

    def inspect(self):
        result = command(["docker", "inspect", self.container])
        if result.returncode:
            if "no such" in result.stderr.lower():
                return None
            raise RuntimeError("Cannot inspect the container")
        return json.loads(result.stdout)[0]

    def addresses_ready(self, bindings):
        required = {b["HostIp"] for values in bindings.values() for b in values or []
                    if b.get("HostIp") not in (None, "", "0.0.0.0", "::")}
        result = command(["ip", "-j", "address", "show"])
        if result.returncode:
            return False
        available = {a["local"] for i in json.loads(result.stdout)
                     for a in i.get("addr_info", [])}
        return required <= available

    def connect(self, network):
        options = self.networks[network]
        unsupported = set(options) - {
            "aliases", "ipv4_address", "ipv6_address", "link_local_ips",
            "gw_priority", "priority", "driver_opts",
        }
        if unsupported:
            raise RuntimeError("Network options require explicit operator handling")
        args = ["docker", "network", "connect"]
        for alias in dict.fromkeys(self.aliases + (options.get("aliases") or [])):
            args += ["--alias", alias]
        for key, flag in (("ipv4_address", "--ip"), ("ipv6_address", "--ip6"),
                          ("gw_priority", "--gw-priority")):
            if key in options:
                args += [flag, str(options[key])]
        for ip in options.get("link_local_ips", []):
            args += ["--link-local-ip", ip]
        for key, value in options.get("driver_opts", {}).items():
            args += ["--driver-opt", f"{key}={value}"]
        result = command(args + [network, self.container])
        if result.returncode:
            raise RuntimeError("Declared network could not be restored")

    def start(self):
        if command(["docker", "start", self.container]).returncode:
            raise RuntimeError("Automatic container recovery failed")

    def reachable(self, container):
        bindings = container["HostConfig"].get("PortBindings") or {}
        for port, values in bindings.items():
            if not port.endswith("/tcp"):
                continue
            for binding in values or []:
                host = binding.get("HostIp") or "127.0.0.1"
                host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
                try:
                    with socket.create_connection((host, int(binding["HostPort"])), 3):
                        pass
                except OSError:
                    return False
        env = dict(value.split("=", 1) for value in container["Config"].get("Env", []))
        proxy = env.get("HTTPS_PROXY") or env.get("https_proxy")
        if proxy:
            parsed = urlparse(proxy)
            code = ("import socket; "
                    f"s=socket.create_connection(({parsed.hostname!r}, {parsed.port or 80}), 3); "
                    "s.close()")
            result = command(["nsenter", "-t", str(container["State"]["Pid"]),
                              "-n", sys.executable, "-c", code])
            if result.returncode:
                return False
        return True


def reconcile_once(docker):
    container = docker.inspect()
    if container is None:
        return True
    state = container["State"]
    policy = container["HostConfig"].get("RestartPolicy", {}).get("Name")
    error = state.get("Error", "").lower()
    recoverable = policy in ("always", "unless-stopped") and (
        "bind host port" in error and "cannot assign requested address" in error)
    if not state["Running"] and not recoverable:
        # An intentional stop must never be undone by a boot readiness check.
        return True
    bindings = container["HostConfig"].get("PortBindings") or {}
    if not docker.addresses_ready(bindings):
        return False
    for network in docker.networks:
        if network not in container["NetworkSettings"]["Networks"]:
            docker.connect(network)
    if not state["Running"]:
        docker.start()
    container = docker.inspect()
    if container is None or not container["State"]["Running"]:
        return False
    actual = container["NetworkSettings"]["Networks"]
    if any(not actual.get(n, {}).get("EndpointID") for n in docker.networks):
        return False
    published = container["NetworkSettings"].get("Ports") or {}
    for port, desired in bindings.items():
        for binding in desired or []:
            if binding not in (published.get(port) or []):
                return False
    return docker.reachable(container)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    parser.add_argument("--compose", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    docker = Docker(args.container, args.compose, args.service)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        if reconcile_once(docker):
            print("Container recovery and network readiness checks completed.")
            return
        time.sleep(3)
    raise RuntimeError("Container networking or configured listeners did not become ready")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        # Do not leak private compose values or command output into the journal.
        print(type(error).__name__ + ": readiness verification failed", file=sys.stderr)
        raise SystemExit(1)
