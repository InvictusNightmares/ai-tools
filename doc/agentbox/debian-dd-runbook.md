# `agentbox` Debian 13 重装与接管手册

> 正式安装会清空唯一一块 120 GB Disk 0，包括 C:、D: 和 Windows RE。必须顺序通过 A–D 四个检查点，不得跳过。

## 0. 固定物料

| 项目 | 固定值 |
| --- | --- |
| Debian | 13 / Trixie |
| 主机 / 用户 | `agentbox` / `agent` |
| 时区 | `America/Los_Angeles`（自动切换 PST/PDT） |
| 系统语言 / 键盘 | 仅 `en_US.UTF-8` / US |
| 容器运行时 | Docker CE + containerd + Buildx + Compose（Docker 官方 Debian 仓库） |
| Headless Chrome | `ghcr.io/browserless/chrome:v2.56.2@sha256:1be15d1e3bad53e89d07ef529a52615739f77b7cd997a49c0ec97aaa78d0fcaf` |
| `reinstall` commit | `6b3a341b4bb5c0b93f25cc0a0518e9bd5088504b` |
| 上游 `reinstall.bat` SHA-256 | `A7BD252241ADEE998FCF9F7C8FCE0EA61C34AAE32A347B278125B543C431984E` |
| 上游 `reinstall.sh` SHA-256 | `FE8CF9D8FB800AA74480BBD2223F268259E2A6EADFEAB68C50A39B57F027139F` |
| 上游 `debian.cfg` SHA-256 | `53DA483158C7D526987BAFE6BF450FFC93A32E5B7B0D16DAA6126F21731A4161` |
| 加固后 `reinstall.bat` SHA-256 | `85D1783C9EE86A224D4E942E64052EE4CAC0613F455F1829D16CB78B058EF0A4` |
| 双代理扩展后 `reinstall.sh` SHA-256 | `78362DC3C3ACD009AB9C6DFE7B22B3CF5BD72935B3A0254A1026E9D219CFD356` |
| 双代理扩展后 `debian.cfg` SHA-256 | `C72584170B2A3630D02AAFF0F3E6DBFF4C827C60259E05DAA9628E1660578BE7` |
| Cygwin setup SHA-256 | `2C9F2FB56E1FB687B5D9680AFA8F8B06E6214F0E483096AF0EAE1946431226C5` |
| Cygwin 签名指纹 | `7C470FD5026C30AA594D5D3782A060DDFFA0D1FD` |
| Linux Mihomo | 1.19.29, amd64-v1 |
| Mihomo `.gz` SHA-256 | `A048ECBE2DC598321F63A6FBEFFA93F0C10CA6DB818F64B2B83CF19EF194D73F` |
| Mihomo 解压后 SHA-256 | `040452CA5FCA2977C038D539F34A60DD03D2CE1B9DF23C61815D6C91E7FF2C25` |
| Clash Verge 兼容基线 | 2.5.2 / `28f2efc504059b1dc75c793618b775c8e1b2a5f1` |
| js-yaml | 5.2.2，CJS SHA-256 `67784D9C17C101918E97F9456957AD6E558CE2F9A50627F40298D5672365BDC1` |

上述数值于 2026-09-04 校验。`Prepare-Reinstall.ps1` 会固定上游 commit、预下载经签名的 Cygwin，将已知 HTTP 地址替换为 HTTPS，并拒绝哈希偏差。

`reinstall.sh` 扩展哈希于 2026-09-06 更新：除 Cygwin 复制权限修复外，Alpine 在 `switch_root` 前必须将 `/proxy-bootstrap` 随 `/configs` 一起复制到新根目录。只把代理包放进 initrd，不能保证登录后的 Live 系统仍可访问它。

`Prepare-ProxyBootstrap.ps1` 会生成私密双代理包：7897 为静态保底节点，7898 为当前远程订阅经过完整 Merge/JavaScript/Rules/Proxies/Groups 增强后的生产配置。脚本会把生产关键区块与 Windows 当前 Clash Verge 渲染结果比较；任何差异都停止。该目录含订阅 URL、节点凭据和自定义规则，只能存在 `.agentbox-staging` 内，绝对不得提交、粘贴到聊天或发送给他人。

