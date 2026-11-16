# 非 root 真机签到自动化

目标：用一台 **非 root Android 手机** 跑中国移动 App，每天自动点签到。  
不需要 root、不需要 token、不需要 Frida、不需要和模拟器检测死磕。

## 前提

- 手机已登录中国移动 App，账号状态正常；
- 手机长期插电、联网；
- 开启 USB 调试；
- 接受和电脑/服务器的 ADB 授权。

## 方案 A：电脑/服务器用 ADB 控制

```bash
adb devices
python3 adb_checkin.py --device <serial>
```

首次可以先 dry-run：

```bash
python3 adb_checkin.py --device <serial> --dry-run
```

脚本流程：

```text
唤醒 + 解锁
启动 StartPageActivity
等首页
uiautomator dump 找“签到有礼”
点击
等 H5
找“签到/立即签到/补签”
点击
检查“成功/已签到”
```

如果 H5 文本没有暴露给 uiautomator，脚本会打印当前页面文本，方便你改用坐标。

### 通过 Tailscale / Wi-Fi ADB 远程跑

手机和服务器都加入同一个 Tailscale 网络后：

```bash
adb tcpip 5555
adb connect <手机TailscaleIP>:5555
adb devices
```

然后青龙/cron 定时：

```cron
30 8 * * * cd /path/to/cmcc-reverse/device && python3 adb_checkin.py --device <手机TailscaleIP>:5555 >> /tmp/cmcc_checkin.log 2>&1
```

注意：

- 手机 ADB over TCP 在重启后会失效，需要重新 `adb tcpip 5555`；
- 部分手机需要关闭“USB 调试安全设置”/允许网络 ADB；
- 手机锁屏可能需要先关闭密码或设置自动解锁。

## 方案 B：手机本地 AutoX.js

1. 安装 AutoX.js / Auto.js；
2. 开启无障碍；
3. 导入 `auto_js_checkin.js`；
4. 在 AutoX.js 里设置每天定时执行；
5. 手机保持插电。

脚本逻辑和 ADB 版一样；WebView 不暴露文本时，需要改成坐标点击或图片匹配。

## 注意

- 这是 UI 自动化，不涉及抓包/token；
- App 必须保持登录，掉登录需要重新短信登录；
- 手机分辨率变化会影响坐标，文本匹配优先；
- 不要在这台手机上 root，否则又会触发 root 检测。
