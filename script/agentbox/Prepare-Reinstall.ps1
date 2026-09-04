[CmdletBinding()]
param(
    [string]$Destination,
    [switch]$VerifyOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$InstallerCommit = '6b3a341b4bb5c0b93f25cc0a0518e9bd5088504b'
$ShortCommit = $InstallerCommit.Substring(0, 12)
$Expected = @{
    UpstreamBat              = 'A7BD252241ADEE998FCF9F7C8FCE0EA61C34AAE32A347B278125B543C431984E'
    UpstreamSh               = 'FE8CF9D8FB800AA74480BBD2223F268259E2A6EADFEAB68C50A39B57F027139F'
    UpstreamDebianCfg        = '53DA483158C7D526987BAFE6BF450FFC93A32E5B7B0D16DAA6126F21731A4161'
    PatchedBat               = '85D1783C9EE86A224D4E942E64052EE4CAC0613F455F1829D16CB78B058EF0A4'
    PatchedSh                = 'DF8385EA660B4B3B3720542CDD8D7DBAFF9B00586EF5C05C83D2C1D65949D5834'
    PatchedDebianCfg         = 'C72584170B2A3630D02AAFF0F3E6DBFF4C827C60259E05DAA9628E1660578BE7'
    CygwinSetup              = '2C9F2FB56E1FB687B5D9680AFA8F8B06E6214F0E483096AF0EAE1946431226C5'
    CygwinSignerThumbprint   = '7C470FD5026C30AA594D5D3782A060DDFFA0D1FD'
}

if ([string]::IsNullOrWhiteSpace($Destination)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $Destination = Join-Path $RepoRoot ".agentbox-staging\$ShortCommit"
}

$Destination = [IO.Path]::GetFullPath($Destination)
$AuditDirectory = Join-Path $Destination 'audit'
$UpstreamBatPath = Join-Path $AuditDirectory 'reinstall.upstream.bat'
$UpstreamShPath = Join-Path $AuditDirectory 'reinstall.upstream.sh'
$UpstreamDebianCfgPath = Join-Path $AuditDirectory 'debian.upstream.cfg'
$PatchedBatPath = Join-Path $Destination 'reinstall.bat'
$PatchedShPath = Join-Path $Destination 'reinstall.sh'
$PatchedDebianCfgPath = Join-Path $Destination 'debian.cfg'
$CygwinSetupPath = Join-Path $Destination 'setup-x86_64.exe'
$ManifestPath = Join-Path $Destination 'PINNED-MANIFEST.txt'

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
    $ActualHash = Get-Sha256 -Path $Path
    if ($ActualHash -ne $ExpectedHash.ToUpperInvariant()) {
        throw "SHA-256 mismatch for $Path`nExpected: $ExpectedHash`nActual:   $ActualHash"
    }
}

function Get-PinnedFile {
    param(
        [Parameter(Mandatory)][string]$Uri,
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ExpectedHash
    )
    $DownloadPath = "$Path.download"
    Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $DownloadPath
    Assert-Hash -Path $DownloadPath -ExpectedHash $ExpectedHash
    Move-Item -Force -LiteralPath $DownloadPath -Destination $Path
}

function Assert-CygwinSignature {
    param([Parameter(Mandatory)][string]$Path)
    $Signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($Signature.Status -ne 'Valid') {
        throw "Cygwin Authenticode signature is not valid: $($Signature.StatusMessage)"
    }
    if ($null -eq $Signature.SignerCertificate) {
        throw 'Cygwin Authenticode signature has no signer certificate.'
    }
    if ($Signature.SignerCertificate.Thumbprint.ToUpperInvariant() -ne $Expected.CygwinSignerThumbprint) {
        throw "Unexpected Cygwin signer thumbprint: $($Signature.SignerCertificate.Thumbprint)"
    }
}

