# `agentbox` Debian 13 重装与接管手册

> 正式安装会清空唯一一块 120 GB Disk 0，包括 C:、D: 和 Windows RE。必须顺序通过 A–D 四个检查点，不得跳过。

## 0. 固定物料

| 项目 | 固定值 |
| --- | --- |
| Debian | 13 / Trixie |
| 主机 / 用户 | `agentbox` / `agent` |
| `reinstall` commit | `6b3a341b4bb5c0b93f25cc0a0518e9bd5088504b` |
| 上游 `reinstall.bat` SHA-256 | `A7BD252241ADEE998FCF9F7C8FCE0EA61C34AAE32A347B278125B543C431984E` |
| 上游 `reinstall.sh` SHA-256 | `FE8CF9D8FB800AA74480BBD2223F268259E2A6EADFEAB68C50A39B57F027139F` |
| 上游 `debian.cfg` SHA-256 | `53DA483158C7D526987BAFE6BF450FFC93A32E5B7B0D16DAA6126F21731A4161` |
| 加固后 `reinstall.bat` SHA-256 | `85D1783C9EE86A224D4E942E64052EE4CAC0613F455F1829D16CB78B058EF0A4` |
| 双代理扩展后 `reinstall.sh` SHA-256 | `46C2750B44CAEED5500AE758F880A2B0DD39E474991C99179229BD3A8E37D3EF` |
| 双代理扩展后 `debian.cfg` SHA-256 | `42A129FA89BB21C551BB6C73474FF07381005F0D422D5B2C3FD3165608EE6F25` |
| Cygwin setup SHA-256 | `2C9F2FB56E1FB687B5D9680AFA8F8B06E6214F0E483096AF0EAE1946431226C5` |
| Cygwin 签名指纹 | `7C470FD5026C30AA594D5D3782A060DDFFA0D1FD` |
| Linux Mihomo | 1.19.29, amd64-v1 |
| Mihomo `.gz` SHA-256 | `A048ECBE2DC598321F63A6FBEFFA93F0C10CA6DB818F64B2B83CF19EF194D73F` |
| Mihomo 解压后 SHA-256 | `040452CA5FCA2977C038D539F34A60DD03D2CE1B9DF23C61815D6C91E7FF2C25` |
| Clash Verge 兼容基线 | 2.5.2 / `28f2efc504059b1dc75c793618b775c8e1b2a5f1` |
| js-yaml | 5.2.2，CJS SHA-256 `67784D9C17C101918E97F9456957AD6E558CE2F9A50627F40298D5672365BDC1` |

上述数值于 2026-09-04 校验。`Prepare-Reinstall.ps1` 会固定上游 commit、预下载经签名的 Cygwin，将已知 HTTP 地址替换为 HTTPS，并拒绝哈希偏差。

`Prepare-ProxyBootstrap.ps1` 会生成私密双代理包：7897 为静态保底节点，7898 为当前远程订阅经过完整 Merge/JavaScript/Rules/Proxies/Groups 增强后的生产配置。脚本会把生产关键区块与 Windows 当前 Clash Verge 渲染结果比较；任何差异都停止。该目录含订阅 URL、节点凭据和自定义规则，只能存在 `.agentbox-staging` 内，绝对不得提交、粘贴到聊天或发送给他人。

## 1. 检查点 A：外部接管

全部勾选前，不运行安装器、不重启：

- [ ] 本手册和脚本已推送到 `InvictusNightmares/ai-tools`。
- [ ] 实体电脑已安装 Codex App，克隆仓库并打开本手册。
- [ ] 实体电脑和手机已加入同一 Tailnet。
- [ ] Tailnet 已建立 `tag:agent-server`，仅本人设备可访问该标签的 TCP 22。
- [ ] 已生成一次性、不可复用、非 Ephemeral、带 `tag:agent-server` 的 auth key；仅临时保存在密码管理器。
- [ ] 实体电脑已生成专用 Ed25519 密钥，私钥未复制到云电脑或手机。
- [ ] 天翼外部客户端可打开控制台，且可在不进入 Windows 时重装官方 Windows。
- [ ] 密码管理器已保存随机临时 root 密码和独立 `agent` 本地密码。
- [ ] 已确认除 GitHub 仓库与手册外不保留本机状态，接受 C:/D:/Windows RE 全部清除。
- [ ] 已理解 7897 是 Tailscale 和订阅刷新的静态救生艇；生产规则或订阅失败不会切断它，但保底节点本身失效仍会导致远程失联。

