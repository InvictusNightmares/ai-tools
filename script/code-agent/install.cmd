@echo off
setlocal

set "SCRIPT_NAME=install.js"
set "DEFAULT_BASE_URL=https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent"
if "%AI_TOOLS_INSTALLER_BASE_URL%"=="" (
  set "BASE_URL=%DEFAULT_BASE_URL%"
) else (
  set "BASE_URL=%AI_TOOLS_INSTALLER_BASE_URL%"
)

set "LOCAL_SCRIPT=%~dp0%SCRIPT_NAME%"

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Installing Node.js first...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo Error: Node.js is required and winget is unavailable. Install Node.js 18+ from https://nodejs.org/ and retry. 1>&2
    exit /b 1
  )
  winget install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo Error: Failed to install Node.js with winget. 1>&2
    exit /b 1
  )
  set "PATH=%ProgramFiles%\nodejs;%APPDATA%\npm;%PATH%"
)

where npm >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Installing Node.js first...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo Error: npm is required and winget is unavailable. Install Node.js 18+ from https://nodejs.org/ and retry. 1>&2
    exit /b 1
  )
  winget install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo Error: Failed to install Node.js with winget. 1>&2
    exit /b 1
  )
  set "PATH=%ProgramFiles%\nodejs;%APPDATA%\npm;%PATH%"
)

if exist "%LOCAL_SCRIPT%" (
  node "%LOCAL_SCRIPT%" %*
  exit /b %ERRORLEVEL%
)

where curl >nul 2>nul
if errorlevel 1 (
  echo Error: curl is required. 1>&2
  exit /b 1
)

set "TMP_SCRIPT=%TEMP%\ai-tools-install-%RANDOM%-%RANDOM%.js"
curl -fsSL "%BASE_URL%/%SCRIPT_NAME%" -o "%TMP_SCRIPT%"
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%BASE_URL%/%SCRIPT_NAME%' -OutFile '%TMP_SCRIPT%'"
  if errorlevel 1 (
    del "%TMP_SCRIPT%" >nul 2>nul
    exit /b 1
  )
)

node "%TMP_SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"
del "%TMP_SCRIPT%" >nul 2>nul
exit /b %EXIT_CODE%
