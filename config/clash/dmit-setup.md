# DMIT：在线规则与客户端配置

目标：保留已确认的直连例外和广告拦截，国内 DIRECT，其余 PROXY。

## 配置分工

| 内容 | 放置位置 | 通过 3x-ui 在线规则链接下发 |
| --- | --- | --- |
| `proxy-groups`、`rule-providers`、`rules` | [dmit-rules.yaml](dmit-rules.yaml) | 可以 |
| DNS、`profile`、规则模式和 IPv6 默认值 | [dmit-client.yaml](dmit-client.yaml)，客户端订阅扩展配置 | 不可以 |
| 系统代理、TUN、端口、局域网访问、控制器、网卡 | 每台电脑的客户端设置 | 不可以；也不在模板中固定 |
| 节点地址和认证信息 `proxies` | 3x-ui 根据用户订阅动态生成 | 随用户订阅下发，不写进公开规则文件 |

3x-ui v3.7 的远程 URL 模式只接受第一行的三个顶层键，其他键会被忽略。这里选用在线模式，不使用内联完整 YAML。[官方合并源码](https://github.com/MHSanaei/3x-ui/blob/v3.7.0/internal/sub/clash_service.go)

## 3x-ui 填什么

1. 先将本地规则改动发布到 GitHub 的 `main` 分支；仅保存本地文件不会改变在线内容。
2. 在 3x-ui 的订阅设置中启用 Clash/Mihomo 订阅及对应的路由规则开关。
3. 在 Clash/Mihomo 的“全局路由规则”输入框中，只填写下面这一条 HTTPS 地址，保存：

```text
https://raw.githubusercontent.com/InvictusNightmares/ai-tools/main/config/clash/dmit-rules.yaml
```

不要填 GitHub 的 `blob` 网页地址、`dmit-client.yaml`、广告 provider 的文本地址，也不要把这个地址填到 Xray 服务端路由设置。

客户端仍导入 3x-ui 为用户生成的 **Clash/Mihomo 订阅链接**，不是上面的规则链接。规则链接本身不包含代理节点，不能当独立订阅使用。

首次拉取是异步的，缓存尚未准备好或下载失败时，订阅可能暂时只有默认规则；稍后更新订阅，并检查生成配置是否包含 `Auto`（隐藏组）、`PROXY`、广告 provider 和末尾的 `MATCH,PROXY`。不能仅凭“保存成功”认定规则已下发。[远程加载源码](https://github.com/MHSanaei/3x-ui/blob/v3.7.0/internal/sub/remote_routing.go)

主选择组必须使用全大写 `PROXY`，广告 provider 的 `proxy` 和最终 `MATCH` 也要引用同名组。远程模式按区分大小写的名称合并，使用 `PROXY` 才能覆盖面板默认组；写成 `Proxy` 会让两组同时保留。代理页只显示一个主选择组 `PROXY`，内含 `Auto`、两个 US 直连节点、`SG-Vless` 直连和一个 DMIT 服务端中转节点。筛选同时兼容旧名称 `Hysteria2` / `Vless`，避免分批改名时漏掉节点。[分组合并源码](https://github.com/MHSanaei/3x-ui/blob/v3.7.0/internal/sub/clash_service.go#L1021-L1062)

## DMIT 服务端中转到 SG

两端独立运行 3x-ui v3.11.0。`zc` 是自用的合并订阅，Clash 主选择组提供以下四个节点；`zm` 保持原有两个 US 节点，不添加 SG 外部订阅或中转绑定。

| 节点 | 客户端连接 | DMIT 到 SG | 最终出口 |
| --- | --- | --- | --- |
| `US-Hysteria2` | DMIT UDP 443 / Hysteria2 | — | US |
| `US-Vless` | DMIT TCP 443 / VLESS REALITY | — | US |
| `SG-Vless` | SG TCP 443 / VLESS REALITY | — | SG |
| `US-Vless-SG-Hysteria2` | DMIT TCP 8443 / VLESS REALITY | SG UDP 443 / Hysteria2 | SG |

中转复用 `zc` 的用户身份，绑定独立的 VLESS 入站（ID 5，TCP 8443，标签 `in-8443-tcp`）。Xray 按这个入站标签路由到 `sg-hysteria2` 出站，不按用户邮箱切换出口，因此 `zc` 的原有 US 节点仍从 DMIT 出口。`zm` 只绑定原有 TCP/UDP 443 入站，凭据、额度和重置配置保持独立。中转节点不加入 `Auto`。

DMIT 从 `zc` 的入站绑定直接生成三个 DMIT 节点，再通过一条 SG Raw/Base64 外部订阅导入 `SG-Vless`。不再维护四个独立中转用户或四条静态分享链接。SG-Hysteria2 入站仅从订阅中隐藏，服务仍供 DMIT 中转使用。客户端将中转节点视为普通 VLESS 节点，不需要配置 `dialer-proxy`。

`zc` 另有一条 `US-Vless-iOS` 外部分享链接。该名称不匹配当前 Clash 的 `PROXY` 过滤器，因此完整订阅包含五条记录，Clash 主选择组仍显示四个节点。维护中转入口时保留这条独立分享链接。

订阅地址和认证信息只保存在私有配置中。修改 DMIT 中转入口端口后，更新原 `zc` 订阅即可获取新端口，订阅链接不变。修改 SG-Hysteria2 凭据或传输参数时，需要同步更新 DMIT 的 `sg-hysteria2` 出站；模板中仍保留的 `sg-vless` 出站没有绑定当前中转规则。中转配置保存在面板的 Xray 模板中，不直接修改运行时生成的 `config.json`。

DMIT 的三个 `zc` 入站绑定共享同一用户额度和用量，中转也计入 `zc`；SG 的 `sg-self` 汇总 SG 两个协议的用量。中转会消耗两台 VPS 的流量，统一订阅不会合并供应商额度。

从旧配置更新后，在 `PROXY` 中手动选择一次 `Auto`。`store-selected: true` 会恢复以前同名组的选择，因此旧的 `Vless` 选择可能覆盖 `default-selected: Auto`；不需要清空缓存。[选择恢复源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.29/hub/executor/executor.go#L439-L467)

## 端口与证书续期

DMIT 的 TCP 80 专供 acme.sh standalone HTTP-01 验证，不能再分配给 Xray 入站。TCP 8443 承载 `zc` 中转，需同时存在于 `/opt/3x-ui/docker-compose.yml` 的端口映射和 `/usr/local/sbin/dmit-firewall-apply` 的 IPv4 Docker 入站允许列表。TCP/UDP 443、TCP 2096 订阅和 TCP 47075 管理入口保持原用途。

DMIT 的证书和 ACME 状态分别持久化在 `/opt/3x-ui/cert`、`/opt/3x-ui/acme`；容器中的 cron 每天运行四次续期检查，成功后通过 `x-ui restart` 重载面板后端和 Xray。公网管理入口的 Nginx 共享同一证书目录，由 `edge-gateway-reload.timer` 每日重载；维护时可执行 `systemctl start edge-gateway-reload.service` 立即加载新证书，再核对 2096、47075 返回的证书。检查 80 是否空闲时，应检查容器内监听；宿主机的 Docker 端口映射占用 80 属于预期。[acme.sh standalone 要求](https://github.com/acmesh-official/acme.sh#3-standalone-mode)

SG 使用宿主机 `sg-3xui-cert-renew.timer` 每天检查四次，80 不映射进 3x-ui 容器，续期后由 `/opt/3x-ui/reload-cert.sh` 重启容器加载证书。不要把正式证书、ACME 账号密钥、数据库或这些长期运行文件当作临时文件清理。

## SG 额度与重置

SG 的 `sg-self` 用户及两个入站统一设为 `traffic_reset=monthly`、`traffic_reset_day=29`，按服务器 `Asia/Shanghai` 时区运行；不足 29 天的月份在最后一天重置。用户和入站额度均保留为 `1099511627776` 字节（1 TiB），修改日期不清空当前累计用量。[v3.11.0 周期重置实现](https://github.com/MHSanaei/3x-ui/blob/v3.11.0/internal/web/job/periodic_traffic_reset_job.go)

`reset_day` 属于到期自动续期配置，不能替代 `traffic_reset_day`；当前用户没有到期时间。维护时同时检查用户和入站的周期，否则任一较早的周期都可能清空关联用户用量。

面板额度按上传与下载合计限制，华为云套餐的 1024 GB 出站额度、实际账期和计费仍以云账单为准；探针用于辅助核对。调整 SG 不修改 DMIT 的 `zc`、`zm` 额度或重置周期。

## 每台电脑只做一次的配置

以 Clash Verge Rev 2.5.2 为例：

1. 导入并选中 3x-ui 的 Clash/Mihomo 订阅。
2. 右键这张订阅卡片，打开“扩展配置”（Merge），将 `dmit-client.yaml` 全文粘贴进去并保存。如果已有自定义扩展，先备份并合并，不要直接覆盖。
3. 界面选择“规则”模式；设置 → Clash 设置 → 关闭 IPv6。
4. 关闭“DNS 覆写”，让订阅扩展文件成为 DNS 的配置来源。
5. 按本机需要启用系统代理或 TUN，并完成系统权限授权。端口、DNS 监听地址、控制器和网卡绑定由本机管理。

不要将 `dmit-client.yaml` 拖入订阅页作为独立本地订阅，它没有节点；也不要直接编辑下载得到的订阅原文件，因为更新订阅会替换原文件。订阅扩展只作用于这张订阅卡片，不需要同时复制到全局扩展。[Clash Verge 扩展配置文档](https://www.clashverge.dev/guide/extend.html)

Clash Verge 2.5.2 最终以界面的 `mode`、顶层 `ipv6` 等设置为准，Merge 中的同名值不能代替第 3 步。开启“DNS 覆写”时，界面的 `dns.ipv6` 也会被恢复；并不是所有 DNS 字段都比 Merge 优先。[客户端合并源码](https://github.com/clash-verge-rev/clash-verge-rev/blob/v2.5.2/src-tauri/src/enhance/mod.rs)

若在 Clash Verge Rev 2.5.5 中选择保留 DNS 覆写，并遇到扩展字段被应用设置接管的警告，参考 [2.5.5 本机设置样例](dmit-verge-2.5.5-example.md)。该样例把冲突字段放在客户端设置页，与上面的 2.5.2 Merge 配置方式不要混用。

DNS 沿用现有选择：国外 DoH、直连目标使用国内 DNS、代理节点用国内 DNS 解析；本次没有将国内 UDP DNS 改为 DoH。不固定 `dns.listen`，保留 `fallback: []`，省略因未启用 fallback 而无效的 `fallback-filter`。

## 更新和换机

- 主规则：修改并发布 `dmit-rules.yaml` 后，3x-ui 重新拉取，客户端再更新用户订阅。v3.7 有 10 分钟缓存，并非实时同步；网络故障时可能继续使用上次成功缓存。
- 广告规则：现有 GitHub Actions 负责更新转换后的 provider；客户端按 `interval: 86400` 拉取。工作流停用或失败、客户端离线都会延迟更新，不保证与上游发布同时生效。
- 客户端配置：修改 `dmit-client.yaml` 后，需要重新复制到每台电脑的订阅扩展；不会通过 3x-ui 更新。换电脑时重复上面的“一次配置”步骤即可。
- 节点选择：`Auto` 只引入 `US-Hysteria2`、`US-Vless`（兼容旧名称 `Hysteria2`、`Vless`）；`SG-Vless` 和 `US-Vless-SG-Hysteria2` 通过 `PROXY` 手动选择。中转名称虽然以 `US-` 开头，也不能进入 `Auto`。现有过滤器保留其他中转名称的兼容匹配，但不会创建订阅中不存在的节点。`SG-Hysteria2` 直连不再展示。Mihomo v1.19.29 会按名称排序，因此 Hysteria2 优先，Vless 备用。没有匹配的 US/旧名称节点时，`Auto` 使用 `REJECT`。若 3x-ui 节点改名，需要同步修改两个组的 `filter`。[Mihomo 排序源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.29/config/config.go)、[过滤与空组处理](https://github.com/MetaCubeX/mihomo/blob/v1.19.29/adapter/outboundgroup/parser.go)

## 使用前检查

修改规则后，先从仓库根目录运行离线合并回归检查（Ruby 标准库，按 3x-ui v3.7 源码建模）：

```bash
ruby script/clash/test-dmit-routing.rb
```

更新订阅后查看客户端最终运行配置，而不只是仓库文件：确认 `mode: rule`、`ipv6: false`、`dns.ipv6: false`，同时确认动态节点、策略组、广告 provider 和国内直连/其余代理规则仍在。已有全局脚本、订阅脚本或可视化规则编辑也可能影响最终结果。

维护服务器后还应检查：DMIT 容器内 80 无常驻监听、8443 的中转规则已生成、证书续期及重载成功；`zc` 主选择组为上述四节点且中转出口为 SG，`zm` 仍只有两个 US 节点；SG 用户和两个入站的月重置日均为 29。逐项验证通过后，只删除本轮明确创建的备份和临时文件。
