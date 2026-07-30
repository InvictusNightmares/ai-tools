#!/usr/bin/env bash

set -euo pipefail

: "${API_KEY:?请先设置 API_KEY}"

curl -sS -i \
  "http://43.153.19.204:8004/v1/models" \
  -H "Authorization: Bearer ${API_KEY}"
