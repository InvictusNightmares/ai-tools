#!/usr/bin/env bash
set -Eeuo pipefail
readonly stack=/srv/agentbox/ctyun
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
compose=(docker compose --project-directory "$stack" --file "$stack/compose.yaml")
case ${1:-help} in
  login)
    [[ -t 0 && -t 1 ]] || { echo 'Login requires a human terminal.' >&2; exit 1; }
    "${compose[@]}" stop keepalive
    # Only an explicit human login can request CAPTCHA/SMS. The daemon never does.
    "${compose[@]}" run --rm --no-deps keepalive login
    "${compose[@]}" up -d --no-build keepalive
    ;;
  start)
    [[ -s $stack/data/session.json ]] || { echo 'Run agentbox-ctyun login first.' >&2; exit 1; }
    "${compose[@]}" up -d --no-build keepalive
    ;;
  stop) "${compose[@]}" stop keepalive ;;
  status) "${compose[@]}" ps -a; "${compose[@]}" logs --tail=20 keepalive ;;
  check) "${compose[@]}" run --rm --no-deps -T keepalive check-config ;;
  help|--help|-h) echo 'agentbox-ctyun {login|start|stop|status|check}' ;;
  *) echo 'Unknown command.' >&2; exit 64 ;;
esac
