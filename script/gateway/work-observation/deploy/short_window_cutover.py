#!/usr/bin/env python3
"""Safely switch one Docker Nginx ingress to its collector sidecar.

The command is deliberately narrow: it changes one exact proxy_pass line,
keeps an immutable backup and refuses to overwrite configuration drift. It
does not retry user requests and never changes the upstream used by the
collector itself.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


SIDECAR_SUFFIX = os.environ.get("WO_SIDECAR_SUFFIX", "")


REGIONS = {
    "tokyo": {
        "container": "tokyo-sub2api-proxy",
        "config": "/data/tokyo-sub2api-proxy/nginx.conf",
        "original": "proxy_pass http://tokyo_sub2api_upstream;",
        "collector": "proxy_pass http://127.0.0.1:18400;",
        "sidecar": "work-observation-collector-tokyo" + SIDECAR_SUFFIX,
        "store": "/data/work-observation/tokyo",
    },
    "us": {
        "container": "us-sub2api-proxy",
        "config": "/data/us-sub2api-proxy/nginx.conf",
        "original": "proxy_pass http://sub2api_upstream;",
        "collector": "proxy_pass http://127.0.0.1:18401;",
        "sidecar": "work-observation-collector-us" + SIDECAR_SUFFIX,
        "store": "/data/work-observation/us",
    },
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def docker(*args, capture=False):
    command = ["docker", *args]
    if capture:
        return subprocess.check_output(command, universal_newlines=True, stderr=subprocess.STDOUT)
    subprocess.run(command, check=True)
    return ""


def atomic_write(path, data, mode):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def check_container(region):
    item = REGIONS[region]
    running = docker("inspect", "--format", "{{.State.Running}}", item["container"], capture=True).strip()
    if running != "true":
        raise RuntimeError("nginx_container_not_running")


def check_sidecar(region):
    item = REGIONS[region]
    running = docker("inspect", "--format", "{{.State.Running}}", item["sidecar"], capture=True).strip()
    if running != "true":
        raise RuntimeError("collector_sidecar_not_running")


def check_collector_path(region):
    item = REGIONS[region]
    port = "18400" if region == "tokyo" else "18401"
    # This is a GET / health probe to the existing upstream. It does not send
    # a model request and proves the shared network namespace is usable.
    docker("exec", item["container"], "sh", "-c", f"timeout 10 wget -q -O /dev/null http://127.0.0.1:{port}/")


def container_has_collector_route(region):
    """Check the rendered configuration, not only the host bind source."""
    item = REGIONS[region]
    try:
        rendered = docker("exec", item["container"], "nginx", "-T", capture=True)
    except subprocess.CalledProcessError:
        return False
    return item["collector"] in rendered


def nginx_test_reload(region):
    container = REGIONS[region]["container"]
    mounted_read_write = docker(
        "inspect",
        "--format",
        "{{range .Mounts}}{{if eq .Destination \"/etc/nginx/nginx.conf\"}}{{.RW}}{{end}}{{end}}",
        container,
        capture=True,
    ).strip()
    if mounted_read_write == "false":
        # The production containers bind-mount nginx.conf read-only. A host
        # side atomic replace therefore becomes visible only after Docker
        # remounts the file during a container restart.
        docker("restart", container)
    else:
        docker("exec", container, "nginx", "-t")
        docker("exec", container, "nginx", "-s", "reload")
    docker("exec", container, "nginx", "-t")


def read_manifest(state_dir, region):
    state = Path(state_dir)
    if state.is_symlink():
        raise RuntimeError("cutover_state_dir_is_symlink")
    path = state / f"active-{region}.json"
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("cutover_manifest_missing")
    manifest = json.loads(path.read_text())
    item = REGIONS[region]
    if (
        manifest.get("region") != region
        or manifest.get("config") != item["config"]
        or manifest.get("collector") != item["collector"]
        or manifest.get("state") not in ("prepared", "enabled")
    ):
        raise RuntimeError("cutover_manifest_mismatch_or_not_enabled")
    return path, manifest


def validate_state_dir(state_dir):
    state = Path(state_dir)
    if state.exists() and state.is_symlink():
        raise RuntimeError("cutover_state_dir_is_symlink")
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    if state.is_symlink() or not state.is_dir():
        raise RuntimeError("cutover_state_dir_invalid")
    return state


@contextmanager
def state_lock(state_dir):
    state = validate_state_dir(state_dir)
    lock_path = state / ".cutover.lock"
    with lock_path.open("a+") as stream:
        os.chmod(lock_path, 0o600)
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield state
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def write_manifest(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2).encode() + b"\n", 0o600)


def enable(region, state_dir, dry_run=False):
    item = REGIONS[region]
    with state_lock(state_dir) as state:
        config = Path(item["config"])
        if config.is_symlink() or not config.is_file():
            raise RuntimeError("nginx_config_missing_or_symlink")
        original = config.read_bytes()
        text = original.decode()
        # A boot-time supervisor may run after a clean process restart while
        # the route is already active.  Treat that exact, manifest-backed
        # state as success; never silently accept an active route with a
        # missing or mismatched rollback manifest.
        if item["collector"] in text:
            try:
                manifest_path, manifest = read_manifest(state_dir, region)
                if (
                    manifest.get("state") == "enabled"
                    and digest(original) == manifest.get("enabled_sha256")
                ):
                    check_container(region)
                    check_sidecar(region)
                    if not dry_run:
                        # A read-only single-file bind mount can retain an
                        # old inode after a host-side atomic replace.
                        if not container_has_collector_route(region):
                            nginx_test_reload(region)
                        check_collector_path(region)
                    print(json.dumps(manifest, ensure_ascii=False, indent=2))
                    return
            except (OSError, ValueError, RuntimeError, json.JSONDecodeError):
                pass
            raise RuntimeError("collector_route_already_enabled_without_valid_manifest")
        if text.count(item["original"]) != 1:
            raise RuntimeError("nginx_config_drift_or_unexpected_upstream")
        check_container(region)
        check_sidecar(region)
        if not dry_run:
            check_collector_path(region)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = state / f"{region}-{stamp}.nginx.conf"
        manifest_path = state / f"active-{region}.json"
        updated = text.replace(item["original"], item["collector"], 1).encode()
        manifest = {
            "region": region,
            "config": str(config),
            "backup": str(backup),
            "original_sha256": digest(original),
            "enabled_sha256": digest(updated),
            "collector": item["collector"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "state": "planned" if dry_run else "prepared",
        }
        if dry_run:
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return
        atomic_write(backup, original, config.stat().st_mode & 0o777)
        # Re-read immediately before the mutation so an external edit cannot
        # be silently overwritten between the first check and atomic_write.
        if config.is_symlink() or digest(config.read_bytes()) != digest(original):
            raise RuntimeError("nginx_config_changed_before_enable")
        write_manifest(manifest_path, manifest)
        try:
            atomic_write(config, updated, config.stat().st_mode & 0o777)
            nginx_test_reload(region)
        except Exception:
            atomic_write(config, original, config.stat().st_mode & 0o777)
            nginx_test_reload(region)
            try:
                nginx_test_reload(region)
            except Exception:
                pass
            raise
        try:
            manifest["state"] = "enabled"
            write_manifest(manifest_path, manifest)
        except Exception as error:
            # Do not leave a live collector route without a usable manifest.
            try:
                atomic_write(config, original, config.stat().st_mode & 0o777)
                nginx_test_reload(region)
                manifest["state"] = "rolled_back_after_manifest_failure"
                write_manifest(manifest_path, manifest)
            except Exception as rollback_error:
                raise RuntimeError(f"manifest_write_failed_and_rollback_failed:{rollback_error}") from error
            raise RuntimeError("manifest_write_failed_route_rolled_back") from error
        print(json.dumps(manifest, ensure_ascii=False, indent=2))


def rollback(region, state_dir, dry_run=False):
    item = REGIONS[region]
    with state_lock(state_dir) as _state:
        manifest_path, manifest = read_manifest(state_dir, region)
        config = Path(item["config"])
        if config.is_symlink() or str(config) != manifest["config"]:
            raise RuntimeError("cutover_manifest_config_mismatch")
        backup = Path(manifest["backup"])
        if backup.is_symlink() or not backup.is_file():
            raise RuntimeError("cutover_backup_missing_or_symlink")
        original = backup.read_bytes()
        if digest(original) != manifest["original_sha256"]:
            raise RuntimeError("cutover_backup_checksum_mismatch")
        current = config.read_bytes()
        if digest(current) == manifest["original_sha256"]:
            # A crash can happen after the prepared manifest is written but
            # before the route mutation. Mark it rolled back without touching
            # Nginx again.
            result = dict(manifest, state="planned_rollback" if dry_run else "rolled_back")
            if dry_run:
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return
            write_manifest(manifest_path, result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        if digest(current) != manifest["enabled_sha256"]:
            raise RuntimeError("nginx_config_drift_since_enable")
        result = dict(manifest, state="planned_rollback" if dry_run else "rolled_back")
        if dry_run:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        atomic_write(config, original, config.stat().st_mode & 0o777)
        try:
            nginx_test_reload(region)
        except Exception:
            atomic_write(config, current, config.stat().st_mode & 0o777)
            try:
                nginx_test_reload(region)
            except Exception:
                pass
            raise
        try:
            write_manifest(manifest_path, result)
        except Exception as error:
            raise RuntimeError("route_rolled_back_manifest_write_failed") from error
        print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enable", "rollback"))
    parser.add_argument("region", choices=sorted(REGIONS))
    parser.add_argument("--state-dir", default="/var/lib/work-observation/cutover")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "enable":
            enable(args.region, args.state_dir, args.dry_run)
        else:
            rollback(args.region, args.state_dir, args.dry_run)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"cutover_failed: {error}")


if __name__ == "__main__":
    main()
