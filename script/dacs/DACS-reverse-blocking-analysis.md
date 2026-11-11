# DACS macOS 客户端逆向分析：封禁机制

样本：`DACS_cpirhzl_2026(2620483)S_Universal_NetDisk_LO.pkg`（224 MB）
- 类型：xar + pkg，内含 `AutoUpdate.pkg`
- 签名：`Developer ID Installer: Datacloak Tech(Shenzhen) Co.,Ltd. (8856CSH399)`
- 公证：Apple notary 通过，时间戳 2026-06-10
- 主程序：`DACS.app` 2.6.2 (48)，Bundle ID `com.TE.TEDataCloak`
- 系统扩展：`com.TE.TEDataCloak.es` / `.ne` / `.nelo` 2.6.2 (48)
- 定制集群：`cpirhzl_cluster`，显示名“中电投”；认证入口与 VPN 入口在包内配置文件中，本文用占位符 `AUTH_CENTER_URL` / `VPN_ENDPOINT`
- 厂商：Datacloak（数篷科技）DACS 数据访问控制系统，macOS 端

> 结论速览：DACS 的“封禁”由**服务端策略引擎**和**本机五个执行面**组成：
> 1. NetworkExtension AppProxy + DProxyd 做**网络访问封禁**；
> 2. EndpointSecurity 系统扩展做**文件打开/改名/删除/执行封禁**；
> 3. ES `AUTH_EXEC` + 程序规则做**进程/应用封禁**；
> 4. 设备证书 + 风控做**设备/账号封禁**；
> 5. 注入 `libDataCube.dylib` + 主程序 hook 做**剪贴板/截图/外发/DLP 封禁**。
>
> 它不是 hosts、pf 或简单防火墙；判定依据是“**进程代码签名身份 + 文件路径/挂载域 + 网络五元组/域名 + 设备证书**”。

---

## 1. 安装后落地的组件

### 1.1 常驻目录

| 路径 | 作用 |
|---|---|
| `/usr/local/bin/mac_agent/` | 策略代理主目录：`bin/mac_agent`、`bin/mac_wireguard`、`bin/mac_netdisk`、`clusters/`、`data/`、`logs/`、`run/user/*.fifo` |
| `/usr/local/bin/com.datacloak.autoUpdate/` | 自动更新器：`payload/`、`bin/DACSScriptExecuter`、`config/agent.plist`、`.mark/state.plist` |
| `/usr/local/bin/output/` | `DProxyd` 与启动脚本、`server_config.sh` |
| `/usr/local/bin/DProxyd` | 代理/网络策略执行进程（Go，基于 `ginuerzh/gost`） |
| `/Applications/DACS.app` | 主程序、UI、注入库、系统扩展安装器 |
| `/Applications/DACS卸载程序.app` | 卸载入口（需管理员验证包） |
| `/Library/LaunchDaemons/com.datacloak.*.plist` | 常驻服务 |
| `/Library/LaunchAgents/com.datacloak.*.plist` | 用户态常驻 |
| `~/Library/Application Support/DACS/` | 用户侧策略/集群缓存（`clusters/`、`PersonalPolicy/`） |

### 1.2 Launchd 驻留项

- `/Library/LaunchDaemons/com.datacloak.softwareupdate.plist` → `DACSScriptExecuter update.sh`
- `/Library/LaunchDaemons/com.datacloak.privilegedTool.plist` → `DACSPrivilegedTool`（XPC 提权工具）
- `/Library/LaunchDaemons/com.datacloak.wireguard.plist` → `mac_wireguard`
- `/Library/LaunchDaemons/com.datacloak.helper.plist` → `DACSPKGInstall.sh`（监听 `.temp_pkg` 队列）
- `/Library/LaunchDaemons/com.meili_mac_agent.meili_mac_agent.plist` → `DACSLaunchInfra.sh`
- `/Library/LaunchAgents/com.datacloak.agentmonitor.plist` → `DACSAgentMonitor`
- `/Library/LaunchAgents/com.datacloak.DACSHelperGPU.plist` → `DACSHelper (GPU)`
- `/Library/LaunchDaemons/com.datacloak.proxy.plist` → `DProxyd`

多数 plist 带 `KeepAlive=true`，被杀后会被 launchd 拉起；`agentmonitor` 还会监控并拉起主程序。

### 1.3 三个系统扩展

| 扩展 | Entitlements | 作用 |
|---|---|---|
| `com.TE.TEDataCloak.es` | `com.apple.developer.endpoint-security.client` + `app-proxy-provider-systemextension` | ES 文件/执行鉴权 + 网络代理，双职责 |
| `com.TE.TEDataCloak.ne` | `app-proxy-provider-systemextension` | 普通模式 AppProxy（按进程代理流量） |
| `com.TE.TEDataCloak.nelo` | `app-proxy-provider-systemextension` | LO 模式（`LO_AUTH=1`）使用的本地网络策略扩展 |

安装脚本通过：

```bash
DACSInstaller -ii es+ne+nelo
```

注册系统扩展。`launch_monitor.sh` 会检查 `systemextensionsctl list` 中三者的版本，缺失/版本不一致会重新拉起安装器。

### 1.4 二进制保护

