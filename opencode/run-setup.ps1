$ScriptName = "setup-opencode-bailian.js"
$DefaultBaseUrl = "https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/opencode"
$BaseUrl = if ($env:OPENCODE_SETUP_BASE_URL) { $env:OPENCODE_SETUP_BASE_URL } else { $DefaultBaseUrl }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalScript = Join-Path $ScriptDir $ScriptName

if (Test-Path $LocalScript) {
  node $LocalScript @args
  exit $LASTEXITCODE
}

$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $TempDir | Out-Null
$DownloadedScript = Join-Path $TempDir $ScriptName

try {
  Invoke-WebRequest -Uri "$BaseUrl/$ScriptName" -OutFile $DownloadedScript
  node $DownloadedScript @args
  exit $LASTEXITCODE
}
finally {
  Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
}