在 Tailscale Access controls 中把下面内容合并进现有 HuJSON 策略，并将邮箱替换为自己的 Tailscale 登录邮箱：

```json
{
  "tagOwners": {
    "tag:agent-server": ["你的登录邮箱@example.com"]
  },
  "grants": [
    {
      "src": ["你的登录邮箱@example.com"],
      "dst": ["tag:agent-server"],
      "ip": ["tcp:22"]
    }
  ]
}
```

必须删除或收窄任何同时覆盖 `tag:agent-server` 的默认全放行规则；Tailscale grant 是累加关系，新增窄规则不会抵消已有宽规则。先使用管理台的策略校验功能，再保存。

实体电脑执行：

```powershell
ssh-keygen -t ed25519 -a 100 -f "$env:USERPROFILE\.ssh\agentbox_ed25519" -C "agentbox-admin"
git clone https://github.com/InvictusNightmares/ai-tools.git
git -C .\ai-tools rev-parse HEAD
git -C .\ai-tools status --short
```

`rev-parse HEAD` 必须与本次交付消息中的远端 commit 一致，`status --short` 必须无输出。

## 2. 准备安装器与私密代理包

此阶段下载 Cygwin、Linux 内核和 initrd 仍依赖 Windows 的 Clash TUN。先确认 Clash Verge Rev 和 Mihomo 正在运行，并通过当前节点访问三个关键站点：

```powershell
Get-Process -Name clash-verge,verge-mihomo
curl.exe --fail --head https://github.com/
curl.exe --fail --head https://deb.debian.org/debian/
curl.exe --fail --head https://pkgs.tailscale.com/
```

任一检查失败都先修复或切换 Windows 节点。检查通过后在当前云电脑 PowerShell 执行：

```powershell
Set-Location D:\Code\ai-tools
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\script\agentbox\Prepare-Reinstall.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\script\agentbox\Prepare-ProxyBootstrap.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\script\agentbox\Prepare-Reinstall.ps1 -VerifyOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\script\agentbox\Prepare-ProxyBootstrap.ps1 -VerifyOnly
```

预期 staging：

```text
D:\Code\ai-tools\.agentbox-staging\6b3a341b4bb5
```

任何哈希、Authenticode、Mihomo 配置语法、Clash Verge 关键区块等价性或私密 ACL 检查失败都必须停止。成功输出应明确包含 `private dual-proxy bundle` 和 `production rules reproduced from Clash Verge Rev 2.5.2`，但不得显示节点名、订阅 URL 或规则内容。

## 3. Alpine Live 无损预检

以管理员身份打开 `cmd.exe`：

```bat
cd /d D:\Code\ai-tools\.agentbox-staging\6b3a341b4bb5
reinstall.bat alpine --hold 1
```

- 通过交互提示输入临时 root 密码，不传入 `--password`。
- 只有看到 `Reboot to start Alpine Live OS` 且无错误才继续。
- 此时尚可运行 `reinstall.bat reset` 取消引导项。
- 如 Defender 明确拦截已验证文件，只短暂暂停实时保护，引导项生成后立即恢复；Windows 防火墙不关闭。
- 手动重启时，当前 Codex 将永久中断，后续依赖实体电脑上的本手册。

进入 Alpine 后，先检查本地硬件与 DHCP：

```sh
cat /etc/alpine-release
uname -a
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL
ip -br link
ip -br addr
ip route
cat /etc/resolv.conf
date -Is
```

再从 initrd 启动私密 Linux Mihomo：

