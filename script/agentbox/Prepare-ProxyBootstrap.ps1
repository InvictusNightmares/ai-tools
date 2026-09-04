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

if ([string]::IsNullOrWhiteSpace($Destination)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $Destination = Join-Path $RepoRoot ".agentbox-staging\$($InstallerCommit.Substring(0, 12))\proxy-bootstrap"
}

$Destination = [IO.Path]::GetFullPath($Destination)
$SourceConfigPath = Join-Path $ClashDataDirectory 'clash-verge.yaml'
$LinuxConfigPath = Join-Path $Destination 'config.yaml'
$LinuxMihomoPath = Join-Path $Destination 'mihomo'
$MihomoServicePath = Join-Path $Destination 'mihomo.service'
$StartProxyPath = Join-Path $Destination 'start-proxy.sh'
$PrivateManifestPath = Join-Path $Destination 'PRIVATE-MANIFEST.txt'

function Get-Sha256 {
    param([Parameter(Mandatory)][string]$Path)
    (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToUpperInvariant()
}

function Assert-Hash {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ExpectedHash
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file is missing: $Path"
    }
    $Actual = Get-Sha256 -Path $Path
    if ($Actual -ne $ExpectedHash.ToUpperInvariant()) {
        throw "SHA-256 mismatch for $Path`nExpected: $ExpectedHash`nActual:   $Actual"
    }
}

function ConvertFrom-HttpChunkedBody {
    param([Parameter(Mandatory)][string]$Body)
    $Decoded = New-Object Text.StringBuilder
    $Position = 0
    while ($true) {
        $LineEnd = $Body.IndexOf("`r`n", $Position)
        if ($LineEnd -lt 0) {
            throw 'Invalid chunk header from the local Mihomo API.'
        }
        $HexSize = $Body.Substring($Position, $LineEnd - $Position).Split(';')[0]
        $Size = [Convert]::ToInt32($HexSize, 16)
        if ($Size -eq 0) {
            break
        }
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
        if (-not [string]::IsNullOrEmpty($Secret)) {
            $Writer.WriteLine("Authorization: Bearer $Secret")
        }
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
    if ($Separator -lt 0) {
        throw 'Invalid HTTP response from the local Mihomo API.'
    }
    $Headers = $Response.Substring(0, $Separator)
    if ($Headers -notmatch '^HTTP/1\.1 200') {
        throw "Local Mihomo API returned a non-success response: $($Headers.Split("`r`n")[0])"
    }
    $Body = $Response.Substring($Separator + 4)
    if ($Headers -match '(?im)^Transfer-Encoding:\s*chunked') {
        $Body = ConvertFrom-HttpChunkedBody -Body $Body
    }
    $Body | ConvertFrom-Json
}

function Get-MatchTarget {
    param([Parameter(Mandatory)][AllowEmptyString()][string[]]$ConfigLines)
    $InRules = $false
    $Target = $null
    foreach ($Line in $ConfigLines) {
        if ($Line -match '^rules:\s*$') {
            $InRules = $true
            continue
        }
        if ($InRules -and $Line -match '^[A-Za-z0-9_-]+:') {
            $InRules = $false
        }
        if ($InRules -and $Line -match '^\s*-\s*["'']?MATCH\s*,\s*([^,#"'']+)') {
            $Target = $Matches[1].Trim()
        }
    }
    if ([string]::IsNullOrWhiteSpace($Target)) {
        throw 'The active Clash configuration has no MATCH rule to resolve.'
    }
    $Target
}

function Resolve-ConcreteProxy {
    param(
        [Parameter(Mandatory)]$ProxyData,
        [Parameter(Mandatory)][string]$InitialTarget
    )
    $Current = $InitialTarget
    for ($Depth = 0; $Depth -lt 10; $Depth++) {
        $Property = $ProxyData.proxies.PSObject.Properties | Where-Object { $_.Name -eq $Current } | Select-Object -First 1
        if ($null -eq $Property) {
            throw 'The active MATCH target does not exist in the local Mihomo API.'
        }
        $Entry = $Property.Value
        if ($Entry.type -notin @('Selector', 'URLTest', 'Fallback', 'LoadBalance')) {
            if ($Entry.type -in @('Direct', 'Reject', 'RejectDrop', 'Pass')) {
                throw "The active route resolves to $($Entry.type), not to an external proxy."
            }
            return [pscustomobject]@{ Name = $Current; Type = [string]$Entry.type; Depth = $Depth }
        }
        if ([string]::IsNullOrWhiteSpace([string]$Entry.now)) {
            throw 'A proxy group has no active selection.'
        }
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
        if ($Line -match '^([A-Za-z0-9_-]+):') {
            $Skip = $SectionNames -contains $Matches[1]
        }
        if (-not $Skip) {
            $Result.Add($Line)
        }
    }
    $Result.ToArray()
}

function New-LinuxBootstrapConfig {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string[]]$SourceLines,
        [Parameter(Mandatory)][string]$ConcreteProxyName
    )
    $SectionsToRemove = @(
        'port',
        'socks-port',
        'mixed-port',
        'redir-port',
        'tproxy-port',
        'allow-lan',
        'bind-address',
        'authentication',
        'skip-auth-prefixes',
        'mode',
        'tun',
        'proxy-groups',
        'rule-providers',
        'rules',
        'external-controller',
        'external-controller-cors',
        'external-controller-pipe',
        'secret'
    )
    $BaseLines = Remove-TopLevelYamlSections -Lines $SourceLines -SectionNames $SectionsToRemove
    $QuotedProxyName = "'" + $ConcreteProxyName.Replace("'", "''") + "'"
    $Suffix = @(
        '',
        'mixed-port: 7897',
        'allow-lan: false',
        "bind-address: '127.0.0.1'",
        'mode: rule',
        'tun:',
        '  enable: false',
        'proxy-groups:',
        '  - name: BOOTSTRAP',
        '    type: select',
        '    proxies:',
        "      - $QuotedProxyName",
        'rules:',
        '  - MATCH,BOOTSTRAP',
        ''
    )
    ($BaseLines + $Suffix) -join "`n"
}

