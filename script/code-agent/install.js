#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline/promises');
const { spawnSync } = require('node:child_process');

const DEFAULT_EXTERNAL_BASE_URL = 'http://192.168.64.16:4000/v1';
const DEFAULT_DACS_BASE_URL = 'http://47.117.95.192:4000/v1';
const DEFAULT_MODEL = 'gpt-5.5';
const DEFAULT_CODEX_MODEL = DEFAULT_MODEL;
const PROVIDER_KEY = '启源Code Model';
const OPENCODE_PACKAGE = 'opencode-ai@latest';
const MIN_NODE_MAJOR = 18;
const NODE_INSTALL_MAJOR = 22;

const AGENTS = ['claude-code', 'codex', 'opencode'];
const MODES = ['install-and-config', 'install-only', 'config-only', 'verify-only'];

const OPENCODE_MODELS = {
  'qwen3.6-plus': 'Qwen3.6 Plus',
  'MiniMax-M2.5': 'MiniMax M2.5',
  'glm-5': 'GLM-5',
  'deepseek-v3.2': 'DeepSeek V3.2',
  'deepseek-v4-pro': 'DeepSeek V4 Pro',
  'deepseek-v4-flash': 'DeepSeek V4 Flash',
  'glm-5.1': 'GLM-5.1',
  'kimi-k2.6': 'Kimi K2.6',
  'qwen3.6-flash': 'Qwen3.6 Flash',
  'gpt-5.5': 'GPT-5.5',
  'gpt-5.4': 'GPT-5.4',
  'gpt-5.4-mini': 'GPT-5.4 Mini',
  'gpt-5.3-codex': 'GPT-5.3 Codex',
  'gpt-5.2': 'GPT-5.2'
};

function supportsImageInput(modelId) {
  return /^(gpt|qwen|kimi)-/i.test(modelId);
}

function usage() {
  console.log(`Usage: node script/code-agent/install.js [options]

Options:
  --agents <list>       all or comma-separated: claude-code,codex,opencode
  --api-key <key>       API key for 启源Code Model
  --external-url <url>  DACS external API base URL
  --dacs-url <url>      DACS internal API base URL
  --mode <mode>         install-and-config, install-only, config-only, verify-only
  --yes                 Do not prompt for confirmation
  --force               Reinstall or overwrite existing files without asking
  --dry-run             Print actions without changing files
  --verbose             Print executed commands
  --help                Show this help`);
}

function parseArgs(argv) {
  const options = {
    agents: undefined,
    apiKey: '',
    externalBaseURL: '',
    dacsBaseURL: '',
    mode: undefined,
    yes: false,
    force: false,
    dryRun: false,
    verbose: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    if (arg === '--help' || arg === '-h') {
      usage();
      process.exit(0);
    }

    if (arg === '--yes') {
      options.yes = true;
      continue;
    }

    if (arg === '--force') {
      options.force = true;
      continue;
    }

    if (arg === '--dry-run') {
      options.dryRun = true;
      continue;
    }

    if (arg === '--verbose') {
      options.verbose = true;
      continue;
    }

    if (['--agents', '--api-key', '--external-url', '--dacs-url', '--mode'].includes(arg)) {
      const value = argv[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error(`Missing value for ${arg}`);
      }

      if (arg === '--agents') options.agents = value;
      if (arg === '--api-key') options.apiKey = value;
      if (arg === '--external-url') options.externalBaseURL = value;
      if (arg === '--dacs-url') options.dacsBaseURL = value;
      if (arg === '--mode') options.mode = value;
      index += 1;
      continue;
    }

    throw new Error(`Unknown option: ${arg}`);
  }

  if (options.mode && !MODES.includes(options.mode)) {
    throw new Error(`Invalid mode: ${options.mode}`);
  }

  return options;
}

function title(text) {
  console.log(`\n${text}`);
  console.log('='.repeat([...text].length));
}

function step(text) {
  console.log(`\n> ${text}`);
}

function success(text) {
  console.log(`OK: ${text}`);
}

function warn(text) {
  console.warn(`Warning: ${text}`);
}

function maskSecret(value) {
  if (!value) return '';
  if (value.length <= 8) return '****';
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function redact(value, apiKey) {
  if (!apiKey) return value;
  return String(value).split(apiKey).join('***');
}

function createPrompt() {
  if (!process.stdin.isTTY && process.platform !== 'win32') {
    try {
      const fd = fs.openSync('/dev/tty', 'r');
      const input = fs.createReadStream(null, { fd, autoClose: true });
      return readline.createInterface({ input, output: process.stdout, terminal: true });
    } catch {
      // Fall back to stdin so non-interactive executions still fail with a clear error.
    }
  }

  return readline.createInterface({ input: process.stdin, output: process.stdout, terminal: true });
}

async function askText(rl, prompt, defaultValue = '') {
  const suffix = defaultValue ? ` [${defaultValue}]` : '';
  const answer = await rl.question(`${prompt}${suffix}: `);
  return answer.trim() || defaultValue;
}

async function askSecret(rl, prompt) {
  if (process.platform === 'win32') {
    return askText(rl, prompt);
  }

  const stdin = process.stdin;
  const onData = (char) => {
    char = char.toString();
    if (char === '\n' || char === '\r' || char === '\u0004') {
      process.stdout.write('\n');
    } else {
      process.stdout.write('*');
    }
  };

  stdin.on('data', onData);
  const answer = await rl.question(`${prompt}: `);
  stdin.off('data', onData);
  return answer.trim();
}

async function askYesNo(rl, prompt, defaultYes = true) {
  const suffix = defaultYes ? '[Y/n]' : '[y/N]';
  const answer = (await rl.question(`${prompt} ${suffix} `)).trim().toLowerCase();
  if (!answer) return defaultYes;
  return answer === 'y' || answer === 'yes';
}

async function askChoice(rl, prompt, choices) {
  console.log(`\n${prompt}`);
  choices.forEach((choice, index) => console.log(`${index + 1}. ${choice.label}`));

  while (true) {
    const answer = await rl.question(`请选择 [1-${choices.length}]: `);
    const parsed = Number(answer.trim());
    if (Number.isInteger(parsed) && parsed >= 1 && parsed <= choices.length) {
      return choices[parsed - 1].value;
    }
    warn('无效选择，请重试。');
  }
}

function normalizeAgents(raw) {
  if (!raw || raw === 'all') return [...AGENTS];

  const selected = [];
  for (const item of raw.split(',').map((entry) => entry.trim()).filter(Boolean)) {
    const normalized = item === 'claude' ? 'claude-code' : item;
    if (!AGENTS.includes(normalized)) {
      throw new Error(`Unknown agent: ${item}`);
    }
    if (!selected.includes(normalized)) selected.push(normalized);
  }

  return selected;
}

function normalizeBaseURL(raw) {
  const baseURL = String(raw || '').trim();
  if (!baseURL) throw new Error('Base URL 不能为空。');
  try {
    return new URL(baseURL).toString().replace(/\/$/, '');
  } catch {
    throw new Error(`Invalid base URL: ${baseURL}`);
  }
}

function claudeBaseURL(baseURL) {
  return baseURL.replace(/\/v1\/?$/, '');
}

async function collectAgents(rl) {
  const choice = await askChoice(rl, '请选择要安装的Code Agent CLI', [
    { label: 'Claude Code', value: ['claude-code'] },
    { label: 'Codex', value: ['codex'] },
    { label: 'OpenCode', value: ['opencode'] },
    { label: '全部安装', value: [...AGENTS] },
    { label: '自定义选择', value: 'custom' },
  ]);

  if (choice !== 'custom') return choice;

  const selected = [];
  if (await askYesNo(rl, '是否安装 Claude Code?', true)) selected.push('claude-code');
  if (await askYesNo(rl, '是否安装 Codex?', true)) selected.push('codex');
  if (await askYesNo(rl, '是否安装 OpenCode?', true)) selected.push('opencode');

  if (selected.length === 0) throw new Error('至少选择一个平台。');
  return selected;
}

async function collectMode(rl) {
  return askChoice(rl, '请选择操作', [
    { label: '安装并配置', value: 'install-and-config' },
    { label: '仅安装 CLI', value: 'install-only' },
    { label: '仅写配置', value: 'config-only' },
    { label: '仅验证', value: 'verify-only' },
  ]);
}

function homeDir() {
  return os.homedir();
}

function configDir() {
  if (process.platform === 'win32') {
    return path.join(homeDir(), '.config');
  }
  return process.env.XDG_CONFIG_HOME || path.join(homeDir(), '.config');
}

function timestamp() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, '0');
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
}

function ensureDir(dir, options) {
  if (options.dryRun) {
    console.log(`[dry-run] mkdir ${dir}`);
    return;
  }
  fs.mkdirSync(dir, { recursive: true });
}

function backupFile(filePath, options) {
  if (!fs.existsSync(filePath)) return;
  const backupPath = `${filePath}.bak.${timestamp()}`;
  if (options.dryRun) {
    console.log(`[dry-run] copy ${filePath} ${backupPath}`);
    return;
  }
  fs.copyFileSync(filePath, backupPath);
  success(`已备份 ${filePath} -> ${backupPath}`);
}