function Add-ProxyHooksToReinstallSh {
    param([Parameter(Mandatory)][string]$Content)

    $OldCommandLine = '        nextos_cmdline+=" url=$nextos_ks"'
    $NewCommandLine = @(
        '        if [ -d "$(dirname "$THIS_SCRIPT")/proxy-bootstrap" ]; then',
        '            nextos_cmdline+=" file=/debian.cfg mirror/http/proxy=http://127.0.0.1:7897"',
        '        else',
        '            nextos_cmdline+=" url=$nextos_ks"',
        '        fi'
    ) -join "`n"
    if (-not $Content.Contains($OldCommandLine)) {
        throw 'Unable to find the Debian kernel-command-line patch anchor.'
    }
    $Content = $Content.Replace($OldCommandLine, $NewCommandLine)

    $OldNetworkHook = '        : get_ip_conf_cmd'
    $NewNetworkHook = @(
        '        : get_ip_conf_cmd',
        '',
        '        if [ -x /proxy-bootstrap/mihomo ]; then',
        '            chmod 700 /proxy-bootstrap/mihomo',
        '            /proxy-bootstrap/mihomo -d /proxy-bootstrap -f /proxy-bootstrap/config.yaml >/var/log/mihomo-bootstrap.log 2>&1 &',
        '            proxy_pid=$!',
        '            sleep 3',
        '            if ! kill -0 "$proxy_pid" 2>/dev/null; then',
        '                cat /var/log/mihomo-bootstrap.log >&2',
        '                exit 1',
        '            fi',
        '            db_set mirror/http/proxy http://127.0.0.1:7897',
        '        fi'
    ) -join "`n"
    if (-not $Content.Contains($OldNetworkHook)) {
        throw 'Unable to find the Debian network hook patch anchor.'
    }
    $Content = $Content.Replace($OldNetworkHook, $NewNetworkHook)

    $OldBundleHook = @(
        '    if is_distro_like_debian $nextos_distro; then',
        '        mod_initrd_debian_kali'
    ) -join "`n"
    $NewBundleHook = @(
        '    bootstrap_proxy_dir=$(dirname "$THIS_SCRIPT")/proxy-bootstrap',
        '    if [ -d "$bootstrap_proxy_dir" ]; then',
        '        for file in mihomo config.yaml production.yaml start-proxy.sh install-target.sh; do',
        '            [ -f "$bootstrap_proxy_dir/$file" ] || error_and_exit "Missing proxy bootstrap file: $file"',
        '        done',
        '        cp -R --no-preserve=mode,ownership,timestamps "$bootstrap_proxy_dir" "$initrd_dir/proxy-bootstrap"',
        '        chmod -R go-rwx "$initrd_dir/proxy-bootstrap"',
        '        chmod 700 "$initrd_dir/proxy-bootstrap/mihomo" "$initrd_dir/proxy-bootstrap/start-proxy.sh" "$initrd_dir/proxy-bootstrap/install-target.sh"',
        '        chmod 600 "$initrd_dir/proxy-bootstrap/config.yaml" "$initrd_dir/proxy-bootstrap/production.yaml"',
        '        if is_distro_like_debian $nextos_distro; then',
        '            debian_cfg=$(dirname "$THIS_SCRIPT")/debian.cfg',
        '            [ -f "$debian_cfg" ] || error_and_exit "Missing pinned proxy-aware debian.cfg"',
        '            cp "$debian_cfg" "$initrd_dir/debian.cfg"',
        '        fi',
        '    fi',
        '',
        '    if is_distro_like_debian $nextos_distro; then',
        '        mod_initrd_debian_kali'
    ) -join "`n"
    if (-not $Content.Contains($OldBundleHook)) {
        throw 'Unable to find the initrd bundle patch anchor.'
    }
    $Content.Replace($OldBundleHook, $NewBundleHook)
}

