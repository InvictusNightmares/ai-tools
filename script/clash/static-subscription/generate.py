#!/usr/bin/env python3
"""Generate a private static subscription with host Python and optional nginx reload."""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import dataclass

import yaml


MAX_BYTES = 8 * 1024 * 1024
GENERATION = re.compile(r"generation-[0-9a-f]{32}\Z")
BUILTINS = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "GLOBAL", "COMPATIBLE"}


class Failure(Exception):
    """A deliberately redacted error safe to send to an operational log."""


class Revoked(Failure):
    """The base subscription explicitly expired or denied access."""


def require(condition, message):
    if not condition:
        raise Failure(message)


def outside_repository(path: Path):
    require(not any((p / ".git").exists() for p in (path, *path.parents)),
            "private configuration and output must stay outside a Git checkout")


def absolute_path(value, field):
    require(isinstance(value, str) and Path(value).is_absolute(),
            f"{field} must be an absolute path")
    return Path(value).resolve()


def positive_int(value, field):
    require(type(value) is int and value > 0, f"{field} must be a positive integer")
    return value


def yaml_map(data, label):
    try:
        value = yaml.safe_load(data)
    except (yaml.YAMLError, UnicodeError, RecursionError):
        raise Failure(f"{label} is not valid YAML") from None
    require(isinstance(value, dict), f"{label} must be a YAML mapping")
    return value


