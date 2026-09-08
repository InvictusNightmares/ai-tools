#!/usr/bin/env bash
# A short gateway stop produces a consistent snapshot of all SQLite/JSON state.
set -euo pipefail
umask 077
[[ ${EUID} -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
dest=/srv/agentbox/hermes
for path in "$dest" "$dest/data" "$dest/workspace" "$dest/backups"; do
  [[ -d "$path" && ! -L "$path" ]] || { echo "Invalid backup path: $path" >&2; exit 1; }
done
exec 9>/run/lock/agentbox-hermes-backup.lock
flock -n 9 || { echo 'Another Hermes backup is running.' >&2; exit 1; }
stamp=$(date -u +%Y%m%dT%H%M%SZ)
archive="$dest/backups/hermes-$stamp.tar.gz"
[[ ! -e "$archive" && ! -e "$archive.partial" ]] || exit 1
was_running=$(docker inspect -f '{{.State.Running}}' agentbox-hermes)
restore_running() {
  if [[ "$was_running" == true ]]; then
    docker compose -f "$dest/compose.yaml" start hermes >/dev/null
  fi
}
trap restore_running EXIT
if [[ "$was_running" == true ]]; then
  docker compose -f "$dest/compose.yaml" stop hermes >/dev/null
fi
tar --numeric-owner -czf "$archive.partial" -C "$dest" compose.yaml data workspace
gzip -t "$archive.partial"
mv -- "$archive.partial" "$archive"
restore_running
trap - EXIT
python3 - <<'PY'
from pathlib import Path
import re
root=Path('/srv/agentbox/hermes/backups')
archives=sorted(p for p in root.iterdir() if re.fullmatch(r'hermes-\d{8}T\d{6}Z\.tar\.gz',p.name) and p.is_file() and not p.is_symlink())
for old in archives[:-7]:
    old.unlink()
print('Consistent backups retained:',min(len(archives),7))
PY
echo "$archive"
