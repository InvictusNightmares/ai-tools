# 中国移动 App 逆向与签到接口分析

目标包：`com.greenpoint.android.mc10086.activity` v12.5.6  
样本：`mc10086-base.apk`（132MB）  
SHA-256：`ac88f974523d8ec9f5e4b29eb81d6deeae409cc0b3eaf0675f25603474ff6eb7`

本目录只放本地分析代码和记录。所有产物默认写入 `out/`，不会提交 APK、DEX、SO、抓包日志或 token。

---

## 1. 结论速览

### 签到入口

```text
https://wx.10086.cn/qwhdhub/qwhdmark/1021122301?channelId=P00000109876
```

### qwhdhub 签到接口

```http
POST https://wx.10086.cn/qwhdhub/api/mark/mark31/domark
Cookie: QWHD_SESSION_TOKEN=...
Referer: https://wx.10086.cn/qwhdhub/qwhdmark/1021122301?channelId=...
```

### qwhdhub 登录/换 token

```http
GET  https://wx.10086.cn/qwhdsso/login?dlwmh=true&actUrl=...
POST https://wx.10086.cn/qwhdsso/appTokenLogin?sid=QWHDSSOD...
POST https://wx.10086.cn/qwhdsso/jwtLogin?sid=QWHDSSOD...
```

页面会检查 UA：

```js
if (navigator.userAgent.indexOf('leadeon') < 0) {
    alert('请在中国移动APP内访问此页面!');
}
```

随后调用 `leadeon.getUserInfo()` 获取原生 `token`，再 POST `appTokenLogin`。  
所以**只伪造 UA/JSBridge 不够，必须取得有效的 App 原生登录凭证**。
登录页的 `enableJwtLogin` 表示前端是否启用 JWT 登录；服务端是否接受续期仍需实测，
不能默认认为 JWT 可独立长期续期。

### 江苏 act2510 签到接口

```http
POST https://wap.js.10086.cn/nact/action.do
Content-Type: application/x-www-form-urlencoded

reqUrl=act2510&method=doSign&operType=1&actCode=2510&isJtAPP=true&fxmobile=&env=jt_app&extendParams=&ywcheckcode=&mywaytoopen=...
```

需要 `jsydsjkhd10086` 等登录 Cookie；匿名 Cookie 重放会返回 `isLogin:false`。

### 已确认的保护

```text
DexHelper（SecNeo）         classes.dex 只有壳
mPaaS SecurityGuard         请求签名 doCommand(10401)
libdatajar.so               152MB 业务数据/类名/配置
libsgmain.so                嵌套 APK，内含 classes.dex + libsgmainso
```

`libsgmain.so` 解包后：

```text
libsgmain.so
├── classes.dex
├── lib/arm64-v8a/libsgmainso-5.6.230509.so
└── lib/arm64-v8a/libsgmainso.ucb.so
```

SecurityGuard 签名链路：

```text
ISecureSignatureComponent.signRequest
  → router.doCommand(10401, {paramMap, appKey, requestType, authCode})
  → JNICLibrary.doCommandNative(10401, Object...)
```

初始化：

```text
doCommandNative(10101, {context, appId, appKey, authCode, pkgName, ver, osVer, processName})
```

配置：

```text
assets/mpaas.properties
WorkspaceId=default
AppId=0F09868011039
Platform=ANDROID
```

`AppKey` / `authCode` 不在明文配置里，需要运行时获取；`libdatajar.so` 里能看到：

```text
IdentityAuthenticationActivity$getAppKey
AppkeyBean
getAppkey / setAppKey
specificAuthCode / parseSpecificAuthCode
```

---

## 2. 目录结构

