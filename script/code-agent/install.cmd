@echo off
setlocal

set "SCRIPT_NAME=install.js"
set "DEFAULT_BASE_URL=https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/script/code-agent"
set "USE_LOCAL_SCRIPT="
if "%AI_TOOLS_INSTALLER_BASE_URL%"=="" (
  set "BASE_URL=%DEFAULT_BASE_URL%"
) else (
  set "BASE_URL=%AI_TOOLS_INSTALLER_BASE_URL%"
)

set "LOCAL_SCRIPT=%~dp0%SCRIPT_NAME%"
if exist "%~dp0README.md" if exist "%~dp0install.sh" set "USE_LOCAL_SCRIPT=1"
if "%AI_TOOLS_INSTALLER_USE_LOCAL%"=="1" set "USE_LOCAL_SCRIPT=1"
if defined USE_LOCAL_SCRIPT if exist "%LOCAL_SCRIPT%" (
  node "%LOCAL_SCRIPT%" %*
  exit /b %ERRORLEVEL%
)

where node >nul 2>nul
if errorlevel 1 (
  echo Error: Node.js is required. Install Node.js 18+ and retry. 1>&2
  exit /b 1
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
