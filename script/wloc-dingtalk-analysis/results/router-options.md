# 家用路由器方案：H3C NX15000

## 结论

H3C Magic NX15000 的原厂固件**不能修改 AP 的 BSSID**：

- 无线设置只暴露 SSID、信道、频宽、加密方式、TWT/OFDMA 等。
- 「MAC 地址克隆」只作用于 **WAN 口**，不影响 Wi-Fi BSSID。
- 没有官方 OpenWrt 适配；社区讨论到 2024 年仍无第三方固件。
- 硬件是 IPQ5018 + IPQ5000 + 3× QCN9074，Flash 128MB/16MB。即使硬件可玩，刷机风险高，不建议动主路由。

## 推荐方案

保留 NX15000 作为主路由，增加一台便宜的 OpenWrt AP，专门广播克隆的 BSSID：

| 设备 | 说明 |
|---|---|
| GL.iNet MT3000（Slate AX） | 双频 Wi-Fi 6，OpenWrt，开箱即用，最省事 |
| Xiaomi AX3000T | MT7981，OpenWrt 支持好，价格低，需要解锁 SSH/刷机 |
| Redmi AX6S / AX6000 | OpenWrt 支持成熟 |
| Netgear R7800 | 老牌 OpenWrt 机型，5GHz 稳定 |

要求：

- 5GHz 可设 channel 44、40MHz
- 可以修改 AP 的 MAC/BSSID
- 建议 MediaTek / Qualcomm 芯片，避免 Broadcom（MAC 修改限制多）

连接方式：

```text
NX15000 LAN ──网线──> OpenWrt AP 的 WAN/LAN
OpenWrt AP 5GHz: SSID=OFFICE_SSID, BSSID=OFFICE_BSSID, channel=44
iPhone: Wi-Fi 打开，5G 可用；放在 AP 旁边
```

## 不建议

- **刷 NX15000 为 OpenWrt**：无官方/社区固件，变砖风险高。
- **用 WAN MAC 克隆**：只影响 WAN，不影响 Wi-Fi BSSID。
- **用访客网络/Mesh**：BSSID 仍是 NX15000 自己的，不是目标 AP。
- **用无线中继模式**：中继器会用自己的 BSSID 重新广播，克隆不了目标 BSSID。

## 非要动 NX15000 的话

需要拿到 root shell（UART 或隐藏 telnet/SSH），找到 hostapd 配置，给某个 5GHz VAP 加 `bssid=...` 并重启 hostapd。问题：

- 原厂固件可能有完整性校验/回滚
- 没有 OpenWrt 端口，改坏了很难恢复
- 主路由一挂，全家断网

风险远高于买一台几十到几百元的 OpenWrt AP。

## 备选（不想买硬件）

- 开发者定位模拟：pymobiledevice3 / Xcode，带 `isSimulatedBySoftware` 标志
- 外接 GPS 尾插：带 `isProducedByAccessory` 标志
- 老设备/备用机：只有在受信任资产版本仍为 1013 时才有效，联网会被推送到 1014
