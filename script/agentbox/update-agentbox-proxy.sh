#!/usr/bin/env bash
set -Eeuo pipefail

force=0
if [[ ${1:-} == --force ]]; then
  force=1
elif [[ $# -ne 0 ]]; then
  echo 'usage: update-agentbox-proxy [--force]' >&2
  exit 2
fi

if [[ $(id -u) -ne 0 ]]; then
  echo 'update-agentbox-proxy must run as root' >&2
  exit 1
fi

readonly bundle=/etc/agentbox-profile
readonly compiler=/usr/local/libexec/agentbox-profile-compiler.js
readonly state_dir=/var/lib/agentbox-profile
readonly last_success=$state_dir/last-success
readonly production_config=/etc/mihomo/config.yaml
readonly previous_config=/etc/mihomo/config.yaml.previous
readonly bootstrap_config=/etc/mihomo-bootstrap/config.yaml
sync_bootstrap=0
[[ ! -e $bundle/agentbox-policy.yaml ]] || sync_bootstrap=1

exec 9>/run/lock/agentbox-proxy-update.lock
if ! flock -n 9; then
  echo 'agentbox proxy update is already running'
  exit 0
fi

read -r enabled interval_minutes < <(node "$compiler" --bundle "$bundle" --settings)
if [[ $enabled != 1 && $force -ne 1 ]]; then
  echo 'automatic profile refresh is disabled in the imported profile'
  exit 0
fi
if [[ ! $interval_minutes =~ ^[0-9]+$ || $interval_minutes -lt 1 ]]; then
  echo 'invalid imported profile refresh interval' >&2
  exit 1
fi

if [[ $force -ne 1 && -e $last_success ]]; then
  now=$(date +%s)
  last=$(stat -c %Y "$last_success")
  if (( now - last < interval_minutes * 60 )); then
    echo 'profile refresh is not due'
    exit 0
  fi
fi

work=$(mktemp -d /run/agentbox-proxy-update.XXXXXX)
candidate_pid=''
production_changed=0
bootstrap_changed=0
committed=0
cleanup() {
  local rc=$?
  trap - EXIT
  set +e
  if [[ -n $candidate_pid ]] && kill -0 "$candidate_pid" 2>/dev/null; then
    kill "$candidate_pid" 2>/dev/null || true
    wait "$candidate_pid" 2>/dev/null || true
  fi
  if [[ $committed -ne 1 ]]; then
    # Restore both files before restarting either service. A failed restart or
    # unexpected error after the first replacement must also trigger rollback.
    for target in production bootstrap; do
      local changed=${target}_changed config
      [[ ${!changed} -eq 1 ]] || continue
      if [[ $target == production ]]; then config=$production_config; else config=$bootstrap_config; fi
      if ! cp -a "$work/$target.previous" "$config.new" || ! mv -f "$config.new" "$config"; then
        echo "CRITICAL: could not restore $target configuration; private rollback files retained in $work" >&2
        exit 1
      fi
    done
    if [[ $production_changed -eq 1 ]]; then systemctl restart mihomo.service || rc=1; fi
    if [[ $bootstrap_changed -eq 1 ]]; then systemctl restart mihomo-bootstrap.service || rc=1; fi
  fi
  case $work in
    /run/agentbox-proxy-update.*) rm -rf -- "$work" ;;
    *) echo 'refusing to remove an unexpected temporary path' >&2 ;;
  esac
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
chmod 0700 "$work"

echo 'downloading the current remote profile through the bootstrap proxy'
node "$compiler" \
  --bundle "$bundle" \
  --write-fetch-config "$work/curl.conf" \
  --fetch-output "$work/subscription.yaml"
curl --config "$work/curl.conf"
[[ -s $work/subscription.yaml ]] || { echo 'downloaded profile is empty' >&2; exit 1; }
chmod 0600 "$work/subscription.yaml"

echo 'compiling the current online profile for Agentbox'
node "$compiler" \
  --bundle "$bundle" \
  --source "$work/subscription.yaml" \
  --port 17898 \
  --output "$work/candidate-test.yaml"
node "$compiler" \
  --bundle "$bundle" \
  --source "$work/subscription.yaml" \
  --port 7898 \
  --output "$work/candidate.yaml"
if [[ $sync_bootstrap -eq 1 ]]; then
  node "$compiler" --bundle "$bundle" --source "$work/subscription.yaml" \
    --port 7897 --output "$work/bootstrap.yaml"
fi

echo 'validating the candidate with Mihomo'
mkdir -p "$work/data"
cp -a /var/lib/mihomo/. "$work/data/"
chown -R mihomo:mihomo "$work/data"
chown root:mihomo "$work"
chmod 0750 "$work"
chown root:mihomo "$work/candidate-test.yaml" "$work/candidate.yaml"
chmod 0640 "$work/candidate-test.yaml" "$work/candidate.yaml"
if ! runuser -u mihomo -- /usr/local/bin/mihomo -t -d "$work/data" -f "$work/candidate-test.yaml" >"$work/validate.log" 2>&1; then
  echo "candidate syntax validation failed; details remain private in $work until this command exits" >&2
  exit 1
fi
if [[ $sync_bootstrap -eq 1 ]]; then
  chown root:mihomo "$work/bootstrap.yaml"
  chmod 0640 "$work/bootstrap.yaml"
  if ! runuser -u mihomo -- /usr/local/bin/mihomo -t -d "$work/data" -f "$work/bootstrap.yaml" >"$work/bootstrap-validate.log" 2>&1; then
    echo 'bootstrap syntax validation failed; keeping both current configurations' >&2
    exit 1
  fi
fi

runuser -u mihomo -- /usr/local/bin/mihomo -d "$work/data" -f "$work/candidate-test.yaml" >"$work/candidate.log" 2>&1 &
candidate_pid=$!
candidate_ok=0
for _ in {1..20}; do
  if ! kill -0 "$candidate_pid" 2>/dev/null; then
    break
  fi
  if curl --silent --show-error --fail --head \
      --connect-timeout 5 --max-time 15 \
      --proxy http://127.0.0.1:17898 \
      https://github.com/ >/dev/null 2>&1; then
    candidate_ok=1
    break
  fi
  sleep 1
done
if [[ $candidate_ok -ne 1 ]]; then
  echo 'candidate proxy did not pass the GitHub HTTPS health check; keeping the current production config' >&2
  exit 1
fi
if [[ -e $bundle/agentbox-policy.yaml ]]; then
  python3 /usr/local/libexec/agentbox-check-dns.py 127.0.0.1 1053
fi
kill "$candidate_pid" 2>/dev/null || true
wait "$candidate_pid" 2>/dev/null || true
candidate_pid=''

check_proxy() {
  local service=$1 port=$2
  for _ in {1..20}; do
    if systemctl is-active --quiet "$service" && curl --silent --show-error --fail --head \
        --connect-timeout 5 --max-time 15 --proxy "http://127.0.0.1:$port" \
        https://github.com/ >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  echo "proxy health check failed on port $port; restoring previous configurations" >&2
  return 1
}

# Keep private rollback copies only for the transaction, including errors in
# activation or source-cache persistence. Unchanged configs need no restart.
[[ -s $production_config ]]
cp -a "$production_config" "$work/production.previous"
if [[ $sync_bootstrap -eq 1 ]]; then
  [[ -s $bootstrap_config ]]
  cp -a "$bootstrap_config" "$work/bootstrap.previous"
  # Seed geodata and downloaded rules for independent startup. Do not share the
  # writable cache.db or copy it while another instance has it open.
  for resource in Country.mmdb geoip.dat geosite.dat ruleset; do
    if [[ -e $work/data/$resource && ! -e /var/lib/mihomo-bootstrap/$resource ]]; then
      runuser -u mihomo -- cp -a "$work/data/$resource" /var/lib/mihomo-bootstrap/
    fi
  done
fi

echo 'activating the validated configurations'
if ! cmp -s "$work/candidate.yaml" "$production_config"; then
  install -o root -g mihomo -m 0640 "$work/candidate.yaml" "$production_config.new"
  production_changed=1
  mv -f "$production_config.new" "$production_config"
  systemctl restart mihomo.service
fi
check_proxy mihomo.service 7898
if [[ $sync_bootstrap -eq 1 ]]; then
  python3 /usr/local/libexec/agentbox-check-dns.py 127.0.0.1 53
  if ! cmp -s "$work/bootstrap.yaml" "$bootstrap_config"; then
    install -o root -g mihomo -m 0640 "$work/bootstrap.yaml" "$bootstrap_config.new"
    bootstrap_changed=1
    mv -f "$bootstrap_config.new" "$bootstrap_config"
    systemctl restart mihomo-bootstrap.service
  fi
  check_proxy mihomo-bootstrap.service 7897
  python3 /usr/local/libexec/agentbox-check-dns.py 127.0.0.1 1054
fi

node "$compiler" --bundle "$bundle" --replace-current-source --source "$work/subscription.yaml"
install -d -o root -g root -m 0700 "$state_dir"
touch "$last_success"
chmod 0600 "$last_success"
if [[ $sync_bootstrap -eq 1 ]]; then
  rm -f -- "$previous_config"
else
  cp -a "$work/production.previous" "$previous_config"
fi
committed=1
echo 'agentbox online proxy profile updated successfully'
