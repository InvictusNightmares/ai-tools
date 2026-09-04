[CmdletBinding()]
param(
    [string]$ClashDataDirectory = (Join-Path $env:APPDATA 'io.github.clash-verge-rev.clash-verge-rev'),
    [string]$WindowsMihomoPath = 'D:\Software\Clash Verge\verge-mihomo.exe',
    [string]$Destination,
    [switch]$VerifyOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$InstallerCommit = '6b3a341b4bb5c0b93f25cc0a0518e9bd5088504b'
$MihomoVersion = '1.19.29'
$MihomoArchiveSha256 = 'A048ECBE2DC598321F63A6FBEFFA93F0C10CA6DB818F64B2B83CF19EF194D73F'
$MihomoBinarySha256 = '040452CA5FCA2977C038D539F34A60DD03D2CE1B9DF23C61815D6C91E7FF2C25'
$MihomoArchiveUrl = "https://github.com/MetaCubeX/mihomo/releases/download/v$MihomoVersion/mihomo-linux-amd64-v1-v$MihomoVersion.gz"
$ClashVergeVersion = '2.5.2'
$ClashVergeCommit = '28f2efc504059b1dc75c793618b775c8e1b2a5f1'
$JsYamlVersion = '5.2.2'
$JsYamlSha256 = '67784D9C17C101918E97F9456957AD6E558CE2F9A50627F40298D5672365BDC1'

if ([string]::IsNullOrWhiteSpace($Destination)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $Destination = Join-Path $RepoRoot ".agentbox-staging\$($InstallerCommit.Substring(0, 12))\proxy-bootstrap"
}

$Destination = [IO.Path]::GetFullPath($Destination)
$SourceRuntimePath = Join-Path $ClashDataDirectory 'clash-verge.yaml'
$SourceProfilesPath = Join-Path $ClashDataDirectory 'profiles.yaml'
$SourceProfileDirectory = Join-Path $ClashDataDirectory 'profiles'
$SourceRulesetDirectory = Join-Path $ClashDataDirectory 'ruleset'
$LinuxBootstrapConfigPath = Join-Path $Destination 'config.yaml'
$LinuxProductionConfigPath = Join-Path $Destination 'production.yaml'
$LinuxMihomoPath = Join-Path $Destination 'mihomo'
$StartProxyPath = Join-Path $Destination 'start-proxy.sh'
$PrivateManifestPath = Join-Path $Destination 'PRIVATE-MANIFEST.txt'
$AppProfileDirectory = Join-Path $Destination 'app-profile'
$BundledProfileDirectory = Join-Path $AppProfileDirectory 'profiles'
$BundledRulesetDirectory = Join-Path $Destination 'ruleset'
$BundledCompilerPath = Join-Path $Destination 'agentbox-profile-compiler.js'
$BundledUpdaterPath = Join-Path $Destination 'update-agentbox-proxy.sh'
$BundledInstallerPath = Join-Path $Destination 'install-target.sh'
$BundledVendorDirectory = Join-Path $Destination 'vendor'

function Get-Sha256 {
    param([Parameter(Mandatory)][string]$Path)
    (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToUpperInvariant()
}

function Assert-Hash {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$ExpectedHash)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required file is missing: $Path" }
    $Actual = Get-Sha256 -Path $Path
    if ($Actual -ne $ExpectedHash.ToUpperInvariant()) {
        throw "SHA-256 mismatch for $Path`nExpected: $ExpectedHash`nActual:   $Actual"
    }
}

function Assert-RegularFile {
    param([Parameter(Mandatory)][string]$Path)
    $Item = Get-Item -Force -LiteralPath $Path
    if ($Item.PSIsContainer -or ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Refusing a directory or reparse point where a regular file is required: $Path"
    }
}

function ConvertFrom-HttpChunkedBody {
    param([Parameter(Mandatory)][string]$Body)
    $Decoded = New-Object Text.StringBuilder
    $Position = 0
    while ($true) {
        $LineEnd = $Body.IndexOf("`r`n", $Position)
        if ($LineEnd -lt 0) { throw 'Invalid chunk header from the local Mihomo API.' }
        $HexSize = $Body.Substring($Position, $LineEnd - $Position).Split(';')[0]
        $Size = [Convert]::ToInt32($HexSize, 16)
        if ($Size -eq 0) { break }
        $Position = $LineEnd + 2
        [void]$Decoded.Append($Body.Substring($Position, $Size))
        $Position += $Size + 2
    }
    $Decoded.ToString()
}

function Get-ActiveMihomoProxyData {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string[]]$ConfigLines,
        [Parameter(Mandatory)][string]$PipeName
    )
    $SecretLine = $ConfigLines | Where-Object { $_ -match '^secret:\s*' } | Select-Object -First 1
    $Secret = if ($null -eq $SecretLine) { '' } else { ($SecretLine -replace '^secret:\s*', '').Trim().Trim('"').Trim("'") }
    $Pipe = [IO.Pipes.NamedPipeClientStream]::new('.', $PipeName, [IO.Pipes.PipeDirection]::InOut)
    $Pipe.Connect(5000)
    try {
        $Writer = [IO.StreamWriter]::new($Pipe, [Text.Encoding]::ASCII, 1024, $true)
        $Writer.NewLine = "`r`n"
        $Writer.WriteLine('GET /proxies HTTP/1.1')
        $Writer.WriteLine('Host: localhost')
        if (-not [string]::IsNullOrEmpty($Secret)) { $Writer.WriteLine("Authorization: Bearer $Secret") }
        $Writer.WriteLine('Connection: close')
        $Writer.WriteLine('')
        $Writer.Flush()
        $Reader = [IO.StreamReader]::new($Pipe, [Text.Encoding]::UTF8)
        $Response = $Reader.ReadToEnd()
    }
    finally {
        $Pipe.Dispose()
        $Secret = $null
    }
    $Separator = $Response.IndexOf("`r`n`r`n")
    if ($Separator -lt 0) { throw 'Invalid HTTP response from the local Mihomo API.' }
    $Headers = $Response.Substring(0, $Separator)
    if ($Headers -notmatch '^HTTP/1\.1 200') { throw "Local Mihomo API returned: $($Headers.Split("`r`n")[0])" }
    $Body = $Response.Substring($Separator + 4)
    if ($Headers -match '(?im)^Transfer-Encoding:\s*chunked') { $Body = ConvertFrom-HttpChunkedBody -Body $Body }
    $Body | ConvertFrom-Json
}

