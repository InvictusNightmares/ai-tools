param([string]$SourcePath = (Join-Path $PSScriptRoot 'Prepare-ProxyBootstrap.ps1'))
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    function node.exe { $input | & node @args }
}
$Tokens = $null
$ParseErrors = $null
$Ast = [Management.Automation.Language.Parser]::ParseFile($SourcePath, [ref]$Tokens, [ref]$ParseErrors)
if ($ParseErrors.Count) { throw 'Generator did not parse.' }
$Names = @('Remove-TopLevelYamlSections', 'Get-BootstrapDirectRules', 'New-LinuxBootstrapConfig')
$script:FixtureScriptRoot = $PSScriptRoot
foreach ($Function in $Ast.FindAll({ param($Node) $Node -is [Management.Automation.Language.FunctionDefinitionAst] }, $false)) {
    if ($Function.Name -in $Names) {
        # Dynamically extracted functions have no script file location.
        Invoke-Expression $Function.Extent.Text.Replace('$PSScriptRoot', '$script:FixtureScriptRoot')
    }
}
function Render-Fixture {
    param([string]$Server, [string]$Rules)
    $Text = @"
proxies:
  - name: "test ' 节点"
    type: socks5
    server: '$Server'
    port: 1080
rules:
$Rules
  - MATCH,PROXY
"@
    New-LinuxBootstrapConfig -SourceLines ($Text -split "`n") -ConcreteProxyName "test ' 节点"
}
function Assert-Contains {
    param([string]$Text, [string]$Expected)
    if (-not $Text.Contains($Expected)) { throw "Missing expected fixture rule: $Expected" }
}
function Assert-Excludes {
    param([string]$Text, [string]$Unexpected)
    if ($Text.Contains($Unexpected)) { throw "Unexpected fixture rule: $Unexpected" }
}
$IPv4 = Render-Fixture '198.51.100.7' @'
  - IP-CIDR,198.51.100.7/32,DIRECT,no-resolve
  - IP-CIDR,198.51.100.0/24,DIRECT
  - DOMAIN,unrelated.invalid,DIRECT
'@
Assert-Contains $IPv4 "  - IP-CIDR,198.51.100.7/32,DIRECT,no-resolve`n  - MATCH,BOOTSTRAP"
Assert-Excludes $IPv4 '198.51.100.0/24'
Assert-Excludes $IPv4 'unrelated.invalid'
$Missing = Render-Fixture '198.51.100.7' '  - IP-CIDR,198.51.100.7/32,REJECT'
Assert-Excludes $Missing 'DIRECT'
$Domain = Render-Fixture 'node.example.invalid' '  - DOMAIN,node.example.invalid,DIRECT'
Assert-Contains $Domain "  - DOMAIN,node.example.invalid,DIRECT`n  - MATCH,BOOTSTRAP"
$IPv6 = Render-Fixture '2001:db8::7' '  - IP-CIDR6,2001:db8::7/128,DIRECT,no-resolve'
Assert-Contains $IPv6 "  - IP-CIDR6,2001:db8::7/128,DIRECT,no-resolve`n  - MATCH,BOOTSTRAP"
Write-Host 'PASS: exact IPv4/IPv6/domain self routes survive; unrelated and broad routes do not; no new DIRECT policy is invented.'