`mac_agent`、`DProxyd`、`mac_wireguard`、`mac_netdisk` 等文件开头有 8 字节 `hello wo` 前缀，安装脚本用：

```bash
dd if=FILE bs=512k | { dd bs=8 count=1 of=/dev/null; dd bs=512k of=FILE_truns; }
mv FILE_truns FILE
```

去掉前缀后才是真正的 universal Mach-O（`cafe babe` fat header）。这是对抗 `strings`/`file`/静态扫描的轻量混淆。

---

## 2. 策略从哪里来：服务端 → 本地代理

### 2.1 登录与策略链

```
用户登录
  → DACS.app
  → auth-center（AUTH_CENTER_URL）
  → 设备证书 / license / 集群配置
  → 配置服务器 + etcd
  → gRPC 拉取策略（ProgramNetRule / ProgramRule / NetPolicyMap / PersonalPolicy ...）
  → mac_agent 落盘并编译
  → NE / ES / DProxyd / FUSE / libDataCube 执行
```

关键 RPC / 策略对象（从 Go 符号与字符串还原）：

- `server.QueryNet4PolicyRequest` / `QueryNet4PolicyResponse`
- `server.QueryProgramNetRules`、`server.ProgramNetRuleInfo`、`ProgramNetRuleMatchType`
- `server.ProgramInstallRule`、`ProgramRule`、`ProgramInfo`、`ProgramBinaryAttr`
- `proto.IpcNetPolicyItem`、`IpcNetPolicyItemList`、`NetPolicyMap`
- `proto.ProgramRoute`、`ProcessRoute`、`server.TailProcessRoute`
- `proto.PermitNetworkAddrService/LoadPermitNetworkAddr`
- `proto.PermitNetworkAddrService/LoadLocalNetworkPermit`
- `proto.IpcService/LoadNetPolicy`
- `server.QueryPersonalPolicy`、`PersonalPolicy`
- `server.FileSecurityClass`、`FileSecurityClassInfo`
- `datacloak.server.TailNetWhiteList`、`TailCommonWhiteList`、`TailProcessRoute`
- `datacloak.server.ProgramInstallRule`、`DomainProgramRule`

网络策略规则类型在 NE 扩展里直接写死：

```
(1:default, 2:common, 3:doamin, 4:program)
```

含义：默认规则、公共规则、域规则、程序规则。匹配优先级与具体实现对应 `DCNetDataManager matchPolicyItemForIpStr:port:netProtocol:domainId:`。

### 2.2 策略开关

Go 二进制里可见一组 `SWITCH_*`，对应服务端下发的布尔开关：

```
SWITCH_BLOCK_IPV6          SWITCH_E2E_POLICY
SWITCH_FILE_OUTGO          SWITCH_NOREDIRECT
SWITCH_SCREENSHOTS         SWITCH_PROCESS_PROTECT
SWITCH_CLIPBOARD           SWITCH_CLIPBOARD_OUTGO
SWITCH_CLIPBOARD_ENC       SWITCH_CHROME_REDIRECT
SWITCH_OFFICE_SECURITY     SWITCH_OPTIMIZE_FASTIO
SWTCH_DOMAIN_ISOLATION     SWITCH_KEY_HANDLE_TAGS
SWITCH_DACSADMIN           SWITCH_MULTI_VPN
SWITCH_IPCCOMMUNICATION_CONTROL
SWITCH_GPU_SCREENSHOT_WATERMARK
SWITCH_SPECIFIC_LEAK       SWITCH_LO_ENC
SWITCH_TRACELESS_MODE      SWITCH_FILE_SAFESHARE
SWITCH_IPCDATA_REPORT      SWITCH_TIMES
```

这些开关就是“封禁”的总闸：是否禁 IPv6、是否禁截图、是否禁剪贴板外发、是否禁文件外发、是否启用域隔离、是否启用进程保护等。

### 2.3 本地缓存

- `/usr/local/bin/mac_agent/clusters/`、`clusters/tmp/`
- `/usr/local/bin/mac_agent/config/`、`config_root/`
- `/usr/local/bin/mac_agent/data/`（SQLite，`policy_learn_%s.db` 等）
- `~/Library/Application Support/DACS/PersonalPolicy/`（`PersonalPolicy.a`、`PersonalDNSPolicy.a`）
- `~/Library/Application Support/DACS/clusters/`
- `/usr/local/bin/com.datacloak.autoUpdate/config/agent.plist`（`jobId`、`report`）

---

## 3. 封禁面一：网络访问

### 3.1 拦截点

网络流量不是靠 pf 规则，而是：

```
进程 socket
  → NetworkExtension AppProxyProvider（ne / nelo / es 三选一或组合）
  → Unix Domain Socket / gRPC
  → DProxyd（本地代理 + 策略执行）
  → 直连 / WireGuard / DENY
```

NE 扩展里的类与方法：

- `DCProxyTcpConnection` / `DCProxyUdpConnection` / `DCProxyUnixTcpConnection`
- `-[DCNetDataManager matchPolicyItemForIpStr:port:netProtocol:domainId:]`
- `-[DCGrpcAgentClient loadNetPolicyCompeleteBlock:]`
- `-[DCGrpcAuthClient syncAuthNetAction:response:]`
- `-[DCProcess generateCSInfo:]`、`getTeamIDByPid:`、`isAuthSpecialProcesss`、`isInAuthPassProcess`、`isPcSpecialDescendant`

