# 开发者定位模拟命令

> 项目位置：`script/wloc-dingtalk-analysis/`。以下命令默认在该目录下执行。

环境：iPhone iOS 26.6.1，USB 连接 Mac，开发者模式已开启。

2026-11-05 复测发现：`pymobiledevice3 11.50.0` 的 DVT 定位命令存在同步等待
阻塞通信和默认连接回退不稳定两个问题。本机实测约 18～26 秒后手机停止模拟，
但终端进程仍在。修复需要异步等待，并直接选择 iOS 17+ 的 RSD 通道。
下方准备步骤包含已验证的本地修复；修复后仍使用原命令。
原因和复测证据见 [developer-simulation-test.md](../results/developer-simulation-test.md)。

## 0. 一次性准备

```bash
python3 -m venv ~/.venv/pmd3
~/.venv/pmd3/bin/pip install 'pymobiledevice3==11.50.0' dpkt
ln -sf ~/.venv/pmd3/bin/pymobiledevice3 ~/.local/bin/pymobiledevice3

# 修复 11.50.0 的等待与连接选择；覆盖 set / play，clear 也直接走 RSD
~/.venv/pmd3/bin/python scripts/fix_pmd3_location_wait.py --apply
~/.venv/pmd3/bin/python scripts/test_simulation_wait.py
```

`~/.local/bin` 已经在 PATH 里，装完后可以直接运行 `pymobiledevice3`。

修复脚本只修改运行它的 Python 环境中的定位 CLI 模块，并校验版本和原文件的
SHA-256；重复执行不会重复打补丁，遇到不同源码会退出。升级或重装工具后先检查：

```bash
~/.venv/pmd3/bin/python scripts/fix_pmd3_location_wait.py --check

# 如需撤销本地修复（会重新出现原有问题）
~/.venv/pmd3/bin/python scripts/fix_pmd3_location_wait.py --restore
```

`--check` 返回 0 表示已修复，1 表示仍是原始受影响代码，2 表示版本或源码不匹配。
补丁不修改坐标、定位来源标志或 App 行为。

手机端：

1. 设置 → 隐私与安全性 → 开发者模式 → 打开 → 重启 → 确认
2. USB 连接 Mac，解锁，点「信任此电脑」

检查设备：

```bash
pymobiledevice3 usbmux list --simple
pymobiledevice3 amfi developer-mode-status   # 应为 true
```

挂载开发者镜像（第一次或重启后需要）：

```bash
pymobiledevice3 mounter auto-mount
```

---

## 1. 设为北京天安门

```bash
pymobiledevice3 developer dvt simulate-location set -- 39.908700 116.397500
```

说明：

- 命令会一直运行，**不要关终端、不要拔线、Mac 不要睡眠**
- 修复后会显示 `Simulation session open. Press Ctrl+C to stop.`
- 检查苹果地图的**当前位置蓝点**，先退出搜索并点定位箭头；搜索地址不会自动改成当前位置
- 终端进程存在本身不能证明定位有效；USB 连接和通信会话也必须正常
- `Ctrl-C` 停止后，手机会恢复真实位置

---

## 2. 清除模拟 / 恢复真实位置

```bash
pymobiledevice3 developer dvt simulate-location clear
```

如果第 1 步的 `set` 还在另一个终端运行，先按 `Ctrl-C` 停掉，再执行 `clear`。

---

## 3. 设为公司

```bash
pymobiledevice3 developer dvt simulate-location set -- 31.19161987 121.28696441
```

这是 Apple WLOC 查到的办公室 AP 坐标。同样需要保持进程运行。

---

## 4. 常用命令速查

```bash
# 北京
pymobiledevice3 developer dvt simulate-location set -- 39.908700 116.397500

# 公司
pymobiledevice3 developer dvt simulate-location set -- 31.19161987 121.28696441

# 清除
pymobiledevice3 developer dvt simulate-location clear
```

---

## 5. 用本地脚本（更短）

脚本位置：`scripts/simulate-location.local.sh`

```bash
chmod +x scripts/simulate-location.local.sh

./scripts/simulate-location.local.sh beijing   # 设为北京
./scripts/simulate-location.local.sh office    # 设为公司
./scripts/simulate-location.local.sh clear     # 清除
```

如果 `pymobiledevice3` 不在 PATH：

```bash
PMD3=$HOME/.venv/pmd3/bin/pymobiledevice3 ./scripts/simulate-location.local.sh beijing
```

---

## 6. 注意事项

- 本次旧地址问题通过异步等待和直接选择 RSD 通道解决，不需要先重启手机或清缓存。
- 模拟会话绑定 USB 连接：拔线、Mac 睡眠、进程退出都会恢复真实位置。
- 本次没有读取 App 收到的 `CLLocation.sourceInformation`，不能据此断定模拟标志的值或 App 的检测策略。
- 测试时先用北京这种明显不同的坐标，并同时核对地图蓝点和目标 App 的地址。
- 当前如果不需要模拟，执行 `clear` 恢复真实位置。