```text
script/cmcc-reverse/
├── README.md
├── .gitignore
├── apk/
│   ├── extract.sh                  # 解包 APK + jadx
│   └── scan_apk.py                 # 扫描 APK 内的接口/关键字
├── native/
│   ├── elf_scan.py                 # ELF 字符串/VA/xref 分析
│   └── extract_securityguard.sh    # 拆 libsgmain.so 嵌套 APK
├── frida/
│   ├── java_only.js                # Java 层 root 隐藏（Frida 17 需 bundle）
│   ├── hide_root.js                # Java + native 完整版（会触发壳检测）
│   └── spawn_load.py               # spawn + 加载脚本的通用 runner
├── capture/
│   ├── qwhd_capture.py             # 原生登录及 qwhdhub/act2510 抓包
│   └── test_qwhd_capture.py        # 合成流量离线回归测试
├── unidbg/
│   ├── README.md                   # unidbg harness 计划
│   └── SecurityGuardHarness.java   # 模板（未完成）
├── device/
│   ├── README.md                   # 非 root 真机 UI 自动化
│   ├── adb_checkin.py              # ADB + uiautomator 签到
│   └── auto_js_checkin.js          # AutoX.js 本地签到
├── notes/
│   └── findings.md                 # 原始分析记录
└── out/                            # 运行产物，git 忽略
```

---

## 3. 快速开始

```bash
cd script/cmcc-reverse

# 1. 解包 + jadx
./apk/extract.sh /path/to/mc10086-base.apk out

# 2. 扫描 APK 内的接口/关键字
python3 apk/scan_apk.py --apk /path/to/mc10086-base.apk

# 3. 拆 SecurityGuard
./native/extract_securityguard.sh /path/to/mc10086-base.apk out

# 4. ELF 字符串/引用分析
python3 native/elf_scan.py out/libs/libdatajar.so --string doSignature
python3 native/elf_scan.py out/libs/libdatajar.so --string doSignature --xrefs
```

---

## 4. APK / DexHelper

`classes.dex` 只有约 21KB，入口是：

```text
com.secneo.apkwrapper.*
libDexHelper.so
libdexvmp.so
```

看雪的 `libDexHelper.so` 分析给出关键检测逻辑：

```text
.init_array
  → 扫描 /proc/self/maps
  → 匹配 libc.so / libdl.so / linker
  → 发现小型 rwx 映射（<= 0x4000）
  → kill(getpid(), SIGKILL) + _Exit(3)
```

Frida 一注入就 native 崩溃，原因就在这里。  
想在本机/真机跑 Frida，需要：

1. hook `fopen/fgets/sscanf`，过滤 `/proc/self/maps` 中的小型 rwx 行；或
2. patch `libDexHelper.so` 的检测分支；或
3. 用 Magisk + Shamiko + 隐藏 maps 的方式。

参考：<https://bbs.kanxue.com/thread-292781.htm>

---

## 5. mPaaS SecurityGuard

`libsgmain.so` 是一个 ZIP/APK，用 `native/extract_securityguard.sh` 解包。

关键类：

```text
com.taobao.wireless.security.adapter.JNICLibrary
  public static native Object doCommandNative(int i, Object... objArr);

com.alibaba.wireless.security.open.securesignature.ISecureSignatureComponent
  signRequest(SecurityGuardParamContext, authCode)
```

命令 ID：

```text
10101  init
10401  sign
10601  static encrypt
10602  getAppKeyByIndex
12501  create LiteVM / AVMP
```

公开的 SecurityGuard 分析仓库：

- <https://github.com/sgInnora/alipay-securityguard-analysis>
- <https://help.aliyun.com/zh/document_detail/171079.html>
- <https://sofa.antdigital.com/docs/11/111990>

当前状态：

- `libsgmain.so` 已拆出 `classes.dex` 和 `libsgmainso-5.6.230509.so`；
- 签名链路已确认；
- `AppKey` / `authCode` 仍是运行时值；
- unidbg harness 仍在搭建。

---

## 6. Frida

`java_only.js` 只 hook Java 层：

- `File.exists/isFile/canExecute`
- `Runtime.exec` / `ProcessBuilder`
- `Build.*`
- `SystemProperties.get`
- `System.exit` / `Runtime.exit`
- `Dialog.show`（拦截 `DECMsgDialog`）

Frida 17 需要先 bundle：

```bash
frida-compile frida/java_only.js -o out/java_only.bundle.js
python3 frida/spawn_load.py \
  --device emulator-5554 \
  --package com.greenpoint.android.mc10086.activity \
  --script out/java_only.bundle.js
```

Frida 16 可以直接使用去掉 `import Java from "frida-java-bridge";` 的版本。  
`hide_root.js` 含 native `open/openat/access/stat` hook，容易触发壳检测或崩溃，只作为参考。

---

## 7. HTTPS 抓包