7897 在 `MATCH,BOOTSTRAP` 前仅保留源配置中针对选中节点自身的精确 `DIRECT` 规则（IPv4 `/32`、IPv6 `/128` 或精确 `DOMAIN`）；不保留其他主机、网段或域名后缀的直连规则，也不创建源配置中不存在的直连策略。当 DMIT 同时提供代理和在线订阅时，删掉这条自身直连规则会让订阅下载绕回同一个代理节点而超时。7898 继续使用完整订阅规则，在线刷新仍固定通过 7897 下载。

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
- [ ] 已确认新 Debian 使用 `America/Los_Angeles`、`en_US.UTF-8` 和 US 键盘，不安装中文 locale、字体、输入法或语言任务包。

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
ip link show
ip addr show
ip route
cat /etc/resolv.conf
date -Is
```

如果 Live 环境没有 `lsblk`，用 `cat /proc/partitions` 和 `cat /proc/mounts` 核对磁盘容量、分区及未挂载状态。BusyBox `ip` 不支持 `-br`，使用上面的完整命令。若控制台同时显示 `tty0` 和 `tty1` 登录提示，切换到独立的 `tty2` 后登录。

启动代理前必须确认 `/proxy-bootstrap/mihomo` 存在，且 `sha256sum /proxy-bootstrap/mihomo` 与上表一致；目录应为 0700，配置应为 0600。若目录缺失，本轮预检失败，返回 Windows 用修复后的生成器重新生成安装器并再跑 Alpine 预检，不从 Windows 分区挂载读取私密包。

先在 Live 内存系统中安装 curl，再启动 initrd 携带的私密 Linux Mihomo。安装 curl 使用当前已能下载 Alpine 启动模块的仓库，保留 APK 签名校验；不会写入 Windows 分区：

```sh
http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= apk add --no-cache curl
```

确认 APK 安装成功后执行：

```sh
sh /proxy-bootstrap/start-proxy.sh >/tmp/agentbox-proxy-start.log 2>&1
echo "PROXY_START_RC=$?"
```

上述两步任何一步失败都停止预检，不直接打印私密代理日志。启动成功后，显式指定 loopback 代理并保留 HTTPS 证书校验：

```sh
for url in \
  https://deb.debian.org/debian/ \
  https://pkgs.tailscale.com/ \
  https://raw.githubusercontent.com/InvictusNightmares/ai-tools/main/doc/agentbox/debian-dd-runbook.md
do
  curl -fsSL --proxy http://127.0.0.1:7897 \
    --connect-timeout 10 --max-time 25 -o /dev/null \
    -w '%{url_effective} HTTP=%{http_code} TLS_VERIFY=%{ssl_verify_result}\n' "$url"
  echo "CURL_RC=$?"
