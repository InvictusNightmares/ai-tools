# 公司 VPN 与 Clash 并用的最小修复提案

2026-09-16 08:58（北京时间），只读诊断，尚未改动 Clash。

- 仓库 `config/clash/dmit-rules.yaml` 与运行时都已有 `DOMAIN-SUFFIX,spicrhdk.com,DIRECT`、GPU 和前置地址的 IP 直连规则。控制器显示公司域名规则已命中 41 次，不能把故障归因为缺少 DIRECT。
- 当前为规则模式，TUN 开启，`route-exclude-address` 为空；系统对 GPU `192.168.64.16` 的路由指向 Clash 的 `utun8` / `198.18.0.1`。
- SSH 系统解析为 `198.18.0.195`，TCP 建立后在 SSH banner 交换阶段被关闭。Mihomo DNS 查询得到堡垒机真实 A 记录 `10.1.88.2`。
- 用户实测开 Clash 时失败；上述证据支持 TUN 与公司 VPN 路径冲突的判断，具体恢复效果须修改后测量。

## 待确认的修改

只修改当前订阅的客户端 Merge `profiles/mHXJsCWbAzhL.yaml`，先备份。保留原有 fake-IP 例外，追加堡垒机精确域名，并合并两个 TUN 排除地址：

```yaml
dns:
  fake-ip-filter:
    # 此处保留已有条目
    - jumpserver.spicrhdk.com
tun:
  route-exclude-address:
    - 10.1.88.2/32
    - 192.168.64.16/32
```

不把这段添加到只接受路由组/规则的 3x-ui 远程规则文件。预备合并文件为 `/tmp/gateway-company-vpn-merge.yaml`。使用客户端现有重载机制使订阅扩展生效，再核对最终配置、真实 DNS、系统路由、三个 SSH 别名和 Guard `/readyz`。排除 TUN 后仍依赖公司 VPN 的既有可达路径；若验证不通过，恢复备份。4000/4001 与服务器配置不属于本次改动。

字段依据：[Mihomo DNS](https://wiki.metacubex.one/config/dns/)、[Mihomo TUN](https://wiki.metacubex.one/config/inbound/tun/)。

## 用户手动应用后的核验

2026-09-16 09:07：用户完成客户端配置并启用公司 VPN。实际运行配置包含原有 8 条 fake-IP 排除和新增堡垒机域名，两个 TUN 排除均在；三个 SSH 别名直接执行 hostname/date 成功，Guard ready。由用户手动修改，代理路由文件未动。第一次粘贴曾覆盖 DNS 数组，现已补回；Merge 的数组替换语义见官方 2.5.2 merge.rs。