function Get-MatchTarget {
    param([Parameter(Mandatory)][AllowEmptyString()][string[]]$ConfigLines)
    $InRules = $false
    $Target = $null
    foreach ($Line in $ConfigLines) {
        if ($Line -match '^rules:\s*$') { $InRules = $true; continue }
        if ($InRules -and $Line -match '^[A-Za-z0-9_-]+:') { $InRules = $false }
        if ($InRules -and $Line -match '^\s*-\s*["'']?MATCH\s*,\s*([^,#"'']+)') { $Target = $Matches[1].Trim() }
    }
    if ([string]::IsNullOrWhiteSpace($Target)) { throw 'The active Clash configuration has no MATCH rule to resolve.' }
    $Target
}

function Resolve-ConcreteProxy {
    param([Parameter(Mandatory)]$ProxyData, [Parameter(Mandatory)][string]$InitialTarget)
    $Current = $InitialTarget
    for ($Depth = 0; $Depth -lt 10; $Depth++) {
        $Property = $ProxyData.proxies.PSObject.Properties | Where-Object { $_.Name -eq $Current } | Select-Object -First 1
        if ($null -eq $Property) { throw 'The active MATCH target does not exist in the local Mihomo API.' }
        $Entry = $Property.Value
        if ($Entry.type -notin @('Selector', 'URLTest', 'Fallback', 'LoadBalance')) {
            if ($Entry.type -in @('Direct', 'Reject', 'RejectDrop', 'Pass')) { throw "The active route resolves to $($Entry.type)." }
            return [pscustomobject]@{ Name = $Current; Type = [string]$Entry.type; Depth = $Depth }
        }
        if ([string]::IsNullOrWhiteSpace([string]$Entry.now)) { throw 'A proxy group has no active selection.' }
        $Current = [string]$Entry.now
    }
    throw 'Proxy-group resolution exceeded the safety depth.'
}

