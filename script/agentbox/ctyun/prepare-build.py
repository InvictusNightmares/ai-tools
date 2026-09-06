#!/usr/bin/env python3
"""Create a credential-free Docker context from an immutable, audited upstream."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile

COMMIT = '975f0cb85780e135e620d851d943a7ab65e5021e'
REPO = 'https://github.com/leleji/CtYun.git'
HERE = Path(__file__).resolve().parent

def run(*args):
    return subprocess.check_output(args)

def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Audited upstream layout changed')
    return text.replace(before, after, 1)

def prepare(repo, output):
    if output.exists():
        raise ValueError('Output must not already exist')
    if run('git', '-C', str(repo), 'rev-parse', COMMIT).decode().strip() != COMMIT:
        raise ValueError('Wrong source revision')
    output.mkdir(parents=True)
    source = output / 'source'
    source.mkdir()
    paths = run('git', '-C', str(repo), 'ls-tree', '-r', '--name-only', COMMIT, 'CtYun').decode().splitlines()
    for name in paths:
        relative = Path(name).relative_to('CtYun')
        if relative.name == 'Program.cs' or relative.suffix not in {'.cs', '.csproj'}:
            continue
        data = run('git', '-C', str(repo), 'show', f'{COMMIT}:{name}')
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    path = source / 'CtYunApi.cs'
    text = path.read_text(encoding='utf-8-sig')
    text = replace_once(text, 'internal class CtYunApi', 'internal class CtYunApi : IDisposable')
    text = replace_once(text, 'private const string orcUrl = "https://orc.1999111.xyz/ocr";', 'private readonly Func<byte[], Task<string>> humanCaptcha;')
    text = replace_once(text, 'public CtYunApi(string deviceCode)', 'public CtYunApi(string deviceCode, Func<byte[], Task<string>> humanCaptcha)')
    text = replace_once(text, '_deviceCode = deviceCode;', '_deviceCode = deviceCode;\n            this.humanCaptcha = humanCaptcha;')
    text = replace_once(text, 'new HttpClientHandler();', 'new HttpClientHandler { AllowAutoRedirect = false };')
    text = replace_once(text, 'client = new HttpClient(handler);', 'client = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(25) };')
    start = text.index('        private async Task<string> GetCaptcha(byte[] img)')
    end = text.index('        public async Task<List<Desktop>> GetLlientListAsync()', start)
    text = text[:start] + '        private Task<string> GetCaptcha(byte[] img) => humanCaptcha(img);\n\n        public void Dispose() => client.Dispose();\n\n' + text[end:]
    text = text.replace('{result.Msg}', '{result.Code}').replace('"BindingDevice Error:" + result.Msg', '"BindingDevice Error:" + result.Code').replace('ex.Message', 'ex.GetType().Name')
    text = text.replace('" + userphone + "', '" + Uri.EscapeDataString(userphone) + "')
    text = text.replace('" + captchaCode,', '" + Uri.EscapeDataString(captchaCode),')
    text = text.replace('" + userphone));', '" + Uri.EscapeDataString(userphone)));')
    text = '\n'.join(line.replace('result.Msg', 'result.Code') if 'Utility.WriteLine' in line else line for line in text.split('\n'))
    path.write_text(text)
    assert 'orc.1999111' not in text and 'MultipartFormDataContent' not in text
    shutil.copyfile(HERE / 'Program.cs', source / 'Program.cs')
    (source / 'NuGet.Config').write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
    shutil.copyfile(HERE / 'Dockerfile', output / 'Dockerfile')
    (output / 'LICENSE.upstream').write_bytes(run('git', '-C', str(repo), 'show', f'{COMMIT}:LICENSE'))
    (output / '.dockerignore').write_text('**/._*\n**/.DS_Store\n')
    manifest = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}
    (output / 'source-manifest.json').write_text(json.dumps({'upstreamCommit': COMMIT, 'sha256': manifest}, indent=2) + '\n')
    print(f'Prepared pinned source {COMMIT}: {len(manifest)} files, no credentials.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, help='Existing checkout; reads only objects at the pinned commit')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--archive', action='store_true', help='Also create an adjacent portable .tar.gz without macOS metadata')
    args = parser.parse_args()
    if args.upstream:
        prepare(args.upstream.resolve(), args.output.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='agentbox-ctyun-source-') as directory:
            subprocess.run(['git', 'init', '-q', directory], check=True)
            subprocess.run(['git', '-C', directory, 'fetch', '--depth=1', REPO, COMMIT], check=True)
            prepare(Path(directory), args.output.resolve())
    if args.archive:
        archive = args.output.resolve().with_suffix('.tar.gz')
        with tarfile.open(archive, 'x:gz') as bundle:
            for path in sorted(args.output.resolve().rglob('*')):
                if path.is_file() and not path.is_symlink():
                    bundle.add(path, arcname=str(path.relative_to(args.output.resolve())), recursive=False)
        print('Archive SHA256: ' + hashlib.sha256(archive.read_bytes()).hexdigest())

if __name__ == '__main__':
    main()
