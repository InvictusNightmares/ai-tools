# `agentbox` 7×24 个人编码 Agent 建设方案

- 目标设备：天翼云 TeleAgent 云电脑精英版
- 目标系统：Debian 13（Trixie）
- 主机名 / 管理用户：`agentbox` / `agent`
- 远程入口：Tailscale + 标准 OpenSSH
- 外网出口：双 Mihomo + Clash Verge Rev 完整订阅增强链
- 时区：`America/Los_Angeles`（自动切换 PST/PDT）
- 系统语言 / 键盘：仅 `en_US.UTF-8` / US

## 1. 目标

将当前 Windows 云电脑改造成无桌面 Linux Agent 主机，用于代码修改、测试、构建、调研和文档等任务。日常从实体电脑通过 `ssh agent@agentbox` 接管，不再依赖 Windows 桌面。

第一阶段建设基础系统、外网代理、Tailscale、SSH 和 Docker 运行底座，但不安装 OpenClaw、Hermes、CtYun 保活程序或 Codex。稳定 24–48 小时后，再把 Agent 和项目工作负载以容器形式部署。

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

1. GitHub 中的本方案和 [Debian 重装手册](./debian-dd-runbook.md)。
2. 实体电脑上的仓库副本、Codex App、Tailscale 和 SSH 私钥。
3. 天翼外部控制台和官方 Windows 重装功能。

不复制 `.codex`、`auth.json`、会话数据库或缓存。临时 root 密码、`agent` 密码、SSH 私钥、Tailscale auth key 和节点凭据不得进入 Git、聊天或日志。

节点和规则配置由 `Prepare-ProxyBootstrap.ps1` 从当前活动 Clash 配置在本机内生成：

- 通过 Mihomo 本地命名管道解析当前 `MATCH → 策略组 → 实际节点`，不输出节点名、地址或凭据。
- 生成 `127.0.0.1:7897` 引导配置：保留内联节点，移除订阅、规则、外部控制端和 TUN，将流量强制经过当前已验证节点。
- 同时复制当前远程 profile、全局及 profile 专属的 Merge/JavaScript、Rules/Proxies/Groups、规则缓存和选择缓存；订阅 URL 仍只存在私密包中。
- 使用与 Clash Verge Rev 2.5.2 相同的增强顺序离线编译 `127.0.0.1:7898` 生产配置，并与 Windows 当前渲染配置的 `proxies`、`proxy-providers`、`proxy-groups`、`rule-providers`、`rules` 五个关键区块逐项比较。不一致即停止。
- 私密包位于被 `.gitignore` 忽略的 `.agentbox-staging` 目录，Windows ACL 只允许当前管理员、Administrators 和 SYSTEM。
- 私密包会进入安装 initrd；Debian 中订阅源与增强脚本保存在仅 root 可读的 `/etc/agentbox-profile`，两个 Mihomo 配置仅允许 root 和 `mihomo` 服务账号读取。

不安装 Clash Verge Rev 的 Linux 桌面包。它是 Tauri 图形程序，官方未提供适合纯 SSH 服务器的 headless 管理模式；本方案只运行 Linux Mihomo 和经过本机等价性校验的无头 profile 编译器。

## 4. 基础系统基线

