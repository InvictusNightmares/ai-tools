# OpenCode Bailian Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-platform setup script that installs OpenCode when needed, writes the Aliyun Token Plan provider into global OpenCode config, and validates the result on macOS and Windows.

**Architecture:** Keep the implementation in one Node.js entry script so platform detection, JSON merge logic, prompting, and verification live in one place. Add tiny shell wrappers for macOS and PowerShell wrappers for Windows so users can launch the same logic consistently, while tests cover the pure helper functions and dry-run output.

**Tech Stack:** Node.js, built-in `fs`, `path`, `os`, `child_process`, shell wrapper, PowerShell wrapper

---

## File Structure

- Create: `setup-opencode-bailian.js` — main CLI entrypoint for detection, install attempts, config merge, backup, validation, and user-facing output
- Create: `run-setup.sh` — macOS wrapper that invokes the Node.js script from the repo root
- Create: `run-setup.ps1` — Windows wrapper that invokes the Node.js script from the repo root
- Create: `tests/setup-opencode-bailian.test.js` — Node test file for helper logic, config merge behavior, path resolution, and dry-run behavior
- Modify: `docs/superpowers/specs/2026-05-07-opencode-bailian-setup-design.md` only if implementation planning reveals a spec contradiction that must be corrected before coding

### Task 1: Scaffold the script contract and failing tests

**Files:**
- Create: `setup-opencode-bailian.js`
- Create: `tests/setup-opencode-bailian.test.js`

- [ ] **Step 1: Write the failing test file for pure helper contracts**

```js
const test = require("node:test")
const assert = require("node:assert/strict")

const {
  DEFAULT_BASE_URL,
  DEFAULT_MODEL,
  PROVIDER_KEY,
  buildProviderConfig,
  mergeProviderConfig,
  parseArgs,
} = require("../setup-opencode-bailian.js")

test("parseArgs reads api key, base url, model, dry-run, and force flags", () => {
  const options = parseArgs([
    "--api-key",
    "token-123",
    "--base-url",
    "https://example.invalid/v1",
    "--model",
    "glm-5",
    "--dry-run",
    "--force",
  ])

  assert.deepEqual(options, {
    apiKey: "token-123",
    baseURL: "https://example.invalid/v1",
    model: "glm-5",
    dryRun: true,
    force: true,
  })
})

test("buildProviderConfig returns the Bailian provider and all models", () => {
  const provider = buildProviderConfig({
    apiKey: "token-123",
    baseURL: DEFAULT_BASE_URL,
  })

  assert.equal(provider.npm, "@ai-sdk/openai-compatible")
  assert.equal(provider.name, "Model Studio Token Plan 团队版")
  assert.equal(provider.options.apiKey, "token-123")
  assert.equal(provider.options.baseURL, DEFAULT_BASE_URL)
  assert.ok(provider.models[DEFAULT_MODEL])
  assert.ok(provider.models["MiniMax-M2.5"])
  assert.ok(provider.models["glm-5"])
  assert.ok(provider.models["deepseek-v3.2"])
})

test("mergeProviderConfig preserves schema and other providers while adding Bailian", () => {
  const existing = {
    $schema: "https://opencode.ai/config.json",
    provider: {
      openai: {
        npm: "@ai-sdk/openai",
      },
    },
  }

  const merged = mergeProviderConfig(
    existing,
    buildProviderConfig({ apiKey: "token-123", baseURL: DEFAULT_BASE_URL }),
    { force: false },
  )

  assert.equal(merged.$schema, "https://opencode.ai/config.json")
  assert.ok(merged.provider.openai)
  assert.ok(merged.provider[PROVIDER_KEY])
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: FAIL with `Cannot find module '../setup-opencode-bailian.js'` or missing export errors.

- [ ] **Step 3: Create the initial script skeleton with exported constants and stubs**

```js
#!/usr/bin/env node

const PROVIDER_KEY = "bailian-token-plan"
const DEFAULT_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
const DEFAULT_MODEL = "qwen3.6-plus"

function parseArgs(argv) {
  throw new Error("parseArgs not implemented")
}