即：每个 flow 先拿 **PID → 进程路径 → 代码签名信息（TeamID / SigningID / CDHash）**，再和目标 `IP:Port/协议/域名` 一起做策略匹配。

### 3.2 决策结果

NE 扩展里的决策字符串：

```
: Auth Unknown, PASS
: DENY for PERSONAL, found policy:
: Forwarding, route:
 (1:default, 2:common, 3:doamin, 4:program), dproxy_port:
: activate: off, PASS
: Personal dproxyd forward disable, PASS
: match forward dproxyd ips, DEFER
: dproxy mode, Auth DEFER
: wg mode, Auth ACCEPT
), dropping flow
: connectionQueue overloaded (pending:
```

可归为四类：

| 结果 | 含义 |
|---|---|
| `PASS` | 直连/绕过，不交给 DProxyd |
| `DEFER` | 交给 DProxyd 做细粒度判定 |
| `ACCEPT` | 走 WireGuard 隧道 |
| `DENY` | 直接丢弃 flow，应用看到连接被重置/超时 |

`DENY` 时 NE 层直接 `dropping flow`，包不会到达目标；因此用户侧表现为“网络不可达/连接被重置/只有部分域名能打开”，而不是 HTTP 403。

### 3.3 DProxyd 的第二道判定

DProxyd 是 Go 程序，符号里能看到 `github.com/ginuerzh/gost`，并带有大量自研 DNS/策略代码。关键日志：

```
[Conn:%p][%s][Handle] policy DENY: target=%s, isVPN=%v
authentication failed: PID=%d, Path=%s, Reason=not in whitelist
authentication failed: PID=%d, Path=%s, Reason=not in whitelist (cached)
[GrpcAuth]%s Cached approval for PID %d (%s), method: %s
[ProgramNet4] program not match, skip this policy
[RouteCheck] ... route novpn because of trie match error
[Conn:%p][%s] dialing target directly: %v
```

- `policy DENY`：策略明确拒绝，直接断流。
- `not in whitelist`：DProxyd 的 Unix socket 鉴权阶段就拒绝该 PID，连代理都不让进。
- `Cached approval for PID`：按 PID+签名缓存放行结果，避免每次 flow 都查服务端。
- `ProgramNet4`：程序级 IPv4 策略；不匹配当前程序就跳过。
- `route novpn`：路由判定为不走 VPN（直连或走本地网络）。

### 3.4 DNS 层的封禁

DProxyd 内置 DNS 代理，域名策略会在 DNS 阶段先落地：

```
[Tag:%p][DNS Proxy] ... add ip policy to cache count:%d, domain:%s
[Conn:%p][DNS Proxy][Filter IPv6] IPv6-DENY. Request for domain:%s (not in keep list)
[Tag:%p][DNS Proxy][Filter IPv6] Filtered %d AAAA records from response for domain: %s
[PersonalPolicy] ... PersonalDNSPolicy.a
[PersonalPolicy] begin personal policy LookupHost %s
```

- 域名解析结果会被写入 **domain → IP 策略缓存**，后续该 IP 的 flow 直接命中策略。
- 默认过滤 AAAA（IPv6），除非域名在 keep list；`SWITCH_BLOCK_IPV6` 控制。
- `PersonalDNSPolicy.a` 支持个人域/域名级 DNS 策略。
- `[DNS Proxy] GetLocalSysDNSAddr`、`SetLocalDNS` 会修改系统 DNS 指向本地代理。

所以“某个域名打不开”可能不是连接被拒，而是 DNS 被改写/过滤，或在 DNS 阶段就被标记为 DENY。

### 3.5 WireGuard 路由层

`mac_wireguard` 基于 WireGuard，创建 utun 并下发路由。策略允许的网段才进隧道：

```
[Route Set] Process route(%+v)
[VPN][WireGuardVpn] ParseCIDR Address:%v
[RouteCheck]request (%v) for addr(%s) route novpn because of trie match error
```

结果：
- 只有命中策略的网段走 VPN；
- 其余可能直连（`PASS`）或被 NE/DProxyd 丢弃；
- `wg mode, Auth ACCEPT` 表示该 flow 直接接受并走 WireGuard。

### 3.6 硬编码兼容豁免

NE 扩展里有一组应用兼容放行：

```
/Applications/Yunshu.app/Contents/MacOS/Yunshu
/Applications/SecureLink/SecureLink.app/Contents
/opt/wapp/bin/wapptunneld
: pass for 2cx webrtc
: pass for WeLink.
```

这些是厂商为云桌面/WeLink/2cx 等做的兼容白名单，不走普通策略或特殊处理。它们也说明“封禁”不是绝对的，存在按应用签名/路径的豁免分支。

---

## 4. 封禁面二：文件/磁盘

### 4.1 安全空间与加密盘

`mac_agent` 里可见：