async function writeFileSafely(filePath, content, options, rl) {
  ensureDir(path.dirname(filePath), options);

  if (fs.existsSync(filePath) && !options.force && !options.yes) {
    const overwrite = await askYesNo(rl, `文件已存在，是否覆盖 ${filePath}?`, false);
    if (!overwrite) {
      warn(`跳过写入 ${filePath}`);
      return;
    }
  }

  backupFile(filePath, options);

  if (options.dryRun) {
    console.log(`[dry-run] write ${filePath}`);
    return;
  }

  fs.writeFileSync(filePath, `${content}\n`, 'utf8');
}

function pathEntries() {
  return String(process.env.PATH || '').split(path.delimiter).filter(Boolean);
}

function addToPathIfExists(dir) {
  if (!dir || !fs.existsSync(dir)) return;
  const existing = pathEntries().map((entry) => process.platform === 'win32' ? entry.toLowerCase() : entry);
  const normalized = process.platform === 'win32' ? dir.toLowerCase() : dir;
  if (existing.includes(normalized)) return;
  process.env.PATH = [dir, process.env.PATH || ''].filter(Boolean).join(path.delimiter);
}

function refreshNodePath() {
  addToPathIfExists(path.dirname(process.execPath || ''));

  if (process.platform === 'win32') {
    const programFiles = [
      process.env.ProgramFiles,
      process.env['ProgramFiles(x86)'],
      process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, 'Programs') : '',
    ].filter(Boolean);

    for (const root of programFiles) {
      addToPathIfExists(path.join(root, 'nodejs'));
      addToPathIfExists(path.join(root, 'nodejs', 'node_modules', 'npm', 'bin'));
    }
    if (process.env.APPDATA) addToPathIfExists(path.join(process.env.APPDATA, 'npm'));
    return;
  }

  addToPathIfExists('/opt/homebrew/bin');
  addToPathIfExists('/usr/local/bin');
  addToPathIfExists('/usr/bin');
}

function commandCandidates(command) {
  if (process.platform !== 'win32') return [command];

  const candidates = [`${command}.cmd`];
  if (process.env.APPDATA) {
    candidates.push(path.join(process.env.APPDATA, 'npm', `${command}.cmd`));
  }
  candidates.push(command);
  return [...new Set(candidates)];
}

function commandExists(command) {
  if (process.platform === 'win32') {
    return commandCandidates(command).some((candidate) => {
      const result = spawnSync('where', [candidate], { stdio: 'ignore', shell: true });
      if (result.status === 0) return true;
      return fs.existsSync(candidate);
    });
  }

  const probe = process.platform === 'win32' ? 'where' : 'command';
  const args = process.platform === 'win32' ? [command] : ['-v', command];
  const result = spawnSync(probe, args, { stdio: 'ignore', shell: process.platform !== 'win32' });
  return result.status === 0;
}

function runCommandCandidate(command, args, options) {
  for (const candidate of commandCandidates(command)) {
    if (options.dryRun) {
      console.log(`[dry-run] ${candidate} ${args.join(' ')}`);
      return true;
    }

    const result = process.platform === 'win32'
      ? spawnSync('cmd.exe', ['/d', '/s', '/c', `"${candidate}" ${args.join(' ')}`], {
          stdio: 'ignore',
        })
      : spawnSync(candidate, args, { stdio: 'ignore' });
    if (result.status === 0) return true;
  }
  return false;
}

function run(command, args, options, env = process.env) {
  if (options.dryRun) {
    console.log(`[dry-run] ${command} ${args.join(' ')}`);
    return;
  }

  if (options.verbose) {
    console.log(`$ ${command} ${args.join(' ')}`);
  }

  const result = spawnSync(command, args, { stdio: 'inherit', shell: process.platform === 'win32', env });
  if (result.status !== 0) {
    throw new Error(`Command failed: ${command} ${args.join(' ')}`);
  }
}

function runStatus(command, args, options, env = process.env) {
  if (options.dryRun) {
    console.log(`[dry-run] ${command} ${args.join(' ')}`);
    return 0;
  }

  if (options.verbose) {
    console.log(`$ ${command} ${args.join(' ')}`);
  }

  const result = spawnSync(command, args, { stdio: 'inherit', shell: process.platform === 'win32', env });
  return result.status === null ? 1 : result.status;
}

function commandOutput(command, args) {
  const result = spawnSync(command, args, { encoding: 'utf8', shell: process.platform === 'win32' });
  if (result.status !== 0) return '';
  return String(result.stdout || '').trim();
}

function nodeMajor(version) {
  const match = String(version || '').trim().match(/^v?(\d+)\./);
  return match ? Number(match[1]) : 0;
}

function installedNodeVersion() {
  return commandOutput('node', ['--version']) || process.version || '';
}

function findMacNodePkgName() {
  const arch = process.arch === 'arm64' ? 'arm64' : 'x64';
  const suffix = `darwin-${arch}.pkg`;
  const shasums = commandOutput('curl', ['-fsSL', `https://nodejs.org/dist/latest-v${NODE_INSTALL_MAJOR}.x/SHASUMS256.txt`]);
  return shasums
    .split(/\r?\n/)
    .map((line) => line.trim().split(/\s+/).pop() || '')
    .find((fileName) => fileName.endsWith(suffix)) || '';
}

function installNodeOnMac(options) {
  if (commandExists('brew')) {
    step('安装 Node.js: brew install node');
    run('brew', ['install', 'node'], options);
    return;
  }

  if (!commandExists('curl')) {
    throw new Error('未找到 Node.js，也未找到 curl，无法下载 Node.js 安装包。请先安装 curl 或手动安装 Node.js 18+。');
  }

  if (!commandExists('sudo')) {
    throw new Error('未找到 Node.js，也未找到 sudo，无法安装官方 Node.js pkg。请手动安装 Node.js 18+ 后重试。');
  }

  if (options.dryRun) {
    console.log(`[dry-run] curl -fsSL https://nodejs.org/dist/latest-v${NODE_INSTALL_MAJOR}.x/<node-darwin.pkg> -o <tmp.pkg>`);
    console.log('[dry-run] sudo installer -pkg <tmp.pkg> -target /');
    return;
  }

  const pkgName = findMacNodePkgName();
  if (!pkgName) {
    throw new Error(`无法解析 Node.js v${NODE_INSTALL_MAJOR} macOS 安装包地址。请手动安装 Node.js 18+ 后重试。`);
  }

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ai-tools-node-'));
  const pkgPath = path.join(tempDir, pkgName);
  try {
    step(`下载 Node.js: ${pkgName}`);
    run('curl', ['-fsSL', `https://nodejs.org/dist/latest-v${NODE_INSTALL_MAJOR}.x/${pkgName}`, '-o', pkgPath], options);
    step('安装 Node.js 官方 pkg');
    run('sudo', ['installer', '-pkg', pkgPath, '-target', '/'], options);
  } finally {
    try {
      fs.rmSync(tempDir, { recursive: true, force: true });
    } catch {
      // Best effort cleanup only.
    }
  }
}

function installNodeOnWindows(options) {
  if (commandExists('winget')) {
    step('安装 Node.js: winget install OpenJS.NodeJS.LTS');
    run('winget', [
      'install',
      '--id',
      'OpenJS.NodeJS.LTS',
      '-e',
      '--accept-package-agreements',
      '--accept-source-agreements',
    ], options);
    return;
  }

  throw new Error('未找到 Node.js，也未找到 winget，无法自动安装 Node.js。请手动安装 Node.js 18+ 后重试: https://nodejs.org/');
}

function installNode(options) {
  if (process.platform === 'darwin') {
    installNodeOnMac(options);
    return;
  }

  if (process.platform === 'win32') {
    installNodeOnWindows(options);
    return;
  }

  throw new Error(`未找到 Node.js，但当前平台 ${process.platform} 暂不支持自动安装。请手动安装 Node.js 18+ 后重试。`);
}

function ensureNodeRuntime(options) {
  refreshNodePath();

  const version = installedNodeVersion();
  const hasNode = commandExists('node');
  const hasNpm = commandExists('npm');
  const major = nodeMajor(version);

  if (hasNode && hasNpm && major >= MIN_NODE_MAJOR) {
    success(`Node.js ${version} 可用`);
    return;
  }

  if (!hasNode) {
    warn(`未检测到 Node.js，先安装 Node.js ${NODE_INSTALL_MAJOR}.x LTS。`);
  } else if (major > 0 && major < MIN_NODE_MAJOR) {
    warn(`Node.js ${version} 版本过低，先安装 Node.js ${NODE_INSTALL_MAJOR}.x LTS。`);
  } else if (!hasNpm) {
    warn('未检测到 npm，先安装完整 Node.js。');
  } else {
    warn('Node.js 状态无法确认，先安装 Node.js。');
  }

  installNode(options);
  refreshNodePath();

  const nextVersion = installedNodeVersion();
  if (!options.dryRun && (!commandExists('node') || nodeMajor(nextVersion) < MIN_NODE_MAJOR || !commandExists('npm'))) {
    throw new Error(`Node.js 安装后仍不可用。请重新打开终端，确认 node --version >= ${MIN_NODE_MAJOR} 且 npm 可用后重试。`);
  }

  if (!options.dryRun) success(`Node.js ${nextVersion} 可用`);
}

function firstCommandPath(command) {
  const output = process.platform === 'win32'
    ? commandOutput('where', [command])
    : commandOutput('command', ['-v', command]);
  return output.split(/\r?\n/).map((line) => line.trim()).find(Boolean) || '';
}