function Remove-TopLevelYamlSections {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string[]]$Lines,
        [Parameter(Mandatory)][string[]]$SectionNames
    )
    $Skip = $false
    $Result = New-Object System.Collections.Generic.List[string]
    foreach ($Line in $Lines) {
        if ($Line -match '^([A-Za-z0-9_-]+):') { $Skip = $SectionNames -contains $Matches[1] }
        if (-not $Skip) { $Result.Add($Line) }
    }
    $Result.ToArray()
}

function New-LinuxBootstrapConfig {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string[]]$SourceLines,
        [Parameter(Mandatory)][string]$ConcreteProxyName
    )
    $SectionsToRemove = @(
        'port', 'socks-port', 'mixed-port', 'redir-port', 'tproxy-port', 'allow-lan',
        'bind-address', 'authentication', 'skip-auth-prefixes', 'mode', 'tun', 'dns',
        'hosts', 'listeners', 'proxy-groups', 'proxy-providers', 'rule-providers',
        'rules', 'external-controller', 'external-controller-unix',
        'external-controller-cors', 'external-controller-pipe', 'secret'
    )
    $BaseLines = Remove-TopLevelYamlSections -Lines $SourceLines -SectionNames $SectionsToRemove
    $QuotedProxyName = "'" + $ConcreteProxyName.Replace("'", "''") + "'"
    $Suffix = @(
        '', 'mixed-port: 7897', 'allow-lan: false', "bind-address: '127.0.0.1'",
        'mode: rule', 'tun:', '  enable: false', 'proxy-groups:',
        '  - name: BOOTSTRAP', '    type: select', '    proxies:',
        "      - $QuotedProxyName", 'rules:', '  - MATCH,BOOTSTRAP', ''
    )
    ($BaseLines + $Suffix) -join "`n"
}

function Copy-PrivateProfileInputs {
    foreach ($Path in @($SourceProfilesPath, (Join-Path $ClashDataDirectory 'config.yaml'), (Join-Path $ClashDataDirectory 'verge.yaml'))) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required Clash profile input is missing: $Path" }
        Assert-RegularFile -Path $Path
    }
    New-Item -ItemType Directory -Force -Path $AppProfileDirectory, $BundledProfileDirectory, $BundledRulesetDirectory | Out-Null
    Copy-Item -Force -LiteralPath $SourceProfilesPath -Destination (Join-Path $AppProfileDirectory 'profiles.yaml')
    foreach ($Name in @('config.yaml', 'verge.yaml', 'dns_config.yaml')) {
        $Source = Join-Path $ClashDataDirectory $Name
        if (Test-Path -LiteralPath $Source -PathType Leaf) {
            Assert-RegularFile -Path $Source
            Copy-Item -Force -LiteralPath $Source -Destination (Join-Path $AppProfileDirectory $Name)
        }
    }
    foreach ($File in Get-ChildItem -Force -File -LiteralPath $SourceProfileDirectory) {
        Assert-RegularFile -Path $File.FullName
        if ($File.Name -notmatch '^(?:[RLmrpg][A-Za-z0-9]+\.yaml|s[A-Za-z0-9]+\.js|Merge\.yaml|Script\.js)$') {
            throw 'The Clash profile directory contains an unexpected file name.'
        }
        Copy-Item -Force -LiteralPath $File.FullName -Destination (Join-Path $BundledProfileDirectory $File.Name)
    }
    if (Test-Path -LiteralPath $SourceRulesetDirectory -PathType Container) {
        foreach ($File in Get-ChildItem -Force -File -LiteralPath $SourceRulesetDirectory) {
            Assert-RegularFile -Path $File.FullName
            Copy-Item -Force -LiteralPath $File.FullName -Destination (Join-Path $BundledRulesetDirectory $File.Name)
        }
    }
}

