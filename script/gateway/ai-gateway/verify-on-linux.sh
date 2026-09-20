#!/usr/bin/env bash
# Run the same project checks with the cached Linux toolchain. No service starts.
set -euo pipefail
root_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
umask 077
output_dir=$(mktemp -d "${TMPDIR:-/tmp}/gateway-linux-verify.XXXXXX")
PYTHONDONTWRITEBYTECODE=1 python3 "$root_dir/tools/source_manifest.py" "$root_dir" "$output_dir/source-manifest.json"
# Shell/Python checks run on the host; the Go image does not supply Python.
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$root_dir/tools" -p 'test_*.py'
python3 - "$root_dir" <<'PY'
import ast
from pathlib import Path
import subprocess
import sys
root = Path(sys.argv[1])
for directory in ('tools', 'deploy'):
    for path in (root / directory).rglob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
for path in root.rglob('*.sh'):
    subprocess.run(['bash', '-n', str(path)], check=True)
PY
docker run --rm --pull never \
  -v "$root_dir:/src:ro" -v "$output_dir:/out" -w /src \
  -e GOTOOLCHAIN=local -e GOPROXY=off -e GOSUMDB=off \
  golang:1.27.1-bookworm sh -ec '
    test -z "$(gofmt -l auto guard cmd service)"
    go vet ./... > /out/go-vet.log 2>&1
    go test -race -count=1 -json ./... > /out/go-race.jsonl
    for command in auto-preview auto-server preflight-api semantic-eval effort-probe model-profile; do
      CGO_ENABLED=0 go build -o "/out/$command" "./cmd/$command"
    done
  '
PYTHONDONTWRITEBYTECODE=1 python3 "$root_dir/tools/source_manifest.py" "$root_dir" "$output_dir/source-manifest.json" --check
PYTHONDONTWRITEBYTECODE=1 python3 - "$root_dir" "$output_dir" <<'PY'
import datetime
import json
from pathlib import Path
import sys
root, output = map(Path, sys.argv[1:])
sys.path.insert(0, str(root / 'tools'))
from source_manifest import digest
sources = json.loads((output / 'source-manifest.json').read_text())
rows = [json.loads(line) for line in (output / 'go-race.jsonl').read_text().splitlines()]
result = {'status': 'passed', 'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'linux_offline', 'source_sha256': digest(sources), 'go_vet': 'passed',
          'python_unittest': 'passed', 'linux_amd64_builds': 6,
          'race_tests_including_subtests': sum(row.get('Action') == 'pass' and bool(row.get('Test')) for row in rows)}
(output / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
PY
echo "Linux verification output: $output_dir"