function npmGlobalBinDir() {
  if (process.platform === 'win32') {
    if (process.env.APPDATA) return path.join(process.env.APPDATA, 'npm');
    const npmPath = firstCommandPath('npm.cmd') || firstCommandPath('npm');
    return npmPath ? path.dirname(npmPath) : '';
  }

  const binDir = commandOutput('npm', ['bin', '-g']);
  if (binDir && !binDir.includes('Unknown command')) return binDir;
  const npmPath = firstCommandPath('npm');
  return npmPath ? path.dirname(npmPath) : '';
}

function installNpmPackage(packageName, binaryName, options) {
  if (commandExists(binaryName) && !options.force) {
    success(`${binaryName} 已安装`);
    return;
  }

  ensureNodeRuntime(options);

  const status = runStatus('npm', ['install', '-g', packageName], options);
  if (status !== 0) {
    if (process.platform === 'win32') {
      throw new Error(`Command failed: npm install -g ${packageName}`);
    }

    if (!commandExists('sudo')) {
      throw new Error(`Command failed: npm install -g ${packageName}. sudo is not available to retry with elevated permissions.`);
    }

    warn(`npm 全局安装失败，使用 sudo 重试。系统可能会要求输入密码。`);
    const sudoStatus = runStatus('sudo', ['npm', 'install', '-g', packageName], options);
    if (sudoStatus !== 0) {
      throw new Error(`Command failed: sudo npm install -g ${packageName}`);
    }
  }

  if (!options.dryRun && !commandExists(binaryName)) {
    const hint = process.platform === 'win32' && process.env.APPDATA
      ? ` Expected candidate: ${path.join(process.env.APPDATA, 'npm', `${binaryName}.cmd`)}`
      : '';
    throw new Error(`${binaryName} was installed but is not runnable from PATH.${hint}`);
  }
}

function npmPackageVersion(packageName) {
  return commandOutput('npm', ['view', packageName, 'version']);
}

function installedNpmPackageVersion(packageName) {
  const npmRoot = commandOutput('npm', ['root', '-g']);
  if (!npmRoot) return '';

  const packageJsonPath = path.join(npmRoot, packageName, 'package.json');
  if (!fs.existsSync(packageJsonPath)) return '';

  try {
    return JSON.parse(fs.readFileSync(packageJsonPath, 'utf8')).version || '';
  } catch {
    return '';
  }
}

function preferOpencodeWindowsAvx2Binary(options) {
  if (process.platform !== 'win32' || process.arch !== 'x64') return '';

  const npmRoot = commandOutput('npm', ['root', '-g']);
  if (!npmRoot) {
    warn('未找到 npm 全局 root，无法替换 OpenCode Windows 非 baseline 二进制。');
    return '';
  }

  const sourcePath = path.join(npmRoot, 'opencode-windows-x64', 'bin', 'opencode.exe');

  if (!fs.existsSync(sourcePath)) {
    const version = installedNpmPackageVersion('opencode-ai') || npmPackageVersion('opencode-ai@latest') || 'latest';
    const packageName = `opencode-windows-x64@${version}`;
    const status = runStatus('npm', ['install', '-g', '--ignore-scripts', packageName], options);
    if (status !== 0) {
      if (fs.existsSync(sourcePath)) {
        warn(`安装 ${packageName} 返回失败，但非 baseline 二进制已存在，继续使用: ${sourcePath}`);
      } else {
        warn(`安装 ${packageName} 失败，继续使用 opencode-ai 默认二进制。`);
        return '';
      }
    }
  }

  if (options.dryRun) {
    console.log(`[dry-run] use ${sourcePath}`);
    return sourcePath;
  }

  if (!fs.existsSync(sourcePath)) {
    warn(`未找到 OpenCode Windows x64 二进制: ${sourcePath}`);
    return '';
  }

  return sourcePath;
}

function installOpencodePackage(options) {
  installNpmPackage(OPENCODE_PACKAGE, 'opencode', options);
  preferOpencodeWindowsAvx2Binary(options);
}

function codexWindowsNativeBinaryPath() {
  if (process.platform !== 'win32') return '';

  const npmRoot = commandOutput('npm', ['root', '-g']);
  if (!npmRoot) return '';

  return path.join(
    npmRoot,
    '@openai',
    'codex',
    'node_modules',
    '@openai',
    process.arch === 'arm64' ? 'codex-win32-arm64' : 'codex-win32-x64',
    'vendor',
    process.arch === 'arm64' ? 'aarch64-pc-windows-msvc' : 'x86_64-pc-windows-msvc',
    'codex',
    'codex.exe'
  );
}

function codexWindowsNodeEntryPath() {
  if (process.platform !== 'win32') return '';

  const npmRoot = commandOutput('npm', ['root', '-g']);
  if (!npmRoot) return '';

  return path.join(npmRoot, '@openai', 'codex', 'bin', 'codex.js');
}

function ensureCodexWindowsNativePackage(options) {
  if (process.platform !== 'win32') return;

  const binaryPath = codexWindowsNativeBinaryPath();
  if (binaryPath && fs.existsSync(binaryPath)) return;

  const version = installedNpmPackageVersion(path.join('@openai', 'codex')) || npmPackageVersion('@openai/codex@latest') || 'latest';
  const archPackage = process.arch === 'arm64' ? 'codex-win32-arm64' : 'codex-win32-x64';
  const packageName = `@openai/${archPackage}@npm:@openai/codex@${version}-${process.arch === 'arm64' ? 'win32-arm64' : 'win32-x64'}`;
  const status = runStatus('npm', ['install', '-g', '--no-save', packageName], options);
  if (status !== 0 && (!binaryPath || !fs.existsSync(binaryPath))) {
    warn(`Codex Windows 原生包安装失败，codex 可能无法启动: ${packageName}`);
  }
}

function windowsVCRuntimePath() {
  if (process.platform !== 'win32') return '';
  const systemRoot = process.env.SystemRoot || process.env.WINDIR || 'C:\\Windows';
  const candidates = [
    path.join(systemRoot, 'System32', 'VCRUNTIME140_1.dll'),
    path.join(systemRoot, 'SysWOW64', 'VCRUNTIME140_1.dll'),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate)) || '';
}

function ensureWindowsVCRuntime(options) {
  if (process.platform !== 'win32') return;
  if (windowsVCRuntimePath()) return;

  warn('缺少 Microsoft Visual C++ 2015-2022 Runtime: VCRUNTIME140_1.dll。Codex Windows 原生二进制无法启动。');
  if (commandExists('winget')) {
    warn('正在尝试通过 winget 安装 Microsoft Visual C++ 2015-2022 Redistributable x64。系统可能会弹出权限确认。');
    const status = runStatus('winget', [
      'install',
      '--id',
      'Microsoft.VCRedist.2015+.x64',
      '-e',
      '--accept-package-agreements',
      '--accept-source-agreements',
    ], options);
    if (status === 0 && windowsVCRuntimePath()) {
      success('Microsoft Visual C++ Runtime 已安装。');
      return;
    }
  }

  warn('请安装 Microsoft Visual C++ Redistributable 2015-2022 x64 后重新运行安装脚本: https://aka.ms/vs/17/release/vc_redist.x64.exe');
}

function installCodexPackage(options) {
  installNpmPackage('@openai/codex', 'codex', options);
  ensureWindowsVCRuntime(options);
  ensureCodexWindowsNativePackage(options);
  removeWindowsExtensionlessCommand('codex', options);
}

function codexWindowsCommandShim(nodeEntry) {
  return `@ECHO off
SETLOCAL EnableExtensions
cd /d "${homeDir()}"
node "${nodeEntry}" %*
EXIT /B %ERRORLEVEL%`;
}

async function writeCodexWindowsCommandShim(options, rl) {
  if (process.platform !== 'win32') return;

  const binDir = npmGlobalBinDir();
  const nodeEntry = codexWindowsNodeEntryPath();
  if (!binDir || !nodeEntry || !fs.existsSync(nodeEntry)) return;

  const cmdPath = path.join(binDir, 'codex.cmd');
  await writeFileSafely(cmdPath, windowsCmdContent(codexWindowsCommandShim(nodeEntry)), options, rl);
  success(`Codex Windows 命令已恢复为官方 Node 入口: ${cmdPath}`);
}

function removeWindowsExtensionlessCommand(command, options) {
  if (process.platform !== 'win32') return;
  const binDir = npmGlobalBinDir();
  if (!binDir) return;

  const filePath = path.join(binDir, command);
  if (!fs.existsSync(filePath)) return;

  backupFile(filePath, options);
  if (!options.dryRun) fs.unlinkSync(filePath);
  success(`已移除 Windows 无扩展名命令，避免遮蔽 .cmd: ${filePath}`);
}

function opencodeConfig(apiKey, baseURL) {
  const models = Object.fromEntries(
    Object.entries(OPENCODE_MODELS).map(([id, name]) => [
      id,
      {
        name,
        modalities: {
          input: supportsImageInput(id) ? ['text', 'image'] : ['text'],
          output: ['text'],
        },
      },
    ])
  );

  return JSON.stringify(
    {
      $schema: 'https://opencode.ai/config.json',
      provider: {
        [PROVIDER_KEY]: {
          npm: '@ai-sdk/openai-compatible',
          name: PROVIDER_KEY,
          options: {
            apiKey,
            baseURL,
          },
          models,
        },
      },
      model: `${PROVIDER_KEY}/${DEFAULT_MODEL}`,
    },
    null,
    2
  );
}

