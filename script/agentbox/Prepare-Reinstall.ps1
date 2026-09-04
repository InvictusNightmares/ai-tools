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
    PatchedSh                = 'E21CB9F52DCAE7FE74E57947859F380F6AC67034F0FB4DEB32A8E3DFC94729E6'
    PatchedDebianCfg         = '63DBD57708CE9AFDC2815292156C2C81359CC6CCBE875A884241B21381ED01EA'
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
    $NewCommandLine = @'
        if [ -d "$(dirname "$THIS_SCRIPT")/proxy-bootstrap" ]; then
            nextos_cmdline+=" file=/debian.cfg mirror/http/proxy=http://127.0.0.1:7897"
        else
            nextos_cmdline+=" url=$nextos_ks"
        fi
'@.TrimEnd("`r", "`n")
    if (-not $Content.Contains($OldCommandLine)) {
        throw 'Unable to find the Debian kernel-command-line patch anchor.'
    }
    $Content = $Content.Replace($OldCommandLine, $NewCommandLine)

    $OldNetworkHook = @'
        : get_ip_conf_cmd

        # 运行 trans.sh，保存配置
'@.TrimEnd("`r", "`n")
    $NewNetworkHook = @'
        : get_ip_conf_cmd

        if [ -x /proxy-bootstrap/mihomo ]; then
            chmod 700 /proxy-bootstrap/mihomo
            /proxy-bootstrap/mihomo -d /proxy-bootstrap -f /proxy-bootstrap/config.yaml >/var/log/mihomo-bootstrap.log 2>&1 &
            proxy_pid=$!
            sleep 3
            if ! kill -0 "$proxy_pid" 2>/dev/null; then
                cat /var/log/mihomo-bootstrap.log >&2
                exit 1
            fi
            db_set mirror/http/proxy http://127.0.0.1:7897
        fi

        # 运行 trans.sh，保存配置
'@.TrimEnd("`r", "`n")
    if (-not $Content.Contains($OldNetworkHook)) {
        throw 'Unable to find the Debian network hook patch anchor.'
    }
    $Content = $Content.Replace($OldNetworkHook, $NewNetworkHook)

    $OldBundleHook = @(
        '    if is_distro_like_debian $nextos_distro; then'
        '        mod_initrd_debian_kali'
    ) -join "`n"
    $NewBundleHook = @(
        '    bootstrap_proxy_dir=$(dirname "$THIS_SCRIPT")/proxy-bootstrap'
        '    if [ -d "$bootstrap_proxy_dir" ]; then'
        '        for file in mihomo config.yaml mihomo.service start-proxy.sh; do'
        '            [ -f "$bootstrap_proxy_dir/$file" ] || error_and_exit "Missing proxy bootstrap file: $file"'
        '        done'
        '        cp -a "$bootstrap_proxy_dir" "$initrd_dir/proxy-bootstrap"'
        '        chmod 700 "$initrd_dir/proxy-bootstrap/mihomo" "$initrd_dir/proxy-bootstrap/start-proxy.sh"'
        '        chmod 600 "$initrd_dir/proxy-bootstrap/config.yaml"'
        '        if is_distro_like_debian $nextos_distro; then'
        '            debian_cfg=$(dirname "$THIS_SCRIPT")/debian.cfg'
        '            [ -f "$debian_cfg" ] || error_and_exit "Missing pinned proxy-aware debian.cfg"'
        '            cp "$debian_cfg" "$initrd_dir/debian.cfg"'
        '        fi'
        '    fi'
        ''
        '    if is_distro_like_debian $nextos_distro; then'
        '        mod_initrd_debian_kali'
    ) -join "`n"
    if (-not $Content.Contains($OldBundleHook)) {
        throw 'Unable to find the initrd bundle patch anchor.'
    }
    $Content.Replace($OldBundleHook, $NewBundleHook)
}

function Add-ProxyHooksToDebianCfg {
    param([Parameter(Mandatory)][string]$Content)

    $Content = $Content.Replace(
        'd-i mirror/country string manual',
        "d-i mirror/country string manual`nd-i mirror/http/proxy string http://127.0.0.1:7897"
    )

    $OldLateCommand = @'
    in-target systemctl enable ssh; \

    if [ "$username" = root ]; then \
'@.TrimEnd("`r", "`n")
    $NewLateCommand = @'
    in-target systemctl enable ssh; \

    mkdir -p /target/usr/local/bin /target/etc/mihomo /target/etc/systemd/system /target/etc/systemd/system/tailscaled.service.d /target/etc/profile.d; \
    cp /proxy-bootstrap/mihomo /target/usr/local/bin/mihomo; \
    cp /proxy-bootstrap/config.yaml /target/etc/mihomo/config.yaml; \
    cp /proxy-bootstrap/mihomo.service /target/etc/systemd/system/mihomo.service; \
    for file in Country.mmdb geoip.dat geosite.dat cache.db; do if [ -f "/proxy-bootstrap/$file" ]; then cp "/proxy-bootstrap/$file" /target/etc/mihomo/; fi; done; \
    chmod 0755 /target/usr/local/bin/mihomo; \
    chmod 0700 /target/etc/mihomo; \
    chmod 0600 /target/etc/mihomo/config.yaml; \
    printf '%s\n' 'Acquire::http::Proxy "http://127.0.0.1:7897/";' 'Acquire::https::Proxy "http://127.0.0.1:7897/";' >/target/etc/apt/apt.conf.d/80agentbox-proxy; \
    printf '%s\n' 'export http_proxy=http://127.0.0.1:7897' 'export https_proxy=http://127.0.0.1:7897' 'export HTTP_PROXY=http://127.0.0.1:7897' 'export HTTPS_PROXY=http://127.0.0.1:7897' >/target/etc/profile.d/agentbox-proxy.sh; \
    printf '%s\n' '[Unit]' 'Wants=mihomo.service' 'After=mihomo.service' '[Service]' 'Environment=HTTP_PROXY=http://127.0.0.1:7897' 'Environment=HTTPS_PROXY=http://127.0.0.1:7897' >/target/etc/systemd/system/tailscaled.service.d/proxy.conf; \
    in-target systemctl enable mihomo; \

    if [ "$username" = root ]; then \
'@.TrimEnd("`r", "`n")
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
    if ($BatContent.Contains('bin456789/reinstall/main') -or $ShContent.Contains('bin456789/reinstall/main')) {
        throw 'An unpinned reinstall/main reference remains in a staged installer file.'
    }
    if ($BatContent -match '(?m)^\s*[^r].*curl .*--insecure' -or $ShContent -match '(?m)^\s*[^#].*curl .*--insecure') {
        throw 'An executable curl --insecure invocation remains in a staged installer file.'
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