```
/usr/bin/hdiutil create -size %v -volname "%s" -fs APFS -type SPARSEBUNDLE -encryption AES-256 -stdinpass "%s"
/usr/bin/hdiutil create -size 50g -volname "%s" -fs APFS -type SPARSEBUNDLE -encryption AES-256 -stdinpass "%s"
/secret.sparsebundle/
```

安全空间是一个 **AES-256 加密的 APFS sparsebundle**，通过 macFUSE / FUSE-T 挂载到用户目录下的安全路径（字符串里是 `/meili/...`、`meili/secure`）。`mac_netdisk` 则是基于 rclone VFS + FUSE 的网络磁盘客户端（独立于本地加密盘）。

### 4.2 ES 文件鉴权

`com.TE.TEDataCloak.es` 导入的 EndpointSecurity API：

```
_es_new_client
_es_subscribe
_es_respond_auth_result
_es_respond_flags_result
_es_mute_path / _es_mute_path_literal / _es_mute_path_prefix
_es_exec_arg / _es_exec_env
```

订阅的事件：

```
ES_EVENT_TYPE_AUTH_OPEN
ES_EVENT_TYPE_AUTH_CLONE
ES_EVENT_TYPE_AUTH_COPYFILE
ES_EVENT_TYPE_AUTH_CREATE
ES_EVENT_TYPE_AUTH_LINK
ES_EVENT_TYPE_AUTH_RENAME
ES_EVENT_TYPE_AUTH_UNLINK
ES_EVENT_TYPE_AUTH_EXEC
ES_EVENT_TYPE_NOTIFY_CLOSE
ES_EVENT_TYPE_NOTIFY_EXEC
ES_EVENT_TYPE_NOTIFY_EXIT
ES_EVENT_TYPE_NOTIFY_FORK
ES_EVENT_TYPE_NOTIFY_WRITE
ES_EVENT_TYPE_NOTIFY_XPC_CONNECT
```

文件打开/改名/删除等是 **AUTH** 事件，ES 扩展可以同步返回 ALLOW/DENY；`es_respond_flags_result` 还可以只放行读、屏蔽写，实现“只读打开”。

核心类：

```
DCAuthNode
  -handleCommonAuthChecksWithClient:message:file:dataManager:isFlagRequest:authResult:outResult:
  -handleDomainProcessAuthWithClient:message:file:dataManager:srcDomainInfo:dstDomainInfo:procDomainInfo:isFlagRequest:authResult:outResult:
  -handlePersonalProcessAuthWithClient:message:file:dataManager:srcDomainInfo:dstDomainInfo:procDomainInfo:isFlagRequest:authResult:outResult:

DCFileAuthManager
  -analyseFileWhitelistForProcess:
  -flushPolicyLearnReports

DCDataManager
  -_generateDiskAccessWhiteList
  -getDenyDiskAccessWithPath:processName:
  -getProcessRightInWhiteListByPath:withSign:signingId:teamId:
  -queryFileWhitelistForProcess:
  -queryFileBlacklistForProcess:
  -setPersonalProcessFileAccessBlacklist:
```

判定输入：
1. **请求进程身份**：`generateCSInfo:` 生成代码签名信息；`getTeamIDByPid:`；`getProcessRightInWhiteListByPath:withSign:signingId:teamId:`
2. **目标文件路径**：是否在 `meiliMountPaths` / `mountPaths` / `diskAccessWhitelist` 内；是否命中 `fileWhitelist` / `fileBlacklist`。
3. **域信息**：`pidToDomainDic`、`srcDomainInfo/dstDomainInfo/procDomainInfo`；跨域访问按源域/目标域判定。
4. **开关**：`diskAccessSwitch`、`domainIsolationSwitch`、`denySwitchValue`、`applicationsProtectSwitch`。
5. **特殊进程**：Apple 进程、DACS 自身、`isAuthSpecialProcesss`、`isInAuthPassProcess`、`isPcSpecialDescendant` 等直接放行。

### 4.3 直接杀进程

除了 ES 拒绝 `open()`，还有一条“已打开文件的进程”清理链。`mac_agent` 内的命令：

```bash
/usr/sbin/lsof -n | grep "/meili/%s/%s" | awk '{print $1,$2}' | uniq \
  | grep -v DACS | grep -v grep | awk '{print $2}' | uniq \
  | xargs /bin/kill -s KILL
```

以及 App 容器路径：

```bash
/usr/sbin/lsof -n | grep "/meili/%s/Applications/%s" ... \
  | xargs /Applications/DACS.app/Contents/SharedSupport/bin/dtools ps --pids \
  | grep "/meili/%s/Applications/%s" ... \
  | xargs /bin/kill -s KILL
```

日志：

```
[DISK] check and kill process access file in domainId:%s, checkCmd:%s, output:%s
[DISK] check in domainId:%s, checkCmd:%s, output:%s
[DISK] check before mount kill processes. domainId:%s, user:%s
exist path:%s, ready to kill
ready to kill process, path:%s, pid:%s
```

含义：
- 挂载/卸载安全盘前，先杀掉占用该盘的进程；
- 运行中检测到未授权进程打开受保护路径，也直接 `SIGKILL`；
- 排除 DACS 自身、`diskimage`、`mds` 等系统进程。

### 4.4 主程序侧的文件黑名单