function Add-ProxyHooksToDebianCfg {
    param([Parameter(Mandatory)][string]$Content)

    if (-not $Content.Contains('d-i time/zone string Asia/Shanghai')) {
        throw 'Unable to find the Debian timezone patch anchor.'
    }
    if (-not $Content.Contains('d-i debian-installer/locale string en_US.UTF-8')) {
        throw 'The pinned Debian preseed does not select the expected English locale.'
    }

    $Content = $Content.Replace(
        'd-i mirror/country string manual',
        "d-i mirror/country string manual`nd-i mirror/http/proxy string http://127.0.0.1:7897"
    )
    $Content = $Content.Replace(
        'd-i time/zone string Asia/Shanghai',
        'd-i time/zone string America/Los_Angeles'
    )
    $Content = $Content.Replace('apbs04.zh-cn.html', 'apbs04.en.html')
    $Content = [regex]::Replace(
        $Content,
        '(?m)^[^\r\n]*#[^\r\n]*[^\x00-\x7F][^\r\n]*(?:\r?\n|$)',
        ''
    )

    $OldLateCommand = @(
        '    in-target systemctl enable ssh; \',
        '',
        '    if [ "$username" = root ]; then \'
    ) -join "`n"
    $NewLateCommand = @(
        '    in-target systemctl enable ssh; \',
        '',
        '    /bin/sh /proxy-bootstrap/install-target.sh /target; \',
        '',
        '    if [ "$username" = root ]; then \'
    ) -join "`n"
    if (-not $Content.Contains($OldLateCommand)) {
        throw 'Unable to find the Debian late-command patch anchor.'
    }
    $Content.Replace($OldLateCommand, $NewLateCommand)
}

function Write-HardenedInstallerFiles {
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

    $Bat = [IO.File]::ReadAllText($UpstreamBatPath)
    $Bat = $Bat.Replace('https://raw.githubusercontent.com/bin456789/reinstall/main', "https://raw.githubusercontent.com/bin456789/reinstall/$InstallerCommit").Replace('https://cnb.cool/bin456789/reinstall/-/git/raw/main', "https://cnb.cool/bin456789/reinstall/-/git/raw/$InstallerCommit").Replace('http://www.qualcomm.cn', 'https://www.qualcomm.cn').Replace('http://mirror.nju.edu.cn', 'https://mirror.nju.edu.cn').Replace('http://mirrors.kernel.org', 'https://mirrors.kernel.org').Replace('http://www.cygwin.com', 'https://www.cygwin.com').Replace('%SystemDrive%\cygwin\bin\curl -L --insecure', '%SystemDrive%\cygwin\bin\curl -L --fail --show-error')
    [IO.File]::WriteAllText($PatchedBatPath, $Bat, $Utf8NoBom)

    $Sh = [IO.File]::ReadAllText($UpstreamShPath)
    $Sh = $Sh.Replace('https://raw.githubusercontent.com/bin456789/reinstall/main', "https://raw.githubusercontent.com/bin456789/reinstall/$InstallerCommit").Replace('https://cnb.cool/bin456789/reinstall/-/git/raw/main', "https://cnb.cool/bin456789/reinstall/-/git/raw/$InstallerCommit").Replace('command curl --insecure --connect-timeout 10', 'command curl --connect-timeout 10').Replace('http://www.qualcomm.cn', 'https://www.qualcomm.cn').Replace('http://mirror.nju.edu.cn', 'https://mirror.nju.edu.cn').Replace('http://dl-cdn.alpinelinux.org', 'https://dl-cdn.alpinelinux.org').Replace('http://$mirror', 'https://$mirror').Replace('http://$host/debian', 'https://$host/debian')
    $Sh = Add-ProxyHooksToReinstallSh -Content $Sh
    [IO.File]::WriteAllText($PatchedShPath, $Sh, $Utf8NoBom)

    $DebianCfg = Add-ProxyHooksToDebianCfg -Content ([IO.File]::ReadAllText($UpstreamDebianCfgPath))
    [IO.File]::WriteAllText($PatchedDebianCfgPath, $DebianCfg, $Utf8NoBom)
}

