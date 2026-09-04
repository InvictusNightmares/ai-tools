# `agentbox` 7×24 个人编码 Agent 建设方案

- 目标设备：天翼云 TeleAgent 云电脑精英版
- 目标系统：Debian 13（Trixie）
- 主机名 / 管理用户：`agentbox` / `agent`
- 远程入口：Tailscale + 标准 OpenSSH
- 外网出口：Mihomo + 用户自有 Hysteria2 节点
- 时区：`Asia/Shanghai`

## 1. 目标

将当前 Windows 云电脑改造成无桌面 Linux Agent 主机，用于代码修改、测试、构建、调研和文档等任务。日常从实体电脑通过 `ssh agent@agentbox` 接管，不再依赖 Windows 桌面。

第一阶段只建设基础系统、外网代理、Tailscale 和 SSH，不安装 Docker、OpenClaw、Hermes、CtYun 保活程序或 Codex。稳定 24–48 小时后再建设 Agent 工具链。

## 2. 当前环境结论

- OpenStack/KVM 虚拟机，SeaBIOS 传统 BIOS，MBR 启动。
- 8 逻辑 CPU、16 GB 内存、120 GB Red Hat VirtIO SCSI 单磁盘。
- C: 和 D: 是同一块磁盘的两个分区；正式重装会同时删除 C:、D: 和 Windows RE。
- Red Hat VirtIO 网卡使用 DHCP，MTU 1450，Linux 具备原生 VirtIO 支持。
- 天翼外部客户端能在客户机失效时重装官方 Windows，这是唯一最终恢复手段。
- 嵌套虚拟化不可用，WSL2 不是可行替代。
- 云电脑不能直连公网。当前 Windows 使用 Clash Verge Rev / Mihomo 1.19.29 的 `Meta Tunnel` TUN 模式，实际出口为用户自有 Hysteria2 节点，本地混合端口为 `127.0.0.1:7897`。

因此，Windows 中的 Clash 不能被假设为可跨重启服务。Alpine Live、Debian 安装器和新 Debian 的第一次启动都必须自带 Linux Mihomo 引导包，否则无法下载 Debian 软件或注册 Tailscale。

## 3. 接管与秘密边界

当前 Codex 位于将被重装的机器中，Alpine 预检的第一次重启就会终止本进程。连续性由三个外部接管点保证：

1. GitHub 中的本方案和 [Debian 重装手册](debian-dd-runbook.md)。
2. 实体电脑上的仓库副本、Codex App、Tailscale 和 SSH 私钥。
3. 天翼外部控制台和官方 Windows 重装功能。

不复制 `.codex`、`auth.json`、会话数据库或缓存。临时 root 密码、`agent` 密码、SSH 私钥、Tailscale auth key 和节点凭据不得进入 Git、聊天或日志。

节点配置由 `Prepare-ProxyBootstrap.ps1` 从当前活动 Clash 配置在本机内生成：

- 通过 Mihomo 本地命名管道解析当前 `MATCH → 策略组 → 实际节点`，不输出节点名、地址或凭据。
- 保留内联 `proxies` 节点，移除规则订阅、外部控制端和 TUN，将所有引导流量强制经过当前已验证节点。
- 私密包位于被 `.gitignore` 忽略的 `.agentbox-staging` 目录，Windows ACL 只允许当前管理员、Administrators 和 SYSTEM。
- 私密包会进入安装 initrd 并最终存放在 Debian 的 `/etc/mihomo`，文件权限限制为 root。

## 4. 基础系统基线

- Debian 13，主机名 `agentbox`，时区 `Asia/Shanghai`。
- Mihomo 开机自启，提供 `127.0.0.1:7897` HTTP/SOCKS 出口；APT、交互 shell 和 `tailscaled` 明确使用该代理。
- Tailscale 的控制面和 DERP HTTPS 经 Mihomo 出站；受限网络下可能长期显示 `relay` 而不是 `direct`，编码与 SSH 可用性优先于直连延迟。
- 日常管理用户 `agent` 加入 `sudo`；root 只在引导期间使用。
- OpenSSH TCP 22 只允许从 `tailscale0` 进入，只接受 `agent` 的 Ed25519 公钥。
- Tailscale 节点使用 `tag:agent-server`，不开启 Tailscale SSH。
- UFW 默认拒绝入站，允许出站，只放行 `tailscale0` 的 TCP 22。
- 4 GB swapfile，`vm.swappiness=10`，不使用需人工解锁的全盘加密。
- 安全更新自动安装，但不自动重启。
- `mihomo`、`ssh`、`tailscaled` 和 `fstrim.timer` 开机自启。