async function writeOpencodeConfig(runtime, options, rl) {
  const opencodeDir = path.join(configDir(), 'opencode');
  const activeConfigPath = path.join(opencodeDir, 'opencode.json');
  const externalConfigPath = path.join(opencodeDir, 'opencode.external.json');
  const dacsConfigPath = path.join(opencodeDir, 'opencode.dacs.json');
  const externalConfig = opencodeConfig(runtime.apiKey, runtime.externalBaseURL);

  await writeFileSafely(activeConfigPath, externalConfig, options, rl);
  await writeFileSafely(externalConfigPath, externalConfig, options, rl);
  await writeFileSafely(dacsConfigPath, opencodeConfig(runtime.apiKey, runtime.dacsBaseURL), options, rl);
  success(`OpenCode DACS 外配置: ${externalConfigPath}`);
  success(`OpenCode DACS 内配置: ${dacsConfigPath}`);
  await writeOpencodeDacsMacAdapter(runtime, options, rl);
  await writeOpencodeDacsWindowsAdapter(runtime, options, rl);
}

function findOpencodeBinary(binDir = '') {
  const commandPath = firstCommandPath(process.platform === 'win32' ? 'opencode.cmd' : 'opencode') ||
    firstCommandPath('opencode');
  const npmRoot = commandOutput('npm', ['root', '-g']);
  const npmBin = npmGlobalBinDir();
  if (process.platform === 'win32') {
    const candidates = [
      npmRoot ? path.join(npmRoot, 'opencode-windows-x64', 'bin', 'opencode.exe') : '',
      npmRoot ? path.join(npmRoot, 'node_modules', 'opencode-windows-x64', 'bin', 'opencode.exe') : '',
      npmRoot ? path.join(npmRoot, 'lib', 'node_modules', 'opencode-windows-x64', 'bin', 'opencode.exe') : '',
      process.env.APPDATA ? path.join(process.env.APPDATA, 'npm', 'node_modules', 'opencode-windows-x64', 'bin', 'opencode.exe') : '',
      npmRoot ? path.join(npmRoot, 'opencode-ai', 'bin', 'opencode.exe') : '',
      npmRoot ? path.join(npmRoot, 'node_modules', 'opencode-ai', 'bin', 'opencode.exe') : '',
      npmRoot ? path.join(npmRoot, 'lib', 'node_modules', 'opencode-ai', 'bin', 'opencode.exe') : '',
      process.env.APPDATA ? path.join(process.env.APPDATA, 'npm', 'node_modules', 'opencode-ai', 'bin', 'opencode.exe') : '',
      commandPath,
      npmBin ? path.join(npmBin, 'opencode.cmd') : '',
      npmBin ? path.join(npmBin, 'node_modules', 'opencode-ai', 'bin', 'opencode.exe') : '',
      npmBin ? path.join(npmBin, 'opencode') : '',
      process.env.APPDATA ? path.join(process.env.APPDATA, 'npm', 'opencode.cmd') : '',
      process.env.APPDATA ? path.join(process.env.APPDATA, 'npm', 'opencode') : '',
    ].filter(Boolean);

    for (const candidate of [...new Set(candidates)]) {
      if (binDir && path.resolve(candidate) === path.resolve(path.join(binDir, 'opencode.cmd'))) continue;
      if (binDir && path.resolve(candidate) === path.resolve(path.join(binDir, 'opencode-dacs.cmd'))) continue;
      if (fs.existsSync(candidate)) return candidate;
      if (candidate === commandPath) return candidate;
    }

    return '';
  }

  const candidates = [
    commandPath,
    path.join(homeDir(), '.opencode', 'bin', 'opencode'),
    path.join(npmRoot, 'opencode-ai', 'bin', 'opencode'),
    path.join(npmRoot, 'node_modules', 'opencode-ai', 'bin', 'opencode'),
    path.join(npmRoot, 'lib', 'node_modules', 'opencode-ai', 'bin', 'opencode'),
    path.join(path.dirname(commandPath || '/'), '..', 'lib', 'node_modules', 'opencode-ai', 'bin', 'opencode'),
    '/usr/local/bin/opencode',
    '/opt/homebrew/bin/opencode',
  ].filter(Boolean);

  for (const candidate of [...new Set(candidates)]) {
    if (binDir && path.resolve(candidate) === path.resolve(path.join(binDir, 'opencode'))) continue;
    if (binDir && path.resolve(candidate) === path.resolve(path.join(binDir, 'opencode-dacs'))) continue;
    if (candidate.includes(`${path.sep}.globalBase${path.sep}usr${path.sep}bin${path.sep}opencode`)) continue;
    if (candidate.includes(`${path.sep}.globalBase${path.sep}usr${path.sep}bin${path.sep}opencode-dacs`)) continue;
    if (fs.existsSync(candidate)) return candidate;
    if (candidate === commandPath) return candidate;
  }

  return '';
}

function opencodeDacsWrapper(runtime, realOpencode) {
  const configJson = opencodeConfig(runtime.apiKey, runtime.dacsBaseURL);
  return `#!/bin/bash
# ai-tools generated OpenCode DACS command
set -eu

REAL_OPENCODE=${shellSingleQuote(realOpencode)}
OPENCODE_TMP_ROOT="\${TMPDIR:-/tmp}"
OPENCODE_TMP_ROOT="\${OPENCODE_TMP_ROOT%/}"
OPENCODE_HOME="$OPENCODE_TMP_ROOT/opencode-home-dacs-$$"
OPENCODE_CONFIG_ROOT="$OPENCODE_HOME/config"
OPENCODE_DATA_ROOT="$OPENCODE_HOME/data"
OPENCODE_STATE_ROOT="$OPENCODE_HOME/state"
OPENCODE_CACHE_ROOT="$OPENCODE_HOME/cache"
OPENCODE_RUNTIME_ROOT="$OPENCODE_HOME/runtime"

export XDG_CONFIG_HOME="$OPENCODE_CONFIG_ROOT"
export XDG_DATA_HOME="$OPENCODE_DATA_ROOT"
export XDG_STATE_HOME="$OPENCODE_STATE_ROOT"
export XDG_CACHE_HOME="$OPENCODE_CACHE_ROOT"
export XDG_RUNTIME_DIR="$OPENCODE_RUNTIME_ROOT"
export OPENCODE_CONFIG_DIR="$OPENCODE_CONFIG_ROOT/opencode"
export OPENCODE_MODELS_URL="http://localhost"

mkdir -p "$OPENCODE_CONFIG_DIR" "$OPENCODE_DATA_ROOT" "$OPENCODE_STATE_ROOT" "$OPENCODE_CACHE_ROOT" "$OPENCODE_RUNTIME_ROOT"

/usr/bin/printf '%s\n' ${shellSingleQuote(configJson)} > "$OPENCODE_CONFIG_DIR/opencode.json"

# Some OpenCode builds treat OPENCODE_CONFIG_DIR as the config directory itself,
# while others follow XDG_CONFIG_HOME/opencode. Keep both paths in sync.
/bin/cp "$OPENCODE_CONFIG_DIR/opencode.json" "$OPENCODE_CONFIG_ROOT/opencode.json" 2>/dev/null || true

if [ "\${AI_TOOLS_DACS_DEBUG:-}" = "1" ]; then
  echo "OpenCode DACS config: $OPENCODE_CONFIG_DIR/opencode.json" >&2
  /usr/bin/grep '"baseURL"' "$OPENCODE_CONFIG_DIR/opencode.json" >&2 || true
fi

exec "$REAL_OPENCODE" "$@"`;
}

function windowsNodeString(value) {
  return JSON.stringify(String(value));
}

function windowsExistingCommandPaths(command) {
  if (process.platform !== 'win32') return [];
  return commandOutput('where', [command])
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((candidate) => /\.(cmd|bat)$/i.test(candidate));
}

function warnWindowsCommandShadows(command) {
  if (process.platform !== 'win32') return;
  const shadows = commandOutput('where', [command])
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((candidate) => !/\.(cmd|bat)$/i.test(candidate));
  for (const shadow of shadows) {
    warn(`${command} 还有非 CMD 入口，可能遮蔽新 wrapper: ${shadow}`);
  }
}