function Test-StagingFiles {
    Assert-Hash -Path $PatchedBatPath -ExpectedHash $Expected.PatchedBat
    Assert-Hash -Path $PatchedShPath -ExpectedHash $Expected.PatchedSh
    Assert-Hash -Path $PatchedDebianCfgPath -ExpectedHash $Expected.PatchedDebianCfg
    Assert-Hash -Path $CygwinSetupPath -ExpectedHash $Expected.CygwinSetup
    Assert-CygwinSignature -Path $CygwinSetupPath

    $BatContent = [IO.File]::ReadAllText($PatchedBatPath)
    $ShContent = [IO.File]::ReadAllText($PatchedShPath)
    $DebianCfgContent = [IO.File]::ReadAllText($PatchedDebianCfgPath)
    if ($BatContent.Contains('bin456789/reinstall/main') -or $ShContent.Contains('bin456789/reinstall/main')) {
        throw 'An unpinned reinstall/main reference remains in a staged installer file.'
    }
    if ($BatContent -match '(?m)^\s*[^r].*curl .*--insecure' -or $ShContent -match '(?m)^\s*[^#].*curl .*--insecure') {
        throw 'An executable curl --insecure invocation remains in a staged installer file.'
    }
    if ($DebianCfgContent -notmatch '(?m)^d-i debian-installer/locale string en_US\.UTF-8$' -or
        $DebianCfgContent -notmatch '(?m)^d-i keyboard-configuration/xkb-keymap select us$' -or
        $DebianCfgContent -notmatch '(?m)^d-i time/zone string America/Los_Angeles$') {
        throw 'The staged Debian preseed is not pinned to English, a US keyboard, and America/Los_Angeles.'
    }
    if ($DebianCfgContent -match 'Asia/Shanghai|(?i)zh[-_](?:cn|hans|hant)|[^\x00-\x7F]') {
        throw 'Chinese locale, timezone, documentation, or non-ASCII text remains in the staged Debian preseed.'
    }
}

if ($VerifyOnly) {
    Test-StagingFiles
    Write-Host "Verified pinned installer staging: $Destination"
    exit 0
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
New-Item -ItemType Directory -Force -Path $Destination, $AuditDirectory | Out-Null
$GitHubBase = "https://raw.githubusercontent.com/bin456789/reinstall/$InstallerCommit"
Get-PinnedFile -Uri "$GitHubBase/reinstall.bat" -Path $UpstreamBatPath -ExpectedHash $Expected.UpstreamBat
Get-PinnedFile -Uri "$GitHubBase/reinstall.sh" -Path $UpstreamShPath -ExpectedHash $Expected.UpstreamSh
Get-PinnedFile -Uri "$GitHubBase/debian.cfg" -Path $UpstreamDebianCfgPath -ExpectedHash $Expected.UpstreamDebianCfg
Get-PinnedFile -Uri 'https://www.cygwin.com/setup-x86_64.exe' -Path $CygwinSetupPath -ExpectedHash $Expected.CygwinSetup
Assert-CygwinSignature -Path $CygwinSetupPath

Write-HardenedInstallerFiles
Test-StagingFiles

$Manifest = @"
Purpose: agentbox Debian 13 proxy-aware reinstall staging
PreparedAt: $([DateTimeOffset]::Now.ToString('o'))
InstallerCommit: $InstallerCommit
UpstreamReinstallBatSha256: $($Expected.UpstreamBat)
UpstreamReinstallShSha256: $($Expected.UpstreamSh)
UpstreamDebianCfgSha256: $($Expected.UpstreamDebianCfg)
PatchedReinstallBatSha256: $($Expected.PatchedBat)
PatchedReinstallShSha256: $($Expected.PatchedSh)
PatchedDebianCfgSha256: $($Expected.PatchedDebianCfg)
CygwinSetupSha256: $($Expected.CygwinSetup)
CygwinSignerThumbprint: $($Expected.CygwinSignerThumbprint)
ContainsSecrets: false
DoesNotExecuteInstaller: true
"@
[IO.File]::WriteAllText($ManifestPath, $Manifest, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "Prepared and verified pinned installer staging: $Destination"
Write-Host 'No boot configuration, partition, firewall, Defender, or operating-system setting was changed.'