function Write-StaticBootstrapFiles {
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $Service = @'
[Unit]
Description=Agentbox bootstrap outbound proxy
After=network-online.target
Wants=network-online.target
Before=tailscaled.service

[Service]
Type=simple
ExecStart=/usr/local/bin/mihomo -d /etc/mihomo -f /etc/mihomo/config.yaml
Restart=always
RestartSec=3
NoNewPrivileges=true
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
'@
    [IO.File]::WriteAllText($MihomoServicePath, $Service.TrimStart(), $Utf8NoBom)

    $StartScript = @'
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

echo "Mihomo bootstrap proxy is running on 127.0.0.1:7897."
echo "Proxy variables are active in this shell only when this script was sourced."
'@
    [IO.File]::WriteAllText($StartProxyPath, $StartScript.TrimStart(), $Utf8NoBom)
}

function Assert-PrivateAcl {
    $CurrentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls.exe $Destination /inheritance:r | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Unable to remove inherited ACLs from the private proxy bundle.' }
    & icacls.exe $Destination /grant:r "*$CurrentSid`:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /T /C | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Unable to apply private ACLs to the proxy bundle.' }
}

function Test-PrivateAcl {
    $ExpectedSids = @(
        [Security.Principal.WindowsIdentity]::GetCurrent().User.Value,
        'S-1-5-18',
        'S-1-5-32-544'
    )
    $Targets = @((Get-Item -LiteralPath $Destination)) + @(Get-ChildItem -Force -Recurse -LiteralPath $Destination)
    foreach ($Target in $Targets) {
        $Acl = Get-Acl -LiteralPath $Target.FullName
        if ($Target.FullName -eq $Destination -and -not $Acl.AreAccessRulesProtected) {
            throw 'The private proxy bundle still inherits ACLs from its parent directory.'
        }
        $Rules = @($Acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
        if ($Rules | Where-Object { $_.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow }) {
            throw "The private proxy bundle has a deny ACL entry: $($Target.FullName)"
        }
        foreach ($Rule in $Rules) {
            if ($Rule.IdentityReference.Value -notin $ExpectedSids) {
                throw "The private proxy bundle grants access to an unexpected SID: $($Target.FullName)"
            }
        }
        foreach ($Sid in $ExpectedSids) {
            $FullControlRule = $Rules | Where-Object {
                $_.IdentityReference.Value -eq $Sid -and
                ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq
                    [Security.AccessControl.FileSystemRights]::FullControl
            }
            if ($null -eq $FullControlRule) {
                throw "The private proxy bundle is missing a required full-control ACL: $($Target.FullName)"
            }
        }
    }
}

function Test-PrivateBundle {
    Assert-Hash -Path $LinuxMihomoPath -ExpectedHash $MihomoBinarySha256
    foreach ($Path in @($LinuxConfigPath, $MihomoServicePath, $StartProxyPath, $PrivateManifestPath)) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            throw "Private proxy bootstrap file is missing: $Path"
        }
    }
    $ConfigText = [IO.File]::ReadAllText($LinuxConfigPath)
    foreach ($Forbidden in @('rule-providers:', 'external-controller:', 'external-controller-pipe:', 'secret:')) {
        if ($ConfigText -match "(?m)^$([regex]::Escape($Forbidden))") {
            throw "Forbidden bootstrap configuration section remains: $Forbidden"
        }
    }
    if ($ConfigText -notmatch '(?m)^\s*- MATCH,BOOTSTRAP\s*$') {
        throw 'The bootstrap config does not force traffic through BOOTSTRAP.'
    }
    if ($ConfigText -notmatch '(?m)^mixed-port:\s*7897\s*$' -or
        $ConfigText -notmatch '(?m)^allow-lan:\s*false\s*$' -or
        $ConfigText -notmatch '(?m)^bind-address:\s*[''"]?127\.0\.0\.1[''"]?\s*$') {
        throw 'The bootstrap proxy is not restricted to 127.0.0.1:7897.'
    }
    $ValidationOutput = & $WindowsMihomoPath -t -d $Destination -f $LinuxConfigPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Mihomo rejected the generated private config: $ValidationOutput"
    }
    Test-PrivateAcl
}

