#!/usr/bin/env bash
set -Eeuo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
case ${1:-run} in
  run|inspect) command=${1:-run} ;;
  *) echo 'Usage: site-check [run|inspect]' >&2; exit 64 ;;
esac
exec 9>/run/lock/agentbox-site-check.lock
flock -n 9 || { echo 'A site-check run is already active.' >&2; exit 1; }
exec docker compose --project-directory /srv/agentbox/site-check --file /srv/agentbox/site-check/compose.yaml run --rm --no-deps -T site-check "$command"
