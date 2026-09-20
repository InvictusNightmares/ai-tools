#!/usr/bin/env python3
"""Collector watchdog for one already-enabled capture window.

It fails closed for collector integrity errors, storage pressure, or a dead
sidecar. Per-event projection/truncation warnings remain visible in the
window result and do not tear down the path: malformed or canceled client
bodies are data-quality gaps, not evidence that the collector itself cannot
continue. Upstream HTTP 5xx responses are recorded for analysis and are only a
rollback trigger when ``--max-5xx`` is non-negative; ordinary upstream errors
must not silently turn off an otherwise healthy capture path.
Latency p95 is intentionally reported as a required post-window check because
the collector status endpoint does not expose a latency histogram.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import time

from short_window_cutover import REGIONS, read_manifest, rollback


"""Counters that indicate the collector itself can no longer preserve data.

`truncated` and `projection_errors` are deliberately not in this set. A
single oversized, malformed, or aborted exchange is a quality warning for
that exchange; treating it as a process failure would turn one incomplete
record into a full production cutover rollback. The rolling analysis still
reports both counters and the source record remains marked incomplete.
"""
BAD_COUNTERS = (
    "dropped",
    "write_errors",
    "loss_persist_errors",
    "unavailable_bypassed_requests",
)
WARN_COUNTERS = ("truncated", "projection_errors")
STATUS_KEYS = BAD_COUNTERS + WARN_COUNTERS + ("queued_bytes", "queue_limit_bytes", "capture_enabled", "capture_unavailable")
STATUS_LINE = re.compile(r'"\s+(\d{3})\s')


class WatchInterrupted(RuntimeError):
    pass


def docker(*args):
    return subprocess.check_output(["docker", *args], universal_newlines=True, stderr=subprocess.STDOUT)


def status(region):
    container = REGIONS[region]["sidecar"]
    raw = docker("exec", container, "/opt/observe", "status", "--dir", "/data/store")
    value = json.loads(raw)
    return {key: value.get(key) for key in STATUS_KEYS}


def running(region):
    return docker("inspect", "--format", "{{.State.Running}}", REGIONS[region]["sidecar"]).strip() == "true"


def collector_path_ready(region):
    """Check the current Nginx namespace can reach the sidecar listener."""
    item = REGIONS[region]
    port = "18400" if region == "tokyo" else "18401"
    try:
        docker(
            "exec", item["container"], "sh", "-c",
            f"timeout 10 wget -q -O /dev/null http://127.0.0.1:{port}/",
        )
    except subprocess.CalledProcessError:
        return False
    return True


def disable(region):
    docker("exec", REGIONS[region]["sidecar"], "/opt/observe", "disable", "--dir", "/data/store")


def access_log_state(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("access_log_missing_or_symlink")
    stat = path.stat()
    return stat.st_ino, stat.st_size, 0


def access_log_delta(path, state):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("access_log_missing_or_symlink")
    current = path.stat()
    if current.st_ino != state[0] or current.st_size < state[1]:
        # Access-log rotation is normal on a long-lived production ingress.
        # The log is only an advisory 5xx signal; reset the cursor and keep
        # the collector alive rather than turning rotation into a rollback.
        return 0, (current.st_ino, current.st_size, 0)
    five_xx = 0
    with path.open("rb") as stream:
        stream.seek(state[1])
        for raw in stream:
            match = STATUS_LINE.search(raw.decode("utf-8", "replace"))
            if match and match.group(1).startswith("5"):
                five_xx += 1
    return five_xx, (current.st_ino, current.st_size, five_xx)


def run(args):
    region = args.region
    item = REGIONS[region]
    store = Path(item["store"])
    started = datetime.now(timezone.utc).isoformat()
    route_enabled = False
    try:
        _, manifest = read_manifest(args.state_dir, region)
        route_enabled = manifest.get("state") in ("prepared", "enabled")
    except Exception:
        # A missing/invalid manifest means there is no safe route to restore.
        # The watchdog still reports its startup failure without touching Nginx.
        pass
    five_xx = 0
    failure = None
    samples = 0
    rollback_attempted = False
    rollback_error = None
    baseline = {}
    warning_delta = {key: 0 for key in WARN_COUNTERS}
    try:
        if not route_enabled:
            raise RuntimeError("cutover_manifest_not_enabled")
        baseline = status(region)
        if not baseline.get("capture_enabled"):
            raise RuntimeError("capture_not_enabled_at_watch_start")
        if baseline.get("capture_unavailable"):
            raise RuntimeError("capture_unavailable_at_watch_start")
        for key in BAD_COUNTERS:
            if (baseline.get(key) or 0) > 0:
                raise RuntimeError("collector_preexisting_" + key)
        warning_last = {key: baseline.get(key) or 0 for key in WARN_COUNTERS}
        warning_delta = {key: 0 for key in WARN_COUNTERS}
        log_state = access_log_state(args.access_log)
        deadline = None if args.seconds == 0 else time.monotonic() + args.seconds
        while deadline is None or time.monotonic() < deadline:
            remaining = args.interval if deadline is None else max(0, deadline - time.monotonic())
            time.sleep(min(args.interval, remaining))
            samples += 1
            if not running(region):
                failure = "collector_sidecar_stopped"
                break
            if not collector_path_ready(region):
                failure = "collector_path_unreachable"
                break
            current = status(region)
            if not current.get("capture_enabled"):
                failure = "capture_disabled_during_window"
                break
            if current.get("capture_unavailable"):
                failure = "capture_unavailable_during_window"
                break
            for key in BAD_COUNTERS:
                if (current.get(key) or 0) > (baseline.get(key) or 0):
                    failure = "collector_" + key
                    break
            if failure:
                break
            for key in WARN_COUNTERS:
                value = current.get(key) or 0
                warning_delta[key] += max(0, value - warning_last[key])
                warning_last[key] = value
            queue_limit = current.get("queue_limit_bytes") or 0
            if queue_limit and (current.get("queued_bytes") or 0) >= queue_limit * 0.8:
                failure = "collector_queue_pressure"
                break
            if shutil.disk_usage(store).free < args.min_free_bytes:
                failure = "collector_disk_pressure"
                break
            delta, log_state = access_log_delta(args.access_log, log_state)
            five_xx += delta
            # A negative threshold explicitly means that upstream 5xx values
            # are observed and reported but cannot tear down an otherwise
            # healthy collector.  This is the production policy: upstream
            # failures are not proof that the observation sidecar failed.
            if args.max_5xx >= 0 and five_xx > args.max_5xx:
                failure = "nginx_5xx_threshold"
                break
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.CalledProcessError, json.JSONDecodeError, WatchInterrupted) as error:
        failure = str(error)[:80] or "watchdog_error"
    finally:
        if route_enabled:
            try:
                disable(region)
                time.sleep(2)
            except Exception as error:
                failure = failure or "collector_disable_failed"
            rollback_attempted = True
            try:
                rollback(region, args.state_dir, dry_run=False)
            except Exception as error:
                rollback_error = str(error)[:120] or "unknown"
                failure = failure or "nginx_rollback_failed"
    result = {
        "region": region,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "requested_seconds": args.seconds,
        "samples": samples,
        "nginx_5xx": five_xx,
        "truncated_delta": warning_delta.get("truncated", 0),
        "projection_errors_delta": warning_delta.get("projection_errors", 0),
        "status": "failed" if failure else "completed",
        "failure": failure,
        "rollback_attempted": rollback_attempted,
        "rollback_error": rollback_error,
        "p95_postcheck_required": True,
    }
    output = Path(args.state_dir) / f"window-{region}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failure else 0


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("region", choices=sorted(REGIONS))
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--max-5xx", type=int, default=0,
                        help="rollback after this many new 5xx responses; use -1 to observe without rollback")
    parser.add_argument("--min-free-bytes", type=int, default=1 << 30)
    parser.add_argument("--state-dir", default="/var/lib/work-observation/cutover")
    parser.add_argument("--access-log", default="")
    args = parser.parse_args()
    if args.seconds < 0 or args.interval <= 0:
        raise SystemExit("invalid_window_limits")
    if not args.access_log:
        args.access_log = "/data/tokyo-sub2api-proxy/logs/access.log" if args.region == "tokyo" else "/data/us-sub2api-proxy/logs/access.log"
    def interrupt(_signum, _frame):
        raise WatchInterrupted("watchdog_interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