function Copy-TrackedRuntimeFiles {
    $Files = @{
        'agentbox-profile-compiler.js' = 'agentbox-profile-compiler.js'
        'update-agentbox-proxy.sh' = 'update-agentbox-proxy.sh'
        'install-proxy-bundle.sh' = 'install-target.sh'
    }
    foreach ($SourceName in $Files.Keys) {
        $Source = Join-Path $PSScriptRoot $SourceName
        if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Tracked runtime file is missing: $Source" }
        $Target = Join-Path $Destination $Files[$SourceName]
        if ($SourceName.EndsWith('.sh')) {
            $Text = [IO.File]::ReadAllText($Source).Replace("`r`n", "`n").Replace("`r", "`n")
            [IO.File]::WriteAllText($Target, $Text, (New-Object Text.UTF8Encoding($false)))
        }
        else {
            Copy-Item -Force -LiteralPath $Source -Destination $Target
        }
    }
    New-Item -ItemType Directory -Force -Path $BundledVendorDirectory | Out-Null
    foreach ($Name in @('js-yaml.cjs', 'js-yaml.LICENSE')) {
        $Source = Join-Path $PSScriptRoot "vendor\$Name"
        Copy-Item -Force -LiteralPath $Source -Destination (Join-Path $BundledVendorDirectory $Name)
    }
    foreach ($Name in @('mihomo-bootstrap.service', 'mihomo.service', 'agentbox-proxy-update.service', 'agentbox-proxy-update.timer')) {
        $Source = Join-Path $PSScriptRoot "systemd\$Name"
        $Text = [IO.File]::ReadAllText($Source).Replace("`r`n", "`n").Replace("`r", "`n")
        [IO.File]::WriteAllText((Join-Path $Destination $Name), $Text, (New-Object Text.UTF8Encoding($false)))
    }
}

function Write-StartProxyScript {
    $Script = @'
#!/bin/sh
set -eu

if ! pidof mihomo >/dev/null 2>&1; then
    /proxy-bootstrap/mihomo -d /proxy-bootstrap -f /proxy-bootstrap/config.yaml >/var/log/mihomo-bootstrap.log 2>&1 &
    proxy_pid=$!
    sleep 3
    if ! kill -0 "$proxy_pid" 2>/dev/null; then
        cat /var/log/mihomo-bootstrap.log >&2
        return 1 2>/dev/null || exit 1
    fi
fi
export http_proxy=http://127.0.0.1:7897
export https_proxy=http://127.0.0.1:7897
export HTTP_PROXY=http://127.0.0.1:7897
export HTTPS_PROXY=http://127.0.0.1:7897
echo "Bootstrap proxy is running on 127.0.0.1:7897."
'@
    $Script = $Script.TrimStart().Replace("`r`n", "`n").Replace("`r", "`n")
    [IO.File]::WriteAllText($StartProxyPath, $Script, (New-Object Text.UTF8Encoding($false)))
}

function Invoke-ProfileCompiler {
    param([Parameter(Mandatory)][string]$OutputPath)
    $Node = Get-Command node.exe -ErrorAction Stop
    $Arguments = @(
        $BundledCompilerPath, '--bundle', $AppProfileDirectory, '--output', $OutputPath,
        '--port', '7898', '--compare-current', $SourceRuntimePath
    )
    $CompilerOutput = & $Node.Source @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "The private profile compiler could not reproduce the current Clash configuration: $CompilerOutput" }
}

function Assert-PrivateAcl {
    $CurrentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls.exe $Destination /inheritance:r | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Unable to remove inherited ACLs from the private proxy bundle.' }
    & icacls.exe $Destination /grant:r "*$CurrentSid`:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /T /C | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Unable to apply private ACLs to the proxy bundle.' }
}

