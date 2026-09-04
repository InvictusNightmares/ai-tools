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
cleanup() {
  if [[ -n $candidate_pid ]] && kill -0 "$candidate_pid" 2>/dev/null; then
    kill "$candidate_pid" 2>/dev/null || true
    wait "$candidate_pid" 2>/dev/null || true
  fi
  case $work in
    /run/agentbox-proxy-update.*) rm -rf -- "$work" ;;
    *) echo 'refusing to remove an unexpected temporary path' >&2 ;;
  esac
}
trap cleanup EXIT
chmod 0700 "$work"

echo 'downloading the current remote profile through the bootstrap proxy'
node "$compiler" \
  --bundle "$bundle" \
  --write-fetch-config "$work/curl.conf" \
  --fetch-output "$work/subscription.yaml"
curl --config "$work/curl.conf"
[[ -s $work/subscription.yaml ]] || { echo 'downloaded profile is empty' >&2; exit 1; }
chmod 0600 "$work/subscription.yaml"

echo 'compiling the imported Clash Verge enhancement chain'
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
kill "$candidate_pid" 2>/dev/null || true
wait "$candidate_pid" 2>/dev/null || true
candidate_pid=''

echo 'activating the validated production configuration'
install -o root -g mihomo -m 0640 "$work/candidate.yaml" "$production_config.new"
if [[ -s $production_config ]]; then
  cp -a "$production_config" "$previous_config.new"
  mv -f "$previous_config.new" "$previous_config"
fi
mv -f "$production_config.new" "$production_config"
systemctl restart mihomo.service

production_ok=0
for _ in {1..20}; do
  if systemctl is-active --quiet mihomo.service && \
      curl --silent --show-error --fail --head \
        --connect-timeout 5 --max-time 15 \
        --proxy http://127.0.0.1:7898 \
        https://github.com/ >/dev/null 2>&1; then
    production_ok=1
    break
  fi
  sleep 1
done

if [[ $production_ok -ne 1 ]]; then
  echo 'production health check failed; rolling back to the last known-good config' >&2
  if [[ -s $previous_config ]]; then
    cp -a "$previous_config" "$production_config.new"
    mv -f "$production_config.new" "$production_config"
    systemctl restart mihomo.service
  fi
  exit 1
fi

node "$compiler" --bundle "$bundle" --replace-current-source --source "$work/subscription.yaml"
install -d -o root -g root -m 0700 "$state_dir"
touch "$last_success"
chmod 0600 "$last_success"
echo 'agentbox production proxy profile updated successfully'
