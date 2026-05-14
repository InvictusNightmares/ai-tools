# AI Agent Installer

Team installer for Claude Code, Codex, and OpenCode.

The installer uses one fixed endpoint:

```text
http://8.216.44.189:8317/v1
```

The default model is fixed:

```text
gpt-5.5
```

Users only provide an API key. The installer does not ask for a base URL or model.

## macOS / Linux

Online install:

```bash
curl -fsSL https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/shell/code-agent/install.sh | bash
```

The bootstrap reopens `/dev/tty`, so interactive prompts work even when the script is piped through `bash`.

Non-interactive:

```bash
curl -fsSL https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/shell/code-agent/install.sh | bash -s -- \
  --agents all \
  --api-key sk-xxx \
  --yes
```

## Windows CMD

Download, run, and delete:

```cmd
curl -fsSL https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/shell/code-agent/install.cmd -o install-ai-agents.cmd && install-ai-agents.cmd && del install-ai-agents.cmd
```

Non-interactive:

```cmd
curl -fsSL https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/shell/code-agent/install.cmd -o install-ai-agents.cmd && install-ai-agents.cmd --agents all --api-key sk-xxx --yes && del install-ai-agents.cmd
```

## Windows PowerShell

Download, run, and delete:

```powershell
Invoke-WebRequest -Uri "https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/shell/code-agent/install.ps1" -OutFile "install-ai-agents.ps1"; powershell -NoProfile -ExecutionPolicy Bypass -File .\install-ai-agents.ps1; Remove-Item .\install-ai-agents.ps1
```

Non-interactive:

```powershell
Invoke-WebRequest -Uri "https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/shell/code-agent/install.ps1" -OutFile "install-ai-agents.ps1"; powershell -NoProfile -ExecutionPolicy Bypass -File .\install-ai-agents.ps1 --agents all --api-key sk-xxx --yes; Remove-Item .\install-ai-agents.ps1
```

## Local Usage

Node.js entry:

```bash
node shell/code-agent/install.js
```

macOS / Linux bootstrap:

```bash
bash shell/code-agent/install.sh
```

Windows bootstrap:

```cmd
shell\code-agent\install.cmd
```

PowerShell bootstrap:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\shell\code-agent\install.ps1
```

## Options

```text
--agents <list>       all or comma-separated: claude-code,codex,opencode
--api-key <key>       API key for AI Tools
--mode <mode>         install-and-config, install-only, config-only, verify-only
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

## Written Files

macOS / Linux Claude Code:

```text
~/.claude/settings.json
~/.ai-agents/env
```

macOS / Linux Codex:

```text
~/.codex/config.toml
~/.ai-agents/env
```

macOS / Linux OpenCode:

```text
~/.config/opencode/opencode.json
```

Windows Claude Code:

```text
%USERPROFILE%\.claude\settings.json
%USERPROFILE%\.ai-agents\env.cmd
```

Windows Codex:

```text
%USERPROFILE%\.codex\config.toml
%USERPROFILE%\.ai-agents\env.cmd
```

Windows OpenCode:

```text
%USERPROFILE%\.config\opencode\opencode.json
```

Existing files are backed up before overwrite:

```text
<file>.bak.YYYYMMDD-HHMMSS
```

## Dry Run

```bash
node shell/code-agent/install.js --agents all --api-key sk-xxx --dry-run --yes
```

Dry run prints actions without installing packages or writing files.

## Bootstrap Override

The online launchers download `install.js` from Gitee by default. For testing a mirror or branch, set:

```bash
AI_TOOLS_INSTALLER_BASE_URL="https://example.com/shell/code-agent" bash shell/code-agent/install.sh
```

Windows:

```cmd
set AI_TOOLS_INSTALLER_BASE_URL=https://example.com/shell/code-agent
install-ai-agents.cmd
```

PowerShell:

```powershell
$env:AI_TOOLS_INSTALLER_BASE_URL = "https://example.com/shell/code-agent"
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-ai-agents.ps1
```