function Test-PrivateAcl {
    $ExpectedSids = @([Security.Principal.WindowsIdentity]::GetCurrent().User.Value, 'S-1-5-18', 'S-1-5-32-544')
    $Targets = @((Get-Item -LiteralPath $Destination)) + @(Get-ChildItem -Force -Recurse -LiteralPath $Destination)
    foreach ($Target in $Targets) {
        $Acl = Get-Acl -LiteralPath $Target.FullName
        if ($Target.FullName -eq $Destination -and -not $Acl.AreAccessRulesProtected) { throw 'The private bundle still inherits ACLs.' }
        $Rules = @($Acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
        if ($Rules | Where-Object { $_.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow }) {
            throw "The private bundle has a deny ACL: $($Target.FullName)"
        }
        foreach ($Rule in $Rules) {
            if ($Rule.IdentityReference.Value -notin $ExpectedSids) { throw "Unexpected ACL SID: $($Target.FullName)" }
        }
        foreach ($Sid in $ExpectedSids) {
            $FullControlRule = $Rules | Where-Object {
                $_.IdentityReference.Value -eq $Sid -and
                ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl
            }
            if ($null -eq $FullControlRule) { throw "Missing private ACL grant: $($Target.FullName)" }
        }
    }
}

function Test-PrivateBundle {
    Assert-Hash -Path $LinuxMihomoPath -ExpectedHash $MihomoBinarySha256
    Assert-Hash -Path (Join-Path $BundledVendorDirectory 'js-yaml.cjs') -ExpectedHash $JsYamlSha256
    $Required = @(
        $LinuxBootstrapConfigPath, $LinuxProductionConfigPath, $StartProxyPath,
        $PrivateManifestPath, $BundledCompilerPath, $BundledUpdaterPath,
        $BundledInstallerPath, (Join-Path $AppProfileDirectory 'profiles.yaml'),
        (Join-Path $AppProfileDirectory 'config.yaml'), (Join-Path $AppProfileDirectory 'verge.yaml')
    )
    foreach ($Path in $Required) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Private proxy bundle is missing: $Path" }
    }
    $BootstrapText = [IO.File]::ReadAllText($LinuxBootstrapConfigPath)
    foreach ($Forbidden in @('rule-providers:', 'proxy-providers:', 'external-controller:', 'external-controller-pipe:', 'secret:')) {
        if ($BootstrapText -match "(?m)^$([regex]::Escape($Forbidden))") { throw "Forbidden bootstrap section remains: $Forbidden" }
    }
    if ($BootstrapText -notmatch '(?m)^\s*- MATCH,BOOTSTRAP\s*$' -or
        $BootstrapText -notmatch '(?m)^mixed-port:\s*7897\s*$' -or
        $BootstrapText -notmatch '(?m)^allow-lan:\s*false\s*$' -or
        $BootstrapText -notmatch '(?m)^bind-address:\s*[''"]?127\.0\.0\.1[''"]?\s*$') {
        throw 'The bootstrap proxy is not restricted to 127.0.0.1:7897.'
    }
    $ProductionText = [IO.File]::ReadAllText($LinuxProductionConfigPath)
    foreach ($Forbidden in @('external-controller:', 'external-controller-pipe:', 'external-controller-unix:', 'secret:', 'listeners:')) {
        if ($ProductionText -match "(?m)^$([regex]::Escape($Forbidden))") { throw "Forbidden production section remains: $Forbidden" }
    }
    if ($ProductionText -notmatch '(?m)^mixed-port:\s*7898\s*$' -or
        $ProductionText -notmatch '(?m)^allow-lan:\s*false\s*$' -or
        $ProductionText -notmatch '(?m)^bind-address:\s*127\.0\.0\.1\s*$') {
        throw 'The production proxy is not restricted to 127.0.0.1:7898.'
    }
    $SelfTestOutput = & node.exe $BundledCompilerPath --self-test 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Profile compiler self-test failed: $SelfTestOutput" }
    $VerifyConfig = Join-Path $Destination 'production.verify.yaml'
    try {
        Invoke-ProfileCompiler -OutputPath $VerifyConfig
        if ((Get-Sha256 -Path $VerifyConfig) -ne (Get-Sha256 -Path $LinuxProductionConfigPath)) {
            throw 'The production config is not reproducible from the private profile chain.'
        }
    }
    finally {
        if (Test-Path -LiteralPath $VerifyConfig -PathType Leaf) { Remove-Item -Force -LiteralPath $VerifyConfig }
    }
    foreach ($Config in @($LinuxBootstrapConfigPath, $LinuxProductionConfigPath)) {
        $ValidationOutput = & $WindowsMihomoPath -t -d $Destination -f $Config 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Mihomo rejected a generated private config: $ValidationOutput" }
    }
    Test-PrivateAcl
}

if ($VerifyOnly) {
    Test-PrivateBundle
    Write-Host "Verified private dual-proxy bundle: $Destination"
    exit 0
}

foreach ($Path in @($SourceRuntimePath, $WindowsMihomoPath, $SourceProfilesPath)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required source file is missing: $Path" }
}
if (-not (Test-Path -LiteralPath $SourceProfileDirectory -PathType Container)) { throw "Clash profile directory is missing: $SourceProfileDirectory" }