`DACS.app` 主二进制里：

```
/usr/sbin/lsof '%@' | ... | xargs /bin/kill -9
TEKernelControl sendFileBlacklist:completion:
TESysExtXpcManager setPersonalDomainProcessFileAccessBlacklist:
TEProgramRuleTypeDeny
TEBlacklistChecker
isPathBlacklisted:
```

主程序通过 XPC 把文件黑名单/进程黑名单下发给内核控制层和系统扩展。

### 4.5 Intel 与 Apple Silicon 的差异

- **Intel**：`SANDBOX_MODE=KERNEL`，安装 `socketnke.kext`，通过 kext 在内核 VFS 层拦截。
- **Apple Silicon**：`SANDBOX_MODE=SYSEXT`，依靠 EndpointSecurity 系统扩展 + FUSE。

安装脚本明确打印：

```
LO_AUTH(0:compat,1:lo_auth):1
MACFUSE(0:fuse-t; 1: macfuse):1
```

### 4.6 驱动异常即卸载

```
[Heartbeat][DriverException] ES system extension missing, will notify TE and unmount all disks
[Heartbeat][DriverException] TE notified, starting async disk unmount
Driver_Exception_Alert_Message = 检测到安全相关驱动异常，加密磁盘已自动退出。
```

即：如果 ES 系统扩展被卸载/失联，客户端会主动卸载所有加密盘，避免“失去管控的明文数据”继续可用。这是防绕过设计的一部分。

---

## 5. 封禁面三：进程/应用

### 5.1 应用清单扫描

`mac_agent` 登录后会扫描全机应用：

```
[LoginTime][scanMacApp] begin, isScanAll=%v isPolicyOnly=%v isCanReport=%v
[LoginTime][scanMacApp] GetAllMacAppPath cost=%v appCount=%d
[LoginTime][scanMacApp] GetAllMacMessage cost=%v appCount=%d
[LoginTime][scanMacApp] done, cost:%v isAccess:%v accessResult:%v checkBlack:%v checkProgram:%v checkService:%v
```

扫描结果写入：

```
/AgentDefault.a
/MacScanAppMessage.a
/AgentEmployeeList.a
```

字段包括 Bundle ID、可执行文件、路径、签名、owner、版本等（`Software Report`、`ProgramBinaryAttr`）。

### 5.2 程序规则判定

```
[SoftwareAccess] CheckAccessProgramInfo BundleId [%s]
[SoftwareAccess] CheckAccessProgramInfo system [%s] owner [%s]
[SoftwareAccess] CheckAccessServiceInfo system [%s] owner [%s]
[SoftwareAccess] CheckAccessBlackProgramInfo [%s] BundleId does not exist
[SoftwareAccess] CheckAccessServiceInfo signature is don't have, err:%s
[SoftwareAccess] programInfo is empty. You do not need to determine
```

关键词：

```
BLACKSOFTWARE
PROGRAM_RULE_DENY
TEProgramRuleTypeAccess
TEProgramRuleTypeDeny
isPathBlacklisted:
```

判定维度：Bundle ID、可执行路径、代码签名（TeamID/SigningID/CDHash）、系统应用/第三方应用/服务。服务端 `ProgramInstallRule` / `ProgramRule` 决定：
- 允许安装/运行；
- 允许访问哪个域/网络；
- 直接拒绝（`TEProgramRuleTypeDeny`）；
- 上报审计。

### 5.3 ES 执行拦截

ES 订阅 `ES_EVENT_TYPE_AUTH_EXEC`，执行前同步判定。相关类：

```
DCExecAuthProgramControlSubNode
DCExecAuthBinaryRedirectorSubNode
DCExecAuthMdutilSubNode
DCExecAuthSafeguardSubNode
```

- `ProgramControl`：程序控制，拒绝未授权二进制。
- `BinaryRedirector`：二进制重定向（兼容/替换）。
- `Mdutil`：处理 Spotlight 索引类进程。
- `Safeguard`：对动态库/注入做保护检查（`DCSafeguardModel shouldCheckDylibForFile:`）。

拒绝时 ES 返回 DENY，进程 `execve` 失败；用户看到“应用闪退/无法启动”，而不是弹窗。

### 5.4 进程事件上报与杀进程

```
proto.ProcessEventService/NotifyProcessAuthEvent
[NotifyProcessAuthEvent] will report progress, request:%v
[System] process event request:%v
[System] process event Operation_AfterTerminate %s, mountPath:%s
```

主程序侧还有：

```
/bin/kill -9 %@
/usr/bin/pkill
[Terminate] Force terminated %@ (PID: %d)
[Terminate] Gracefully terminated %@ (PID: %d)
killProcessWithPid:
```

### 5.5 注入式管控（关键）

主程序对目标应用做 Mach-O 注入：

```
DYLD_INSERT_LIBRARIES
/usr/local/lib/libDataCube.dylib
libDataCubeLite.dylib
bin/optool
/usr/bin/codesign --deep -f -s "-" "%@"
/usr/bin/codesign --remove-signature "%@"
[Common][M1_importApp] start injecting
[Common][M1_importApp] Injected successfully:%@
[AppCompat] %@ not inject, pass
[AppCompat] isHaveWhite not inject, pass
```