长期调用需要先取得 App 原生登录和续期材料，再验证会话失效后的恢复流程。
单独保存 `QWHD_SESSION_TOKEN` 只能获得当前活动会话；抓到一次 `appTokenLogin`
也不等于已取得可长期续期的凭证。

`capture/qwhd_capture.py` 是 mitmproxy addon，按准确的域名和路径抓：

```text
wx.10086.cn/qwhdhub
wx.10086.cn/qwhdsso
wap.js.10086.cn/nact
client.app.coc.10086.cn/biz-orange/...
clientaccess.10086.cn/biz-orange/...
```

原生采集覆盖 `/biz-orange/` 下的请求，包括 `uamonekeylogin` 登录、会话刷新和活动票据交换，
具体入口仍需用自己的 App 版本实测。这也会记录 App 同时发起的账号查询，请仅在排查期间开启。
应采集两段操作：已有登录态的 App 冷启动，然后进入签到页。冷启动不等于退出账号；
不要为抓包主动注销现有登录态。

从本目录启动（先安装 mitmproxy）：

```bash
export CMCC_CAPTURE_DIR="$PWD/out/captures"
mitmweb --listen-port 8080 --web-port 8081 \
  --set connection_strategy=lazy \
  --scripts capture/qwhd_capture.py
```

每条命中请求写入 `out/captures/flows/<flow-id>.json`，保存全部请求头、响应头、
原始 body（base64）和可解码的文本。响应到达后更新同一记录，保留请求/响应对应关系；
并发请求不会互相覆盖。启动或热重载时，会从 mitmweb 尚保留的流量中补存当前过滤规则匹配、
且尚未落盘的记录；此过程不重放网络请求，也不覆盖已有文件。mitmdump 没有历史视图时跳过补存。
同时生成 `host_inventory.json`，汇总域名、请求数量和状态统计。江苏活动域名及顺丰官方
`sf-express.com`、`sf-express.com.cn` 域名下的请求额外汇总脱敏路径，帮助定位遗漏的 SSO 或取票入口；
路径中的长数字和长不透明片段会被替换，顺丰路径中的 UUID 和 32 位十六进制标识也会脱敏。
这份索引不含查询参数、请求头或正文。江苏登录额外采集两个准确路径：
`/vw/gateway/auth/auth/jtWx10086AuthLogin`、`/hyl/content/provider-user/sso/china/mobile`；
不扩展到该站点的其他账号接口。
原有 `qwhd_apptoken_body.json`、`qwhd_apptoken_resp.json`
仍是最近一次各自事件的便捷副本，配对分析以 `flows/` 为准。
所有输出文件使用 `0600` 权限；其中含 Cookie、签名和原生凭证，**不要提交或公开分享**。
记录完整不代表请求体已解密，也不代表其中字段能直接重放。

### 原生接口的上游 TLS 兼容

在 mitmproxy 12.3.1 / OpenSSL 4.0.3 上，`client.app.coc.10086.cn` 的 TLS 握手可能返回
`unsafe legacy renegotiation disabled`。这是代理连接上游时未收到 RFC 5746 安全重协商支持，
与手机是否信任代理 CA 是两个独立问题。

addon 对该准确域名的 HTTPS 连接启用 `OP_LEGACY_SERVER_CONNECT`，并设置
`OP_NO_RENEGOTIATION` 禁用后续重协商。它复用 mitmproxy 的 CA、主机名验证、TLS 版本和
密码套件配置，只修改当前 SSL 连接，不修改共享上下文，也不自动开启全局 `ssl_insecure`。
旧服务端初始握手兼容仍有安全取舍，应仅用于本人的短时排查；不要扩大到其他域名。
此适配已通过该版本的无凭证握手和独立代理请求检查，取票和活动登录仍需单独验证。

### 未 root 设备的边界

- Android 上安装用户 CA 不保证第三方 App 信任它；App 的信任配置和证书固定校验是不同层。
  `ssl_insecure` 只控制代理对服务器证书的验证，不能解决 App 对代理 CA 的信任。
