$ErrorActionPreference = "Stop"

$ScriptName = "install.js"
$DefaultBaseUrl = "https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent"
$BaseUrl = if ($env:AI_TOOLS_INSTALLER_BASE_URL) { $env:AI_TOOLS_INSTALLER_BASE_URL } else { $DefaultBaseUrl }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalScript = Join-Path $ScriptDir $ScriptName

function Test-Command($Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command "node")) {
  Write-Error "Node.js is required. Install Node.js 18+ and retry."
  exit 1
}

if (Test-Path $LocalScript) {
  & node $LocalScript @args
  exit $LASTEXITCODE
}

$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $TempDir | Out-Null
$DownloadedScript = Join-Path $TempDir $ScriptName

try {
  Invoke-WebRequest -Uri "$BaseUrl/$ScriptName" -OutFile $DownloadedScript
  & node $DownloadedScript @args
  exit $LASTEXITCODE
}
finally {
  Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
}