function buildProviderConfig({ apiKey, baseURL = DEFAULT_BASE_URL }) {
  throw new Error("buildProviderConfig not implemented")
}

function mergeProviderConfig(existingConfig, providerConfig, options = {}) {
  throw new Error("mergeProviderConfig not implemented")
}

module.exports = {
  PROVIDER_KEY,
  DEFAULT_BASE_URL,
  DEFAULT_MODEL,
  parseArgs,
  buildProviderConfig,
  mergeProviderConfig,
}

if (require.main === module) {
  console.error("Not implemented")
  process.exit(1)
}
```

- [ ] **Step 4: Re-run the test to verify the failure moved to unimplemented functions**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: FAIL with `parseArgs not implemented`.

- [ ] **Step 5: Commit the scaffold**

```bash
git add setup-opencode-bailian.js tests/setup-opencode-bailian.test.js
git commit -m "feat: scaffold Bailian setup script"
```

### Task 2: Implement argument parsing and provider construction

**Files:**
- Modify: `setup-opencode-bailian.js`
- Test: `tests/setup-opencode-bailian.test.js`

- [ ] **Step 1: Add failing tests for default values and unknown flags**

```js
test("parseArgs returns defaults when optional flags are absent", () => {
  const options = parseArgs(["--api-key", "token-123"])

  assert.deepEqual(options, {
    apiKey: "token-123",
    baseURL: undefined,
    model: undefined,
    dryRun: false,
    force: false,
  })
})

test("parseArgs rejects unknown flags", () => {
  assert.throws(() => parseArgs(["--wat"]), /Unknown argument: --wat/)
})
```

- [ ] **Step 2: Run the targeted tests to confirm they fail**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: FAIL because `parseArgs` is still unimplemented.

- [ ] **Step 3: Implement `parseArgs` and `buildProviderConfig` minimally**

```js
function parseArgs(argv) {
  const options = {
    apiKey: undefined,
    baseURL: undefined,
    model: undefined,
    dryRun: false,
    force: false,
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]

    if (arg === "--dry-run") {
      options.dryRun = true
      continue
    }

    if (arg === "--force") {
      options.force = true
      continue
    }

    if (arg === "--api-key" || arg === "--base-url" || arg === "--model") {
      const value = argv[index + 1]
      if (!value || value.startsWith("--")) {
        throw new Error(`Missing value for ${arg}`)
      }
      if (arg === "--api-key") options.apiKey = value
      if (arg === "--base-url") options.baseURL = value
      if (arg === "--model") options.model = value
      index += 1
      continue
    }

    throw new Error(`Unknown argument: ${arg}`)
  }

  return options
}

function buildProviderConfig({ apiKey, baseURL = DEFAULT_BASE_URL }) {
  return {
    npm: "@ai-sdk/openai-compatible",
    name: "Model Studio Token Plan 团队版",
    options: {
      baseURL,
      apiKey,
    },
    models: {
      "qwen3.6-plus": {
        name: "Qwen3.6 Plus",
        modalities: { input: ["text", "image"], output: ["text"] },
        options: { thinking: { type: "enabled", budgetTokens: 8192 } },
        limit: { context: 1000000, output: 65536 },
      },
      "MiniMax-M2.5": {
        name: "MiniMax M2.5",
        modalities: { input: ["text"], output: ["text"] },
        options: { thinking: { type: "enabled", budgetTokens: 8192 } },
        limit: { context: 196608, output: 24576 },
      },
      "glm-5": {
        name: "GLM-5",
        modalities: { input: ["text"], output: ["text"] },
        options: { thinking: { type: "enabled", budgetTokens: 8192 } },
        limit: { context: 202752, output: 16384 },
      },
      "deepseek-v3.2": {
        name: "DeepSeek V3.2",
        modalities: { input: ["text"], output: ["text"] },
        limit: { context: 131072, output: 16384 },
      },
    },
  }
}
```

- [ ] **Step 4: Run the tests to verify argument parsing and provider construction pass**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: PASS for parse/build tests, FAIL for merge tests.

- [ ] **Step 5: Commit the parsing and provider logic**

```bash
git add setup-opencode-bailian.js tests/setup-opencode-bailian.test.js
git commit -m "feat: add Bailian provider defaults"
```

### Task 3: Implement config merge rules and backup-safe parsing

**Files:**
- Modify: `setup-opencode-bailian.js`
- Test: `tests/setup-opencode-bailian.test.js`

- [ ] **Step 1: Add failing tests for merge overwrite behavior and invalid JSON handling**

```js
const fs = require("node:fs")
const os = require("node:os")
const path = require("node:path")