done
pidof mihomo
netstat -lnt
```

2026-09-06 实测：BusyBox 1.37.0 的 `wget` 经同一代理访问这三个 HTTPS 地址均返回 502；换用 curl 后均为 HTTP 200，证书校验成功。BusyBox 的[代理请求代码](https://github.com/mirror/busybox/blob/master/networking/wget.c)使用绝对 URL 的 GET，不能用这条失败路径判断 Mihomo 的 HTTPS CONNECT 出口不可用。预检以 curl 的 HTTP 状态、`TLS_VERIFY=0` 和 `CURL_RC=0` 为准，不添加 `-k` 或 `--no-check-certificate`。

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

两个配置目录必须为 `root:mihomo`、0750，配置文件为 `root:mihomo`、0640。若旧版安装器留下 `root:root` 的 0750 目录，服务账号无法遍历目录，即使配置文件属组正确也会启动失败；先修正两个目录的属组，再重启并验证代理。诊断时不要把包含节点信息的完整日志或配置粘贴到聊天。

Mihomo 正常后，先通过安装器写入的 APT 代理安装 HTTPS 检查工具，再下载固定版初始化脚本：

```sh
apt-get update
apt-get install -y ca-certificates curl
curl -I https://deb.debian.org/debian/
curl -fL -o /root/bootstrap-debian.sh https://raw.githubusercontent.com/InvictusNightmares/ai-tools/aa32363b774c68a770d86350e68aa8c8d46564aa/script/agentbox/bootstrap-debian.sh &&
printf '%s\n' '4e2d24f5633577ec8addf40be485db73533c6bd7040893bf6dfc6edacc7e825b  /root/bootstrap-debian.sh' | sha256sum -c - &&
chmod 700 /root/bootstrap-debian.sh &&
/root/bootstrap-debian.sh
```

脚本先经 7897 安装 Node 等基础依赖，再验证 7898 的完整规则出口。只有 7898 能通过 GitHub HTTPS 检查时，才把 APT/交互 shell 切到 7898 并启用 profile 更新 timer；`tailscaled` 始终固定使用 7897。随后脚本交互请求实体电脑 SSH **公钥**、`agent` 本地密码，以及一次性不可复用的 `tag:agent-server` Tailscale auth key。它不会在这一步锁定 root。

脚本同时把主机时区固定为 `America/Los_Angeles`（由系统时区数据库自动处理 PST/PDT），只生成并启用 `en_US.UTF-8`，清除已知中文 locale 全量包、中文桌面任务包、字体和输入法。Debian 软件包自带但未启用的翻译目录不做破坏性删改；系统选择、会话环境和控制台输出保持英文。

脚本安装并启用 `systemd-timesyncd`，通过 Debian NTP 池自动校时；同步失败会停止初始化，先检查原生 UDP 123 连通性。`America/Los_Angeles` 只决定显示时区，系统时钟和虚拟 RTC 均使用正确 UTC。Windows 遗留的错误 RTC 时间须在 NTP 同步后写回，不能靠修改时区抵消。

脚本还会屏蔽 `sleep.target`、`suspend.target`、`hibernate.target`、`hybrid-sleep.target` 和 `suspend-then-hibernate.target`，并写入 `/etc/systemd/{sleep,logind}.conf.d/90-agentbox.conf`：禁止所有睡眠/休眠模式，空闲、虚拟电源/重启/睡眠键及合盖均不触发自动停机，空闲会话不自动退出。屏蔽立即生效，logind 配置在计划内的重启验收时加载；不要屏蔽 `shutdown.target` 或 `reboot.target`，管理员仍需能主动维护机器。

脚本还会从 Docker 官方 Debian 13 仓库安装 Docker CE、containerd、Buildx 和 Compose。Docker daemon 拉镜像固定经 7897；未来业务容器通过专用 `agentbox-egress` 网络和 `/srv/agentbox/proxy.env` 使用 7898。默认端口发布只绑定 loopback，`DOCKER-USER` 额外拒绝非 Tailscale 入站。`agent` 不加入 `docker` 组，管理容器统一使用 `sudo docker ...`。

宿主机与容器的边界固定为：OpenSSH、Tailscale、UFW/iptables、双 Mihomo、Docker/containerd、时间/磁盘/安全更新留在 systemd；Agent worker、数据库、队列、浏览器自动化、Dashboard 和项目服务放进 Compose。接管层依赖项不得容器化，否则 Docker 故障会同时切断修复入口。

业务栈放在 `/srv/agentbox/<stack>/compose.yaml`。需要外网的服务使用以下最小结构；内部服务名如 `db`、`redis` 还应追加到该栈的 `NO_PROXY`：

```yaml
services:
  app:
    image: example/image:fixed-version
    restart: unless-stopped
    env_file:
      - /srv/agentbox/proxy.env
    security_opt:
      - no-new-privileges:true
    networks:
      - default
      - agentbox-egress

networks:
  agentbox-egress:
    external: true