## 5. 建设顺序

1. 将手册、准备脚本和 Debian 引导脚本提交、推送 GitHub。
2. 实体电脑克隆对应 commit，准备 Codex App、Tailnet 和专用 SSH 密钥。
3. 在 Windows 中生成经哈希校验的安装器和带 ACL 的私密 Mihomo 引导包。
4. 启动 Alpine Live，先验证 VirtIO/DHCP，再从 initrd 启动 Linux Mihomo，验证通过代理访问外网；不写磁盘，返回 Windows。
5. 确认预检通过后，使用同一固定安装器执行 Debian 13 网络安装。
6. Debian 安装器在 DHCP 后启动 initrd 内的 Mihomo，并将 APT 镜像代理设为 `127.0.0.1:7897`。
7. 安装完成前将 Mihomo、配置、APT/shell 代理和 `tailscaled` systemd 代理 drop-in 复制到目标系统。
8. 首次启动后执行 `bootstrap-debian.sh`，建立 `agent` + Tailscale + SSH。
9. 实体电脑验证两条独立 SSH 会话和 `sudo`，然后执行 `finalize-debian.sh` 锁定 root。
10. 重启验收并观察 24–48 小时，再安装 Agent 工具链。

## 6. 风险与可用性边界

- `bin456789/reinstall` 和 Mihomo 都是第三方组件。安装器锁定 commit，原文件和修改文件均校验 SHA-256；Mihomo 锁定与当前 Windows 相同的 1.19.29 版本和官方发布哈希。
- Debian 安装期间仍需要外部镜像站；Alpine 无损预检必须先证明 Linux Mihomo 可用，否则不得清盘。
- Mihomo HTTP 代理不能转发 Tailscale 的 UDP 打洞流量；若平台原生 UDP 出站也不可用，Tailnet 流量会回退到 DERP 中继，这是预期降级而非失联。
- 如自有节点密码、证书、地址或协议发生变化，必须在 Windows 上重新生成私密引导包并重做 Alpine 预检。
- 客户机内的 systemd 可恢复进程，但无法在云平台关闭整台虚拟机时自我唤醒。
- [CtYun 保活工具](https://github.com/leleji/CtYun) 待基础系统稳定后单独审计。本机部署只能防止运行期间休眠，停机恢复仍需天翼平台或第二台外部常在设备。

## 7. 验收标准

- Debian 重启后无需图形登录，Mihomo、Tailscale 和 SSH 自动恢复。
- 实体电脑可使用 `ssh agent@agentbox`，公网接口不能访问 TCP 22。
- root SSH、SSH 密码认证和 Tailscale SSH 关闭；手机不持有 SSH 私钥。
- APT、GitHub HTTPS 和 Tailscale 通过 Mihomo 出站正常。
- 临时 Tailscale auth key 已撤销，Git 仓库不包含任何节点或账号凭据。
- 安全更新自动安装，但不会无人值守自动重启。
- 断开天翼客户端 2 小时和 26 小时的平台行为已记录。

## 8. 参考

- [bin456789/reinstall](https://github.com/bin456789/reinstall)
- [Debian 发行版](https://www.debian.org/releases/)
- [Tailscale Linux 安装](https://tailscale.com/docs/install/linux)
- [Tailscale 服务器建议](https://tailscale.com/docs/how-to/set-up-servers)
- [Tailscale Grants](https://tailscale.com/docs/features/access-control/grants)
- [Tailscale Auth keys](https://tailscale.com/docs/features/access-control/auth-keys)
- [MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo)
- [Linux.do 天翼云电脑 Debian 实践](https://linux.do/t/topic/654530)
