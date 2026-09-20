#!/usr/bin/env bash
set -euo pipefail
# Run only after source verification, in an isolated GPU temporary directory.
# Pass a private token file and explicit evaluated classifiers. No production writes.
: "${AUTO_GATEWAY_PILOT_TOKEN_FILE:?path to the authorized test key file}"
: "${AUTO_CLASSIFIER_MODEL:?explicit candidate required}"
: "${AUTO_CLASSIFIER_REVIEW_MODEL:?explicit independent reviewer required}"
: "${AUTO_GUARD_ENDPOINT:?explicit private Guard r4 endpoint required}"
: "${AUTO_PILOT_WORKDIR:?new private directory for pilot logs and state}"
[[ ! -e "$AUTO_PILOT_WORKDIR" ]] || { echo 'pilot workdir must be new' >&2; exit 1; }
umask 077
mkdir -p "$AUTO_PILOT_WORKDIR"
export AUTO_GATEWAY_MODE=pilot
export AUTO_GATEWAY_LISTEN=127.0.0.1:8092
export AUTO_GATEWAY_REGION=tokyo AUTO_GATEWAY_API_KEY_ID=141
export AUTO_GATEWAY_AUTH_CHECK_URL=http://106.14.254.110:9881/v1/models
export AUTO_GUARD_ENDPOINT
export AUTO_CLASSIFIER_URL=http://106.14.254.110:9881/v1/chat/completions
export AUTO_UPSTREAM_CHAT_URL=http://106.14.254.110:9881/v1/chat/completions
export AUTO_UPSTREAM_RESPONSES_URL=http://106.14.254.110:9881/v1/responses
export AUTO_UPSTREAM_ANTHROPIC_URL=http://106.14.254.110:9881/v1/messages
export AUTO_UPSTREAM_COUNT_TOKENS_URL=http://106.14.254.110:9881/v1/messages/count_tokens
export AUTO_GATEWAY_SESSION_STATE_PATH="$AUTO_PILOT_WORKDIR/session-state.json"
export AUTO_GATEWAY_USAGE_SINK_PATH="$AUTO_PILOT_WORKDIR/usage.jsonl"
export AUTO_GATEWAY_AUDIT_SINK_PATH="$AUTO_PILOT_WORKDIR/route-audit.jsonl"
export AUTO_GATEWAY_CACHE_SECRET
AUTO_GATEWAY_CACHE_SECRET=$(openssl rand -hex 32)
export AUTO_GATEWAY_MODEL_REVISION=guard-r4-semantic-v5-pilot
unset AUTO_UPSTREAM_TOKEN AUTO_CLASSIFIER_TOKEN
cd -- "$(dirname -- "$0")/.."
exec ./bin/auto-server >"$AUTO_PILOT_WORKDIR/process.log" 2>&1