```

不要使用 `network_mode: host`，不要挂载 `/var/run/docker.sock`，不要使用 `privileged: true`，不要把密钥写进镜像或 Compose。默认只允许本机访问发布端口；需要从实体电脑访问的新端口，必须同时显式绑定 Tailscale 地址并在 Tailnet grant 中逐端口授权。

初始化脚本会直接启动 `/srv/agentbox/headless-chrome/compose.yaml`：Browserless v2.56.2 的实际 Google Chrome 镜像被 tag 和 digest 双重固定，仅连接内部 `agentbox-browser` 和出口 `agentbox-egress`，不设置 `ports`。随机 256-bit token 分别以 root-only Compose 环境和 `root:agent` 0640 客户端环境保存，任何正常输出都不会显示 token。Chrome 限制为 2 个并发会话、10 个排队请求、5 分钟超时、2 GB `/dev/shm`、4 GB 内存和 4 CPU。

未来 Agent 容器需同时加入 `agentbox-browser` 网络并安全加载 `/srv/agentbox/headless-chrome/client.env`。Browserless v2 的 Chrome WebSocket 基址是 `ws://headless-chrome:3000/chrome`；由于 Browserless 要求自带代理按会话传入，客户端必须把 `BROWSERLESS_PROXY_SERVER` 和 `BROWSERLESS_LANGUAGE` 分别编码为 `--proxy-server`、`--lang` launch 参数，不能依赖 Chrome 自动读取 `HTTP_PROXY`。不得把 token 放进 URL 日志、Git 或聊天。

需要检测云电脑实际浏览器环境时，使用 [site-check 检测工具](../../script/agentbox/site-check/README.md)。它复用上述 Chrome 和 7898 出口，在云电脑上打开 Net.Coffee Claude 检测及 Fuck Claude，保留页面实际完成状态、环境数据和截图；未完成的扫描非零退出。网站评分不代替真实 Claude 账号/CLI 验证。

## 7. 检查点 D：SSH 验证后加固

实体电脑第一个终端：

```powershell
ssh -i "$env:USERPROFILE\.ssh\agentbox_ed25519" agent@agentbox
sudo -v
```

在该 SSH 会话中：

```sh
curl -fL -o /tmp/finalize-debian.sh https://raw.githubusercontent.com/InvictusNightmares/ai-tools/f8ce10a75e26fc65a2a80b73db7e6e1c02cb09ff/script/agentbox/finalize-debian.sh &&
printf '%s\n' '9234d8ab3948df698c5b8094905e3496d6c20e0bd84f919884790a38b7d3201c  /tmp/finalize-debian.sh' | sha256sum -c - &&
chmod 700 /tmp/finalize-debian.sh &&
sudo /tmp/finalize-debian.sh
```

脚本重载 SSH 后会暂停。保留第一个会话，在第二个终端重新验证 SSH 和 `sudo`。只有成功后才返回第一个会话输入 `LOCK ROOT`。