const {
  readConfigFile,
  mergeProviderConfig,
  writeBackupFile,
} = require("../setup-opencode-bailian.js")

test("mergeProviderConfig throws when provider exists and force is false", () => {
  const existing = {
    provider: {
      [PROVIDER_KEY]: {
        name: "Old Provider",
      },
    },
  }

  assert.throws(
    () => mergeProviderConfig(existing, buildProviderConfig({ apiKey: "token-123" }), { force: false }),
    /already exists/,
  )
})

test("readConfigFile throws a helpful error for invalid JSON", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "opencode-config-"))
  const configPath = path.join(tempDir, "opencode.json")
  fs.writeFileSync(configPath, "{ nope", "utf8")

  assert.throws(() => readConfigFile(configPath), /Invalid JSON in config file/)
})

test("writeBackupFile creates a sibling backup file", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "opencode-config-"))
  const configPath = path.join(tempDir, "opencode.json")
  fs.writeFileSync(configPath, '{"ok":true}', "utf8")

  const backupPath = writeBackupFile(configPath)

  assert.match(backupPath, /opencode\.json\.bak\./)
  assert.equal(fs.existsSync(backupPath), true)
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: FAIL because `readConfigFile` and `writeBackupFile` are missing.

- [ ] **Step 3: Implement minimal config read, merge, and backup helpers**

```js
const fs = require("node:fs")
const path = require("node:path")

function readConfigFile(configPath) {
  if (!fs.existsSync(configPath)) {
    return {
      $schema: "https://opencode.ai/config.json",
      provider: {},
    }
  }

  const raw = fs.readFileSync(configPath, "utf8")

  try {
    return JSON.parse(raw)
  } catch {
    throw new Error(`Invalid JSON in config file: ${configPath}`)
  }
}

function writeBackupFile(configPath) {
  const backupPath = `${configPath}.bak.${Date.now()}`
  fs.copyFileSync(configPath, backupPath)
  return backupPath
}

function mergeProviderConfig(existingConfig, providerConfig, options = {}) {
  const next = {
    ...existingConfig,
    $schema: existingConfig.$schema || "https://opencode.ai/config.json",
    provider: {
      ...(existingConfig.provider || {}),
    },
  }

  if (next.provider[PROVIDER_KEY] && !options.force) {
    throw new Error(`${PROVIDER_KEY} already exists`)
  }

  next.provider[PROVIDER_KEY] = providerConfig
  return next
}
```

- [ ] **Step 4: Run the tests to verify config helpers pass**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: PASS for merge and file helper tests.

- [ ] **Step 5: Commit the config helper logic**

```bash
git add setup-opencode-bailian.js tests/setup-opencode-bailian.test.js
git commit -m "feat: add config merge and backup helpers"
```

### Task 4: Resolve platform paths and credential sources

**Files:**
- Modify: `setup-opencode-bailian.js`
- Test: `tests/setup-opencode-bailian.test.js`

- [ ] **Step 1: Add failing tests for config path resolution and credential precedence**