流程：
1. 用 `optool` 给目标 Mach-O 写入 `LC_LOAD_DYLIB`，加载 `libDataCube.dylib`；
2. 用 ad-hoc 签名重新签名（`codesign -f -s -`）；
3. 应用启动后 dylib hook 文件/剪贴板/截图等 API，执行 DACS 的数据管控；
4. 黑名单应用不注入；`IgnoreInjectProcList` 里的进程跳过注入；
5. Java/Citrix 等通过修改 JVM options 注入（`_loadAndInjectVMOptionsWithAppPath:`）。

因此“应用被封禁”有两种形态：
- **不能启动**：ES `AUTH_EXEC` 拒绝；
- **能启动但功能被限制**：注入 dylib 后，文件读写、剪贴板、截图、打印被 hook 拒绝或审计。

---

## 6. 封禁面四：设备/账号

### 6.1 设备证书

```
QueryDeviceCertStatus
DeviceCertExpired
DeviceCertRevoked
DeviceCertUnknown
RevokeDeviceCert
DC_DEVICE_CERT_IS_REJECTED
DC_CONFIG_SERVER_DEVICE_DISABLED
DC_AUTH_SERVER_ACCOUNT_FORBIDEN
```

- 每台设备有设备证书；证书过期/吊销/未知，登录直接被拒。
- 管理员可远程吊销，客户端下次登录/心跳时失效。
- 设备证书与应用账号绑定，换机/重装需要重新认证。

### 6.2 风控与踢下线

```
CheckSessionRisk
CheckRiskReloginByCert
ReportReloginEvent
CLIENT_KICK_OFF
CLIENT_KICK_OFF_BY_USER_SELF
agent will kill, relogin
agent will kill, unlogin
```

服务端风控（异地、异常、并发、证书风险）可下发 `CLIENT_KICK_OFF`，客户端收到后：
- 杀掉 `DACS.app` / 相关 agent；
- 强制重新登录；
- 清理本地策略/凭据（`IncognitoMode`、`ClearProgramRules`）。

### 6.3 卸载管控

```
QueryUninstallConfig
如果您确认要卸载本软件，请向管理员提供设备名并索取卸载验证包进行安全校验。
```

卸载器需要管理员验证包，普通用户无法直接彻底卸载。

---

## 7. 封禁面五：数据外发 / DLP

### 7.1 剪贴板

```
SWITCH_CLIPBOARD
SWITCH_CLIPBOARD_OUTGO
SWITCH_CLIPBOARD_ENC
ClipboardFreqRisk
ClipboardSizeRisk
clipboard_outgo_data.proto
DACSClipSyncAgent
[Info][Inject][Clipboard]: suspend clipboard sync
[Info][Inject][Clipboard]: resume clipboard sync
[Search] in search view, DENY pasteItem
```

- 安全域内/外剪贴板单向或双向禁用；
- 频率/大小超限拦截（`剪切板外发文字超出限制`）；
- 注入 dylib 在应用内 hook 粘贴板，主程序侧 `DACSClipSyncAgent` 同步/拦截；
- `findUpdatedClipboardIndexWithDenyGeneral:` 处理“拒绝通用粘贴”。

### 7.2 截图/录屏

```
SWITCH_SCREENSHOTS
SWITCH_GPU_SCREENSHOT_WATERMARK
PRO_ID_ATTR_SCREEN_CUT
screen_capture_permission
ScreenshotReport
ScreenCaptureLog
screenshot_report.proto
[DarkWatermark]: screenConfig is nil, kill DACSWatermark success
```

- 服务端开关决定是否允许截图；
- 截图行为上报（`ScreenshotReport`）；
- 屏幕水印（可见/隐形）叠加；
- 注入库 hook 截图 API（`CGWindowListCreateImage` / ScreenCaptureKit 等）。

### 7.3 水印与打印

```
AddWatermarkTask
WatermarkTextStyle
ScreenWatermarkIntensity
WATERMARK_TYPE_NORMAL
WATERMARK_TYPE_HIDDEN
InvisibleWatermark
printer_watermark.proto
QueryPrinterACLs
```

- 屏幕水印：明文/隐写，含用户/设备/时间等信息；
- 打印水印 + 打印机 ACL；
- 隐形水印用于泄密溯源。

### 7.4 文件外发

```
SWITCH_FILE_OUTGO
FILE_OUTGO
ShortFileOutUploadFile
OutgoFileUploadCallback
ExternalSharingApply
CrossFileSharingRecord
EMAIL_SEND
FileAppOutgoMail
```

- 文件外发（上传/邮件/共享链接）需要策略允许或审批；
- 超大小/类型限制直接拦截（`文件大小超出外发限制`）；
- 外发记录上报审计。

### 7.5 键盘记录

```
KeyboardRecordLog
keyboard_record.proto
```

用于审计/风控的键盘事件记录（具体触发条件由策略控制）。

---

## 8. 自保护与“封禁难以绕过”的原因