- Debian 13，主机名 `agentbox`，时区 `America/Los_Angeles`（自动切换 PST/PDT）。
- 系统界面、locale、键盘和命令输出统一为英文：只生成 `en_US.UTF-8`，使用 US 键盘；不安装中文 locale、字体、输入法或语言任务包。仓库中的中文操作手册仅供实体电脑上的操作者阅读，不属于新系统语言配置。
- `mihomo-bootstrap.service` 在 `127.0.0.1:7897` 提供固定保底出口，只服务安装、订阅刷新和 Tailscale。
- `mihomo.service` 在 `127.0.0.1:7898` 提供完整订阅、自定义规则、策略组和脚本增强后的生产出口；APT、交互 shell、Git 和未来的 Agent 默认使用它。
- Tailscale 的控制面和 DERP HTTPS 固定经 7897 出站，不依赖 7898 的自定义规则；受限网络下可能长期显示 `relay` 而不是 `direct`。
- `agentbox-proxy-update.timer` 每 15 分钟检查一次，但只在导入 profile 的刷新周期到期时下载；当前 profile 为自动更新、720 分钟。下载固定经 7897，候选配置先在临时端口 17898 做 Mihomo 语法和 GitHub HTTPS 检查，再切换 7898；失败保留或恢复上一版。
- 日常管理用户 `agent` 加入 `sudo`；root 只在引导期间使用。
- OpenSSH TCP 22 只允许从 `tailscale0` 进入，只接受 `agent` 的 Ed25519 公钥。
- Tailscale 节点使用 `tag:agent-server`，不开启 Tailscale SSH。
- UFW 默认拒绝入站，允许出站，只放行 `tailscale0` 的 TCP 22。
- 4 GB swapfile，`vm.swappiness=10`，不使用需人工解锁的全盘加密。
- 安全更新自动安装，但不自动重启。
- 预装 Docker 官方仓库的 Docker CE、containerd、Buildx 和 Compose 插件；daemon 拉取镜像固定经 7897，启用 `live-restore`、`local` 日志驱动和默认 `no-new-privileges`。
- Docker 创建专用 `agentbox-egress` 网络。需要外网的业务容器同时挂载该网络并载入 `/srv/agentbox/proxy.env`，经只对该网络开放的转发器使用 7898 完整规则。
- 预装 `ghcr.io/browserless/chrome:v2.56.2` 的真实 Headless Chrome（amd64，镜像 digest 固定），仅加入内部 `agentbox-browser` 与出口 `agentbox-egress` 网络，不发布宿主机端口；使用随机 256-bit token、2 个并发会话、10 个排队请求、5 分钟会话上限、2 GB `/dev/shm` 和 4 GB 内存上限。
- Docker bridge 的默认端口发布地址为 `127.0.0.1`；`DOCKER-USER` 链只接受宿主机 Docker bridge 出站和 `tailscale0` 入站，其余外部容器入站拒绝。对外服务还必须在 Tailnet ACL 中逐端口授权。
- 所有 Agent、数据库、任务队列、浏览器自动化和项目服务都放在 `/srv/agentbox/<stack>` 的 Compose 栈中。`agent` 不加入等同 root 权限的 `docker` 组，使用 `sudo docker compose ...` 管理。
- 宿主机只保留 OpenSSH、Tailscale、UFW/iptables、双 Mihomo、Docker/containerd、时间同步、磁盘维护和系统安全更新；这些是接管与容器运行底座，不容器化。
- `mihomo-bootstrap`、`mihomo`、`agentbox-proxy-update.timer`、`ssh`、`tailscaled`、`docker`、`containerd`、`agentbox-container-proxy` 和 `fstrim.timer` 开机自启。

## 5. 建设顺序

1. 将手册、准备脚本和 Debian 引导脚本提交、推送 GitHub。
2. 实体电脑克隆对应 commit，准备 Codex App、Tailnet 和专用 SSH 密钥。
3. 在 Windows 中生成经哈希校验的安装器和带 ACL 的私密双代理/profile 包；生产配置必须通过 Clash Verge 关键区块等价性检查。
4. 启动 Alpine Live，先验证 VirtIO/DHCP，再从 initrd 启动 Linux Mihomo，验证通过代理访问外网；不写磁盘，返回 Windows。
5. 确认预检通过后，使用同一固定安装器执行 Debian 13 网络安装。
6. Debian 安装器在 DHCP 后启动 initrd 内的 Mihomo，并将 APT 镜像代理设为 `127.0.0.1:7897`。
7. 安装完成前落盘双 Mihomo、完整私密 profile、离线编译器、刷新/回滚服务；APT/shell 初始仍走 7897，`tailscaled` 永久走 7897。
8. 首次启动后执行 `bootstrap-debian.sh`；生产 7898 通过 HTTPS 检查后才切换日常 APT/shell，并启用自动更新，然后建立 `agent` + Tailscale + SSH，安装并加固 Docker，创建容器专用代理网络。
9. 实体电脑验证两条独立 SSH 会话和 `sudo`，然后执行 `finalize-debian.sh` 锁定 root。
10. 重启验收并观察 24–48 小时，再安装 Agent 工具链。