```sh
. /proxy-bootstrap/start-proxy.sh
wget -S --spider https://deb.debian.org/debian/
wget -S --spider https://pkgs.tailscale.com/
wget -S --spider https://raw.githubusercontent.com/InvictusNightmares/ai-tools/main/doc/debian-dd-runbook.md
```

通过标准：

- 约 120 GB VirtIO 磁盘可见，Windows 分区未挂载或写入。
- VirtIO 网卡获得 DHCP 地址，存在默认路由。
- 7897 引导 Mihomo 进程持续运行，三个 HTTPS 检查全部通过。Alpine 阶段不启动 7898，也不测试自动订阅刷新。
- 天翼控制台可持续显示并接收输入。

禁止执行 `mount`、`fdisk`、`parted`、`mkfs`、`dd` 或 `/trans.sh`。检查完成后：

```sh
reboot
```

## 4. 检查点 B：返回 Windows

- [ ] Windows、C: 和 D: 正常。
- [ ] 外部仓库、控制台和官方 Windows 重装入口正常。
- [ ] Alpine 的 VirtIO、DHCP、控制台和 Mihomo HTTPS 检查全部通过。
- [ ] 两个 `Prepare-*.ps1 -VerifyOnly` 再次通过。

任何一项失败都不得正式安装。

## 5. 检查点 C：正式 Debian 安装

先再次执行第 2 节的 Clash 进程和三个 HTTPS 检查；正式安装器仍需借助 Windows TUN 下载 Debian 内核及 initrd。然后由管理员 PowerShell 最后复核磁盘：

```powershell
Get-Disk -Number 0 | Format-List Number,FriendlyName,PartitionStyle,Size,IsBoot,IsSystem
Get-Partition -DiskNumber 0 | Format-Table PartitionNumber,DriveLetter,Type,Size
```

在用户再次明确确认“清空 Disk 0 上的 C:/D:/Windows RE”后，管理员 `cmd.exe` 执行：

```bat
cd /d D:\Code\ai-tools\.agentbox-staging\6b3a341b4bb5
reinstall.bat debian 13
```

- 交互设置临时 root 密码，不使用 `--password`。
- 不使用 `dd --img` 或第三方 RAW 镜像。
- 重启前仍可用 `reinstall.bat reset` 取消；重启后将开始清盘。
- Debian 安装器会在 DHCP 配置后自动启动 initrd 内的 7897 引导 Mihomo，并使用它下载软件；安装结束前同时把 7898 完整规则配置、私密 profile、更新器和回滚服务写入目标系统。
- 全程通过天翼控制台观察。清盘后的最终恢复路径只有官方 Windows 重装。

## 6. Debian 首次引导

用天翼控制台以 root 登录，先检查：

```sh
cat /etc/os-release
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL
ip -br addr
ip route
systemctl status mihomo-bootstrap mihomo --no-pager
```

如 `mihomo-bootstrap` 失败，不继续 SSH 加固，保留 root 控制台入口查看 `journalctl -u mihomo-bootstrap`。如仅 `mihomo` 失败，7897 和后续 Tailscale 接管仍可用，但日常出口暂不切到 7898。

Mihomo 正常后，先通过安装器写入的 APT 代理安装 HTTPS 检查工具，再下载固定版初始化脚本：

```sh
apt-get update
apt-get install -y ca-certificates curl
curl -I https://deb.debian.org/debian/
curl -fL -o /root/bootstrap-debian.sh https://raw.githubusercontent.com/InvictusNightmares/ai-tools/26c4cd39704e0227a1d19e663059f0ff856beeef/script/agentbox/bootstrap-debian.sh
chmod 700 /root/bootstrap-debian.sh
/root/bootstrap-debian.sh
```

脚本先经 7897 安装 Node 等基础依赖，再验证 7898 的完整规则出口。只有 7898 能通过 GitHub HTTPS 检查时，才把 APT/交互 shell 切到 7898 并启用 profile 更新 timer；`tailscaled` 始终固定使用 7897。随后脚本交互请求实体电脑 SSH **公钥**、`agent` 本地密码，以及一次性不可复用的 `tag:agent-server` Tailscale auth key。它不会在这一步锁定 root。

## 7. 检查点 D：SSH 验证后加固