function opencodeDacsWindowsCmdShim(runtime, realOpencode, sourceConfigPath) {
  const exeDir = path.dirname(realOpencode);
  const systemRoot = process.env.SYSTEMROOT || process.env.WINDIR || 'C:\\Windows';
  const tempRoot = process.env.TEMP || process.env.TMP || path.join(homeDir(), 'AppData', 'Local', 'Temp');
  const userProfile = process.env.USERPROFILE || homeDir();
  const appData = process.env.APPDATA || path.join(userProfile, 'AppData', 'Roaming');
  const localAppData = process.env.LOCALAPPDATA || path.join(userProfile, 'AppData', 'Local');
  const comspec = process.env.COMSPEC || path.join(systemRoot, 'System32', 'cmd.exe');
  const homeDrive = process.env.HOMEDRIVE || path.parse(userProfile).root.replace(/\\$/, '');
  const homePath = process.env.HOMEPATH || userProfile.slice(homeDrive.length) || '\\';

  const safePath = [
    exeDir,
    path.join(systemRoot, 'System32'),
    systemRoot,
    path.join(systemRoot, 'System32', 'Wbem'),
    path.join(systemRoot, 'System32', 'WindowsPowerShell', 'v1.0'),
    path.join(appData, 'npm'),
  ].filter(Boolean).join(';');

  return `@ECHO off
SETLOCAL EnableExtensions

FOR /F "tokens=1 delims==" %%E IN ('set') DO SET "%%E="

SET "SYSTEMROOT=${systemRoot}"
SET "WINDIR=${systemRoot}"
SET "COMSPEC=${comspec}"
SET "TEMP=${tempRoot}"
SET "TMP=${tempRoot}"
SET "USERPROFILE=${userProfile}"
SET "APPDATA=${appData}"
SET "LOCALAPPDATA=${localAppData}"
SET "HOMEDRIVE=${homeDrive}"
SET "HOMEPATH=${homePath}"
SET "PATHEXT=.COM;.EXE;.BAT;.CMD"
SET "PATH=${safePath}"

SET "OPENCODE_TMP_ROOT=${tempRoot}"
SET "OPENCODE_HOME=%OPENCODE_TMP_ROOT%\\opencode-home-dacs-%RANDOM%-%RANDOM%"
SET "OPENCODE_CONFIG_ROOT=%OPENCODE_HOME%\\config"
SET "OPENCODE_DATA_ROOT=%OPENCODE_HOME%\\data"
SET "OPENCODE_STATE_ROOT=%OPENCODE_HOME%\\state"
SET "OPENCODE_CACHE_ROOT=%OPENCODE_HOME%\\cache"
SET "OPENCODE_RUNTIME_ROOT=%OPENCODE_HOME%\\runtime"
SET "OPENCODE_CONFIG_DIR=%OPENCODE_CONFIG_ROOT%\\opencode"

mkdir "%OPENCODE_CONFIG_DIR%" 2>NUL
mkdir "%OPENCODE_DATA_ROOT%" 2>NUL
mkdir "%OPENCODE_STATE_ROOT%" 2>NUL
mkdir "%OPENCODE_CACHE_ROOT%" 2>NUL
mkdir "%OPENCODE_RUNTIME_ROOT%" 2>NUL

IF NOT EXIST "${sourceConfigPath}" (
  ECHO OpenCode DACS source config not found: ${sourceConfigPath} 1>&2
  EXIT /B 1
)
copy /Y "${sourceConfigPath}" "%OPENCODE_CONFIG_DIR%\\opencode.json" >NUL
copy /Y "${sourceConfigPath}" "%OPENCODE_CONFIG_ROOT%\\opencode.json" >NUL

SET "XDG_CONFIG_HOME=%OPENCODE_CONFIG_ROOT%"
SET "XDG_DATA_HOME=%OPENCODE_DATA_ROOT%"
SET "XDG_STATE_HOME=%OPENCODE_STATE_ROOT%"
SET "XDG_CACHE_HOME=%OPENCODE_CACHE_ROOT%"
SET "XDG_RUNTIME_DIR=%OPENCODE_RUNTIME_ROOT%"
SET "OPENCODE_MODELS_URL=http://localhost"

cd /d "${userProfile}"

"${realOpencode}" %1 %2 %3 %4 %5 %6 %7 %8 %9
EXIT /B %ERRORLEVEL%`;
}

function codexDacsWindowsCmdShim(runtime, realCodex) {
  const exeDir = path.dirname(realCodex);
  const systemRoot = process.env.SYSTEMROOT || process.env.WINDIR || 'C:\\Windows';
  const tempRoot = process.env.TEMP || process.env.TMP || path.join(homeDir(), 'AppData', 'Local', 'Temp');
  const userProfile = process.env.USERPROFILE || homeDir();
  const appData = process.env.APPDATA || path.join(userProfile, 'AppData', 'Roaming');
  const localAppData = process.env.LOCALAPPDATA || path.join(userProfile, 'AppData', 'Local');
  const comspec = process.env.COMSPEC || path.join(systemRoot, 'System32', 'cmd.exe');
  const homeDrive = process.env.HOMEDRIVE || path.parse(userProfile).root.replace(/\\$/, '');
  const homePath = process.env.HOMEPATH || userProfile.slice(homeDrive.length) || '\\';

  const safePath = [
    exeDir,
    path.join(systemRoot, 'System32'),
    systemRoot,
    path.join(systemRoot, 'System32', 'Wbem'),
    path.join(systemRoot, 'System32', 'WindowsPowerShell', 'v1.0'),
    path.join(appData, 'npm'),
  ].filter(Boolean).join(';');

  return `@ECHO off
SETLOCAL EnableExtensions

FOR /F "tokens=1 delims==" %%E IN ('set') DO SET "%%E="

SET "SYSTEMROOT=${systemRoot}"
SET "WINDIR=${systemRoot}"
SET "COMSPEC=${comspec}"
SET "TEMP=${tempRoot}"
SET "TMP=${tempRoot}"
SET "USERPROFILE=${userProfile}"
SET "APPDATA=${appData}"
SET "LOCALAPPDATA=${localAppData}"
SET "HOMEDRIVE=${homeDrive}"
SET "HOMEPATH=${homePath}"
SET "PATHEXT=.COM;.EXE;.BAT;.CMD"
SET "PATH=${safePath}"

SET "CODEX_TMP_ROOT=${tempRoot}"
SET "CODEX_HOME=%CODEX_TMP_ROOT%\\codex-home-dacs-%RANDOM%-%RANDOM%"
mkdir "%CODEX_HOME%" 2>NUL
mkdir "%CODEX_HOME%\\xdg\\config" 2>NUL
mkdir "%CODEX_HOME%\\xdg\\data" 2>NUL
mkdir "%CODEX_HOME%\\xdg\\state" 2>NUL
mkdir "%CODEX_HOME%\\xdg\\cache" 2>NUL
mkdir "%CODEX_HOME%\\xdg\\runtime" 2>NUL
mkdir "%CODEX_HOME%\\sqlite" 2>NUL

SET "CODEX_MANAGED_BY_NPM=1"
SET "XDG_CONFIG_HOME=%CODEX_HOME%\\xdg\\config"
SET "XDG_DATA_HOME=%CODEX_HOME%\\xdg\\data"
SET "XDG_STATE_HOME=%CODEX_HOME%\\xdg\\state"
SET "XDG_CACHE_HOME=%CODEX_HOME%\\xdg\\cache"
SET "XDG_RUNTIME_DIR=%CODEX_HOME%\\xdg\\runtime"
SET "CODEX_SQLITE_HOME=%CODEX_HOME%\\sqlite"
SET "OPENAI_API_KEY=${runtime.apiKey}"
SET "CODEX_API_KEY=${runtime.apiKey}"

cd /d "${userProfile}"

call "${realCodex}" -c model_provider=${JSON.stringify(PROVIDER_KEY)} -c model=${JSON.stringify(DEFAULT_CODEX_MODEL)} -c model_reasoning_effort="high" -c network_access="enabled" -c disable_response_storage=true -c model_providers.${JSON.stringify(PROVIDER_KEY)}.name="OpenAI" -c model_providers.${JSON.stringify(PROVIDER_KEY)}.base_url=${JSON.stringify(runtime.dacsBaseURL)} -c model_providers.${JSON.stringify(PROVIDER_KEY)}.wire_api="responses" -c model_providers.${JSON.stringify(PROVIDER_KEY)}.requires_openai_auth=true %1 %2 %3 %4 %5 %6 %7 %8 %9
EXIT /B %ERRORLEVEL%`;
}

function codexDacsWindowsNativeShim(runtime, nodeEntry) {
  const modelsPath = path.join(homeDir(), '.codex', 'models.json').replace(/\\/g, '\\\\');

  return `@ECHO off
SETLOCAL EnableExtensions
SET "OPENAI_API_KEY=${runtime.apiKey}"
SET "CODEX_API_KEY=${runtime.apiKey}"

cd /d "${homeDir()}"

node "${nodeEntry}" -c model_catalog_json="${modelsPath}" -c model_provider=${JSON.stringify(PROVIDER_KEY)} -c model=${JSON.stringify(DEFAULT_CODEX_MODEL)} -c model_reasoning_effort="high" -c network_access="enabled" -c disable_response_storage=true -c model_providers.${JSON.stringify(PROVIDER_KEY)}.name="OpenAI" -c model_providers.${JSON.stringify(PROVIDER_KEY)}.base_url=${JSON.stringify(runtime.dacsBaseURL)} -c model_providers.${JSON.stringify(PROVIDER_KEY)}.wire_api="responses" -c model_providers.${JSON.stringify(PROVIDER_KEY)}.requires_openai_auth=true %*
EXIT /B %ERRORLEVEL%`;
}

async function writeOpencodeDacsMacAdapter(runtime, options, rl) {
  if (process.platform !== 'darwin') return;

  const binDir = dacsGlobalBaseBinDir();
  if (!binDir) {
    warn('未找到 DACS .globalBase/usr/bin，跳过 macOS OpenCode DACS 适配。可设置 AI_TOOLS_DACS_BIN_DIR 后重试。');
    return;
  }

  const realOpencode = findOpencodeBinary(binDir);

  if (!realOpencode) {
    warn('未找到 OpenCode 可执行文件，跳过 DACS OpenCode 替身。请先安装 opencode 后重试。');
    return;
  }

  await writeExecutableSafely(path.join(binDir, 'opencode-dacs'), opencodeDacsWrapper(runtime, realOpencode), options, rl);
  await removeLegacyDacsShadow(path.join(binDir, 'opencode'), 'OpenCode', options);
  success(`OpenCode macOS DACS 命令: ${path.join(binDir, 'opencode-dacs')}`);
}

