#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /ql/data/scripts/bing_rewards
export PLAYWRIGHT_BROWSERS_PATH=/ql/data/browsers
export TZ=Asia/Shanghai
export NODE_USE_ENV_PROXY=1
exec node ../bing_rewards_notify.js "$@"
