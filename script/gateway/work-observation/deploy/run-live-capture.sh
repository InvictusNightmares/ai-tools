#!/bin/sh
# Keep one production ingress on the observation sidecar until a collector
# fatal error, storage failure, or explicit stop requires a fail-closed
# rollback.  This wrapper is intentionally limited to the collector and the
# Nginx cutover scripts; it never calls Guard, Auto, or any business API.
set -eu
umask 077

region=${1:-}
case "$region" in
  tokyo) nginx_container=tokyo-sub2api-proxy; collector_port=18400 ;;
  us) nginx_container=us-sub2api-proxy; collector_port=18401 ;;
  *) echo 'usage: run-live-capture.sh tokyo|us' >&2; exit 2 ;;
esac

root=${WO_ROOT:-/opt/work-observation/current}
python=${WO_PYTHON:-/usr/bin/python3}
suffix=${WO_SIDECAR_SUFFIX:-}
state_dir=${WO_STATE_DIR:-/var/lib/work-observation/cutover-live}
interval=${WO_INTERVAL:-5}
max_5xx=${WO_MAX_5XX:--1}
enable_timeout=${WO_ENABLE_TIMEOUT:-30}
TRANSIENT_EXIT=75
sidecar_unit_prefix=${WO_SIDECAR_UNIT_PREFIX:-work-observation-collector-sidecar}
collector="work-observation-collector-${region}${suffix}"
sidecar_unit="${sidecar_unit_prefix}@${region}.service"
cutover="$root/deploy/short_window_cutover.py"
watch="$root/deploy/short_window_watch.py"

test -x "$python" || { echo collector_python_missing >&2; exit 1; }
test -r "$cutover" || { echo cutover_script_missing >&2; exit 1; }
test -r "$watch" || { echo watchdog_script_missing >&2; exit 1; }
if ! docker inspect --format '{{.State.Running}}' "$collector" 2>/dev/null | grep -qx true; then
  echo collector_sidecar_not_running >&2
  # The sidecar/Nginx containers can come up after systemd during boot.
  # Exit 75 so Restart=on-failure retries; fatal watcher exits remain 1.
  exit "$TRANSIENT_EXIT"
fi

path_probe() {
  docker exec "$nginx_container" sh -c \
    "timeout 10 wget -q -O /dev/null http://127.0.0.1:${collector_port}/" >/dev/null 2>&1
}

restart_sidecar_and_wait() {
  systemctl restart "$sidecar_unit" >/dev/null 2>&1 || {
    echo collector_network_namespace_restart_failed >&2
    exit "$TRANSIENT_EXIT"
  }
  path_ready=0
  for _ in $(seq 1 "$enable_timeout"); do
    if docker inspect --format '{{.State.Running}}' "$collector" 2>/dev/null | grep -qx true && path_probe; then
      path_ready=1
      break
    fi
    sleep 1
  done
  test "$path_ready" -eq 1 || { echo collector_network_namespace_not_ready >&2; exit "$TRANSIENT_EXIT"; }
}

ensure_path() {
  if ! path_probe; then
    restart_sidecar_and_wait
  fi
}

# A sidecar using `--network container:<nginx>` becomes attached to the old
# network namespace if Docker recreates Nginx.  Recreate it once before the
# cutover instead of exposing a route to a stale namespace.
ensure_path

route_ready=0
watch_pid=
cleanup() {
  # The watchdog normally performs the ordered disable-then-rollback.  Keep
  # the same fail-closed action here for a wrapper crash or a signal delivered
  # before the child has installed its own cleanup path.
  if test -z "$watch_pid" || test "$route_ready" -eq 0; then
    docker exec "$collector" /opt/observe disable --dir /data/store >/dev/null 2>&1 || true
    "$python" "$cutover" rollback "$region" --state-dir "$state_dir" >/dev/null 2>&1 || true
  fi
  if test -n "$watch_pid"; then
    kill -TERM "$watch_pid" 2>/dev/null || true
  fi
}
on_signal() {
  if test -n "$watch_pid"; then
    kill -TERM "$watch_pid" 2>/dev/null || true
  else
    cleanup
  fi
}
trap on_signal INT TERM HUP
trap cleanup EXIT

# The config deliberately starts with capture disabled.  Enabling it here
# makes a host reboot/restart deterministic and avoids a live route with a
# passive sidecar.  The control file lives on the restricted collector store.
docker exec "$collector" /opt/observe enable --dir /data/store >/dev/null
ready=0
for _ in $(seq 1 "$enable_timeout"); do
  if docker exec "$collector" /opt/observe status --dir /data/store \
      | "$python" -c 'import json,sys; value=json.load(sys.stdin); sys.exit(0 if value.get("capture_enabled") and not value.get("capture_unavailable") else 1)'; then
    ready=1
    break
  fi
  sleep 1
done
if test "$ready" -ne 1; then
  docker exec "$collector" /opt/observe disable --dir /data/store >/dev/null 2>&1 || true
  echo capture_enable_timeout >&2
  exit "$TRANSIENT_EXIT"
fi

# `enable` is idempotent only for a matching active manifest.  Any drift or a
# collector route without a rollback manifest fails closed before Nginx is
# touched.
if ! "$python" "$cutover" enable "$region" --state-dir "$state_dir"; then
  # Cutover has its own transaction rollback.  A failed startup attempt is
  # safe to retry after Docker/Nginx settles; configuration drift remains
  # fail-closed because each retry revalidates the exact manifest and route.
  echo live_cutover_startup_failed >&2
  exit "$TRANSIENT_EXIT"
fi
# Publishing a read-only bind-mounted Nginx config can recreate its network
# namespace; repair the sidecar before the watchdog accepts the route.
ensure_path
route_ready=1

set +e
"$python" "$watch" "$region" --seconds 0 --interval "$interval" \
  --max-5xx "$max_5xx" --state-dir "$state_dir" &
watch_pid=$!
wait "$watch_pid"
rc=$?
set -e
watch_pid=
exit "$rc"