async function writeOpencodeDacsWindowsAdapter(runtime, options, rl) {
  if (process.platform !== 'win32') return;

  const binDir = npmGlobalBinDir();
  if (!binDir) {
    warn('未找到 npm 全局 bin 目录，跳过 Windows OpenCode DACS 适配。');
    return;
  }

  let realOpencode = findOpencodeBinary(binDir);
  const avx2Opencode = preferOpencodeWindowsAvx2Binary(options);
  if (avx2Opencode) realOpencode = avx2Opencode;
  if (!realOpencode) {
    warn('未找到 OpenCode 可执行文件，跳过 DACS OpenCode 替身。请先安装 opencode 后重试。');
    return;
  }

  const dacsHome = path.join(homeDir(), '.opencode-dacs');
  ensureDir(dacsHome, options);
  const dacsConfig = opencodeConfig(runtime.apiKey, runtime.dacsBaseURL);
  const dacsConfigPath = path.join(dacsHome, 'opencode.json');
  backupFile(dacsConfigPath, options);
  if (!options.dryRun) fs.writeFileSync(dacsConfigPath, `${dacsConfig}\n`, 'utf8');
  success(`OpenCode Windows DACS 配置: ${dacsConfigPath}`);

  const cmdPath = path.join(binDir, 'opencode-dacs.cmd');
  const shim = windowsCmdContent(`${opencodeDacsWindowsCmdShim(runtime, realOpencode, dacsConfigPath)}\n`);
  const commandPaths = [cmdPath, ...windowsExistingCommandPaths('opencode-dacs')];
  for (const targetPath of [...new Set(commandPaths.map((candidate) => path.resolve(candidate)))]) {
    backupFile(targetPath, options);
    if (!options.dryRun) fs.writeFileSync(targetPath, shim, 'utf8');
    success(`OpenCode Windows DACS 命令: ${targetPath}`);
  }
  warnWindowsCommandShadows('opencode-dacs');

  const oldJsPath = path.join(binDir, 'opencode-dacs.js');
  if (fs.existsSync(oldJsPath)) {
    backupFile(oldJsPath, options);
    if (!options.dryRun) fs.unlinkSync(oldJsPath);
    success(`已移除旧 Node.js wrapper: ${oldJsPath}`);
  }
}

function codexConfig(baseURL) {
  if (process.platform === 'win32') {
    return `model = "${DEFAULT_CODEX_MODEL}"
model_reasoning_effort = "high"
network_access = "enabled"
disable_response_storage = true
model_catalog_json = "${path.join(homeDir(), '.codex', 'models.json').replace(/\\/g, '\\\\')}"`;
  }

  return `model_provider = "${PROVIDER_KEY}"
model = "${DEFAULT_CODEX_MODEL}"
model_reasoning_effort = "high"
network_access = "enabled"
disable_response_storage = true

[model_providers.${JSON.stringify(PROVIDER_KEY)}]
name = "OpenAI"
base_url = "${baseURL}"
wire_api = "responses"
requires_openai_auth = true`;
}

function codexModelCatalog() {
  return JSON.stringify(
    {
      models: Object.entries(OPENCODE_MODELS).map(([slug, displayName], index) => ({
        slug,
        display_name: displayName,
        description: `${displayName} via ${PROVIDER_KEY}`,
        default_reasoning_level: null,
        supported_reasoning_levels: [],
        shell_type: 'default',
        visibility: 'list',
        supported_in_api: true,
        priority: index + 1,
        additional_speed_tiers: [],
        service_tiers: [],
        availability_nux: null,
        upgrade: null,
        base_instructions: '',
        model_messages: null,
        supports_reasoning_summaries: false,
        default_reasoning_summary: 'auto',
        support_verbosity: false,
        default_verbosity: null,
        apply_patch_tool_type: null,
        web_search_tool_type: 'text',
        truncation_policy: {
          mode: 'bytes',
          limit: 10000,
        },
        supports_parallel_tool_calls: false,
        supports_image_detail_original: false,
        context_window: 272000,
        max_context_window: 272000,
        auto_compact_token_limit: null,
        effective_context_window_percent: 95,
        experimental_supported_tools: [],
        input_modalities: supportsImageInput(slug) ? ['text', 'image'] : ['text'],
        supports_search_tool: false,
      })),
    },
    null,
    2
  );
}

function codexAuth(apiKey) {
  return JSON.stringify(
    {
      OPENAI_API_KEY: apiKey,
    },
    null,
    2
  );
}

function writeExecutableSafely(filePath, content, options, rl) {
  return writeFileSafely(filePath, content, options, rl).then(() => {
    if (options.dryRun) {
      console.log(`[dry-run] chmod 755 ${filePath}`);
      return;
    }
    fs.chmodSync(filePath, 0o755);
  });
}

function windowsCmdContent(content) {
  return String(content).replace(/\r?\n/g, '\r\n');
}

async function removeLegacyDacsShadow(filePath, label, options) {
  if (!fs.existsSync(filePath)) return;

  let content = '';
  try {
    content = fs.readFileSync(filePath, 'utf8');
  } catch {
    return;
  }

  const isGenerated = content.includes(`ai-tools generated ${label} DACS command`) ||
    content.includes(`${label === 'Codex' ? 'codex' : 'opencode'}-home-dacs`) ||
    (label === 'Codex' && content.includes('REAL_CODEX=') && content.includes('exec -a codex')) ||
    (label === 'OpenCode' && content.includes('REAL_OPENCODE=') && content.includes('OPENCODE_CONFIG_DIR'));
  if (!isGenerated) return;

  if (options.dryRun) {
    console.log(`[dry-run] remove legacy DACS shadow ${filePath}`);
    return;
  }

  fs.unlinkSync(filePath);
  success(`已移除旧 DACS 覆盖命令: ${filePath}`);
}