if ($VerifyOnly) {
    Test-PrivateBundle
    Write-Host "Verified private proxy bootstrap bundle: $Destination"
    exit 0
}

if (-not (Test-Path -LiteralPath $SourceConfigPath -PathType Leaf)) {
    throw "Active Clash configuration is missing: $SourceConfigPath"
}
if (-not (Test-Path -LiteralPath $WindowsMihomoPath -PathType Leaf)) {
    throw "Windows Mihomo core is missing: $WindowsMihomoPath"
}

$ConfigLines = Get-Content -LiteralPath $SourceConfigPath
$PipeLine = $ConfigLines | Where-Object { $_ -match '^external-controller-pipe:\s*' } | Select-Object -First 1
if ($null -eq $PipeLine -or $PipeLine -notmatch '\\\\.\\pipe\\([^\s]+)') {
    throw 'Unable to determine the local Mihomo named pipe.'
}
$PipeName = $Matches[1]
$ProxyData = Get-ActiveMihomoProxyData -ConfigLines $ConfigLines -PipeName $PipeName
$MatchTarget = Get-MatchTarget -ConfigLines $ConfigLines
$ConcreteProxy = Resolve-ConcreteProxy -ProxyData $ProxyData -InitialTarget $MatchTarget

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$LinuxConfig = New-LinuxBootstrapConfig -SourceLines $ConfigLines -ConcreteProxyName $ConcreteProxy.Name
[IO.File]::WriteAllText($LinuxConfigPath, $LinuxConfig, (New-Object System.Text.UTF8Encoding($false)))

foreach ($Name in @('Country.mmdb', 'geoip.dat', 'geosite.dat')) {
    $SourcePath = Join-Path $ClashDataDirectory $Name
    if (Test-Path -LiteralPath $SourcePath -PathType Leaf) {
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

Write-StaticBootstrapFiles
$PrivateManifest = @"
Purpose: private outbound proxy bootstrap for agentbox
PreparedAt: $([DateTimeOffset]::Now.ToString('o'))
MihomoVersion: $MihomoVersion
MihomoLinuxBinarySha256: $MihomoBinarySha256
ResolvedProxyType: $($ConcreteProxy.Type)
ResolvedProxyDepth: $($ConcreteProxy.Depth)
GeneratedConfigSha256: $(Get-Sha256 -Path $LinuxConfigPath)
ContainsNodeCredentials: true
CommitToGit: NEVER
"@
[IO.File]::WriteAllText($PrivateManifestPath, $PrivateManifest, (New-Object System.Text.UTF8Encoding($false)))

Assert-PrivateAcl
Test-PrivateBundle

Write-Host "Prepared private proxy bootstrap bundle: $Destination"
Write-Host "Resolved a working $($ConcreteProxy.Type) route without printing its name or credentials."
Write-Host 'This directory contains node credentials and must never be committed, copied to chat, or shared.'
