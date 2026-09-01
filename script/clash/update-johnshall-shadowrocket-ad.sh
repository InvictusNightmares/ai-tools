#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"

source_repo="Johnshall/Shadowrocket-ADBlock-Rules-Forever"
source_branch="release"
source_name="sr_ad_only.conf"
target_file="${repo_root}/config/clash/rule-providers/johnshall-shadowrocket-ad.txt"

mode="update"
source_file=""
source_commit=""

usage() {
  cat <<'EOF'
Usage:
  script/clash/update-johnshall-shadowrocket-ad.sh [--check]
  script/clash/update-johnshall-shadowrocket-ad.sh [--check] --source-file PATH --source-commit SHA

Options:
  --check              Verify whether the generated provider is current without changing it.
  --source-file PATH   Use an already downloaded sr_ad_only.conf instead of the network.
  --source-commit SHA  Pin the source commit; required with --source-file.
  -h, --help           Show this help without downloading or changing files.

Without --check, the script updates only:
  config/clash/rule-providers/johnshall-shadowrocket-ad.txt
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      mode="check"
      shift
      ;;
    --source-file)
      [[ $# -ge 2 ]] || { printf '%s\n' "--source-file requires a path" >&2; exit 2; }
      source_file="$2"
      shift 2
      ;;
    --source-commit)
      [[ $# -ge 2 ]] || { printf '%s\n' "--source-commit requires a SHA" >&2; exit 2; }
      source_commit="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -n "${source_file}" && -z "${source_commit}" ]]; then
  printf '%s\n' "--source-commit is required with --source-file" >&2
  exit 2
fi

if [[ -n "${source_commit}" && ! "${source_commit}" =~ ^[0-9a-fA-F]{40}$ ]]; then
  printf '%s\n' "--source-commit must be a full 40-character Git SHA" >&2
  exit 2
fi

update_tmp_dir="$(mktemp -d)"
trap 'rm -rf "${update_tmp_dir}"' EXIT INT TERM

downloaded_source="${update_tmp_dir}/${source_name}"
payload_file="${update_tmp_dir}/payload.txt"
stats_file="${update_tmp_dir}/stats.txt"
generated_file="${update_tmp_dir}/johnshall-shadowrocket-ad.txt"

if [[ -n "${source_file}" ]]; then
  [[ -f "${source_file}" ]] || { printf 'Source file not found: %s\n' "${source_file}" >&2; exit 1; }
  cp "${source_file}" "${downloaded_source}"
else
  if [[ -z "${source_commit}" ]]; then
    source_commit="$(git ls-remote --exit-code "https://github.com/${source_repo}.git" "refs/heads/${source_branch}" | awk 'NR == 1 { print $1 }')"
  fi

  [[ "${source_commit}" =~ ^[0-9a-fA-F]{40}$ ]] || { printf '%s\n' "Could not resolve the upstream release commit" >&2; exit 1; }

  curl --fail --silent --show-error --location \
    --retry 4 --retry-all-errors \
    --connect-timeout 15 --max-time 180 \
    "https://raw.githubusercontent.com/${source_repo}/${source_commit}/${source_name}" \
    --output "${downloaded_source}"
fi

source_bytes="$(wc -c < "${downloaded_source}" | tr -d '[:space:]')"
if (( source_bytes < 1000000 || source_bytes > 5000000 )); then
  printf 'Unexpected source size: %s bytes\n' "${source_bytes}" >&2
  exit 1
fi

awk -F',' -v payload_file="${payload_file}" -v stats_file="${stats_file}" '
  /^[[:space:]]*($|#|\[)/ { next }
  {
    sub(/\r$/, "", $3)

    valid_type = ($1 == "DOMAIN-SUFFIX" || $1 == "IP-CIDR")
    valid_value = ($2 != "")
    if ($1 == "DOMAIN-SUFFIX") valid_value = ($2 ~ /^[A-Za-z0-9._-]+$/)
    if ($1 == "IP-CIDR") valid_value = ($2 ~ /^[0-9.]+\/[0-9]+$/)

    if (NF != 3 || !valid_type || !valid_value || $3 != "Reject") {
      print "Unsupported source rule at line " NR ": " $0 > "/dev/stderr"
      bad = 1
      next
    }

    raw_count++
    type_count[$1]++
    key = $1 FS $2
    if (!seen[key]++) {
      print key > payload_file
      unique_count++
      unique_type_count[$1]++
    }
  }
  END {
    if (bad) exit 1
    duplicates = raw_count - unique_count
    print raw_count, type_count["DOMAIN-SUFFIX"], type_count["IP-CIDR"], unique_count, unique_type_count["DOMAIN-SUFFIX"], unique_type_count["IP-CIDR"], duplicates > stats_file
  }
' "${downloaded_source}"

read -r raw_count domain_count ip_count unique_count unique_domain_count unique_ip_count duplicate_count < "${stats_file}"

if (( raw_count < 50000 || domain_count < 50000 || ip_count < 1 )); then
  printf 'Unexpected rule counts: total=%s domain=%s ip=%s\n' "${raw_count}" "${domain_count}" "${ip_count}" >&2
  exit 1
fi

if (( unique_count != unique_domain_count + unique_ip_count || raw_count != domain_count + ip_count || duplicate_count != raw_count - unique_count )); then
  printf '%s\n' "Provider count consistency check failed" >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  source_sha256="$(sha256sum "${downloaded_source}" | awk '{ print $1 }')"
else
  source_sha256="$(LC_ALL=C shasum -a 256 "${downloaded_source}" | awk '{ print $1 }')"
fi

{
  printf '%s\n' "# Johnshall Shadowrocket ad rules converted for Mihomo classical rule-provider."
  printf '# Source: https://github.com/%s/blob/%s/%s\n' "${source_repo}" "${source_commit}" "${source_name}"
  printf '# Source commit: %s\n' "${source_commit}"
  printf '# Source SHA-256: %s\n' "${source_sha256}"
  printf '%s\n' "# Transform: removed Shadowrocket section/comments and Reject policy; removed exact duplicates; preserved rule order."
  printf '# Effective rules: %s (%s DOMAIN-SUFFIX + %s IP-CIDR; %s exact duplicates removed).\n' \
    "${unique_count}" "${unique_domain_count}" "${unique_ip_count}" "${duplicate_count}"
  printf '%s\n' "# License: CC BY-SA 4.0, same as the source (https://creativecommons.org/licenses/by-sa/4.0/)."
  printf '\n'
  while IFS= read -r rule; do
    printf '%s\n' "${rule}"
  done < "${payload_file}"
} > "${generated_file}"

if [[ -f "${target_file}" ]] && cmp -s "${generated_file}" "${target_file}"; then
  printf 'Provider is current: %s rules from %s\n' "${unique_count}" "${source_commit}"
  exit 0
fi

if [[ "${mode}" == "check" ]]; then
  printf 'Provider is stale: expected %s rules from %s\n' "${unique_count}" "${source_commit}" >&2
  exit 1
fi

mkdir -p "$(dirname "${target_file}")"
cp "${generated_file}" "${target_file}"
printf 'Updated provider: %s rules from %s\n' "${unique_count}" "${source_commit}"