function dacsGlobalBaseBinDir() {
  const override = process.env.AI_TOOLS_DACS_BIN_DIR || process.env.DACS_GLOBAL_BASE_BIN;
  if (override) return override;

  const pathEntries = String(process.env.PATH || '').split(path.delimiter).filter(Boolean);
  const globalBaseEntry = pathEntries.find((entry) => entry.includes(`${path.sep}.globalBase${path.sep}usr${path.sep}bin`));
  if (globalBaseEntry) return globalBaseEntry;

  const meiliDir = path.join(homeDir(), 'meili');
  if (fs.existsSync(meiliDir)) {
    for (const entry of fs.readdirSync(meiliDir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const candidate = path.join(meiliDir, entry.name, 'Applications', '.globalBase', 'usr', 'bin');
      if (fs.existsSync(path.dirname(candidate))) return candidate;
    }
  }

  return '';
}

function codexDarwinTargetTriple() {
  if (process.arch === 'arm64') return 'aarch64-apple-darwin';
  if (process.arch === 'x64') return 'x86_64-apple-darwin';
  return '';
}

function findCodexNativeBinary() {
  if (process.platform !== 'darwin') return null;

  const targetTriple = codexDarwinTargetTriple();
  if (!targetTriple) return null;

  const packageName = process.arch === 'arm64' ? '@openai/codex-darwin-arm64' : '@openai/codex-darwin-x64';
  const npmRoot = commandOutput('npm', ['root', '-g']);
  const codexCommand = commandOutput('command', ['-v', 'codex']);
  const roots = [
    npmRoot,
    path.join(npmRoot, 'node_modules'),
    path.join(npmRoot, 'lib', 'node_modules'),
    codexCommand ? path.resolve(path.dirname(codexCommand), '..') : '',
    codexCommand ? path.resolve(path.dirname(codexCommand), '..', 'lib', 'node_modules') : '',
  ].filter(Boolean);

  for (const root of [...new Set(roots)]) {
    const vendorRoot = path.join(root, '@openai', 'codex', 'node_modules', packageName, 'vendor', targetTriple);
    const binaryPath = path.join(vendorRoot, 'codex', 'codex');
    const pathDir = path.join(vendorRoot, 'path');
    if (fs.existsSync(binaryPath)) return { binaryPath, pathDir };
  }

  return null;
}

function findCodexCommand(binDir = '') {
  const commandPath = firstCommandPath(process.platform === 'win32' ? 'codex.cmd' : 'codex') ||
    firstCommandPath('codex');
  const npmBin = npmGlobalBinDir();
  const candidates = process.platform === 'win32'
    ? [
        commandPath,
        npmBin ? path.join(npmBin, 'codex.cmd') : '',
        npmBin ? path.join(npmBin, 'codex') : '',
        process.env.APPDATA ? path.join(process.env.APPDATA, 'npm', 'codex.cmd') : '',
        process.env.APPDATA ? path.join(process.env.APPDATA, 'npm', 'codex') : '',
      ]
    : [commandPath];

  for (const candidate of [...new Set(candidates.filter(Boolean))]) {
    if (binDir && path.resolve(candidate) === path.resolve(path.join(binDir, 'codex.cmd'))) continue;
    if (binDir && path.resolve(candidate) === path.resolve(path.join(binDir, 'codex-dacs.cmd'))) continue;
    if (fs.existsSync(candidate)) return candidate;
    if (candidate === commandPath) return candidate;
  }

  return '';
}

function shellSingleQuote(value) {
  return `'${String(value).replace(/'/g, `'"'"'`)}'`;
}

function codexDacsWrapper(runtime, nativePaths) {
  const configLines = [
    `model_provider = ${JSON.stringify(PROVIDER_KEY)}`,
    `model = ${JSON.stringify(DEFAULT_CODEX_MODEL)}`,
    'model_reasoning_effort = "high"',
    'network_access = "enabled"',
    'disable_response_storage = true',
  ];
  const providerConfigLines = [
    '',
    `[model_providers.${JSON.stringify(PROVIDER_KEY)}]`,
    'name = "OpenAI"',
    `base_url = ${JSON.stringify(runtime.dacsBaseURL)}`,
    'wire_api = "responses"',
    'requires_openai_auth = true',
  ];
  const configPrintfArgs = configLines.map(shellSingleQuote).join(' ');
  const providerConfigPrintfArgs = providerConfigLines.map(shellSingleQuote).join(' ');
  const authJson = codexAuth(runtime.apiKey);
  const modelsJson = codexModelCatalog();

  return `#!/bin/bash
# ai-tools generated Codex DACS command
set -eu

REAL_CODEX=${shellSingleQuote(nativePaths.binaryPath)}
CODEX_PATH_DIR=${shellSingleQuote(nativePaths.pathDir)}
CODEX_TMP_ROOT="\${TMPDIR:-/tmp}"
CODEX_TMP_ROOT="\${CODEX_TMP_ROOT%/}"

export CODEX_HOME="$CODEX_TMP_ROOT/codex-home-dacs-$$"
export PATH="$CODEX_PATH_DIR:$PATH"
export CODEX_MANAGED_BY_NPM=1
export HOME="$CODEX_HOME/home"
export XDG_CONFIG_HOME="$CODEX_HOME/xdg/config"
export XDG_DATA_HOME="$CODEX_HOME/xdg/data"
export XDG_STATE_HOME="$CODEX_HOME/xdg/state"
export XDG_CACHE_HOME="$CODEX_HOME/xdg/cache"
export XDG_RUNTIME_DIR="$CODEX_HOME/xdg/runtime"
export CODEX_SQLITE_HOME="$CODEX_HOME/sqlite"
mkdir -p "$CODEX_HOME" "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR" "$CODEX_SQLITE_HOME"

export OPENAI_API_KEY=${shellSingleQuote(runtime.apiKey)}
export CODEX_API_KEY=${shellSingleQuote(runtime.apiKey)}
unset OPENAI_TOKEN OPENAI_AUTH_TOKEN CODEX_AUTH_TOKEN CODEX_REFRESH_TOKEN

/usr/bin/printf '%s\n' ${configPrintfArgs} > "$CODEX_HOME/config.toml"
/usr/bin/printf 'model_catalog_json = "%s/models.json"\n' "$CODEX_HOME" >> "$CODEX_HOME/config.toml"
/usr/bin/printf '%s\n' ${providerConfigPrintfArgs} >> "$CODEX_HOME/config.toml"
/usr/bin/printf '%s\n' ${shellSingleQuote(authJson)} > "$CODEX_HOME/auth.json"
/usr/bin/printf '%s\n' ${shellSingleQuote(modelsJson)} > "$CODEX_HOME/models.json"

if [ "\${AI_TOOLS_DACS_DEBUG:-}" = "1" ]; then
  echo "Codex DACS config: $CODEX_HOME/config.toml" >&2
  echo "Codex DACS home: $CODEX_HOME" >&2
  /usr/bin/grep '^model =' "$CODEX_HOME/config.toml" >&2 || true
  /usr/bin/grep 'base_url' "$CODEX_HOME/config.toml" >&2 || true
  /usr/bin/grep 'model_catalog_json' "$CODEX_HOME/config.toml" >&2 || true
  [ -s "$CODEX_HOME/auth.json" ] && echo "Codex DACS auth: $CODEX_HOME/auth.json" >&2
  [ -s "$CODEX_HOME/models.json" ] && echo "Codex DACS models: $CODEX_HOME/models.json" >&2
  echo "Codex DACS HOME: $HOME" >&2
  echo "Codex DACS CODEX_SQLITE_HOME: $CODEX_SQLITE_HOME" >&2
  if [ -n "\${OPENAI_API_KEY:-}" ]; then
    key_tail="\${OPENAI_API_KEY: -4}"
    echo "Codex DACS OPENAI_API_KEY: ****$key_tail" >&2
  fi
  if [ -n "\${CODEX_API_KEY:-}" ]; then
    key_tail="\${CODEX_API_KEY: -4}"
    echo "Codex DACS CODEX_API_KEY: ****$key_tail" >&2
  fi
fi

exec -a codex "$REAL_CODEX" "$@"`;
}

function dacsWritableProbe() {
  return `#!/bin/bash
set -u

echo "PWD=$PWD"
echo "HOME=$HOME"
echo "TMPDIR=\${TMPDIR:-}"
echo "PATH=$PATH"
echo

candidates=(
  "$PWD"
  "$HOME"
  "\${TMPDIR:-}"
  "/tmp"
  "/private/tmp"
  "$HOME/meili"
)

if [ -d "$HOME/meili" ]; then
  for user_dir in "$HOME"/meili/*; do
    [ -d "$user_dir" ] || continue
    candidates+=(
      "$user_dir"
      "$user_dir/Applications"
      "$user_dir/Applications/.globalBase"
      "$user_dir/Applications/.globalBase/var"
    )
  done
fi

for dir in "\${candidates[@]}"; do
  [ -n "$dir" ] || continue
  test_root="$dir/.dacs-write-probe-$$"

  if mkdir -p "$test_root" 2>/dev/null && printf test > "$test_root/file" 2>/dev/null; then
    rm -rf "$test_root" 2>/dev/null || true
    echo "OK    $dir"
  else
    rm -rf "$test_root" 2>/dev/null || true
    echo "FAIL  $dir"
  fi
done`;
}

async function writeCodexDacsMacAdapter(runtime, options, rl) {
  if (process.platform !== 'darwin') return;

  const binDir = dacsGlobalBaseBinDir();
  if (!binDir) {
    warn('未找到 DACS .globalBase/usr/bin，跳过 macOS Codex DACS 适配。可设置 AI_TOOLS_DACS_BIN_DIR 后重试。');
    return;
  }

  const nativePaths = findCodexNativeBinary();
  if (!nativePaths) {
    warn('未找到 Codex macOS 原生二进制，跳过 DACS Codex 替身。请先安装 @openai/codex 后重试。');
    return;
  }

  await writeExecutableSafely(path.join(binDir, 'codex-dacs'), codexDacsWrapper(runtime, nativePaths), options, rl);
  await removeLegacyDacsShadow(path.join(binDir, 'codex'), 'Codex', options);
  await writeExecutableSafely(path.join(binDir, 'dacs-writable-probe'), dacsWritableProbe(), options, rl);
  success(`Codex macOS DACS 命令: ${path.join(binDir, 'codex-dacs')}`);
  success(`DACS 可写目录探测: ${path.join(binDir, 'dacs-writable-probe')}`);
}

async function writeCodexDacsWindowsAdapter(runtime, options, rl) {
  if (process.platform !== 'win32') return;

  const binDir = npmGlobalBinDir();
  if (!binDir) {
    warn('未找到 npm 全局 bin 目录，跳过 Windows Codex DACS 适配。');
    return;
  }

  const nodeEntry = codexWindowsNodeEntryPath();
  if (!nodeEntry || !fs.existsSync(nodeEntry)) {
    warn('未找到 Codex Windows Node 入口，跳过 DACS Codex 替身。请先安装 @openai/codex 后重试。');
    return;
  }

  const cmdPath = path.join(binDir, 'codex-dacs.cmd');
  const shim = windowsCmdContent(`${codexDacsWindowsNativeShim(runtime, nodeEntry)}\n`);
  const commandPaths = [cmdPath, ...windowsExistingCommandPaths('codex-dacs')];
  for (const targetPath of [...new Set(commandPaths.map((candidate) => path.resolve(candidate)))]) {
    backupFile(targetPath, options);
    if (!options.dryRun) fs.writeFileSync(targetPath, shim, 'utf8');
    success(`Codex Windows DACS 命令: ${targetPath}`);
  }
  warnWindowsCommandShadows('codex-dacs');

  const oldJsPath = path.join(binDir, 'codex-dacs.js');
  if (fs.existsSync(oldJsPath)) {
    backupFile(oldJsPath, options);
    if (!options.dryRun) fs.unlinkSync(oldJsPath);
    success(`已移除旧 Node.js wrapper: ${oldJsPath}`);
  }
}

async function writeCodexConfig(runtime, options, rl) {
  const codexDir = path.join(homeDir(), '.codex');
  const activeConfigPath = path.join(codexDir, 'config.toml');
  const externalConfigPath = path.join(codexDir, 'config.external.toml');
  const dacsConfigPath = path.join(codexDir, 'config.dacs.toml');
  const externalConfig = codexConfig(runtime.externalBaseURL);

  await writeFileSafely(activeConfigPath, externalConfig, options, rl);
  await writeFileSafely(externalConfigPath, externalConfig, options, rl);
  await writeFileSafely(dacsConfigPath, codexConfig(runtime.dacsBaseURL), options, rl);
  success(`Codex DACS 外配置: ${externalConfigPath}`);
  success(`Codex DACS 内配置: ${dacsConfigPath}`);
}

async function codexLogin(apiKey, options) {
  if (process.platform === 'win32') return false;

  if (options.dryRun) {
    console.log('[dry-run] codex login --with-api-key');
    return false;
  }

  const result = spawnSync('codex', ['login', '--with-api-key'], {
    input: `${apiKey}\n`,
    stdio: ['pipe', options.verbose ? 'inherit' : 'ignore', options.verbose ? 'inherit' : 'ignore'],
    shell: process.platform === 'win32',
  });
  return result.status === 0;
}

function claudeSettings(apiKey, baseURL) {
  return JSON.stringify(
    {
      availableModels: Object.keys(OPENCODE_MODELS),
      env: {
        ANTHROPIC_API_KEY: apiKey,
        ANTHROPIC_AUTH_TOKEN: apiKey,
        ANTHROPIC_BASE_URL: claudeBaseURL(baseURL),
        ANTHROPIC_MODEL: DEFAULT_MODEL,
      },
    },
    null,
    2
  );
}

function claudeGlobalConfig(existing = {}) {
  return JSON.stringify(
    {
      ...existing,
      hasCompletedOnboarding: true,
    },
    null,
    2
  );
}

async function writeClaudeSettings(runtime, options, rl) {
  const claudeDir = path.join(homeDir(), '.claude');
  const activeSettingsPath = path.join(claudeDir, 'settings.json');
  const externalSettingsPath = path.join(claudeDir, 'settings.external.json');
  const dacsSettingsPath = path.join(claudeDir, 'settings.dacs.json');
  const externalSettings = claudeSettings(runtime.apiKey, runtime.externalBaseURL);

  await writeFileSafely(activeSettingsPath, externalSettings, options, rl);
  await writeFileSafely(externalSettingsPath, externalSettings, options, rl);
  await writeFileSafely(dacsSettingsPath, claudeSettings(runtime.apiKey, runtime.dacsBaseURL), options, rl);
  success(`Claude Code DACS 外配置: ${externalSettingsPath}`);
  success(`Claude Code DACS 内配置: ${dacsSettingsPath}`);
}

function readJsonFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return {};
  }
}

