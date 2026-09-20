#!/usr/bin/env python3
"""Hash the deployable source tree, without credentials or runtime state."""
import argparse
import hashlib
import json
from pathlib import Path

DIRECTORIES = ('auto', 'guard', 'cmd', 'service', 'vendor', 'tools', 'deploy', 'config')
ROOT_FILES = ('go.mod', 'go.sum', 'README.md', 'AGENTS.md', 'verify.sh', 'verify-on-linux.sh')


def manifest(root):
    paths = [p for directory in DIRECTORIES for p in (root / directory).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts]
    paths += [root / name for name in ROOT_FILES if (root / name).is_file()]
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('source symlink rejected')
    return {'files': [{'path': p.relative_to(root).as_posix(),
                       'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                      for p in sorted(paths)]}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    current = manifest(args.source)
    if args.check:
        if current != json.loads(args.output.read_text()):
            raise SystemExit('source changed during verification')
    else:
        args.output.write_text(json.dumps(current, indent=2) + '\n')
