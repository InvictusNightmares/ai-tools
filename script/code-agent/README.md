# AI Agent Installer

Team installer for Claude Code, Codex, and OpenCode.

The installer uses fixed DACS external/internal endpoints and no longer accepts URL input.

DACS external endpoint:

```text
http://192.168.64.16:4001/v1
```

DACS internal endpoint:

```text
http://47.117.95.192:4001/v1
```

Claude Code uses each configured endpoint without the `/v1` suffix.

The default model is fixed:

```text
gpt-5.5
```

Users provide an API key. The model and DACS external/internal endpoints remain fixed.

## macOS / Linux

Online install:

```bash
curl -fsSL https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent/install.sh | bash
```

The bootstrap reopens `/dev/tty`, so interactive prompts work even when the script is piped through `bash`.

On macOS / Linux, if `npm install -g` fails because the system global npm directory is not writable, the installer automatically retries with sudo:

```bash
sudo npm install -g <package>
```

The system may ask for the user's password.

Non-interactive:

```bash
curl -fsSL https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent/install.sh | bash -s -- \
  --agents all \
  --api-key sk-xxx \
  --yes
```

## Windows CMD

Download, run, and delete:

```cmd
curl -fsSL https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent/install.cmd -o install-ai-agents.cmd && .\install-ai-agents.cmd && del install-ai-agents.cmd
```

Non-interactive:

```cmd
curl -fsSL https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent/install.cmd -o install-ai-agents.cmd && .\install-ai-agents.cmd --agents all --api-key sk-xxx --yes && del install-ai-agents.cmd
```

## Windows PowerShell

Download, run, and delete:

```powershell
Invoke-WebRequest -Uri "https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent/install.ps1" -OutFile "install-ai-agents.ps1"; powershell -NoProfile -ExecutionPolicy Bypass -File .\install-ai-agents.ps1; Remove-Item .\install-ai-agents.ps1
```

Non-interactive:

```powershell
Invoke-WebRequest -Uri "https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent/install.ps1" -OutFile "install-ai-agents.ps1"; powershell -NoProfile -ExecutionPolicy Bypass -File .\install-ai-agents.ps1 --agents all --api-key sk-xxx --yes; Remove-Item .\install-ai-agents.ps1
```

## Local Usage

Node.js entry:

```bash
node script/code-agent/install.js
```

macOS / Linux bootstrap:

```bash
bash script/code-agent/install.sh
```

Windows bootstrap:

```cmd
script\code-agent\install.cmd
```

