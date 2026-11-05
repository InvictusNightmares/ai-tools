# 钉钉定位链路分析结论

分析时间：2026-11-05 16:30–16:32
设备：iPhone，iOS 26.6.1
钉钉进程：`DingTalk`（PID 440）

## 1. 钉钉的定位来源是 CoreLocation

钉钉进程的 syslog 中出现完整的 CoreLocation 调用链：

```text
DingTalk{CoreLocation}[440] CLLocationManager
DingTalk{LocationSupport}[440] kCLConnectionMessageLocation
DingTalk{CoreLocation}[440] dt_startUpdatingLocation
DingTalk{CoreLocation}[440] locationManager:didUpdateLocations:
```

定位参数：

```text
setDesiredAccuracy: -1.000000              # 最高精度
setDistanceFilter: 100.000000              # 100 米更新一次
setPausesLocationUpdatesAutomatically: 0   # 不自动暂停
setAllowsBackgroundLocationUpdates: 0
```

另有一个粗精度 manager：

```text
setDesiredAccuracy: 12000.000000           # 约 3 公里，城市级
```

结论：钉钉只消费 CoreLocation 返回的 `CLLocation`，不自己扫描 Wi-Fi 或读取 BSSID。

## 2. 高德 SDK 负责地址解析

钉钉进程日志中出现：

```text
com.autonavi.locationUserDefault
amap_foundation_network_userdefault
dualstack-arestapi.amap.com
```

`arestapi.amap.com` 是高德逆地理编码接口，用于把坐标转换成地址。高德 SDK 可能还会参与网络定位修正，但本次日志的直接定位来源仍是 `CLLocationManager`。

## 3. 系统当时使用 Wi-Fi 定位

`locationd` 日志中的关键证据：

```text
CLWifiLocationProvider
numAps,19
haveLoc,1
stationaryProbability,0.986
gpsOutdoor,-1
wifiIndoor,-1
```

含义：

- 扫到了 19 个 AP
- 设备处于室内、静止
- 没有有效的 GPS 户外信号
- 系统正在使用 Wi-Fi 定位结果

这说明 BSSID 克隆方案的攻击面是真实存在的：iOS 会把扫描到的 BSSID 列表发给 Apple 的 WLOC 服务，Apple 返回这些 BSSID 对应的坐标。

补充网络环境：抓包时手机数据走 **5G**，**没有连接公司 Wi-Fi**。但 Wi-Fi 开关是打开的，`locationd` 仍扫描到 19 个附近 AP。也就是说：

- 数据链路和定位链路是分开的：钉钉用 5G 联网，系统用 Wi-Fi 扫描结果做网络定位。
- BSSID 克隆不需要给手机提供互联网，手机保持 5G 即可。
- 如果担心 5G 基站定位干扰，可以让手机进入飞行模式 + 只开 Wi-Fi；此时伪 AP 需要提供上行网络，钉钉才能打卡。

这也解释了“手机没连公司 Wi-Fi 也能打卡”：**钉钉只看位置，不看手机是否关联了公司 Wi-Fi**。对 BSSID 方案的含义是：

- 手机保持 5G 即可，不需要连接公司 Wi-Fi。
- 但 **Wi-Fi 开关必须打开**，让系统能扫描到伪 AP；Wi-Fi 关闭时只剩基站/GPS，BSSID 方案失效。
- 伪 AP 不需要提供互联网；它只是一个“定位信标”。
- 伪 AP 的 BSSID 必须来自 Apple 数据库里真实存在于办公室附近的 AP，否则 Apple 不会返回办公室坐标。

## 4. 网络抓包结果

`dingtalk-checkin.pcap` 中共 180 个包，TLS SNI 中观察到：

```text
down-sr.dingtalk.com
bird.cn-hangzhou.log.aliyuncs.com
px.effirst.com
```

- `down-sr.dingtalk.com`：钉钉资源下载
- `bird.cn-hangzhou.log.aliyuncs.com`：阿里日志上报
- `px.effirst.com`：统计/追踪

抓包中的目标地址大部分位于 `198.18.0.0/15`，这是 iPhone 上 TUN/代理的 fake IP 段，说明抓包时手机有代理在接管流量。打卡接口本身是 TLS，未解密，因此没有看到请求体。

## 5. 模拟定位检测痕迹

在钉钉 syslog 中搜索以下关键词：

```text
isSimulatedBySoftware
isProducedByAccessory
mock location
spoof
fake location
```

没有发现钉钉主动读取或记录这些标志。唯一匹配到 `mock` 的是 WebKit 的偏好键（`WebKit2MockScrollbarsEnabled` 等），与定位无关。

注意：**日志中没有不等于代码中没有**。钉钉可能在原生代码或风控请求里静默读取 `CLLocation.sourceInformation`，只是不打日志。因此不能据此认定开发者模拟一定安全。

## 6. 对现有方案的影响