## 6. 风险与可用性边界

- `bin456789/reinstall` 和 Mihomo 都是第三方组件。安装器锁定 commit，原文件和修改文件均校验 SHA-256；Mihomo 锁定与当前 Windows 相同的 1.19.29 版本和官方发布哈希。
- Debian 安装期间仍需要外部镜像站；Alpine 无损预检必须先证明 Linux Mihomo 可用，否则不得清盘。
- Mihomo HTTP 代理不能转发 Tailscale 的 UDP 打洞流量；若平台原生 UDP 出站也不可用，Tailnet 流量会回退到 DERP 中继，这是预期降级而非失联。
- 7897 是静态“救生艇”，不会随订阅自动变化。若这个保底节点的密码、证书、地址或协议失效，7898 的订阅更新和 Tailscale 都会失去外网；应在它失效前通过新的订阅配置重新建立保底节点。
- 远程订阅及用户自定义 JavaScript 被视为可信输入，但仍在无 `process`、`require`、动态代码生成和网络 API 的 Node `vm` 中执行，单次限制 5 秒、输入输出限制 10 MiB。脚本失败会拒绝整次更新并保留旧生产配置。
- 生产实例故障不应影响 Tailscale/SSH；但单个节点本身同时被两实例使用，因此节点级失效仍会影响两条链路。
- Docker 发布端口会绕过 UFW 的常规 INPUT 规则；本方案同时使用默认 loopback 绑定和 Docker 官方预留的 `DOCKER-USER` 链。Compose 文件不得使用 `network_mode: host`，不得无审查地显式绑定 `0.0.0.0`。
- `live-restore` 只能降低 Docker daemon 短暂重启或补丁更新的中断，并不代替 Compose 的 `restart: unless-stopped`，也不能跨宿主机停机维持服务。
- 客户机内的 systemd 可恢复进程，但无法在云平台关闭整台虚拟机时自我唤醒。
- [CtYun 保活工具](https://github.com/leleji/CtYun) 待基础系统稳定后单独审计。本机部署只能防止运行期间休眠，停机恢复仍需天翼平台或第二台外部常在设备。

## 7. 验收标准

- Debian 重启后无需图形登录，两个 Mihomo、Tailscale、SSH、Docker 和容器代理转发器自动恢复。
- 实体电脑可使用 `ssh agent@agentbox`，公网接口不能访问 TCP 22。
- root SSH、SSH 密码认证和 Tailscale SSH 关闭；手机不持有 SSH 私钥。
- APT、GitHub HTTPS 和未来 Agent 通过 7898 的完整规则出站；Tailscale 通过独立 7897 出站。
- Docker daemon 能通过 7897 拉取镜像，Compose 可用；业务容器接入 `agentbox-egress` 后通过 7898 出站，公网接口不能直接访问已发布容器端口。
- `agentbox-headless-chrome` 容器健康，Agent 容器只能通过 `agentbox-browser:3000` 内网和 token 连接；每次创建浏览器会话时显式传入 `/srv/agentbox/headless-chrome/client.env` 中的 7898 代理地址。
- 强制执行一次 `sudo update-agentbox-proxy --force` 能成功刷新；故意提供无效候选时不会替换最后可用的生产配置。
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
- [Clash Verge Rev v2.5.2](https://github.com/clash-verge-rev/clash-verge-rev/releases/tag/v2.5.2)
- [Clash Verge Rev headless Linux 结论](https://github.com/clash-verge-rev/clash-verge-rev/issues/7079)
- [js-yaml](https://github.com/nodeca/js-yaml)
- [Docker Engine on Debian](https://docs.docker.com/engine/install/debian/)
- [Docker daemon proxy](https://docs.docker.com/engine/daemon/proxy/)
- [Docker with iptables](https://docs.docker.com/engine/network/firewall-iptables/)
- [Browserless open-source Docker deployment](https://docs.browserless.io/enterprise/open-source)
- [Linux.do 天翼云电脑 Debian 实践](https://linux.do/t/topic/654530)
