@echo off
setlocal
set "BASE_URL=https://raw.giteeusercontent.com/InvictusNightmares/ai-tools/raw/main/opencode"
if not "%OPENCODE_SETUP_BASE_URL%"=="" set "BASE_URL=%OPENCODE_SETUP_BASE_URL%"

if exist "%~dp0setup-opencode-bailian.js" (
  node "%~dp0setup-opencode-bailian.js" %*
  exit /b %ERRORLEVEL%
)

if exist "%~dp0run-setup.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-setup.ps1" %*
  exit /b %ERRORLEVEL%
)

set "TMP_PS1=%TEMP%\opencode-run-setup-%RANDOM%%RANDOM%.ps1"
curl -fsSL "%BASE_URL%/run-setup.ps1" -o "%TMP_PS1%"
if errorlevel 1 exit /b %ERRORLEVEL%

powershell -NoProfile -ExecutionPolicy Bypass -File "%TMP_PS1%" %*
set "RC=%ERRORLEVEL%"
del "%TMP_PS1%" >nul 2>nul
exit /b %RC%