```js
const {
  getConfigPath,
  resolveRuntimeOptions,
} = require("../setup-opencode-bailian.js")

test("getConfigPath resolves macOS config path", () => {
  const configPath = getConfigPath({
    platform: "darwin",
    env: { HOME: "/Users/demo" },
  })

  assert.equal(configPath, "/Users/demo/.config/opencode/opencode.json")
})

test("getConfigPath resolves Windows config path", () => {
  const configPath = getConfigPath({
    platform: "win32",
    env: { APPDATA: "C:\\Users\\demo\\AppData\\Roaming" },
  })

  assert.equal(configPath, "C:\\Users\\demo\\AppData\\Roaming\\opencode\\opencode.json")
})

test("resolveRuntimeOptions prefers argv over env", async () => {
  const runtime = await resolveRuntimeOptions({
    args: {
      apiKey: "arg-token",
      baseURL: "https://arg.invalid/v1",
      model: "glm-5",
      dryRun: false,
      force: false,
    },
    env: {
      DASHSCOPE_API_KEY: "env-token",
      BAILIAN_BASE_URL: "https://env.invalid/v1",
      BAILIAN_MODEL: "deepseek-v3.2",
    },
    isInteractive: false,
    prompt: async () => {
      throw new Error("prompt should not run")
    },
  })

  assert.equal(runtime.apiKey, "arg-token")
  assert.equal(runtime.baseURL, "https://arg.invalid/v1")
  assert.equal(runtime.model, "glm-5")
})
```

- [ ] **Step 2: Run the test suite to confirm the new cases fail**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: FAIL because the new helpers are not implemented.

- [ ] **Step 3: Implement platform path and credential resolution helpers**

```js
const os = require("node:os")
const readline = require("node:readline/promises")

function getConfigPath({ platform = process.platform, env = process.env } = {}) {
  if (platform === "darwin") {
    return path.join(env.HOME || os.homedir(), ".config", "opencode", "opencode.json")
  }

  if (platform === "win32") {
    if (!env.APPDATA) {
      throw new Error("APPDATA is required to resolve the OpenCode config path on Windows")
    }
    return path.join(env.APPDATA, "opencode", "opencode.json")
  }

  throw new Error(`Unsupported platform: ${platform}`)
}

async function resolveRuntimeOptions({ args, env = process.env, isInteractive, prompt }) {
  const apiKey = args.apiKey || env.DASHSCOPE_API_KEY || env.BAILIAN_API_KEY
  const baseURL = args.baseURL || env.BAILIAN_BASE_URL || DEFAULT_BASE_URL
  const model = args.model || env.BAILIAN_MODEL || DEFAULT_MODEL

  if (apiKey) {
    return {
      apiKey,
      baseURL,
      model,
      dryRun: args.dryRun,
      force: args.force,
    }
  }

  if (!isInteractive) {
    throw new Error("Missing API key. Pass --api-key or set DASHSCOPE_API_KEY.")
  }

  const promptedApiKey = await prompt("Enter Bailian API key: ")
  if (!promptedApiKey) {
    throw new Error("Missing API key. Pass --api-key or set DASHSCOPE_API_KEY.")
  }

  return {
    apiKey: promptedApiKey,
    baseURL,
    model,
    dryRun: args.dryRun,
    force: args.force,
  }
}
```

- [ ] **Step 4: Run the tests to verify path and precedence logic passes**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: PASS for path and runtime option tests.

- [ ] **Step 5: Commit the path and credential resolution**

```bash
git add setup-opencode-bailian.js tests/setup-opencode-bailian.test.js
git commit -m "feat: resolve config paths and credentials"
```

### Task 5: Add install detection, install attempts, and validation helpers

**Files:**
- Modify: `setup-opencode-bailian.js`
- Test: `tests/setup-opencode-bailian.test.js`

- [ ] **Step 1: Add failing tests for install command planning and validation**

```js
const {
  buildManualInstallHint,
  getInstallPlan,
  validateConfig,
} = require("../setup-opencode-bailian.js")

test("getInstallPlan returns macOS install commands", () => {
  const plan = getInstallPlan("darwin")
  assert.deepEqual(plan[0], ["brew", ["install", "opencode-ai"]])
})

test("getInstallPlan returns Windows install commands", () => {
  const plan = getInstallPlan("win32")
  assert.deepEqual(plan[0], ["winget", ["install", "sst.opencode"]])
})

test("validateConfig checks the expected provider keys", () => {
  const issues = validateConfig({
    provider: {
      [PROVIDER_KEY]: buildProviderConfig({ apiKey: "token-123", baseURL: DEFAULT_BASE_URL }),
    },
  })

  assert.deepEqual(issues, [])
})
```

