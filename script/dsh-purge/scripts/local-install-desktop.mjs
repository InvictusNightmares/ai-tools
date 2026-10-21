import fs from 'node:fs';
import path from 'node:path';
import { homedir } from 'node:os';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const args = process.argv.slice(2);
const mode = args[0] ?? '--status';
if (args.length > 1 || !['--status', '--install', '--help', '-h'].includes(mode)) {
  console.error('用法: local-install-desktop.sh [--status | --install | --help]');
  process.exit(2);
}
if (mode === '--help' || mode === '-h') {
  console.log('用法: local-install-desktop.sh [--status | --install | --help]\n--status  只读显示源码、安装版本和启用状态（默认）\n--install 从本项目离线安装或更新，要求插件已停用，保留 bundle 选择');
  process.exit(0);
}

const sourceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dshHome = path.resolve(process.env.DSH_HOME || path.join(homedir(), '.dsh'));
const profileDir = path.join(dshHome, 'profiles', 'desktop');
const manifestPath = path.join(profileDir, 'package.json');
const installedManifestPath = path.join(profileDir, 'node_modules', 'dsh-purge', 'package.json');
const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));
const source = readJson(path.join(sourceRoot, 'package.json'));
if (source.name !== 'dsh-purge') throw new Error('项目目录不是 dsh-purge 包。');

function readDesktopProfile() {
  const profile = readJson(manifestPath);
  if (profile.name !== 'dsh-profile-desktop' || !Array.isArray(profile.dsh?.profile?.bundles)) {
    throw new Error('目标不是有效的官方 desktop profile；未作修改。');
  }
  return profile;
}

function status() {
  const profile = readDesktopProfile();
  const installed = fs.existsSync(installedManifestPath) ? readJson(installedManifestPath) : null;
  return {
    source: sourceRoot,
    sourceVersion: source.version,
    upstreamDshTarget: source.dshTarget,
    profile: profileDir,
    dependency: profile.dependencies?.['dsh-purge'] ?? null,
    installedVersion: installed?.version ?? null,
    selected: profile.dsh.profile.bundles.includes('dsh-purge'),
  };
}

if (mode === '--status') {
  console.log(JSON.stringify(status(), null, 2));
} else {
  if (!process.versions.electron) throw new Error('请通过 local-install-desktop.sh 使用桌面版自带运行时。');
  const resources = path.resolve(path.dirname(process.execPath), '..', 'Resources');
  const runtime = path.join(resources, 'runtime');
  const require = createRequire(path.join(resources, 'app.asar', 'dsh', 'package.json'));
  const { runProfilePnpm } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-plugin-manager/operations')).href);
  const { withFileLock } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-atomic-write')).href);
  const installAnchor = require.resolve('@deepseek-ai/dsh/package.json');

  const result = await withFileLock(manifestPath, async () => {
    const before = readDesktopProfile();
    if (before.dsh.profile.bundles.includes('dsh-purge')) {
      throw new Error('dsh-purge 当前已启用；请先在桌面插件管理中停用，避免更新时自动改写宿主。未执行安装。');
    }
    const backupRoot = path.join(profileDir, '.plugin-manager', 'backups');
    fs.mkdirSync(backupRoot, { recursive: true, mode: 0o700 });
    const backupDir = fs.mkdtempSync(path.join(backupRoot, 'dsh-purge-'));
    for (const name of ['package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml']) {
      const original = path.join(profileDir, name);
      if (!fs.existsSync(original)) continue;
      const saved = path.join(backupDir, name);
      fs.copyFileSync(original, saved);
      fs.chmodSync(saved, 0o600);
    }
    console.log(`配置备份: ${backupDir}`);
    const operation = await runProfilePnpm({
      profile: 'desktop', dir: profileDir, installAnchor, cwd: sourceRoot,
    }, ['add', `file:${sourceRoot}`, '--offline', '--ignore-scripts'], {
      command: process.execPath,
      args: ['--expose-internals', path.join(runtime, 'primary-runtime', 'dependencies', 'pnpm', 'bin', 'pnpm.mjs')],
      env: {
        ELECTRON_RUN_AS_NODE: '1',
        DSH_DESKTOP_NODE_EXECUTABLE: process.execPath,
        PATH: `${path.join(runtime, 'bin')}${path.delimiter}${process.env.PATH ?? ''}`,
      },
      execution: 'cli', outputBytes: 16384, lookupTimeoutMs: 120000,
      activateNewBundles: false,
      onOutput: (text, stream) => process[stream].write(text),
    });
    const after = readDesktopProfile();
    if (JSON.stringify(after.dsh.profile.bundles) !== JSON.stringify(before.dsh.profile.bundles)) {
      throw new Error(`bundle 选择意外发生变化；请检查配置和备份 ${backupDir}`);
    }
    for (const [name, version] of Object.entries(before.dependencies ?? {})) {
      if (name !== 'dsh-purge' && after.dependencies?.[name] !== version) {
        throw new Error(`其他依赖 ${name} 意外发生变化；请检查配置和备份 ${backupDir}`);
      }
    }
    return operation;
  }, { waitMs: 120000 });
  console.log(JSON.stringify({ ...status(), exitCode: result.exitCode, logPath: result.logPath }, null, 2));
  process.exitCode = result.exitCode;
}
