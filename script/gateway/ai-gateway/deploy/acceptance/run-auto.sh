#!/bin/sh
set -eu
umask 077
# Keep the cache signing secret out of Compose environment/inspection output.
AUTO_GATEWAY_CACHE_SECRET=$(cat /run/secrets/cache-secret)
export AUTO_GATEWAY_CACHE_SECRET
exec /app/auto-server
