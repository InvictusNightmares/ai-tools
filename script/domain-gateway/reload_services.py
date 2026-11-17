#!/usr/bin/env python3
"""Validate and load one installed certificate into its Docker consumers.

The ACME renewal unit must hold the same lock while installing certificates.
This prevents restarting a container that is still running its ACME client.
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from common import ConfigError, absolute_path, domain, load_private


def command(args, *, data=None, timeout=30):
    return subprocess.run(args, input=data, capture_output=True, check=True,
                          timeout=timeout).stdout


def validate_config(config):
    for key in ("certificate", "private_key", "lock_file", "state_file"):
        absolute_path(config[key], key)
    if config["certificate"] == config["private_key"]:
        raise ConfigError("certificate and key must be different files")
    for key in ("panel_container", "gateway_container"):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", config[key]):
            raise ConfigError("invalid container name")
    if not config.get("domains"):
        raise ConfigError("at least one certificate identity is required")
    for name in config["domains"]:
        domain(name)
    return config


def certificate_digest(config):
    cert, key = config["certificate"], config["private_key"]
    for filename in (cert, key):
        path = Path(filename)
        if path.is_symlink() or not path.is_file():
            raise ConfigError("certificate material must be regular files")
    if Path(key).stat().st_mode & 0o077:
        raise ConfigError("private key permissions are too broad")
    command(["openssl", "x509", "-in", cert, "-noout", "-checkend", "86400"])
    for name in config["domains"]:
        checked = command(["openssl", "x509", "-in", cert, "-noout", "-checkhost", name])
        if b" does match certificate" not in checked:
            raise ConfigError("certificate identity does not match")
    cert_pub = command(["openssl", "x509", "-in", cert, "-noout", "-pubkey"])
    key_pub = command(["openssl", "pkey", "-in", key, "-pubout"])
    if cert_pub != key_pub:
        raise ConfigError("certificate and private key do not match")
    # Include intermediates so a changed chain is loaded even for the same leaf.
    return hashlib.sha256(Path(cert).read_bytes()).hexdigest()


def wait_for_acme(panel, *, timeout=300):
    deadline = time.monotonic() + timeout
    while True:
        processes = command(["docker", "top", panel, "-eo", "pid,args"]).decode()
        if not any(re.search(r"(?:^|[\s/])acme\.sh(?:\s|$)", line)
                   for line in processes.splitlines()[1:]):
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("ACME is still running; certificate reload deferred")
        time.sleep(2)


def wait_for_panel(panel, *, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        processes = command(["docker", "top", panel, "-eo", "pid,args"]).decode()
        if re.search(r"(?:^|\s)/app/x-ui(?:\s|$)", processes) and "xray-" in processes:
            return
        time.sleep(1)
    raise TimeoutError("panel and proxy did not become ready")


def reload_locked(config, *, force=False):
    """Caller holds the renewal lock. Never mark a partial reload successful."""
    digest = certificate_digest(config)
    state = Path(config["state_file"])
    if state.is_symlink():
        raise ConfigError("state file must not be a symlink")
    if not force and state.is_file() and state.read_text().strip() == digest:
        return "unchanged"
    panel, gateway = config["panel_container"], config["gateway_container"]
    wait_for_acme(panel)
    # Check gateway before interrupting any consumers.
    command(["docker", "exec", gateway, "nginx", "-t"])
    if certificate_digest(config) != digest:
        raise ConfigError("certificate changed during validation; retry required")
    command(["docker", "restart", panel], timeout=60)
    wait_for_panel(panel)
    command(["docker", "exec", gateway, "nginx", "-s", "reload"])
    if certificate_digest(config) != digest:
        raise ConfigError("certificate changed during reload; retry required")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    with os.fdopen(os.open(state, flags, 0o600), "w") as stream:
        stream.write(digest + "\n")
    return "reloaded"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    config = validate_config(load_private(args.config))
    fd = os.open(config["lock_file"], os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        deadline = time.monotonic() + 300
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("renewal lock is busy; retry later")
                time.sleep(2)
        print(json.dumps({"status": reload_locked(config, force=args.force)}))


if __name__ == "__main__":
    try:
        main()
    except (ConfigError, OSError, ValueError, KeyError, TypeError,
            subprocess.SubprocessError) as exc:
        # Do not leak command arguments, paths, identities or PEM material.
        print(json.dumps({"status": "failed", "error": type(exc).__name__}))
        raise SystemExit(1) from None
