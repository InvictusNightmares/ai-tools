#!/usr/bin/env python3
"""Regenerate the complete feature patch from a verified upstream archive."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import tarfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('archive',type=Path)
    args=parser.parse_args()
    bundle=Path(__file__).resolve().parent.parent
    meta=json.loads((bundle/'upstream.json').read_text())
    if hashlib.sha256(args.archive.read_bytes()).hexdigest()!=meta['upstream_archive_sha256']:
        raise SystemExit('Upstream checksum mismatch')
    files={}
    with tarfile.open(args.archive) as tar:
        for entry in tar:
            if entry.isfile():
                files['/'.join(Path(entry.name).parts[1:])]=tar.extractfile(entry).read()
    changes=[];added=modified=0
    for path in sorted((bundle/'source').rglob('*')):
        if not path.is_file():continue
        rel=path.relative_to(bundle/'source').as_posix()
        new=path.read_bytes();old=files.get(rel,b'')
        if old==new:raise SystemExit(f'Unmodified upstream file in compact source: {rel}')
        changes.append(f'diff --git a/{rel} b/{rel}\n')
        if rel not in files:
            added+=1;changes.append('new file mode 100644\n')
        else:modified+=1
        def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        changes.append(f'index {blob(old) if rel in files else "0"*40}..{blob(new)}'+(' 100644' if rel in files else '')+'\n')
        changes.extend(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),
                       fromfile=f'a/{rel}' if rel in files else '/dev/null',tofile=f'b/{rel}'))
    patch=''.join(changes).encode()
    (bundle/'policy-log.patch').write_bytes(patch)
    meta.update(custom_version='0.2.0+policy-log.6',patch_sha256=hashlib.sha256(patch).hexdigest(),
                source_file_count=added+modified,added_files=added,modified_files=modified)
    (bundle/'upstream.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    print(f'{added+modified} source files; {len(patch)} patch bytes; SHA256 {meta["patch_sha256"]}')


if __name__=='__main__':main()