PowerShell bootstrap:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\script\code-agent\install.ps1
```

## Options

```text
--agents <list>       all or comma-separated: claude-code,codex,opencode
--api-key <key>       API key for OpenAI-compatible API
--mode <mode>         install-and-config, install-only, config-only, verify-only
--codex-websockets    Enable Codex provider WebSocket support
--no-codex-websockets Disable Codex provider WebSocket support
--yes                 Do not prompt for confirmation
--force               Reinstall or overwrite existing files without asking
--dry-run             Print actions without changing files
--verbose             Print executed commands
--help                Show help
```

## Modes

```text
install-and-config  Install CLI tools and write config files
install-only        Only install CLI tools
config-only         Only write config files
verify-only         Only verify commands and API
```

## DACS Usage

The installer keeps external and internal startup separate.

Outside DACS, use the normal commands:

```bash
codex
opencode
claude
```

Inside DACS, use the explicit DACS commands:

```bash
codex-dacs
opencode-dacs
```

This prevents the DACS internal URL from leaking into normal terminal usage.

On macOS, the installer writes the DACS commands into the DACS `.globalBase/usr/bin` directory when it can find one:

```text
~/meili/<user>/Applications/.globalBase/usr/bin/codex-dacs
~/meili/<user>/Applications/.globalBase/usr/bin/opencode-dacs
~/meili/<user>/Applications/.globalBase/usr/bin/dacs-writable-probe
```

Discovery order:

```text
1. AI_TOOLS_DACS_BIN_DIR
2. DACS_GLOBAL_BASE_BIN
3. Current PATH entries containing .globalBase/usr/bin
4. ~/meili/*/Applications/.globalBase/usr/bin
```

Override the target directory when needed:

```bash
AI_TOOLS_DACS_BIN_DIR=/path/to/.globalBase/usr/bin node script/code-agent/install.js --agents codex,opencode --api-key sk-xxx --yes
```

If an older installer created `codex` or `opencode` shadow commands in `.globalBase/usr/bin`, the newer installer removes only the old ai-tools generated shadows and replaces them with `codex-dacs` / `opencode-dacs`.

Troubleshooting DACS writable paths:

```bash
dacs-writable-probe
```

## Written Files

macOS / Linux Claude Code:

```text
~/.claude.json
~/.claude/settings.json
~/.claude/settings.external.json
~/.claude/settings.dacs.json
```

macOS / Linux Codex:

```text
~/.codex/config.toml
~/.codex/config.external.toml
~/.codex/config.dacs.toml
~/.codex/auth.json
```

macOS Codex DACS command:

```text
~/meili/<user>/Applications/.globalBase/usr/bin/codex-dacs
~/meili/<user>/Applications/.globalBase/usr/bin/dacs-writable-probe
```

Inside DACS:

```bash
codex-dacs
```

If Codex fails with `Operation not permitted`, run:

```bash
dacs-writable-probe
```

The Codex DACS command uses a fresh `$TMPDIR/codex-home-dacs-<pid>` directory, reads `OPENAI_API_KEY` from `~/.codex/auth.json` when needed, and passes DACS provider settings through `codex -c` flags to avoid writing `config.toml` inside DACS. Outside DACS, keep using `codex` so it reads the external URL config.

macOS / Linux OpenCode:

```text
~/.config/opencode/opencode.json
~/.config/opencode/opencode.external.json
~/.config/opencode/opencode.dacs.json
```

macOS OpenCode DACS command:

```text
~/meili/<user>/Applications/.globalBase/usr/bin/opencode-dacs
```

Outside DACS, run `opencode`; it reads `~/.config/opencode/opencode.json` and uses the external URL. Inside DACS, run `opencode-dacs`; it creates a fresh `$TMPDIR/opencode-home-dacs-<pid>` runtime, writes an internal-URL `opencode.json`, points `XDG_*` and `OPENCODE_CONFIG_DIR` at that temporary runtime, and then starts the real OpenCode binary.

Windows Claude Code:

```text
%USERPROFILE%\.claude.json
%USERPROFILE%\.claude\settings.json
%USERPROFILE%\.claude\settings.external.json
%USERPROFILE%\.claude\settings.dacs.json
```

Windows Codex:

```text
%USERPROFILE%\.codex\config.toml
%USERPROFILE%\.codex\config.external.toml
%USERPROFILE%\.codex\config.dacs.toml
%USERPROFILE%\.codex\auth.json
```

Windows OpenCode:

```text
%USERPROFILE%\.config\opencode\opencode.json
%USERPROFILE%\.config\opencode\opencode.external.json
%USERPROFILE%\.config\opencode\opencode.dacs.json
```

Active config files are written with the DACS external URL by default. DACS can switch to the internal URL by replacing or linking the active file to the `.dacs` file; switch back by pointing it to the `.external` file.

Active/substitute files:

```text
Claude Code: ~/.claude/settings.json -> settings.external.json or settings.dacs.json
Codex: ~/.codex/config.toml -> config.external.toml or config.dacs.toml
OpenCode: ~/.config/opencode/opencode.json -> opencode.external.json or opencode.dacs.json
```

Existing files are backed up before overwrite:

```text
<file>.bak.YYYYMMDD-HHMMSS
```

## Dry Run

```bash
node script/code-agent/install.js --agents all --api-key sk-xxx --dry-run --yes
```

Dry run prints actions without installing packages or writing files.

## Bootstrap Override

The online launchers download `install.js` from Gitee by default. For testing a mirror or branch, set:

```bash
AI_TOOLS_INSTALLER_BASE_URL="https://example.com/script/code-agent" bash script/code-agent/install.sh
```

Windows:

```cmd
set AI_TOOLS_INSTALLER_BASE_URL=https://example.com/script/code-agent
install-ai-agents.cmd
```

PowerShell:

```powershell
$env:AI_TOOLS_INSTALLER_BASE_URL = "https://example.com/script/code-agent"
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-ai-agents.ps1
```
