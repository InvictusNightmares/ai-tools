#!/usr/bin/env python3
"""Run an explicit ACME operation from private configuration; dry-run by default."""

import argparse
import json
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path

from common import ConfigError, absolute_path, append_log, domain, load_private, text

SERVERS = {"zerossl", "letsencrypt", "letsencrypt_test"}


def arguments(config, operation):
    prefix = config.get("acme_command")
    if not isinstance(prefix, list) or not prefix:
        raise ConfigError("acme_command must be an argument array")
    prefix = [text(part, "acme_command") for part in prefix]
    home = absolute_path(config.get("home"), "home")
    common = ["--home", home]
    if config.get("config_home"):
        common += ["--config-home", absolute_path(config["config_home"], "config_home")]
    if operation == "renew":
        return prefix + ["--cron"] + common
    server = config.get("server")
    if server not in SERVERS:
        raise ConfigError("unsupported ACME server")
    if server == "letsencrypt_test" and not config.get("config_home"):
        raise ConfigError("test issuance requires a separate config_home")
    if server == "letsencrypt_test" and os.path.normpath(config["config_home"]) == os.path.normpath(home):
        raise ConfigError("test config_home must differ from the production home")
    if operation == "register":
        email = text(config.get("email"), "email")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ConfigError("valid account email required")
        return prefix + ["--register-account", "--server", server, "-m", email] + common
    names = config.get("domains")
    if not isinstance(names, list) or not names:
        raise ConfigError("domains must be a nonempty list")
    names = [domain(name) for name in names]
    if operation == "issue":
        args = ["--issue", "--server", server, "--keylength", "ec-256"]
        method = config.get("validation")
        if method == "http":
            args += ["--webroot", absolute_path(config.get("webroot"), "webroot")]
        elif method == "dns":
            args += ["--dns", "dns_cf", "--challenge-alias", domain(config.get("challenge_alias")), "--dnssleep", "60"]
        else:
            raise ConfigError("validation must be http or dns")
        for name in names:
            args += ["-d", name]
    else:
        reload = config.get("reload_command")
        if not isinstance(reload, list) or not reload:
            raise ConfigError("reload_command must be an argument array")
        reload = [text(part, "reload_command") for part in reload]
        key_file = absolute_path(config.get("key_file"), "key_file")
        chain_file = absolute_path(config.get("fullchain_file"), "fullchain_file")
        if os.path.normpath(key_file) == os.path.normpath(chain_file):
            raise ConfigError("key and fullchain files must differ")
        args = ["--install-cert", "-d", names[0], "--ecc",
                "--key-file", key_file,
                "--fullchain-file", chain_file,
                "--reloadcmd", shlex.join(reload)]
    return prefix + args + common


def dns_environment(config):
    environment = os.environ.copy()
    if config.get("validation") != "dns":
        return environment
    path = Path(absolute_path(config.get("dns_env_file"), "dns_env_file"))
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ConfigError("DNS credentials must be a private regular file")
    parsed = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError("invalid DNS credential file")
        key, value = line.split("=", 1)
        if key not in ("CF_Token", "CF_Zone_ID") or key in parsed:
            raise ConfigError("only CF_Token and CF_Zone_ID are accepted")
        values = shlex.split(value)
        if len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]+", values[0]):
            raise ConfigError("invalid DNS credential value")
        parsed[key] = values[0]
    if set(parsed) != {"CF_Token", "CF_Zone_ID"}:
        raise ConfigError("both scoped DNS credential fields are required")
    if not re.fullmatch(r"[a-fA-F0-9]{32}", parsed["CF_Zone_ID"]):
        raise ConfigError("invalid scoped zone identifier")
    environment.update(parsed)
    return environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["register", "issue", "install", "renew"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--apply", action="store_true", help="execute; otherwise only validate and show a redacted plan")
    args = parser.parse_args()
    try:
        config = load_private(args.config)
        command = arguments(config, args.operation)
        environment = dns_environment(config) if args.operation in ("issue", "renew") else os.environ.copy()
        if not args.apply:
            print(json.dumps({"operation": args.operation, "dry_run": True, "argument_count": len(command)}))
            return 0
        os.umask(0o077)
        log_path = absolute_path(config.get("log_file"), "log_file")
        with append_log(log_path) as log:
            log.write(("\nACME operation: " + args.operation + "\n").encode())
            result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        print(json.dumps({"operation": args.operation, "success": result.returncode == 0, "exit_code": result.returncode}))
        return 0 if result.returncode == 0 else 1
    except (ConfigError, OSError, ValueError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, ConfigError) else "ACME operation failed; inspect the private log"
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