@dataclass(frozen=True)
class Settings:
    base_url: str
    extra_url: str
    nodes: dict[str, str]
    output_dir: Path
    required_base_nodes: list[str]
    group: str = "PROXY"
    protected_groups: tuple[str, ...] = ("Auto",)
    user_agent: str = "ClashVerge"
    timeout_seconds: int = 20
    max_stale_seconds: int = 3600
    reader_gid: int | None = None
    nginx_check_command: tuple[str, ...] = ()
    nginx_reload_command: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: Path):
        outside_repository(path.resolve())
        require(path.is_file() and not path.is_symlink(), "config must be a regular private file")
        require(stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
                "config must not be readable by group or other users (use chmod 600)")
        data = yaml_map(path.read_bytes(), "config")
        fields = cls.__dataclass_fields__
        require(set(data) <= set(fields), "config contains unknown fields")
        for key in ("base_url", "extra_url", "nodes", "output_dir", "required_base_nodes"):
            require(key in data, f"config is missing {key}")
        for key in ("base_url", "extra_url"):
            require(isinstance(data[key], str), f"{key} must be an HTTPS URL")
            url = urllib.parse.urlsplit(data[key])
            require(url.scheme == "https" and bool(url.hostname) and not url.username and not url.fragment,
                    f"{key} must be an HTTPS URL without userinfo or a fragment")
        nodes = data["nodes"]
        require(isinstance(nodes, dict) and bool(nodes), "nodes must be a nonempty name mapping")
        require(all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
                    for k, v in nodes.items()), "node names must be nonempty strings")
        require(len(set(nodes.values())) == len(nodes), "destination node names must be unique")
        data["output_dir"] = absolute_path(data["output_dir"], "output_dir")
        outside_repository(data["output_dir"])
        for key in ("required_base_nodes", "protected_groups"):
            if key in data:
                require(isinstance(data[key], list) and all(isinstance(v, str) and v for v in data[key]),
                        f"{key} must be a list of names")
        require(bool(data["required_base_nodes"]), "required_base_nodes must not be empty")
        require(not set(data["required_base_nodes"]) & set(nodes.values()),
                "required base nodes must not be replaced nodes")
        for key in ("timeout_seconds", "max_stale_seconds"):
            if key in data:
                positive_int(data[key], key)
        if data.get("reader_gid") is not None:
            require(type(data["reader_gid"]) is int and data["reader_gid"] >= 0,
                    "reader_gid must be a nonnegative integer")
        for key in ("nginx_check_command", "nginx_reload_command"):
            value = data.get(key, [])
            require(isinstance(value, list) and all(isinstance(v, str) and v for v in value),
                    f"{key} must be an argument list")
            data[key] = tuple(value)
        require(bool(data["nginx_check_command"]) == bool(data["nginx_reload_command"]),
                "configure both nginx commands or neither")
        for key in ("group", "user_agent"):
            if key in data:
                require(isinstance(data[key], str) and data[key].strip()
                        and "\n" not in data[key] and "\r" not in data[key], f"invalid {key}")
        return cls(**data)


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require(urllib.parse.urlsplit(newurl).scheme == "https", "refusing a non-HTTPS redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, settings, label):
    request = urllib.request.Request(url, headers={
        "User-Agent": settings.user_agent, "Accept-Encoding": "identity", "Cache-Control": "no-cache",
    })
    try:
        with urllib.request.build_opener(HTTPSRedirects()).open(
                request, timeout=settings.timeout_seconds) as response:
            require(response.status == 200, f"{label} returned an unexpected HTTP status")
            body = response.read(MAX_BYTES + 1)
            require(len(body) <= MAX_BYTES, f"{label} exceeds the size limit")
            return yaml_map(body, label), response.headers.get("Subscription-Userinfo", "")
    except urllib.error.HTTPError as error:
        if label == "base" and error.code in (401, 403, 404, 410):
            raise Revoked("base subscription denied access") from None
        raise Failure(f"{label} returned HTTP {error.code}") from None
    except (OSError, urllib.error.URLError, ValueError):
        raise Failure(f"{label} download failed") from None


def userinfo(raw, now):
    values = {}
    for part in raw.split(";"):
        match = re.fullmatch(r"\s*(upload|download|total|expire)\s*=\s*([0-9]+)\s*", part)
        require(match is not None, "base subscription has missing or invalid traffic metadata")
        key, number = match.groups()
        require(key not in values, "base subscription has duplicate traffic metadata")
        values[key] = int(number)
    require({"upload", "download", "total"} <= values.keys(), "base traffic metadata is incomplete")
    values.setdefault("expire", 0)
    if values["expire"] and values["expire"] <= now:
        raise Revoked("base subscription has expired")
    if values["total"] and values["upload"] + values["download"] >= values["total"]:
        raise Revoked("base subscription quota is exhausted")
    return values


def named_entries(document, key):
    entries = document.get(key)
    require(isinstance(entries, list), f"{key} must be a list")
    require(all(isinstance(item, dict) and isinstance(item.get("name"), str)
                and item["name"].strip() for item in entries), f"{key} contains unnamed entries")
    names = [item["name"] for item in entries]
    require(len(names) == len(set(names)), f"{key} contains duplicate names")
    return {item["name"]: item for item in entries}


def filter_matches(pattern, name):
    try:
        return any(re.search(part, name) for part in pattern.split("`"))
    except (re.error, AttributeError):
        raise Failure("unsupported group filter; retain the previous subscription") from None


def dynamic_member(group, name, node_type):
    included = group.get("include-all") is True or group.get("include-all-proxies") is True
    return (included and filter_matches(group.get("filter", ".*"), name)
            and not excluded_member(group, name, node_type))


def excluded_member(group, name, node_type):
    # exclude-type uses adapter names (Shadowsocks), not YAML type names (ss).
    adapter = {"ss": "shadowsocks"}.get(node_type, node_type.lower())
    return (bool(group.get("exclude-filter") and filter_matches(group["exclude-filter"], name))
            or adapter in str(group.get("exclude-type", "")).lower().split("|"))


def merge(base, extra, settings):
    base_nodes = named_entries(base, "proxies")
    extra_nodes = named_entries(extra, "proxies")
    groups = named_entries(base, "proxy-groups")
    require(set(settings.required_base_nodes) <= base_nodes.keys(), "required base nodes are missing")
    require(settings.group in groups and groups[settings.group].get("type") == "select",
            "destination group must be an existing select group")
    require(not set(settings.nodes.values()) & (groups.keys() | BUILTINS),
            "destination node name collides with a group or built-in policy")
    replacements = {}
    for source_name, target_name in settings.nodes.items():
        require(source_name in extra_nodes, "a selected source node is missing")
        node = copy.deepcopy(extra_nodes[source_name])
        require(node.get("type") == "ss" and node.get("plugin") == "obfs",
                "selected nodes must be native Shadowsocks with obfs")
        require(all(isinstance(node.get(k), str) and node[k] for k in ("server", "cipher", "password")),
                "selected node is missing connection parameters")
        require(type(node.get("port")) is int and 1 <= node["port"] <= 65535, "invalid node port")
        opts = node.get("plugin-opts")
        require(isinstance(opts, dict) and opts.get("mode") in ("tls", "http")
                and isinstance(opts.get("host"), str) and bool(opts["host"]), "invalid obfs parameters")
        require(not node.get("dialer-proxy"), "selected node requires an external proxy chain")
        node["name"] = target_name
        replacements[target_name] = node
    for name in settings.protected_groups:
        require(name in groups, "a protected group is missing")
        require(name != settings.group, "destination group cannot also be protected")
        group = groups[name]
        for name, node in replacements.items():
            require(name not in group.get("proxies", []) and not dynamic_member(group, name, node["type"]),
                    "an added node would enter a protected group")
    merged = copy.deepcopy(base)
    merged["proxies"] = [copy.deepcopy(replacements.get(name, node)) for name, node in base_nodes.items()]
    merged["proxies"].extend(copy.deepcopy(node) for name, node in replacements.items() if name not in base_nodes)
    group = next(g for g in merged["proxy-groups"] if g["name"] == settings.group)
    refs = group.get("proxies", [])
    require(isinstance(refs, list) and all(isinstance(name, str) for name in refs),
            "destination group proxies must be a list of names")
    if group.get("include-all") is True or group.get("include-all-proxies") is True:
        # Do not offer the same node twice through explicit and dynamic members.
        group["proxies"] = [name for name in refs if name not in replacements]
        if group.get("filter"):
            missing = [name for name in replacements if not filter_matches(group["filter"], name)]
            if missing:
                exact = "^(" + "|".join(re.escape(name) for name in missing) + ")$"
                group["filter"] += "`" + exact
    else:
        group["proxies"] = list(dict.fromkeys([*refs, *replacements]))
    require(not any(excluded_member(group, name, node["type"]) for name, node in replacements.items()),
            "destination group exclusions hide an added node")
    require(isinstance(merged.get("rules"), list) and bool(merged["rules"]), "base rules are missing")
    return merged


def run_command(args, timeout, label):
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Failure(f"{label} could not complete") from None
    # Command output may contain credentials, URLs or private deployment paths.
    require(result.returncode == 0, f"{label} failed (exit {result.returncode})")


def validate_references(document):
    """Check local references without running a proxy core or fetching providers."""
    nodes = named_entries(document, "proxies")
    groups = named_entries(document, "proxy-groups")
    require(not nodes.keys() & (groups.keys() | BUILTINS), "node name collides with a policy")
    known = nodes.keys() | groups.keys() | BUILTINS
    mappings = {}
    for key in ("proxy-providers", "rule-providers", "sub-rules"):
        value = document.get(key, {})
        require(isinstance(value, dict) and all(isinstance(name, str) and name for name in value),
                f"{key} must be a name mapping")
        mappings[key] = value
    for group in groups.values():
        refs = group.get("proxies", [])
        require(isinstance(refs, list) and all(isinstance(name, str) and name in known for name in refs),
                "a group references an unknown policy")
        providers = group.get("use", [])
        require(isinstance(providers, list)
                and all(isinstance(name, str) and name in mappings["proxy-providers"] for name in providers),
                "a group references an unknown proxy provider")
    for rules in [document.get("rules"), *mappings["sub-rules"].values()]:
        require(isinstance(rules, list) and bool(rules), "rules must be a nonempty list")
        for rule in rules:
            require(isinstance(rule, str), "rules must contain strings")
            parts = [part.strip() for part in rule.split(",")]
            while len(parts) > 1 and parts[-1] in ("no-resolve", "src", "dst"):
                parts.pop()
            require(len(parts) >= 2 and bool(parts[0]), "invalid rule structure")
            targets = mappings["sub-rules"] if parts[0] == "SUB-RULE" else known
            require(parts[-1] in targets, "a rule references an unknown policy or sub-rule")
            if parts[0] == "RULE-SET":
                require(len(parts) >= 3 and parts[1] in mappings["rule-providers"],
                        "a rule references an unknown rule provider")


def permissions(path, settings, directory=False):
    if settings.reader_gid is not None:
        os.chown(path, -1, settings.reader_gid)
    os.chmod(path, (0o750 if directory else 0o640) if settings.reader_gid is not None
             else (0o700 if directory else 0o600))


def write_private(path, content, settings):
    with path.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    permissions(path, settings)


def current_target(root):
    current = root / "current"
    if not current.is_symlink():
        require(not current.exists(), "output current path must be a managed symlink")
        return None
    target = os.readlink(current)
    require(GENERATION.fullmatch(target) is not None, "output current symlink is not managed")
    require((root / target).is_dir() and not (root / target).is_symlink(), "current generation is invalid")
    return target


def switch_current(root, target):
    if target is None:
        (root / "current").unlink(missing_ok=True)
        return
    link = root / (".current-" + uuid.uuid4().hex)
    try:
        link.symlink_to(target)
        os.replace(link, root / "current")
    finally:
        link.unlink(missing_ok=True)


@contextmanager
def publish_lock(settings):
    root = settings.output_dir
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    permissions(root, settings, directory=True)
    with (root / ".lock").open("a") as lock:
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Failure("another generator is already running") from None
        yield


def withdraw_if_expired(settings, now, revoked=False):
    target = current_target(settings.output_dir)
    if target is None:
        return False
    try:
        state = json.loads((settings.output_dir / target / "state.json").read_bytes())
        deadline = min(state["generated_at"] + settings.max_stale_seconds, state["valid_until"])
        expired = now >= deadline
    except (OSError, ValueError, KeyError, TypeError):
        expired = True
    if revoked or expired:
        # Keep the header include available so unrelated nginx reloads still work.
        # An unlinked YAML returns 404 even if nginx retains the previous header.
        (settings.output_dir / target / "subscription.yaml").unlink(missing_ok=True)
        return True
    return False


def publish(candidate, stats, settings, now):
    root = settings.output_dir
    previous = current_target(root)
    generation = root / ("generation-" + uuid.uuid4().hex)
    generation.mkdir(mode=0o700)
    switched = False
    try:
        permissions(generation, settings, directory=True)
        write_private(generation / "subscription.yaml", candidate, settings)
        header = "; ".join(f"{key}={stats[key]}" for key in ("upload", "download", "total", "expire"))
        write_private(generation / "headers.conf",
                      f'add_header Subscription-Userinfo "{header}" always;\n'.encode(), settings)
        state = {"generated_at": now, "valid_until": stats["expire"] or now + settings.max_stale_seconds}
        write_private(generation / "state.json", json.dumps(state).encode(), settings)
        switch_current(root, generation.name)
        switched = True
        if settings.nginx_check_command:
            run_command(settings.nginx_check_command, 30, "nginx configuration check")
            run_command(settings.nginx_reload_command, 30, "nginx reload")
    except BaseException:
        if switched:
            switch_current(root, previous)
        shutil.rmtree(generation)
        raise
    if previous:
        try:
            shutil.rmtree(root / previous)
        except OSError:
            print("WARNING: old generation cleanup failed", file=sys.stderr)


def generate(settings, dry_run=False):
    now = int(time.time())
    base, raw_stats = fetch(settings.base_url, settings, "base")
    stats = userinfo(raw_stats, now)
    extra, _ = fetch(settings.extra_url, settings, "extra")
    merged = merge(base, extra, settings)
    validate_references(merged)
    candidate = yaml.safe_dump(merged, allow_unicode=True, sort_keys=False).encode()
    finished_at = int(time.time())
    stats = userinfo(raw_stats, finished_at)
    require(finished_at < now + settings.max_stale_seconds, "candidate exceeded its freshness limit")
    if not dry_run:
        publish(candidate, stats, settings, now)
    return {"status": "validated" if dry_run else "published", "nodes": len(merged["proxies"]),
            "selected_nodes": len(settings.nodes), "traffic_source": "base_only"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="private configuration outside the repository")
    parser.add_argument("--dry-run", action="store_true", help="fetch and validate without publishing or reloading nginx")
    args = parser.parse_args(argv)
    try:
        settings = Settings.load(args.config)
        if args.dry_run:
            result = generate(settings, dry_run=True)
        else:
            with publish_lock(settings):
                try:
                    result = generate(settings)
                except (Failure, OSError, ValueError, TypeError, RecursionError) as error:
                    withdrawn = withdraw_if_expired(settings, int(time.time()), isinstance(error, Revoked))
                    if withdrawn:
                        print("previous subscription withdrawn: expired or access revoked", file=sys.stderr)
                    raise
        print(json.dumps(result))
        return 0
    except Failure as error:
        print(f"ERROR: {error}", file=sys.stderr)
    except (OSError, ValueError, TypeError, RecursionError):
        print("ERROR: local configuration, filesystem or serialization failure", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
