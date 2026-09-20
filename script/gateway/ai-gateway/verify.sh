#!/usr/bin/env bash
# Offline project regression; temporary HTTP fixtures only, no real model calls.
set -euo pipefail
root_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
go_bin=${GO:-go}
if [[ $# -gt 1 ]]; then
  echo 'usage: GO=/path/to/go bash verify.sh [new-output-directory]' >&2
  exit 2
fi
umask 077
if [[ $# -eq 1 ]]; then
  [[ ! -e "$1" ]] || { echo 'output directory must be new' >&2; exit 2; }
  mkdir -p -- "$1"
  output_dir=$(CDPATH= cd -- "$1" && pwd)
else
  output_dir=$(mktemp -d "${TMPDIR:-/tmp}/gateway-verify.XXXXXX")
fi
echo "Verification output: $output_dir"
export GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off PYTHONDONTWRITEBYTECODE=1
gofmt_bin=$("$go_bin" env GOROOT)/bin/gofmt
"$go_bin" version >"$output_dir/toolchain.txt"
cd "$root_dir"
unformatted=$("$gofmt_bin" -l auto guard cmd service)
[[ -z "$unformatted" ]] || { echo "$unformatted" >&2; exit 1; }
"$go_bin" vet ./... >"$output_dir/go-vet.log" 2>&1
"$go_bin" test -race -count=1 -json ./... >"$output_dir/go-race.jsonl"
for command in auto-preview auto-server preflight-api semantic-eval effort-probe model-profile; do
  CGO_ENABLED=0 GOOS=linux GOARCH=amd64 "$go_bin" build -o "$output_dir/$command" "./cmd/$command"
done
python3 -m unittest discover -s tools -p 'test_*.py' >"$output_dir/python-tests.log" 2>&1
python3 - "$root_dir" "$output_dir" <<'PY'
import ast
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root, output = map(Path, sys.argv[1:])
sources = []
for directory in ('auto', 'guard', 'cmd', 'service', 'vendor', 'tools', 'deploy', 'config'):
    for path in sorted((root / directory).rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        if path.suffix == '.py':
            ast.parse(path.read_text(), filename=str(path))
        elif path.suffix == '.sh':
            subprocess.run(['bash', '-n', str(path)], check=True)
        if path.suffix in {'.go', '.py', '.sh', '.yaml', '.md', '.template'} or path.name == 'Dockerfile' or ('testdata' in path.parts and path.suffix == '.json'):
            sources.append({'path': path.relative_to(root).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
for name in ('go.mod', 'verify.sh', 'verify-on-linux.sh', 'README.md', 'AGENTS.md'):
    path = root / name
    if path.suffix == '.sh':
        subprocess.run(['bash', '-n', str(path)], check=True)
    sources.append({'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
rows = [json.loads(line) for line in (output / 'go-race.jsonl').read_text().splitlines()]
counts = {}
for row in rows:
    if row.get('Action') == 'pass' and row.get('Test'):
        package = row['Package'].removeprefix('local/ai-gateway/')
        counts[package] = counts.get(package, 0) + 1
result = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'scope': 'local_offline', 'race_tests_including_subtests': counts, 'go_vet': 'passed', 'linux_amd64_builds': 6, 'python_unittest': 'passed', 'python_and_shell_syntax': 'passed', 'live_upstream_tested': False, 'servers_modified': False}
(output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
(output / 'source-manifest.json').write_text(json.dumps({'files': sources}, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
PY
