#!/usr/bin/env python3
"""Render one reviewed template; never deploy or overwrite live files."""

import argparse
import ipaddress
import json
from pathlib import Path
import re
import sys

from common import ConfigError, domain, load_private, text, write_new_private

TEMPLATES = Path(__file__).resolve().parent / "templates"
TOKEN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


def value_for(key, values):
    if key == "SNI_ROUTES":
        names = values.get("WEB_DOMAINS")
        if not isinstance(names, list) or not names:
            raise ConfigError("WEB_DOMAINS must be a nonempty list")
        port = value_for("TLS_PORT", values)
        return "\n".join(f"        {domain(name)} 127.0.0.1:{port};" for name in names)
    if key == "SERVER_NAMES":
        names = values.get("WEB_DOMAINS")
        if not isinstance(names, list) or not names:
            raise ConfigError("WEB_DOMAINS must be a nonempty list")
        return " ".join(domain(name) for name in names)
    if key not in values:
        raise ConfigError(f"missing template field: {key}")
    value = values[key]
    if key.endswith("_PORT"):
        if type(value) is not int or not 1 <= value <= 65535:
            raise ConfigError(f"valid integer port required: {key}")
        return str(value)
    value = text(value, key)
    if key.endswith("_DOMAIN"):
        return domain(value)
    if key == "PRIVATE_BIND_IP":
        try:
            address = ipaddress.ip_address(value)
            allowed = address in ipaddress.ip_network("100.64.0.0/10")
        except ValueError:
            allowed = False
        if not allowed:
            raise ConfigError("PRIVATE_BIND_IP must be a Tailscale IPv4 address")
    if key == "RENEW_CALENDAR":
        if not re.fullmatch(r"[0-9*,: /-]+", value):
            raise ConfigError("unsupported calendar expression")
        return value
    if any(c.isspace() or c in '\"\'{};$`\\#' for c in value):
        raise ConfigError(f"unsafe template scalar: {key}")
    return value


def render(name, values):
    allowed = {p.name for p in TEMPLATES.glob("*.template")}
    if name not in allowed:
        raise ConfigError("unknown bundled template")
    source = (TEMPLATES / name).read_text()
    port_keys = ["HTTP_PORT", "HTTPS_PORT"]
    if name == "public-nginx.conf.template":
        port_keys += ["TLS_PORT", "RAW_PORT"]
    if name in ("public-nginx.conf.template", "private-nginx.conf.template"):
        ports = [value_for(key, values) for key in port_keys]
        if len(set(ports)) != len(ports):
            raise ConfigError("gateway listener ports must differ")
    result = TOKEN.sub(lambda match: value_for(match.group(1), values), source)
    if "{{" in result:
        raise ConfigError("unresolved template placeholder")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True)
    parser.add_argument("--values", required=True, help="0600 private JSON file")
    parser.add_argument("--output", required=True, help="new private file; existing files are refused")
    args = parser.parse_args()
    try:
        output = render(args.template, load_private(args.values))
        write_new_private(args.output, output)
    except (ConfigError, OSError) as error:
        message = str(error) if isinstance(error, ConfigError) else "private output could not be created"
        print(message, file=sys.stderr)
        return 1
    print(json.dumps({"template": args.template, "rendered": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