SSH 永久基线是公钥认证：`agent` 的本地密码只用于控制台和 `sudo`，不得为方便维护重新开启 SSH 密码认证。策略写入 `00-agentbox.conf`，优先于安装器遗留的 `01-permitrootlogin.conf`；OpenSSH 对这些选项采用首个读到的值，不能把较晚加载的 `90-*.conf` 当成覆盖。脚本必须在重载和锁 root 前检查 `sshd -T` 的实际结果，确认 `PermitRootLogin no`、`AuthenticationMethods publickey`、`PasswordAuthentication no`、`KbdInteractiveAuthentication no`、`PubkeyAuthentication yes` 和 `AllowUsers agent`。

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
timedatectl timesync-status
locale
locale -a
swapon --show
systemctl is-enabled systemd-timesyncd mihomo-bootstrap mihomo agentbox-proxy-update.timer ssh tailscaled docker containerd agentbox-container-proxy fstrim.timer
systemctl is-active systemd-timesyncd mihomo-bootstrap mihomo ssh tailscaled docker containerd agentbox-container-proxy
curl --proxy http://127.0.0.1:7897 -I https://github.com/
curl --proxy http://127.0.0.1:7898 -I https://github.com/
sudo docker version
sudo docker compose version
sudo docker info --format '{{.LoggingDriver}}'
sudo docker network inspect agentbox-egress
sudo docker network inspect agentbox-browser
sudo docker inspect --format '{{.State.Health.Status}}' agentbox-headless-chrome
sudo docker compose --env-file /srv/agentbox/headless-chrome/.env --file /srv/agentbox/headless-chrome/compose.yaml ps
sudo iptables -S DOCKER-USER
id -nG agent
systemctl list-timers agentbox-proxy-update.timer --no-pager
tailscale status
tailscale netcheck
sudo ufw status verbose
sudo sshd -T | grep -E 'permitrootlogin|authenticationmethods|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|allowusers'
systemctl is-enabled sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target
busctl introspect org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager | grep -E 'IdleAction|StopIdleSessionUSec|Handle(Power|Reboot|Suspend|Hibernate|Lid)'
ss -lntp
journalctl -b -p warning --no-pager
```

验收要求：`timedatectl` 显示 `America/Los_Angeles`、`System clock synchronized: yes`、`NTP service: active` 和 `RTC in local TZ: no`，UTC 与可信时间源一致；`locale` 的 `LANG`/`LANGUAGE`/`LC_ALL` 分别为 `en_US.UTF-8`、`en_US:en`、`en_US.UTF-8`，`locale -a` 含 `en_US.utf8` 且不含 `zh_*`；两个 Mihomo/Tailscale/SSH/Docker/容器代理无人登录即自启；Docker 日志驱动为 `local`，Compose、`agentbox-egress` 和内部 `agentbox-browser` 可用，Headless Chrome 为 `healthy` 且没有宿主机端口映射，`agent` 不属于 `docker` 组；7897/7898 的宿主机实例只监听 loopback，容器代理只监听专用 bridge，公网 TCP 22 和容器发布端口不可访问；SSH 只接受 `agent` 公钥，4 GB swap 有效，root 已锁定，自动安全更新不触发自动重启。

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

先确认天翼客户端“自动退出登录”和“自动锁屏”均为“永不”。Debian 的禁用休眠配置不能阻止平台从虚拟机外部关机；必须通过以下断连观察和独立平台保活验证分别确认，不能仅凭 systemd 配置宣称永久在线。CtYun 的部署边界见[建设方案](./personal-agent-plan.md#6-风险与可用性边界)。

平台保活使用仓库中的 [CtYun 单桌面部署模块](../../script/agentbox/ctyun/README.md)，不要直接运行上游默认程序。该模块固定上游版本，移除第三方 OCR，要求人工验证码/短信登录，按指定 DesktopId 每 60 秒更新连接，并持久保存私密会话。完成初次登录后，Compose 的 `restart: unless-stopped` 可在宿主机启动后恢复保活；账号会话失效时仍需人工重新认证。

先按模块手册通过至少三个连续握手周期、容器健康检查及重启复用会话验收，再进行下面的断连观察。只有构建成功、容器启动或 Debian 防休眠配置生效，都不能代替真实平台保活验收。

1. 断开天翼图形客户端 2 小时，通过 SSH 验证。
2. 再断开 26 小时，检查平台休眠、停机或重启。
3. 观察 24–48 小时的 `journalctl`、磁盘、两个 Mihomo、profile 更新 timer、Tailscale、SSH、Docker 和 `agentbox-container-proxy`。
4. 稳定后才以 Compose 栈安装 Codex/Agent、GitHub 认证代理和项目工具链；不把这些业务服务直接安装到宿主机。

本次问题全部解决且验收通过后，再按清单删除安装、诊断和修复过程中生成的临时文件及备份。不要递归清理未知目录，不删除 SSH 私钥、可信主机指纹、当前代理配置或私密 profile。删除 `/etc/mihomo/config.yaml.previous` 会移除当前手工回滚副本；下次成功订阅更新仍会重新生成它，这不等于禁用更新器的失败回滚机制。

## 10. 恢复矩阵

| 阶段 | 恢复方式 |
| --- | --- |
| 只生成 staging | 系统未改变，可忽略 staging |
| 已生成引导项、未重启 | `reinstall.bat reset` |
| Alpine Live 且未写盘 | `reboot` 返回 Windows |
| Debian 安装中 | 天翼控制台查看日志；不随意重启 |
| Disk 0 已清除且无法启动 | 天翼外部客户端重装官方 Windows |
