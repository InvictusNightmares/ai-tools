$ErrorActionPreference = "Stop"

$ScriptName = "install.js"
$DefaultBaseUrl = "https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent"
$BaseUrl = if ($env:AI_TOOLS_INSTALLER_BASE_URL) { $env:AI_TOOLS_INSTALLER_BASE_URL } else { $DefaultBaseUrl }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalScript = Join-Path $ScriptDir $ScriptName
$MinNodeMajor = 18

function Test-Command($Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Update-NodePath {
  $paths = @()
  if ($env:ProgramFiles) { $paths += (Join-Path $env:ProgramFiles "nodejs") }
  if (${env:ProgramFiles(x86)}) { $paths += (Join-Path ${env:ProgramFiles(x86)} "nodejs") }
  if ($env:APPDATA) { $paths += (Join-Path $env:APPDATA "npm") }

  foreach ($candidate in $paths) {
    if ((Test-Path $candidate) -and (($env:Path -split ';') -notcontains $candidate)) {
      $env:Path = "$candidate;$env:Path"
    }
  }
}

function Test-NodeUsable {
  Update-NodePath
  if (-not (Test-Command "node")) { return $false }
  if (-not (Test-Command "npm")) { return $false }

  try {
    $version = (& node --version).TrimStart("v")
    $major = [int]($version.Split(".")[0])
    return $major -ge $MinNodeMajor
  }
  catch {
    return $false
  }
}

function Install-Node {
  if (-not (Test-Command "winget")) {
    Write-Error "Node.js $MinNodeMajor+ with npm was not found, and winget is unavailable. Install Node.js from https://nodejs.org/ and retry."
    exit 1
  }

  Write-Host "Node.js $MinNodeMajor+ with npm was not found. Installing Node.js first..."
  winget install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install Node.js with winget."
    exit $LASTEXITCODE
  }

  Update-NodePath
}

if (-not (Test-NodeUsable)) {
  Install-Node
}

if (-not (Test-NodeUsable)) {
  Write-Error "Node.js was installed but is not available in PATH. Reopen PowerShell and retry."
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