实体电脑第一个终端：

```powershell
ssh -i "$env:USERPROFILE\.ssh\agentbox_ed25519" agent@agentbox
sudo -v
```

在该 SSH 会话中：

```sh
curl -fL -o /tmp/finalize-debian.sh https://raw.githubusercontent.com/InvictusNightmares/ai-tools/26c4cd39704e0227a1d19e663059f0ff856beeef/script/agentbox/finalize-debian.sh
chmod 700 /tmp/finalize-debian.sh
sudo /tmp/finalize-debian.sh
```

脚本重载 SSH 后会暂停。保留第一个会话，在第二个终端重新验证 SSH 和 `sudo`。只有成功后才返回第一个会话输入 `LOCK ROOT`。

然后在 Tailscale 管理台确认一次性 auth key 已自动撤销（若仍显示有效则手动撤销），删除密码管理器中的临时副本，并确认 `agentbox` 由 `tag:agent-server` 管理。

## 8. 重启验收

```sh
sudo reboot
```

重新 SSH 后执行：

```sh
cat /etc/debian_version
hostnamectl
timedatectl
swapon --show
systemctl is-enabled mihomo-bootstrap mihomo agentbox-proxy-update.timer ssh tailscaled fstrim.timer
systemctl is-active mihomo-bootstrap mihomo ssh tailscaled
curl --proxy http://127.0.0.1:7897 -I https://github.com/
curl --proxy http://127.0.0.1:7898 -I https://github.com/
systemctl list-timers agentbox-proxy-update.timer --no-pager
tailscale status
tailscale netcheck
sudo ufw status verbose
sudo sshd -T | grep -E 'permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|allowusers'
ss -lntp
journalctl -b -p warning --no-pager
```

验收要求：两个 Mihomo/Tailscale/SSH 无人登录即自启，7897/7898 只监听 loopback，公网 TCP 22 不可访问，SSH 只接受 `agent` 公钥，4 GB swap 有效，root 已锁定，自动安全更新不触发自动重启。

如果 `tailscale status` 显示 `relay` 或 `tailscale netcheck` 显示 UDP 不可用，但实体电脑的 SSH 可持续连接，这符合“控制面和 DERP 经 Mihomo、UDP 直连不可用”的预期降级。不要为追求 `direct` 而开放公网 SSH；只有在天翼网络本身允许时，才考虑单独放行 Tailscale 的 UDP 41641。

完成重启验收后手动做一次订阅刷新：

```sh
sudo update-agentbox-proxy --force
sudo systemctl status mihomo-bootstrap mihomo agentbox-proxy-update.service --no-pager
sudo journalctl -u agentbox-proxy-update.service -n 50 --no-pager
```

更新器不会把订阅 URL、节点名或规则写入正常日志。它通过 7897 下载，用临时 17898 实例验证，再原子替换 7898；失败保持原配置。上一版保存在 `/etc/mihomo/config.yaml.previous`。如必须人工回滚：

```sh
sudo install -o root -g mihomo -m 0640 /etc/mihomo/config.yaml.previous /etc/mihomo/config.yaml
sudo systemctl restart mihomo
curl --proxy http://127.0.0.1:7898 -I https://github.com/
```

## 9. 稳定性观察

1. 断开天翼图形客户端 2 小时，通过 SSH 验证。
2. 再断开 26 小时，检查平台休眠、停机或重启。
3. 观察 24–48 小时的 `journalctl`、磁盘、两个 Mihomo、profile 更新 timer、Tailscale 和 SSH。
4. 稳定后才安装 Codex、GitHub 认证和开发工具链。

## 10. 恢复矩阵

| 阶段 | 恢复方式 |
| --- | --- |
| 只生成 staging | 系统未改变，可忽略 staging |
| 已生成引导项、未重启 | `reinstall.bat reset` |
| Alpine Live 且未写盘 | `reboot` 返回 Windows |
| Debian 安装中 | 天翼控制台查看日志；不随意重启 |
| Disk 0 已清除且无法启动 | 天翼外部客户端重装官方 Windows |
