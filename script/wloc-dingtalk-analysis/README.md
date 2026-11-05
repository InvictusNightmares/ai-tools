# 钉钉 iOS 定位链路抓包分析

- 分析日期：2026-11-05
- 设备环境：iPhone，iOS 26.6.1
- 分析目标：确认钉钉打卡时如何获取定位，评估 wloc 失效后的替代方案

## 结论（TL;DR）

1. **钉钉不自己定位。** 它通过 iOS `CoreLocation` 的 `CLLocationManager` 获取坐标，日志中可见 `dt_startUpdatingLocation` 与 `didUpdateLocations`。
2. **高德 SDK 只做地址解析。** 日志中出现 `dualstack-arestapi.amap.com` 与 `com.autonavi.locationUserDefault`，用于把经纬度逆地理编码成地址，不是定位源。
3. **系统当时在用 Wi-Fi 定位。** `locationd` 日志显示 `CLWifiLocationProvider`、`numAps=19`、室内静止、无 GPS 户外信号。注意：手机数据走 5G、未连接公司 Wi-Fi，但 Wi-Fi 开关是开的，系统仍在扫描附近 AP——数据链路和定位链路是分开的。
4. **BSSID 克隆方案作用在 CoreLocation 的上游**，理论上可行，且不会产生 `isSimulatedBySoftware` 标志。
5. **打卡不依赖公司 Wi-Fi 关联。** 手机用 5G、不连公司 Wi-Fi 也能打卡，说明钉钉只看位置；BSSID 方案中手机可以继续用 5G，但 Wi-Fi 开关必须打开以扫描伪 AP。
6. **打卡是地理围栏，不是精确到工位。** 只要坐标落在公司设置的打卡范围内即可；BSSID 不一定要克隆办公室那台 AP，围栏内任意真实 AP 都可以，越靠近中心越稳。
7. **Apple WLOC 数据库已确认目标 BSSID 存在。** 直接查询 `gs-loc.apple.com` 返回了办公室附近的坐标；WiGLE/Google 搜不到不代表 Apple 没有，Apple 的库是私有的。查询工具见 [apple_wloc_lookup.py](scripts/apple_wloc_lookup.py)，具体坐标与候选 BSSID 保存在 `artifacts/office-ap.txt`。
8. **没有在钉钉日志中发现模拟定位检测痕迹**，但这不能证明它不检查；强风控应用可能静默读取 `CLLocation.sourceInformation`。

> 家用路由器 H3C NX15000 的原厂固件不支持修改 AP BSSID，也没有 OpenWrt 适配。推荐保留它做主路由，另加一台便宜的 OpenWrt AP 专门广播克隆 BSSID。详见 [router-options.md](results/router-options.md)。
>
> 如果能在办公室长期放一台备用 iPhone，也可以走「真实设备 + 真实位置」的远程打卡路线，风控最低；详见 [remote-device-options.md](results/remote-device-options.md)。

## 目录结构

项目位置：`script/wloc-dingtalk-analysis/`。

```
wloc-dingtalk-analysis/
├── README.md
├── artifacts/                     # 原始抓包与系统日志（已纳入版本库）
│   ├── dingtalk-checkin.pcap
│   ├── dingtalk-checkin-syslog.json
│   ├── locationd-checkin.pcap
│   ├── locationd-checkin-syslog.json
│   └── office-ap.txt              # 办公室 SSID/BSSID/坐标
├── results/
│   ├── findings.md                # 完整分析结论
│   ├── endpoints.txt              # 抓到的公开域名
│   ├── locationd-evidence.txt     # locationd 的 Wi-Fi 定位证据
│   ├── pcap-analysis.txt          # 抓包摘要（已脱敏）
│   ├── router-options.md          # H3C NX15000 与 OpenWrt AP 方案
│   ├── remote-device-options.md   # 备用机 / WDA / 云真机方案对比
│   └── developer-simulation-test.md # 开发者模拟实测：天气变了，地图/钉钉没变
└── scripts/
    ├── analyze_pcap.py            # pcap/pcapng DNS、SNI、端点提取
    ├── capture_dingtalk.sh       # 只抓 DingTalk 进程的 USB 抓包脚本
    ├── apple_wloc_lookup.py      # 直接查询 Apple WLOC：BSSID 坐标 + 附近 AP
    ├── developer-simulation-commands.md # 模拟定位命令（含公司坐标）
    ├── simulate-location.local.sh # 本地快捷脚本（北京/公司/清除）
    ├── simulate-location.sh      # 通用模拟定位包装脚本（env 传入坐标）
    ├── openwrt-clone-office-ap.local.sh # 针对本办公室的克隆脚本
    └── openwrt-clone-office-ap.sh # 通用 OpenWrt BSSID 克隆模板
```

## 模拟定位命令

完整操作文档：[scripts/developer-simulation-commands.md](scripts/developer-simulation-commands.md)

常用命令：

```bash
# 北京
pymobiledevice3 developer dvt simulate-location set -- 39.908700 116.397500

# 公司
pymobiledevice3 developer dvt simulate-location set -- 31.19161987 121.28696441

# 清除
pymobiledevice3 developer dvt simulate-location clear
```

## 复现方法

```bash
# 1. 安装 pymobiledevice3（永久 venv，软链到全局 PATH）
python3 -m venv ~/.venv/pmd3
~/.venv/pmd3/bin/pip install -U pymobiledevice3 dpkt
ln -sf ~/.venv/pmd3/bin/pymobiledevice3 ~/.local/bin/pymobiledevice3
# ~/.local/bin 已在 PATH 中，之后可直接运行 pymobiledevice3

# 2. iPhone 用 USB 连接，解锁并信任此电脑
pymobiledevice3 usbmux list --simple

# 3. 找到钉钉进程
pymobiledevice3 processes ps | grep -i ding

# 4. 抓钉钉进程的包
pymobiledevice3 pcap --process DingTalk --out dingtalk.pcap

# 5. 抓 syslog
pymobiledevice3 syslog live --process-name DingTalk --out dingtalk-syslog.json

# 6. 分析（用装了 dpkt 的 venv）
~/.venv/pmd3/bin/python scripts/analyze_pcap.py dingtalk.pcap
```

抓包时在 iPhone 上打开钉钉 → 打卡页面，刷新或点一次打卡，保持前台 20～30 秒。

## 隐私说明

`artifacts/` 中的原始 pcap 和 syslog 已按用户要求纳入版本库。经检查，日志中没有出现联系人姓名、手机号、邮箱或凭据；内容主要是 WebKit、CoreLocation 和网络端点诊断信息。

`artifacts/office-ap.txt`、`scripts/developer-simulation-commands.md`、`scripts/simulate-location.local.sh` 和 `scripts/openwrt-clone-office-ap.local.sh` 含办公室 SSID/BSSID/坐标，也按用户要求直接纳入版本库。

## 关联背景

- Apple 2026-11-04 起的 `gs-loc.apple.com` 证书 pinning 问题：
  - https://github.com/Yu9191/wloc/issues/130
  - https://github.com/Yu9191/wloc/issues/123
- wloc 项目：https://github.com/Yu9191/wloc
