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

主选择组必须使用全大写 `PROXY`，广告 provider 的 `proxy` 和最终 `MATCH` 也要引用同名组。远程模式按区分大小写的名称合并，使用 `PROXY` 才能覆盖面板默认组；写成 `Proxy` 会让两组同时保留。正常情况下，代理页只显示一个主选择组 `PROXY`，内含 `Auto` 及实际匹配到的 `Hysteria2` / `Vless` 节点。[分组合并源码](https://github.com/MHSanaei/3x-ui/blob/v3.7.0/internal/sub/clash_service.go#L1021-L1062)

从旧配置更新后，在 `PROXY` 中手动选择一次 `Auto`。`store-selected: true` 会恢复以前同名组的选择，因此旧的 `Vless` 选择可能覆盖 `default-selected: Auto`；不需要清空缓存。[选择恢复源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.29/hub/executor/executor.go#L439-L467)

## 每台电脑只做一次的配置

以 Clash Verge Rev 2.5.2 为例：

1. 导入并选中 3x-ui 的 Clash/Mihomo 订阅。
2. 右键这张订阅卡片，打开“扩展配置”（Merge），将 `dmit-client.yaml` 全文粘贴进去并保存。如果已有自定义扩展，先备份并合并，不要直接覆盖。
3. 界面选择“规则”模式；设置 → Clash 设置 → 关闭 IPv6。
4. 关闭“DNS 覆写”，让订阅扩展文件成为 DNS 的配置来源。
5. 按本机需要启用系统代理或 TUN，并完成系统权限授权。端口、DNS 监听地址、控制器和网卡绑定由本机管理。

不要将 `dmit-client.yaml` 拖入订阅页作为独立本地订阅，它没有节点；也不要直接编辑下载得到的订阅原文件，因为更新订阅会替换原文件。订阅扩展只作用于这张订阅卡片，不需要同时复制到全局扩展。[Clash Verge 扩展配置文档](https://www.clashverge.dev/guide/extend.html)

Clash Verge 2.5.2 最终以界面的 `mode`、顶层 `ipv6` 等设置为准，Merge 中的同名值不能代替第 3 步。开启“DNS 覆写”时，界面的 `dns.ipv6` 也会被恢复；并不是所有 DNS 字段都比 Merge 优先。[客户端合并源码](https://github.com/clash-verge-rev/clash-verge-rev/blob/v2.5.2/src-tauri/src/enhance/mod.rs)

DNS 沿用现有选择：国外 DoH、直连目标使用国内 DNS、代理节点用国内 DNS 解析；本次没有将国内 UDP DNS 改为 DoH。不固定 `dns.listen`，保留 `fallback: []`，省略因未启用 fallback 而无效的 `fallback-filter`。

## 更新和换机

- 主规则：修改并发布 `dmit-rules.yaml` 后，3x-ui 重新拉取，客户端再更新用户订阅。v3.7 有 10 分钟缓存，并非实时同步；网络故障时可能继续使用上次成功缓存。
- 广告规则：现有 GitHub Actions 负责更新转换后的 provider；客户端按 `interval: 86400` 拉取。工作流停用或失败、客户端离线都会延迟更新，不保证与上游发布同时生效。
- 客户端配置：修改 `dmit-client.yaml` 后，需要重新复制到每台电脑的订阅扩展；不会通过 3x-ui 更新。换电脑时重复上面的“一次配置”步骤即可。
- 节点选择：`Auto` 按名称引入 `Hysteria2`、`Vless`。Mihomo v1.19.29 会按名称排序，因此 Hysteria2 优先，Vless 备用。两者都没有匹配时使用 `REJECT`，不会自动变成直连。若 3x-ui 节点改名，需要同步修改两个组的 `filter`。[Mihomo 排序源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.29/config/config.go)、[过滤与空组处理](https://github.com/MetaCubeX/mihomo/blob/v1.19.29/adapter/outboundgroup/parser.go)

## 使用前检查

修改规则后，先从仓库根目录运行离线合并回归检查（Ruby 标准库，按 3x-ui v3.7 源码建模）：

```bash
ruby script/clash/test-dmit-routing.rb
```

更新订阅后查看客户端最终运行配置，而不只是仓库文件：确认 `mode: rule`、`ipv6: false`、`dns.ipv6: false`，同时确认动态节点、策略组、广告 provider 和国内直连/其余代理规则仍在。已有全局脚本、订阅脚本或可视化规则编辑也可能影响最终结果。