- 在未越狱 iPhone 上可先验证系统证书信任路线：将 Wi-Fi 代理指向本机 mitmproxy，
  用 Safari 打开 `http://mitm.it` 安装证书，再到“设置 → 通用 → 关于本机 → 证书信任设置”
  开启该证书的完全信任。先确认 Safari 的目标 HTTPS 请求可解密，再检查官方 App。
  如果 App 使用证书固定校验或不走系统代理，这条路线也可能失败，不能提前承诺可用。
- 对原版 App，WebView 调试仅在 App 已主动开放调试入口时可用；普通 ADB 不能替第三方
  发布包打开该开关。VPN 抓包、换代理工具或 `ssl_insecure` 都不能自动消除证书信任限制。

确认取得原生材料后，按实际活动验证登录链路：qwhdhub 使用 `appTokenLogin`；江苏 `act2510`
可能由 `leadeon.getYDRZToken()` 获取票据后调用 `jtTokenLogin`。两者的票据不能直接互换。
先验证活动登录和只查签到状态，再在自然会话过期后验证原生登录是否能重新建立活动会话。
JWT 开关、设备绑定和服务端
有效期都可能变化，未做这个验证前不要声称可长期无人值守。

离线验证（使用安装了 mitmproxy 的同一个 Python 环境）：

```bash
python -m unittest discover -s capture -p 'test_*.py' -v
```