$ConfigLines = Get-Content -LiteralPath $SourceRuntimePath
$PipeLine = $ConfigLines | Where-Object { $_ -match '^external-controller-pipe:\s*' } | Select-Object -First 1
if ($null -eq $PipeLine -or $PipeLine -notmatch '\\\\.\\pipe\\([^\s]+)') { throw 'Unable to determine the local Mihomo named pipe.' }
$PipeName = $Matches[1]
$ProxyData = Get-ActiveMihomoProxyData -ConfigLines $ConfigLines -PipeName $PipeName
$MatchTarget = Get-MatchTarget -ConfigLines $ConfigLines
$ConcreteProxy = Resolve-ConcreteProxy -ProxyData $ProxyData -InitialTarget $MatchTarget

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$LinuxBootstrapConfig = New-LinuxBootstrapConfig -SourceLines $ConfigLines -ConcreteProxyName $ConcreteProxy.Name
[IO.File]::WriteAllText($LinuxBootstrapConfigPath, $LinuxBootstrapConfig, (New-Object Text.UTF8Encoding($false)))
Copy-PrivateProfileInputs
Copy-TrackedRuntimeFiles
Write-StartProxyScript

foreach ($Name in @('Country.mmdb', 'geoip.dat', 'geosite.dat', 'cache.db')) {
    $SourcePath = Join-Path $ClashDataDirectory $Name
    if (Test-Path -LiteralPath $SourcePath -PathType Leaf) {
        Assert-RegularFile -Path $SourcePath
        Copy-Item -Force -LiteralPath $SourcePath -Destination (Join-Path $Destination $Name)
    }
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ArchivePath = Join-Path $Destination "mihomo-linux-amd64-v1-v$MihomoVersion.gz"
$DownloadPath = "$ArchivePath.download"
Invoke-WebRequest -UseBasicParsing -Uri $MihomoArchiveUrl -OutFile $DownloadPath
Assert-Hash -Path $DownloadPath -ExpectedHash $MihomoArchiveSha256
Move-Item -Force -LiteralPath $DownloadPath -Destination $ArchivePath
$InputStream = [IO.File]::OpenRead($ArchivePath)
try {
    $GzipStream = [IO.Compression.GZipStream]::new($InputStream, [IO.Compression.CompressionMode]::Decompress)
    try {
        $OutputStream = [IO.File]::Create($LinuxMihomoPath)
        try { $GzipStream.CopyTo($OutputStream) } finally { $OutputStream.Dispose() }
    }
    finally { $GzipStream.Dispose() }
}
finally { $InputStream.Dispose() }
Assert-Hash -Path $LinuxMihomoPath -ExpectedHash $MihomoBinarySha256
Remove-Item -LiteralPath $ArchivePath

Invoke-ProfileCompiler -OutputPath $LinuxProductionConfigPath
$PrivateManifest = @"
Purpose: private dual-proxy and Clash Verge profile bundle for agentbox
PreparedAt: $([DateTimeOffset]::Now.ToString('o'))
MihomoVersion: $MihomoVersion
MihomoLinuxBinarySha256: $MihomoBinarySha256
ClashVergeCompatibilityVersion: $ClashVergeVersion
ClashVergeSourceCommit: $ClashVergeCommit
JsYamlVersion: $JsYamlVersion
JsYamlDistSha256: $JsYamlSha256
ResolvedProxyType: $($ConcreteProxy.Type)
ResolvedProxyDepth: $($ConcreteProxy.Depth)
BootstrapConfigSha256: $(Get-Sha256 -Path $LinuxBootstrapConfigPath)
ProductionConfigSha256: $(Get-Sha256 -Path $LinuxProductionConfigPath)
ContainsSubscriptionUrlAndNodeCredentials: true
CommitToGit: NEVER
"@
[IO.File]::WriteAllText($PrivateManifestPath, $PrivateManifest, (New-Object Text.UTF8Encoding($false)))
Assert-PrivateAcl
Test-PrivateBundle

Write-Host "Prepared and verified private dual-proxy bundle: $Destination"
Write-Host "Bootstrap route type: $($ConcreteProxy.Type); production rules reproduced from Clash Verge Rev $ClashVergeVersion."
Write-Host 'This directory contains subscription and node credentials; never commit, paste, or share it.'