1. **launchd KeepAlive**：主服务/代理/监控被杀会自动拉起。
2. **三系统扩展**：ES + NE + NELO，缺一不可；ES 失联会卸载加密盘。
3. **代码签名校验**：进程身份用 TeamID/SigningID/CDHash，改文件名/复制路径不能伪造。
4. **更新包校验**：
   - 更新脚本校验 `pkgutil --check-signature` 的签名者；
   - payload 整体 MD5 固定值 `f4d74164560f6e95e8725d21798f2c61`；
   - `DACSScriptExecuter` 只有 root 可写。
5. **卸载管控**：需要管理员验证包。
6. **注入库 + 主程序双保险**：即使应用不注入，网络/文件仍有 NE/ES 管控；即使 NE 被绕，DProxyd 仍判定。
7. **进程清理**：`lsof` + `kill -9` 清理占用受保护文件的进程。
8. **服务端兜底**：设备吊销、会话风控、强制下线都在服务端，纯本地手段无法恢复。

---

## 9. 现场定位：到底是哪一层在封

### 9.1 基础命令

```bash
# 系统扩展状态
systemextensionsctl list | grep -i TEDataCloak

# 常驻服务
launchctl list | grep -E 'datacloak|meili'

# 进程
ps aux | grep -E 'mac_agent|DProxyd|mac_netdisk|mac_wireguard|DACS'

# 网络代理/路由
scutil --dns
netstat -rn
ifconfig | grep -A3 utun

# 日志（近 10 分钟）
log show --last 10m --predicate 'process == "mac_agent" OR process == "DProxyd" OR process == "DACS"' --info --debug

# 代理日志
tail -f /usr/local/bin/mac_agent/logs/*.log
tail -f /usr/local/bin/mac_agent/logs/DProxy_error.log
```

### 9.2 日志关键词 → 封禁层

| 关键词 | 层 |
|---|---|
| `policy DENY` / `dropping flow` / `not in whitelist` | NE / DProxyd 网络 |
| `IPv6-DENY` / `Filtered ... AAAA` / `ResetLocalDNS` | DNS 代理 |
| `route novpn` / `ParseCIDR` / `wg mode` | WireGuard 路由 |
| `AUTH_EVENT_OPEN` / `handlePersonalProcessAuth` / `es_respond_auth_result` | ES 文件 |
| `ready to kill process` / `check before mount kill processes` | 文件/进程清理 |
| `AUTH_EVENT_EXEC` / `ProgramControl` / `PROGRAM_RULE_DENY` | ES 进程/应用 |
| `DeviceCertRevoked` / `CLIENT_KICK_OFF` / `agent will kill` | 设备/账号 |
| `SWITCH_SCREENSHOTS` / `clipboard` / `watermark` / `FILE_OUTGO` | DLP |
| `ES system extension missing` / `DriverException` | 自保护/驱动异常 |

### 9.3 症状对照

| 现象 | 最可能的封禁点 |
|---|---|
| 某网站/接口连接被重置、超时 | NE `dropping flow` 或 DProxyd `policy DENY` |
| 域名解析失败/返回异常 IP | DProxyd DNS 策略、AAAA 过滤、DNS 改写 |
| 只有内网能通，公网全断 | 策略只放行 VPN/内网网段，公网走 DENY |
| 特定应用不能联网，其他正常 | 程序规则（type 4:program）按签名/路径匹配 |
| 打开受保护文件报“权限不足” | ES `AUTH_OPEN` 返回 DENY |
| 打开可以但保存失败 | `es_respond_flags_result` 只放行读、屏蔽写 |
| 程序启动即闪退 | ES `AUTH_EXEC` DENY 或进程被 kill |
| 文件复制到一半进程被杀 | `lsof` + `kill -9` 清理链 |
| 登录被踢/设备不可用 | 设备证书吊销/风控 `CLIENT_KICK_OFF` |
| 截图黑屏/剪贴板失效 | 注入 dylib + 策略开关 |
| 卸载后加密盘打不开 | 设计如此（密钥/证书在服务端） |

---

## 10. 设计上的关键点与可利用面（静态分析结论）

> 以下是机制分析，不是操作指令。

1. **判定锚点是代码签名，不是进程名**：`getTeamIDByPid`、`getProcessRightInWhiteListByPath:withSign:signingId:teamId:`、`CDHash`。改 app 名、复制路径、换图标都不会改变判定。
2. **白名单/黑名单是“路径 + 签名 + 域”的组合**：`fileWhitelist`、`bidToFileBlacklistDic`、`signToFileBlacklistDic`、`diskAccessWhitelist`。单靠路径伪造很难通过签名检查。
3. **网络策略双实现**：NE 层先粗判（PASS/DEFER/ACCEPT/DENY），DProxyd 再细判。只处理一个组件，另一个仍会拦。
4. **默认行为依赖策略**：NE 日志有 `Auth Unknown, PASS` 和 `POLICY_LEARNING_ENABLED: ALLOW`，说明在策略缺失/学习模式下是放行；一旦服务端下发明确规则，就按规则拒绝。
5. **兼容豁免是真实存在的口子**：WeLink、2cx webrtc、Yunshu、SecureLink、`wapptunneld` 有硬编码放行分支；这类“厂商兼容白名单”通常是策略覆盖的薄弱点。
6. **更新完整性用 MD5**：payload 整体 MD5 是固定值，强度弱于签名；但外层 pkg 有 Developer ID 签名 + 公证，且更新脚本校验签名者，单改 payload 仍过不了签名门。
7. **ES 缺失即卸载加密盘**：`ES system extension missing → unmount all disks`。这使“禁用驱动继续用明文”的路径被堵死。
8. **设备封禁在服务端**：吊销/风控/强制下线不依赖本地文件，纯本地绕过无法恢复服务端授权。
9. **FUSE 只覆盖挂载点**：安全盘走 FUSE/加密 sparsebundle；挂载点之外的文件访问由 ES 负责，两者互补。
10. **进程清理排除项**：`grep -v DACS`、`grep -v diskimage`、`grep -v mds`，说明清理链只针对“非 DACS、非系统镜像、非 Spotlight”的占用者。