参考：[Android CA 信任配置](https://developer.android.com/privacy-and-security/security-config)、
[mitmproxy 证书安装](https://docs.mitmproxy.org/stable/concepts/certificates/)、
[WebView 调试前置条件](https://developer.chrome.com/docs/devtools/remote-debugging/webviews)。

江苏活动的青龙适配器和无通知验收命令见 [script/qinglong/cmcc-checkin/README.md](../qinglong/cmcc-checkin/README.md)。
它还不具备原生自动取票能力，不能把当前 Cookie 的活动访问测试当作长期续期验收。

### 顺丰会员登录与签到采集

同一 addon 也采集 `mcs-mimp-web.sf-express.com` 下的 `/mcs-mimp/`、`/share/`
以及 `/superWelfare` 入口，保存登录跳转、完整 Cookie 请求头、Set-Cookie 响应头和请求/响应正文。
顺丰记录单独写入 `out/captures/sf/flows/`，便捷日志为 `out/captures/sf/sf.log`，文件权限为 `0600`。
热重载会补存代理内存中符合这些规则的历史记录，且不重放请求。

原生取票额外完整采集上述顺丰官方域名下，以
`/cx-app-member/member/app/user/universalSign` 结尾的准确接口路径，记录类型为
`sf-native-ticket`，同样保存在顺丰目录。网关前缀可以不同，但其他会员账号接口不扩大采集。

采集时保持手机连接该代理，重新打开官方 App 并进入会员/积分签到页；需要登录时按官方流程完成，
无需主动注销已有账号。未命中完整采集规则的顺丰官方子域名只记录域名统计和脱敏路径，
请求头和正文不额外落盘；先定位实际取票入口，再添加准确的完整采集规则。
补查原生取票时，从后台结束 App 后重新启动并进入签到页，分析完成前保持 mitmweb 运行，
以便从其保留的流量中补存已确认的目标请求；关闭代理进程会丢失这些尚未落盘的原生请求。
代理连通和规则加载通过不代表手机 App 已接受代理证书，也不证明获取的会话可以自动续期。

普通系统代理遗漏原生请求时，可使用 mitmproxy 的 WireGuard 模式，由手机 WireGuard
客户端导入本机生成的私有配置或二维码。手机与抓包电脑需能通过局域网互通，并关闭手机
原来的 Wi-Fi HTTP 代理；抓包期间手机使用该 WireGuard 隧道。密钥、二维码、实际连接地址
只保留在忽略目录的私有配置中，不写入文档或提交。VPN 路由不替代 HTTPS 证书信任；
手机连接、HTTPS 解密和目标取票请求出现需要分别确认。抓包完成后关闭手机隧道。

WireGuard 流量的连接目标可能是 IP 地址。对于 HTTP Host（HTTP/2 为 `:authority`）
与 TLS SNI 一致的顺丰请求，采集器使用该域名匹配规则，并在记录的 `origin_host` 中保存；
原始目标 URL 和传输模式也会保留。域名不一致或未命中原有路径规则时不扩大完整采集。

---

## 8. unidbg

目标：

1. 加载 `libsgmainso-5.6.230509.so`；
2. 初始化 `JNICLibrary.doCommandNative(10101, ...)`；
3. 调 `10602 getAppKeyByIndex` 取 AppKey；
4. 调 `10401` 对测试串签名；
5. 与抓到的请求做对比。

`unidbg/SecurityGuardHarness.java` 已能加载 SecurityGuard、执行 `JNI_OnLoad` 并调用
`10101/10602/10401`。当前 `10602` 抛 `SecException 106440105`，`10401` 返回 null，
原因是独立插件没有主 App 的 `appKey` / `authCode` / 完整 Context。  
`libsgmainso` 有自解密/环境检测，可能需要：

- 补 Android Context / PackageManager；
- 处理 `JNI_OnLoad` 和 native 注册；
- 或先用真机 Frida hook `doCommandNative` 拿到输入输出。

---

## 9. 待办 / 已知阻塞

- [x] 解包 APK，确认 DexHelper 壳
- [x] 找到 qwhdhub / act2510 接口
- [x] 拆出 SecurityGuard 组件和命令映射
- [x] 确认 `doSignature` → `doCommand(10401)`
- [ ] 取到 `appKey` / `authCode`（运行时值，已改用等价原生登录绕过）
- [ ] unidbg 跑通 SecurityGuard 签名（非当前关键路径）
- [x] 取到活动会话刷新链路（autoLogin + appTokenLogin + getYDRZToken）
- [x] 长期无人值守签到（青龙 `cmcc_auto.py`）

公开项目 [cmcc-auto-checkin](https://github.com/mli84/cmcc-auto-checkin) 提供了原生自动登录
和活动会话交换的研究线索，但仍依赖首次取得本人 App 的原生请求材料，且不同版本的服务端
行为可能变化。本目录尚未完成真实账号的续期验证，不能将该项目的说明直接作为已验证结论。

---

## 9.1 模拟器测试结论

- MuMu：root 开关不删 `su`；关 Root、重启仍提示 ROOT；Frida 被 DexHelper maps 检测 kill。
- Android Studio AVD（Google APIs arm64 userdebug）：无 root 开关但镜像自带 `/system/xbin/su`；改 `ro.debuggable=0`、`ro.build.type=user`、型号/指纹后，App 仍弹 `Device Rooted`。
- 结论：原版 MuMu/AVD/BlueStacks 都不是干净非 root 环境；要在模拟器跑，需要预修改镜像或 Magisk + Shamiko + resetprop，成本高且可能被 `libZWRisk` 检测。
- 实用路线：非 root 真机 + UI 自动化，见 `device/`。

## 10. 自动续期结果（2026-11-19）

江苏 `act2510` 已改为等价原生登录，不再依赖手工 Cookie 或 SecurityGuard `authCode`：

```text
autoLogin（client.app.coc）       现签 App 会话
→ appTokenLogin（qwhdsso）        换 QWHD 会话
→ getYDRZToken(sourceId=039014)  换江苏 jtToken
→ jtWx10086AuthLogin             换江苏活动 Cookie
→ initIndexPage / doSign         查状态、签到
```

- 链路分析：[notes/jsyd-login-chain.md](notes/jsyd-login-chain.md)
- 脱敏抓包样本：[analysis/samples/](analysis/samples/)
- 接口探测：[analysis/jsyd_probe.py](analysis/jsyd_probe.py)
- HAR 导入 profile：[analysis/import_auto_login.py](analysis/import_auto_login.py)
- SecurityGuard harness：[unidbg/SecurityGuardHarness.java](unidbg/SecurityGuardHarness.java)
- 青龙生产脚本：[../qinglong/cmcc-checkin/cmcc_auto.py](../qinglong/cmcc-checkin/cmcc_auto.py)

首次仍需从 App 冷启动抓一次 `autoLogin` 以取得 `xk` / `cellNum` 模板；之后青龙每次运行自动续期。
原始抓包、profile、Cookie、token 只保存在 `out/` 或青龙 `data/config/`，不入库。

## 11. 注意

- 不要把 APK、DEX、SO、抓包日志、Cookie、token 提交到仓库；
- `out/` 已加入 `.gitignore`；
- 分析只针对本地样本和自有账号；
- 本目录记录的是研究过程，不是可直接分发的成品。