| 方案 | 是否经过 CoreLocation | 是否带模拟标志 | 当前状态 |
|---|---|---|---|
| wloc / MITM | 是 | 无 | 被 Apple 的 `gs-loc` 证书 pinning 封死 |
| BSSID 克隆 | 是（Wi-Fi 定位输入） | 无 | 可行，取决于目标 BSSID 是否在 Apple 库 |
| 开发者模拟定位 | 是 | `isSimulatedBySoftware=true` | 可用，但可能被强风控识别 |
| 外接 GPS / 尾插 | 是 | `isProducedByAccessory=true` | 可用，风控策略因 App 而异 |
| 真机放公司 | 是（真实 GPS/Wi-Fi） | 无 | 最稳，但需要物理设备 |

## 7. 推荐路线

1. **优先 BSSID 克隆**：不产生模拟标志，DingTalk 也拿不到 BSSID（iOS 不向普通 App 开放）。
2. 手机可以继续用 5G；Wi-Fi 开关保持打开，不一定要连接伪 AP。伪 AP 只需要广播目标 BSSID。
3. 如果 5G 基站定位干扰明显，再切飞行模式 + 只开 Wi-Fi；此时给伪 AP 提供上行网络，让钉钉能联网打卡。
4. 测试时关闭 wloc 模块和 `gs-loc` 的 MITM，让 `locationd` 正常访问 Apple。
5. 克隆 2～3 个办公室同 SSID 的 AP，提高定位收敛。
6. 开发者模拟可作为临时备用方案，但先用非关键设备验证钉钉是否识别 `isSimulatedBySoftware`。

## 8. Apple WLOC 实测验证

用 [apple_wloc_lookup.py](../scripts/apple_wloc_lookup.py) 直接查询 Apple 的 `gs-loc.apple.com/clls/wloc`：

```bash
python3 scripts/apple_wloc_lookup.py AA:BB:CC:DD:EE:FF --near 12 --radius 50
```

结果：

- 目标 BSSID 在 Apple 数据库中**存在**
- 返回坐标落在办公室区域（具体值保存在 `artifacts/office-ap.txt`）
- 50 米内还有 32 个 Apple 已知的 BSSID，可作为克隆候选

这一步很关键：WiGLE、Google、mylnikov 查不到，只是因为它们没有这个 AP 的数据；Apple 自己的库有办公室 AP 的记录。BSSID 方案不是猜测，数据库层面已经验证可行。

## 9. 打卡范围的含义

钉钉打卡是**地理围栏**判断，不是 Wi-Fi 关联判断：

- 只要上报的坐标落在管理员设置的打卡范围内（常见 100m / 300m / 500m / 1000m），就能打卡。
- 不要求手机连接公司 Wi-Fi，也不要求人进入办公室；手机用 5G、在公司附近一样能打卡。
- 因此 BSSID 候选不必是办公室那台 AP，可以是**围栏内任意一个真实存在于 Apple 数据库的 AP**（同楼、楼下商铺、附近路口都可以）。
- 越靠近围栏中心越稳；围栏越小（例如 100m），越建议克隆 2～3 个同区域的 BSSID 来收敛定位。

## 附录：在 macOS 上采集办公室 BSSID

macOS 默认会对 SSID/BSSID 脱敏，`wdutil info`、`system_profiler`、`ioreg` 都可能显示 `<redacted>` 或 `00:00:00:00:00:00`。可用以下方式之一：

1. **无线诊断（推荐，无需 sudo）**
   - 按住 Option 点菜单栏 Wi-Fi 图标 → Open Wireless Diagnostics
   - 忽略向导，菜单栏 Window → Scan
   - 找到目标 SSID，记录 BSSID、信道、RSSI；同 SSID 有多个 AP 时记 2～3 个
2. **给终端位置权限**
   - 系统设置 → 隐私与安全性 → 定位服务 → 打开终端 App（Terminal / iTerm）的定位权限
   - 退出并重开终端，再运行 `sudo wdutil info`
3. **Windows**
   - `netsh wlan show networks mode=bssid`
4. **Android**
   - WiFi Analyzer 类 App 可直接看到 BSSID、信道、信号强度
5. **WiGLE**
   - 按 SSID 或公司坐标搜索，NetID 即 BSSID

注意：如果原 AP 在 5GHz（例如 channel 44），克隆时尽量使用同一频段和信道；只有 2.4GHz 的路由器也可以从同区域找一个 2.4GHz 的 BSSID 来克隆。

已采集到一个办公室 5GHz AP，真实 SSID/BSSID/信道保存在 `artifacts/office-ap.txt`。对应的办公室克隆脚本是 `scripts/openwrt-clone-office-ap.local.sh`；通用模板见 `scripts/openwrt-clone-office-ap.sh`。

## 10. 局限

- 打卡接口是 TLS，未解密；无法确认钉钉是否把 `sourceInformation` 或 Wi-Fi 信息放进请求体。
- 未在钉钉二进制中做字符串/反编译分析（App Store 二进制受 FairPlay 加密）。
- 抓包时手机存在 TUN/代理，部分流量以 fake IP 形式出现，域名覆盖不完整。