---

## 11. 关键证据索引

### 11.1 系统扩展

```text
com.TE.TEDataCloak.es:
  entitlements: com.apple.developer.endpoint-security.client
                app-proxy-provider-systemextension
  ES: es_new_client / es_subscribe / es_respond_auth_result / es_respond_flags_result
  events: AUTH_OPEN / AUTH_CLONE / AUTH_COPYFILE / AUTH_CREATE /
          AUTH_LINK / AUTH_RENAME / AUTH_UNLINK / AUTH_EXEC
  classes: DCAuthNode / DCFileAuthManager / DCDataManager / DCNetDataManager
  methods: handlePersonalProcessAuthWithClient:...
           handleDomainProcessAuthWithClient:...
           matchPolicyItemForIpStr:port:netProtocol:domainId:
           
com.TE.TEDataCloak.ne / .nelo:
  NetworkExtension app-proxy-provider-systemextension
  classes: DCProxyTcpConnection / DCProxyUdpConnection
  logs: "), dropping flow", "DENY for PERSONAL, found policy:"
        "wg mode, Auth ACCEPT", "dproxy mode, Auth DEFER"
```

### 11.2 mac_agent

```text
[DISK] check and kill process access file in domainId:%s, checkCmd:%s, output:%s
[DISK] check before mount kill processes. domainId:%s, user:%s
ready to kill process, path:%s, pid:%s
/usr/sbin/lsof -n | grep "/meili/%s/%s" ... | xargs /bin/kill -s KILL
/usr/sbin/lsof -n | grep "/meili/%s/Applications/%s" ... | xargs /bin/kill -s KILL
/usr/bin/hdiutil create ... -encryption AES-256 -stdinpass ...
[SoftwareAccess] CheckAccessProgramInfo BundleId [%s]
[SoftwareAccess] CheckAccessBlackProgramInfo [%s]
authentication failed: PID=%d, Path=%s, Reason=not in whitelist
[Heartbeat][DriverException] ES system extension missing, will notify TE and unmount all disks
```

### 11.3 DProxyd

```text
[Conn:%p][%s][Handle] policy DENY: target=%s, isVPN=%v
[ProgramNet4] program not match, skip this policy
[RouteCheck] ... route novpn because of trie match error
[Conn:%p][DNS Proxy][Filter IPv6] IPv6-DENY. Request for domain:%s (not in keep list)
[PersonalPolicy] begin personal policy LookupHost %s
[GrpcAuth] Cached approval for PID %d (%s), method: %s
```

### 11.4 DACS.app

```text
DYLD_INSERT_LIBRARIES
/usr/local/lib/libDataCube.dylib
bin/optool
/usr/bin/codesign --deep -f -s "-" "%@"
/usr/sbin/lsof '%@' | ... | xargs /bin/kill -9
TEKernelControl sendFileBlacklist:
TESysExtXpcManager setPersonalDomainProcessFileAccessBlacklist:
TEProgramRuleTypeDeny
[AppDisk][APP] kill process before unmount disk
[Terminate] Force terminated %@ (PID: %d)
```

### 11.5 本地化文案（用户可见的“封禁”语义）

```text
DomainAccessAlert_Message = 由于安全管控要求，当前环境下您不能访问以下空间，已为您自动隐藏：%@
SECURITY_RESTRICTED_ACCESS_MESSAGE = 由于安全管控要求，当前环境下您不能访问任何安全空间，请联系管理员！
Device_Auth_Revoke_Result_Desc = 您的设备证书已被吊销，再次登录DACS客户端，设备将不再被信任，并不被允许登录。
Clipboard_Interception_Alert: = 剪贴板拦截提醒：
Outgoing_SizeLimit = 文件大小超出外发限制
Driver_Exception_Alert_Message = 检测到安全相关驱动异常，加密磁盘已自动退出。
```

---

## 12. 一句话总结

DACS 的“封禁”本质是：

> **服务端把“谁（进程签名）、访问什么（文件路径/域/网络目标）、用什么设备”编译成策略；本机用 EndpointSecurity 在系统调用层拒绝，用 NetworkExtension + DProxyd 在流量层丢弃，用 FUSE/加密盘隔离数据，用注入 dylib 在应用层拦截剪贴板/截图/外发，用设备证书和风控在服务端踢人。**

它强在“多层冗余 + 签名身份 + 服务端兜底”，不是单点可关闭的开关。
