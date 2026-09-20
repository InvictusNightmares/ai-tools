#!/bin/sh
# Run one collector in the Nginx container's network namespace.
# The collector itself remains loopback-only; this is what makes the Docker
# bridge topology safe without changing the collector's listener policy.
set -eu

instance=${1:-}
case "$instance" in
  tokyo) nginx_container=tokyo-sub2api-proxy; config=/etc/work-observation/collector-tokyo.json; store=/data/work-observation/tokyo ;;
  us) nginx_container=us-sub2api-proxy; config=/etc/work-observation/collector-us.json; store=/data/work-observation/us ;;
  *) echo 'usage: run-collector-sidecar.sh tokyo|us' >&2; exit 2 ;;
esac

binary=${WO_BINARY:-/opt/work-observation/current/observe}
# Pin the verified immutable GPU mirror digest.  The historical candidate
# Pin the verified immutable local image ID. The GPU mirror once exposed a
# malformed 63-character RepoDigest; this ID is the image actually present
# on the host and Docker accepts it without depending on mirror metadata.
image=${WO_IMAGE:-sha256:f787d2269bb599297ef6e2fc50d690813821fa348870b62abfc6fa99112ad7d2}
name="work-observation-collector-${instance}"

test -x "$binary" || { echo 'collector_binary_missing' >&2; exit 1; }
test -r "$config" || { echo 'collector_config_missing' >&2; exit 1; }
test -d "$store" || { echo 'collector_store_missing' >&2; exit 1; }
docker inspect --format '{{.State.Running}}' "$nginx_container" 2>/dev/null | grep -qx true || {
  echo 'nginx_container_not_running' >&2
  exit 1
}
docker image inspect "$image" >/dev/null 2>&1 || { echo 'collector_image_missing' >&2; exit 1; }
docker run --rm --user 65532:65532 \
  -v "$store:/data/store:rw" \
  "$image" sh -c 'test -w /data/store && touch /data/store/.collector-write-test && rm -f /data/store/.collector-write-test' || {
  echo 'collector_store_not_writable_for_uid_65532' >&2
  exit 1
}

exec docker run --rm --name "$name" \
  --network "container:${nginx_container}" \
  --entrypoint /opt/observe \
  --user 65532:65532 \
  --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  --pids-limit=64 --memory=1g --cpus=2 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
  -v "$binary:/opt/observe:ro" \
  -v "$config:/etc/observe.json:ro" \
  -v "$store:/data/store:rw" \
  "$image" serve --config /etc/observe.json