- [ ] **Step 2: Run the tests to confirm the helper gaps**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: FAIL because install and validation helpers are missing.

- [ ] **Step 3: Implement install planning and validation helpers**

```js
function getInstallPlan(platform) {
  if (platform === "darwin") {
    return [
      ["brew", ["install", "opencode-ai"]],
      ["npm", ["install", "-g", "opencode-ai"]],
    ]
  }

  if (platform === "win32") {
    return [
      ["winget", ["install", "sst.opencode"]],
      ["npm", ["install", "-g", "opencode-ai"]],
    ]
  }

  throw new Error(`Unsupported platform: ${platform}`)
}

function buildManualInstallHint(platform) {
  const commands = getInstallPlan(platform)
  return commands
    .map(([command, args]) => `${command} ${args.join(" ")}`)
    .join("\n")
}

function validateConfig(config) {
  const issues = []
  const provider = config.provider && config.provider[PROVIDER_KEY]

  if (!provider) issues.push(`Missing provider.${PROVIDER_KEY}`)
  if (!provider?.options?.baseURL) issues.push("Missing provider options.baseURL")
  if (!provider?.options?.apiKey) issues.push("Missing provider options.apiKey")
  if (!provider?.models?.[DEFAULT_MODEL]) issues.push(`Missing default model ${DEFAULT_MODEL}`)

  return issues
}
```

- [ ] **Step 4: Run the tests to verify install and validation helpers pass**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: PASS for install and validation helper tests.

- [ ] **Step 5: Commit the install and validation helpers**

```bash
git add setup-opencode-bailian.js tests/setup-opencode-bailian.test.js
git commit -m "feat: add install planning and validation helpers"
```

### Task 6: Wire the executable flow and dry-run output

**Files:**
- Modify: `setup-opencode-bailian.js`
- Test: `tests/setup-opencode-bailian.test.js`

- [ ] **Step 1: Add failing tests for dry-run output and non-interactive error handling**

```js
const {
  run,
} = require("../setup-opencode-bailian.js")

test("run returns a dry-run result without writing files", async () => {
  const writes = []

  const result = await run({
    argv: ["--api-key", "token-123", "--dry-run"],
    platform: "darwin",
    env: { HOME: "/Users/demo" },
    isInteractive: false,
    execFileSync() {
      return "0.0.0"
    },
    fs: {
      existsSync() {
        return false
      },
      mkdirSync() {},
      readFileSync() {
        throw new Error("should not read")
      },
      writeFileSync(filePath, content) {
        writes.push([filePath, content])
      },
      copyFileSync() {},
    },
  })

  assert.equal(result.mode, "dry-run")
  assert.equal(writes.length, 0)
  assert.match(result.preview, /bailian-token-plan/)
})

test("run throws a helpful error when API key is missing in non-interactive mode", async () => {
  await assert.rejects(
    () =>
      run({
        argv: [],
        platform: "darwin",
        env: { HOME: "/Users/demo" },
        isInteractive: false,
        execFileSync() {
          return "0.0.0"
        },
      }),
    /Missing API key/,
  )
})
```

- [ ] **Step 2: Run the tests to verify the executable flow is still missing**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: FAIL because `run` is not implemented.

- [ ] **Step 3: Implement the `run` function and CLI entrypoint with minimal side effects**

