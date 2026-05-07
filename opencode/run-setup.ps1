$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
node (Join-Path $ScriptDir "setup-opencode-bailian.js") @args
exit $LASTEXITCODE