const agentDefinitions = {
  'claude-code': {
    install: (options) => installNpmPackage('@anthropic-ai/claude-code', 'claude', options),
    configure: async (runtime, options, rl) => {
      await writeClaudeSettings(runtime, options, rl);
      const claudeJsonPath = path.join(homeDir(), '.claude.json');
      await writeFileSafely(claudeJsonPath, claudeGlobalConfig(readJsonFile(claudeJsonPath)), options, rl);
    },
    verify: (options) => verifyCommand('claude', options),
    next: () => 'Claude Code: run claude.',
  },
  codex: {
    install: (options) => installCodexPackage(options),
    configure: async (runtime, options, rl) => {
      ensureWindowsVCRuntime(options);
      ensureCodexWindowsNativePackage(options);
      removeWindowsExtensionlessCommand('codex', options);
      await writeCodexConfig(runtime, options, rl);
      await writeFileSafely(path.join(homeDir(), '.codex', 'models.json'), codexModelCatalog(), options, rl);
      await writeCodexWindowsCommandShim(options, rl);
      await writeCodexDacsMacAdapter(runtime, options, rl);
      await writeCodexDacsWindowsAdapter(runtime, options, rl);
      if (!(await codexLogin(runtime.apiKey, options))) {
        await writeFileSafely(path.join(homeDir(), '.codex', 'auth.json'), codexAuth(runtime.apiKey), options, rl);
      }
    },
    verify: (options) => {
      verifyCommand('codex', options);
      verifyDacsCommand('codex', options);
    },
    next: () => 'Codex: run codex outside DACS; run codex-dacs inside DACS.',
  },
  opencode: {
    install: (options) => installOpencodePackage(options),
    configure: async (runtime, options, rl) => {
      await writeOpencodeConfig(runtime, options, rl);
    },
    verify: (options) => {
      verifyCommand('opencode', options);
      verifyDacsCommand('opencode', options);
    },
    next: () => `OpenCode: run opencode outside DACS; run opencode-dacs inside DACS. Use ${PROVIDER_KEY}/${DEFAULT_MODEL}.`,
  },
};

function verifyCommand(command, options) {
  if (options.dryRun) {
    console.log(`[dry-run] ${commandCandidates(command)[0]} --version`);
    return;
  }

  if (runCommandCandidate(command, ['--version'], options)) {
    success(`${command} 可用`);
  } else {
    const candidates = commandCandidates(command).join(', ');
    warn(`${command} --version 执行失败。Checked: ${candidates}`);
  }
}

function verifyDacsCommand(command, options) {
  const dacsCommand = `${command}-dacs`;
  if (options.dryRun) {
    console.log(`[dry-run] ${commandCandidates(dacsCommand)[0]} --version`);
    return;
  }

  if (commandExists(dacsCommand)) {
    success(`${dacsCommand} 可用`);
  } else {
    const candidates = commandCandidates(dacsCommand).join(', ');
    warn(`${dacsCommand} 未找到。Checked: ${candidates}`);
  }
}

async function collectRuntime(options) {
  const rl = createPrompt();
  try {
    if (!process.stdin.isTTY && process.platform !== 'win32' && !options.agents && !options.yes) {
      throw new Error(
        'Interactive input is unavailable because stdin is not a TTY. ' +
          'Run from a terminal or use: bash -s -- --agents all --api-key <key> --yes'
      );
    }

    const agents = options.agents ? normalizeAgents(options.agents) : await collectAgents(rl);
    const mode = options.mode || (options.yes ? 'install-and-config' : await collectMode(rl));

    const externalBaseURL = normalizeBaseURL(
      options.externalBaseURL || (options.yes ? DEFAULT_EXTERNAL_BASE_URL : await askText(rl, '请输入 DACS 外 Base URL', DEFAULT_EXTERNAL_BASE_URL))
    );
    const dacsBaseURL = normalizeBaseURL(
      options.dacsBaseURL || (options.yes ? DEFAULT_DACS_BASE_URL : await askText(rl, '请输入 DACS 内 Base URL', DEFAULT_DACS_BASE_URL))
    );

    let apiKey = options.apiKey || (options.yes ? process.env.AI_TOOLS_API_KEY || process.env.OPENAI_API_KEY || '' : '');
    if (mode !== 'install-only' && !apiKey) {
      if (options.yes) throw new Error('Missing --api-key or AI_TOOLS_API_KEY/OPENAI_API_KEY for non-interactive configuration.');
      apiKey = await askSecret(rl, '请输入 API Key');
    }

    if (mode !== 'install-only' && !apiKey) {
      throw new Error('API Key 不能为空。');
    }

    return { rl, runtime: { agents, mode, apiKey, externalBaseURL, dacsBaseURL } };
  } catch (error) {
    rl.close();
    throw error;
  }
}

function printPlan(runtime, options) {
  title('安装计划');
  console.log(`DACS 外 Base URL: ${runtime.externalBaseURL}`);
  console.log(`DACS 内 Base URL: ${runtime.dacsBaseURL}`);
  console.log(`Default model: ${DEFAULT_MODEL}`);
  console.log(`Agents: ${runtime.agents.join(', ')}`);
  console.log(`Mode: ${runtime.mode}`);
  if (runtime.agents.includes('opencode')) console.log(`OpenCode package: ${OPENCODE_PACKAGE}`);
  console.log(`API Key: ${runtime.apiKey ? maskSecret(runtime.apiKey) : 'not required for this mode'}`);
  console.log(`Dry run: ${options.dryRun ? 'yes' : 'no'}`);
  console.log(`Force: ${options.force ? 'yes' : 'no'}`);
}

async function executePlan(runtime, options, rl) {
  step('检查 Node.js');
  ensureNodeRuntime(options);

  for (const agent of runtime.agents) {
    const definition = agentDefinitions[agent];
    if (runtime.mode === 'install-and-config' || runtime.mode === 'install-only') {
      step(`安装 ${agent}`);
      definition.install(options);
    }

    if (runtime.mode === 'install-and-config' || runtime.mode === 'config-only') {
      step(`配置 ${agent}`);
      await definition.configure(runtime, options, rl);
    }
  }

  step('验证 CLI');
  for (const agent of runtime.agents) {
    agentDefinitions[agent].verify(options);
  }

}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  title('AI Agent Installer');
  const { rl, runtime } = await collectRuntime(options);

  try {
    printPlan(runtime, options);

    if (!options.yes) {
      const confirmed = await askYesNo(rl, '继续执行?', true);
      if (!confirmed) {
        warn('已取消。');
        return;
      }
    }

    await executePlan(runtime, options, rl);

    title('下一步');
    for (const agent of runtime.agents) {
      console.log(agentDefinitions[agent].next());
    }
  } finally {
    rl.close();
  }
}

main().catch((error) => {
  console.error(`Error: ${redact(error.message, process.env.AI_TOOLS_API_KEY || process.env.OPENAI_API_KEY || '')}`);
  process.exit(1);
});