```js
function ensureOpencodeInstalled(execFileSync, platform) {
  try {
    execFileSync("opencode", ["--version"], { stdio: "pipe", encoding: "utf8" })
    return { installed: true, installedNow: false }
  } catch {
    const plan = getInstallPlan(platform)

    for (const [command, args] of plan) {
      try {
        execFileSync(command, args, { stdio: "inherit" })
        execFileSync("opencode", ["--version"], { stdio: "pipe", encoding: "utf8" })
        return { installed: true, installedNow: true }
      } catch {
      }
    }

    throw new Error(`Unable to install opencode automatically. Try one of:\n${buildManualInstallHint(platform)}`)
  }
}

async function run({
  argv = process.argv.slice(2),
  platform = process.platform,
  env = process.env,
  isInteractive = Boolean(process.stdin.isTTY && process.stdout.isTTY),
  execFileSync = require("node:child_process").execFileSync,
  fs: fsImpl = fs,
  prompt = async (question) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout })
    try {
      return (await rl.question(question)).trim()
    } finally {
      rl.close()
    }
  },
} = {}) {
  const args = parseArgs(argv)
  const runtime = await resolveRuntimeOptions({ args, env, isInteractive, prompt })
  const install = ensureOpencodeInstalled(execFileSync, platform)
  const configPath = getConfigPath({ platform, env })
  const configDir = path.dirname(configPath)

  if (args.dryRun) {
    return {
      mode: "dry-run",
      installed: install.installed,
      installedNow: install.installedNow,
      configPath,
      preview: JSON.stringify(buildProviderConfig(runtime), null, 2),
    }
  }

  fsImpl.mkdirSync(configDir, { recursive: true })
  const existingConfig = readConfigFile(configPath)
  if (fsImpl.existsSync(configPath)) {
    writeBackupFile(configPath)
  }
  const nextConfig = mergeProviderConfig(existingConfig, buildProviderConfig(runtime), {
    force: runtime.force,
  })
  fsImpl.writeFileSync(`${configPath}.tmp`, `${JSON.stringify(nextConfig, null, 2)}\n`, "utf8")
  fsImpl.renameSync(`${configPath}.tmp`, configPath)

  const issues = validateConfig(nextConfig)
  if (issues.length > 0) {
    throw new Error(`Config validation failed:\n${issues.join("\n")}`)
  }

  return {
    mode: "write",
    installed: install.installed,
    installedNow: install.installedNow,
    configPath,
    providerKey: PROVIDER_KEY,
    defaultModel: runtime.model,
  }
}

module.exports = {
  ...module.exports,
  buildManualInstallHint,
  getConfigPath,
  getInstallPlan,
  readConfigFile,
  resolveRuntimeOptions,
  run,
  validateConfig,
  writeBackupFile,
}

if (require.main === module) {
  run()
    .then((result) => {
      if (result.mode === "dry-run") {
        console.log(`Dry run OK. Config path: ${result.configPath}`)
        console.log(result.preview)
        return
      }

      console.log(`OpenCode ready. Config written to ${result.configPath}`)
      console.log(`Provider: ${result.providerKey}`)
      console.log(`Default model: ${result.defaultModel}`)
      console.log("Next: run opencode and select bailian-token-plan.")
    })
    .catch((error) => {
      console.error(error.message)
      process.exit(1)
    })
}
```

- [ ] **Step 4: Run the tests to verify dry-run and execution flow pass**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: PASS for dry-run and missing API key coverage; adjust injected `fs` methods if the implementation needs `renameSync` in the test double.

- [ ] **Step 5: Commit the executable flow**

```bash
git add setup-opencode-bailian.js tests/setup-opencode-bailian.test.js
git commit -m "feat: wire Bailian setup flow"
```

### Task 7: Add platform wrappers and manual smoke commands

**Files:**
- Create: `run-setup.sh`
- Create: `run-setup.ps1`
- Modify: `setup-opencode-bailian.js`

- [ ] **Step 1: Write the wrapper files**

```sh
#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec node "$SCRIPT_DIR/setup-opencode-bailian.js" "$@"
```

```powershell
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
node (Join-Path $ScriptDir "setup-opencode-bailian.js") @args
exit $LASTEXITCODE
```

- [ ] **Step 2: Make the shell wrapper executable and verify both wrappers call the Node script**

Run:

```bash
chmod +x run-setup.sh
./run-setup.sh --dry-run --api-key token-123
```

Expected: output begins with `Dry run OK.`

Run in PowerShell:

```powershell
./run-setup.ps1 --dry-run --api-key token-123
```

Expected: output begins with `Dry run OK.`

- [ ] **Step 3: Tighten final output to include the exact next-step commands**

