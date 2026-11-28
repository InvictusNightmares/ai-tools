#!/usr/bin/env bash
# Consistent backup of Hermes (excluding caches/logs/WAL) and ctyun keepalive data.
set -euo pipefail
umask 077
[[ ${EUID} -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
dest=/srv/agentbox/hermes
ctyun_data=/srv/agentbox/ctyun/data
for path in "$dest" "$dest/data" "$dest/workspace" "$dest/backups"; do
  [[ -d "$path" && ! -L "$path" ]] || { echo "Invalid backup path: $path" >&2; exit 1; }
done
exec 9>/run/lock/agentbox-hermes-backup.lock
flock -n 9 || { echo 'Another Hermes backup is running.' >&2; exit 1; }
stamp=$(date -u +%Y%m%dT%H%M%SZ)
archive="$dest/backups/hermes-$stamp.tar.gz"
[[ ! -e "$archive" && ! -e "$archive.partial" ]] || exit 1

was_running=$(docker inspect -f '{{.State.Running}}' agentbox-hermes 2>/dev/null || echo false)
restore_running() {
  rm -f -- "$archive.partial"
  if [[ "$was_running" == true ]]; then
    docker compose -f "$dest/compose.yaml" start hermes >/dev/null || true
  fi
}
trap restore_running EXIT
if [[ "$was_running" == true ]]; then
  docker compose -f "$dest/compose.yaml" stop hermes >/dev/null
fi

# Checkpoint all SQLite databases inside Hermes data/ (including subdirectories such as data/cron/)
# as UID/GID 10000:10000 so no root-owned WAL/SHM sidecars can ever be created.
python3 - "$dest/data" <<'PY'
import os, pathlib, sqlite3, sys

os.umask(0o077)
os.setgid(10000)
os.setuid(10000)

root = pathlib.Path(sys.argv[1])
seen = set()
for pattern in ("*.db", "*.sqlite", "*.sqlite3"):
    for db in sorted(root.rglob(pattern)):
        if db in seen or not db.is_file() or db.is_symlink():
            continue
        seen.add(db)
        try:
            conn = sqlite3.connect(str(db))
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.close()
        except Exception as exc:
            print(f"warning: checkpoint failed for {db}: {exc}", file=sys.stderr)
PY

tar_args=(
  --numeric-owner
  --exclude='data/logs'
  --exclude='data/image_cache'
  --exclude='data/lazy-packages'
  --exclude='data/home/.cache'
  --exclude='data/home/.local/share/uv'
  --exclude='data/*cache*'
  --exclude='*.db-wal'
  --exclude='*.db-shm'
  --exclude='*.sqlite-wal'
  --exclude='*.sqlite-shm'
  --exclude='*.sqlite3-wal'
  --exclude='*.sqlite3-shm'
  --exclude='*.lock'
  --exclude='*.log'
  --exclude='__pycache__'
  -czf "$archive.partial"
  -C "$dest" compose.yaml data workspace
)
if [[ -d "$ctyun_data" && ! -L "$ctyun_data" ]]; then
  tar_args+=(
    --exclude='worker.lock'
    -C /srv/agentbox ctyun/data
  )
fi
tar "${tar_args[@]}"
gzip -t "$archive.partial"
mv -- "$archive.partial" "$archive"
restore_running
trap - EXIT

python3 - <<'PY'
from pathlib import Path
import re
root = Path('/srv/agentbox/hermes/backups')
archives = sorted(
    p for p in root.iterdir()
    if re.fullmatch(r'hermes-\d{8}T\d{6}Z\.tar\.gz', p.name)
    and p.is_file() and not p.is_symlink()
)
for old in archives[:-3]:
    old.unlink()
print('Consistent backups retained:', min(len(archives), 3))
PY
echo "$archive"
