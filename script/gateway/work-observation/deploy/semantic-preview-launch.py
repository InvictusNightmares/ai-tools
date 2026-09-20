#!/usr/bin/env python3
"""Launch a loopback-only Auto route-preview process for offline analysis.

The launcher reads the active regional Auto environment from Docker metadata,
then execs the exact mounted release binary with only the preview-specific
listen/state and dedicated classifier settings changed. The cache secret and
classifier token are read from private files by the child configuration; they
are never passed in argv, written to logs, or printed.
"""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys


CASES = {
    "tokyo": {
        "container": "auto-acceptance-tokyo",
        "listen": "127.0.0.1:8095",
        "state_root": "/data/ai-gateway/acceptance-tokyo/state/work-observation-semantic-preview",
        "log_root": "/data/ai-gateway/acceptance-tokyo/logs/work-observation-semantic-preview",
        "secret_file": "/data/ai-gateway/acceptance-tokyo/secrets/cache-secret",
        "classifier_url": "http://106.14.254.110:9881/v1/chat/completions",
        "classifier_token_file": "/run/work-observation/auto-route-tokyo.token",
    },
    "us": {
        "container": "auto-acceptance-us",
        "listen": "127.0.0.1:8096",
        "state_root": "/data/ai-gateway/acceptance-us/state/work-observation-semantic-preview",
        "log_root": "/data/ai-gateway/acceptance-us/logs/work-observation-semantic-preview",
        "secret_file": "/data/ai-gateway/acceptance-us/secrets/cache-secret",
        "classifier_url": "http://106.14.254.110:9880/v1/chat/completions",
        "classifier_token_file": "/run/work-observation/auto-route-us.token",
    },
}


def fail(message):
    raise SystemExit("semantic_preview_launch_failed: " + message)


def read_private_file(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        fail("secret_path_invalid")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        fail("secret_unavailable:" + type(exc).__name__)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size < 32 or info.st_size > 4096:
            fail("secret_file_invalid")
        if stat.S_IMODE(info.st_mode) & 0o077:
            fail("secret_file_permissions")
        value = os.read(fd, 4097).decode("utf-8").strip()
    except (OSError, UnicodeDecodeError):
        fail("secret_file_invalid")
    finally:
        os.close(fd)
    if not value or "\n" in value or "\r" in value:
        fail("secret_value_invalid")
    return value


def ensure_private_dir(path):
    path = Path(path)
    if path.exists() and path.is_symlink():
        fail("state_path_symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        fail("state_path_not_directory")
    os.chmod(path, 0o700)
    return path


def inspect_env(container):
    try:
        raw = subprocess.check_output(
            ["/usr/bin/docker", "inspect", "-f", "{{json .Config.Env}}", container],
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
        )
        entries = json.loads(raw)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        fail("container_environment_unavailable")
    env = os.environ.copy()
    for entry in entries:
        if isinstance(entry, str) and "=" in entry:
            key, value = entry.split("=", 1)
            env[key] = value
    return env


def mounted_binary(container):
    try:
        path = subprocess.check_output(
            [
                "/usr/bin/docker",
                "inspect",
                "-f",
                '{{range .Mounts}}{{if eq .Destination "/app/auto-server"}}{{.Source}}{{end}}{{end}}',
                container,
            ],
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        fail("auto_binary_metadata_unavailable")
    binary = Path(path)
    if not binary.is_absolute() or not binary.is_file() or binary.is_symlink():
        fail("auto_binary_invalid")
    return binary


def main():
    if os.geteuid() != 0:
        fail("must_run_as_root")
    if len(sys.argv) != 2 or sys.argv[1] not in CASES:
        fail("region_required")
    region = sys.argv[1]
    case = CASES[region]
    state_root = ensure_private_dir(case["state_root"])
    log_root = ensure_private_dir(case["log_root"])
    files_root = ensure_private_dir(state_root / "files")
    secret = read_private_file(case["secret_file"])
    env = inspect_env(case["container"])
    # The preview uses only its dedicated token file. Do not inherit a shared
    # classifier or pilot credential from the host/container metadata.
    for name in ("AUTO_CLASSIFIER_TOKEN", "AUTO_GATEWAY_API_KEY_ID", "AUTO_GATEWAY_PILOT_TOKEN_FILE", "AUTO_UPSTREAM_TOKEN"):
        env.pop(name, None)
    env.update(
        {
            "AUTO_GATEWAY_LISTEN": case["listen"],
            "AUTO_GATEWAY_ROUTE_PREVIEW": "1",
            "AUTO_CLASSIFIER_URL": case["classifier_url"],
            "AUTO_CLASSIFIER_TOKEN_FILE": case["classifier_token_file"],
            "AUTO_GATEWAY_CACHE_SECRET": secret,
            "AUTO_GATEWAY_SESSION_STATE_PATH": str(state_root / "session-state.json"),
            "AUTO_GATEWAY_USAGE_SINK_PATH": str(log_root / "usage.jsonl"),
            "AUTO_GATEWAY_AUDIT_SINK_PATH": str(log_root / "route-audit.jsonl"),
            "AUTO_NATIVE_FILES_ROOT": str(files_root),
        }
    )
    binary = mounted_binary(case["container"])
    os.execve(str(binary), [str(binary)], env)


if __name__ == "__main__":
    main()
