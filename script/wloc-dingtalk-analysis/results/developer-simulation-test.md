# 开发者定位模拟复测（2026-11-05）

## 结论

本次“命令仍在运行，但苹果地图和钉钉仍显示旧地址”的原因是
`pymobiledevice3 11.50.0` 的 DVT 定位 CLI 存在两个已复现的问题：
同步等待阻塞通信事件循环；默认先尝试旧 USB 服务、失败后回退到 RSD 的入口，
在这台设备上仍会提前失去服务端连接。手机随后结束模拟，Mac 上的命令却仍挂着。

改为直接建立 RSD 通道并异步等待后，不重复下发坐标、不重启手机，系统持续输出模拟位置。
用户确认苹果地图和钉钉都已显示北京。
这修正了初次报告中把本次现象归因于缓存或 App 过滤的判断。

## 环境与复现

- iPhone：USB 连接，iOS 26.6.1。
- 开发者模式：查询结果为 `true`。
- DeveloperDiskImage：已挂载。
- Mac：macOS 14.8.7；Python 3.13.13；pymobiledevice3 11.50.0。
- 目标：北京测试坐标 `39.9087, 116.3975`。
- 连接：命令自动选择进程内 userspace tunnel。

```bash
pymobiledevice3 developer dvt simulate-location set -- 39.908700 116.397500
```

## 根因证据

1. 安装包中的 `cli/developer/dvt/simulate_location.py` 在
   `await location_simulation.set(...)` 后调用同步 `OSUTILS.wait_return()`。
   macOS 实现使用 `signal.sigwait(...)`。
2. 对正在复现问题的命令采样，主线程停在
   `asyncio task_step_impl → signal_sigwait → __sigwait`。
3. `locationd` 在 18:18:28 至 18:18:45 输出了 18 条 `@ClxSimulated`；
   18:18:46 收到停止请求。此时命令进程仍然存在，用户确认地图蓝点仍在原位置。

```text
18:18:46.518022 received daemon-side request to stop location simulation
18:18:46.518030 Simulation stop request received, fSimulationRunning: 1
18:18:46.518051 LocationController,setting simulation to 0 for all location providers
```

4. 对照程序直接建立 userspace/RSD 通道，使用同一 DVT 服务并异步等待。
   坐标只发送一次。从 18:20:25 至 18:24:44，日志连续记录 258 条模拟位置，
   没有停止请求。用户确认地图和钉钉都变成北京。

5. 将异步等待移回原 CLI 后，默认入口在约 22 秒和 26 秒时仍停止模拟。
   再次采样证实事件循环已恢复运行，DVT 客户端仍未报告断开，
   但手机的 `DTServiceHub` 在 18:30:33 记录
   `RSD handler: Socket transport disconnect action fired. Closing socket.`，
   随即向 `locationd` 发送停止模拟请求。这推翻了“只修等待就足够”的初步判断。
6. 保持相同的异步等待，给 CLI 显式传入 `--userspace`，跳过旧服务尝试和自动重试，
   从 18:31:51 至 18:34:02 持续产生 131 条模拟位置，没有停止请求。
   因此最终修复同时将定位 CLI 的依赖改为 `RSDServiceProviderDep`，直接建立 RSD。

直接 RSD 与自动回退的对照已验证；自动回退为何触发设备端 socket 关闭的更深层协议原因，
尚未单独定位，不能仅凭本次日志断定是 iOS 缓存或 App 风控。

初次报告引用的模拟日志确实存在于本机临时抓取中，但它只能证明模拟曾经启动。
`onSimulatedNotification` 也会出现在非模拟运行阶段；
`didUpdateLocations` 的坐标被日志脱敏，不能单凭回调名称认定 App 收到了目标坐标。

## 修复与回归检查

使用 [fix_pmd3_location_wait.py](../scripts/fix_pmd3_location_wait.py)
对现有虚拟环境中的定位 CLI 模块应用可逆补丁：将 `set` 和 GPX `play`
末尾的同步等待改为 `await asyncio.Event().wait()`，并将该模块三个命令的
`ServiceProviderDep` 改为 `RSDServiceProviderDep`，直接选择现代设备通道。
保留原 CLI 的 Ctrl-C 取消和上下文清理机制。原来的命令及两个 shell 包装脚本无需更换。

补丁仅接受已检查的 11.50.0 原文件 SHA-256。升级或重装后需要重新检查，
不会自动修改不同版本。应用、检查和撤销方式见
[操作命令](../scripts/developer-simulation-commands.md)。

[test_simulation_wait.py](../scripts/test_simulation_wait.py) 不连接手机，直接调用
已安装 CLI 的异步处理函数，验证同一事件循环仍能处理其他任务及取消、关闭会话：

- 原始代码：最初 4 项中 2 项失败，`set` 和 `play` 均因阻塞事件循环而超时。
- 只修等待：新增的默认入口测试失败，命令仍尝试旧 USB 服务。
- 完整修复后：5 项全部通过，覆盖默认入口直接选择 RSD、异步等待和取消清理、补丁往返恢复及未知源码拒绝修改。
- 同类扫描：定位模块中的两处等待均已修复；安装包其他功能中的同步等待不在本次定位调用链内，未修改、未进行设备验证。

最终通过原始命令（没有额外传入 `--userspace`）复测：18:34:47 至 18:36:34
连续输出 108 条模拟位置，持续约 107 秒，无提前停止。18:36:35 手动按 Ctrl-C
后命令正常取消（退出码 130），手机收到停止模拟请求；随后执行 `clear` 成功
（退出码 0），18:36:40 日志确认 `fSimulationRunning: 0`。测试定位已清除。

## 证据范围

本次确认的是这台设备上的模拟会话和地图、钉钉地址显示。
没有提交打卡，也没有读取或修改 `CLLocation.sourceInformation`。
不能从本次结果推断 App 的检测策略或其他设备、系统版本的行为。
初始研究中关于缓存、模拟标志及其他替代方案的推测，不是本次故障的已验证原因。

原始设备日志、进程采样和验证截图留在本机临时目录，未复制进版本库。