```js
console.log("Next steps:")
console.log(`1. opencode`)
console.log(`2. Use provider ${result.providerKey}`)
console.log(`3. Start with model ${result.defaultModel}`)
```

- [ ] **Step 4: Run the full automated test suite again**

Run:

```bash
node --test tests/setup-opencode-bailian.test.js
```

Expected: PASS

- [ ] **Step 5: Commit the wrappers and output polish**

```bash
git add setup-opencode-bailian.js run-setup.sh run-setup.ps1 tests/setup-opencode-bailian.test.js
git commit -m "feat: add cross-platform setup wrappers"
```

### Task 8: Manual validation against the spec scenarios

**Files:**
- Modify: `setup-opencode-bailian.js` if any manual validation uncovers gaps
- Modify: `tests/setup-opencode-bailian.test.js` if new failing test coverage is needed

- [ ] **Step 1: Dry-run with a missing config file on macOS inputs**

Run:

```bash
HOME="$(mktemp -d)" node setup-opencode-bailian.js --api-key token-123 --dry-run
```

Expected: PASS, prints a preview, does not create `opencode.json`.

- [ ] **Step 2: Write mode with an existing config containing another provider**

Run:

```bash
TMP_HOME="$(mktemp -d)"
mkdir -p "$TMP_HOME/.config/opencode"
printf '%s\n' '{"$schema":"https://opencode.ai/config.json","provider":{"openai":{"npm":"@ai-sdk/openai"}}}' > "$TMP_HOME/.config/opencode/opencode.json"
HOME="$TMP_HOME" node setup-opencode-bailian.js --api-key token-123 --force
node -e 'const fs=require("node:fs");const p=process.argv[1];const data=JSON.parse(fs.readFileSync(p,"utf8"));if(!data.provider.openai||!data.provider["bailian-token-plan"]) process.exit(1)' "$TMP_HOME/.config/opencode/opencode.json"
```

Expected: PASS, preserves `openai`, writes `bailian-token-plan`, creates a backup file.

- [ ] **Step 3: Existing provider without `--force` should fail cleanly**

Run:

```bash
TMP_HOME="$(mktemp -d)"
mkdir -p "$TMP_HOME/.config/opencode"
printf '%s\n' '{"provider":{"bailian-token-plan":{"name":"Old"}}}' > "$TMP_HOME/.config/opencode/opencode.json"
HOME="$TMP_HOME" node setup-opencode-bailian.js --api-key token-123
```

Expected: FAIL with a message that the provider already exists.

- [ ] **Step 4: Invalid JSON should fail before overwrite**

Run:

```bash
TMP_HOME="$(mktemp -d)"
mkdir -p "$TMP_HOME/.config/opencode"
printf '%s\n' '{ nope' > "$TMP_HOME/.config/opencode/opencode.json"
HOME="$TMP_HOME" node setup-opencode-bailian.js --api-key token-123 --force
```

Expected: FAIL with `Invalid JSON in config file` and no overwrite of the original file.

- [ ] **Step 5: Commit any fixes that came out of manual validation**

```bash
git add setup-opencode-bailian.js tests/setup-opencode-bailian.test.js run-setup.sh run-setup.ps1
git commit -m "fix: cover setup validation edge cases"
```

## Self-Review Notes

- **Spec coverage:** The tasks cover platform detection, install attempts, global path resolution, config backup, merge rules, credential precedence, dry-run, force overwrite, validation, wrappers, and manual checks. The one spec item left for implementation-time verification is the exact official install command and config path documentation; Task 5 and Task 8 require confirming those before finalizing helper values.
- **Placeholder scan:** No TODO or TBD placeholders remain in task steps. Each coding step contains concrete code or exact commands.
- **Type consistency:** The plan uses the same exported helper names throughout: `parseArgs`, `buildProviderConfig`, `mergeProviderConfig`, `readConfigFile`, `writeBackupFile`, `getConfigPath`, `resolveRuntimeOptions`, `getInstallPlan`, `buildManualInstallHint`, `validateConfig`, and `run`.
