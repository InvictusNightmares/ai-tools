# Clash Verge Rev 2.5.5：DMIT 本机设置样例

这个样例按 2026-09-23 截图中的 DMIT 订阅 Merge 改写：原配置有 9 条 `dns.fake-ip-filter` 和 2 条 `tun.route-exclude-address`。2.5.5 提示这些值被应用设置接管；需要把仍然需要的值填在对应的设置页，再从 Merge 中删除重复项。[2.5.5 配置合并源码](https://github.com/clash-verge-rev/clash-verge-rev/blob/v2.5.5/src-tauri/src/enhance/mod.rs)

下面是原 Merge 的**脱敏对照**，不是 2.5.5 中要再次粘贴的配置。两个内网地址和跳板机域名使用不能直接应用的占位符；其余 8 条过滤项与截图保持一致。填写界面时必须从原配置复制实际值，不要复制占位符，也不要把本机内网地址或公司域名提交到公开仓库。

```yaml
# 旧订阅扩展：仅用于核对，不能直接作为新的 Merge 使用
dns:
  fake-ip-filter:
    - '*.lan'
    - '*.local'
    - '*.arpa'
    - 'time.*.com'
    - 'ntp.*.com'
    - localhost.ptlogin2.qq.com
    - '*.msftncsi.com'
    - www.msftconnecttest.com
    - <原配置中的跳板机域名>
tun:
  route-exclude-address:
    - <原配置中的内网地址 1>/32
    - <原配置中的内网地址 2>/32
```

## 按截图迁移

本机当前的 DNS 覆写列表已经有前 8 条通用过滤项，缺的是最后一条跳板机域名；TUN 设置中的路由排除列表当前为空，缺的是原 Merge 中的两个地址。按以下位置填写，替换示例值时使用你原配置里的对应值：

| 位置 | 示例填写值 | 作用范围 |
| --- | --- | --- |
| 设置 → TUN → 路由排除地址 | 原 Merge 中的 2 条实际 CIDR，不能填占位符 | 本机 TUN 设置，切换其他订阅也会使用 |
| DMIT 订阅启用 DNS 覆写；DNS 覆写 → Fake-IP 过滤 | 保留已有 8 条，只添加原 Merge 中的实际跳板机域名 | 应用保存的 DNS 覆写内容；当前只有 DMIT 订阅启用 |

保留 DNS 覆写页原有的过滤条目和其他 DNS 设置，不要用示例值替换整张列表。`route-exclude-address` 只在启用 TUN 自动路由时用于排除目标网段；`fake-ip-filter` 让匹配的域名不使用 Fake-IP 映射。[Mihomo TUN 文档](https://wiki.metacubex.one/config/inbound/tun/)、[DNS 文档](https://wiki.metacubex.one/config/dns/)

随后右键 DMIT 订阅卡片，打开「扩展配置」，删除其中的 `tun.route-exclude-address` 和 `dns.fake-ip-filter`。截图中的 Merge 只有这两部分；确认没有其他内容后，可以不再关联这份 Merge。这里不改 3x-ui 的在线规则或节点订阅。仓库里的 [dmit-client.yaml](dmit-client.yaml) 是关闭 DNS 覆写时使用的另一种配置方式，不要把它整份叠加到这个样例上。

切回 DMIT 订阅后，检查警告是否消失，并在 Clash Verge 的最终生成配置中确认：

- `tun.route-exclude-address` 包含实际要绕过 TUN 的地址。
- `dns.fake-ip-filter` 保留原有条目，并包含实际要排除 Fake-IP 的域名。
- `mode: rule`，主规则仍以 `MATCH,PROXY` 结尾。

最后实际访问对应的内网地址和域名。生成配置正确，只能证明配置已合并，不能代替连通性检查。
