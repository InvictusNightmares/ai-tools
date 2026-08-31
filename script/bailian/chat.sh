#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"

base_url="${BAILIAN_BASE_URL:-https://llm-6mzaq98lqitckvz7.cn-beijing.maas.aliyuncs.com/compatible-mode/v1}"
model="${BAILIAN_MODEL:-vanchin/deepseek-v4-pro}"
key_file="${BAILIAN_KEY_FILE:-${repo_root}/key.yaml}"
key_name="${BAILIAN_KEY_NAME:-key8}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  script/bailian/chat.sh [message]

Examples:
  script/bailian/chat.sh
  script/bailian/chat.sh "介绍一下你自己"

Optional environment variables:
  BAILIAN_BASE_URL   API base URL
  BAILIAN_MODEL      Model name
  BAILIAN_KEY_FILE   YAML key file path
  BAILIAN_KEY_NAME   YAML field name (default: key8)
EOF
  exit 0
fi

if [[ ! -f "${key_file}" ]]; then
  echo "未找到密钥文件：${key_file}" >&2
  exit 1
fi

api_key="$({
  awk -v wanted="${key_name}" '
    {
      separator = index($0, ":")
      if (separator == 0) next

      name = substr($0, 1, separator - 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
      if (name == wanted) {
        print substr($0, separator + 1)
        exit
      }
    }
  ' "${key_file}"
} | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

case "${api_key}" in
  \"*\") api_key="${api_key#\"}"; api_key="${api_key%\"}" ;;
  \'*\') api_key="${api_key#\'}"; api_key="${api_key%\'}" ;;
esac

if [[ -z "${api_key}" ]]; then
  echo "${key_file} 中未找到有效的 ${key_name}" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "缺少 jq，无法生成 JSON 请求体" >&2
  exit 1
fi

prompt="${*:-你是谁}"
payload="$(jq -n \
  --arg model "${model}" \
  --arg prompt "${prompt}" \
  '{
    model: $model,
    enable_thinking: true,
    messages: [
      {
        role: "user",
        content: $prompt
      }
    ]
  }')"

curl -sS --fail-with-body \
  --connect-timeout 15 \
  --max-time 180 \
  -X POST "${base_url%/}/chat/completions" \
  -H "Authorization: Bearer ${api_key}" \
  -H "Content-Type: application/json" \
  --data-binary "${payload}"

printf '\n'
