# 分析记录

样本：`com.greenpoint.android.mc10086.activity` v12.5.6  
APK SHA-256：`ac88f974523d8ec9f5e4b29eb81d6deeae409cc0b3eaf0675f25603474ff6eb7`

## APK 结构

```text
classes.dex                  ~21KB，DexHelper 壳
lib/arm64-v8a/libDexHelper.so
lib/arm64-v8a/libdexvmp.so
lib/arm64-v8a/libnative-cube.so     5.7MB mPaaS cube
lib/arm64-v8a/libdatajar.so         152MB 业务数据/类名/配置
lib/arm64-v8a/libsgmain.so          1.1MB 嵌套 APK
lib/arm64-v8a/libsgmainso.ucb.so
```

## 字符串命中

```text
libdatajar.so:
  qwhdhub
  doSignature
  doSignHttpRequest
  doSignContent2Header
  getAuthCodeForSecurityGuard
  com.alibaba.wireless.security.open.securesignature.ISecureSignatureComponent
  com.alibaba.wireless.security.open.avmp.IAVMPGenericComponent
  com.alibaba.wireless.security.open.staticdataencrypt.IStaticDataEncryptComponent
```

`assets/home_data_error_v2.json` 里也有：

```text
https://wx.10086.cn/qwhdhub/qwhdmark/1021122301?channelId=P00000109876
```

## SecurityGuard

`libsgmain.so` 是 ZIP/APK：

```text
classes.dex
lib/arm64-v8a/libsgmainso-5.6.230509.so
lib/arm64-v8a/libsgmainso.ucb.so
```

关键类：

```text
com.taobao.wireless.security.adapter.JNICLibrary
  static native Object doCommandNative(int i, Object... objArr);

com.alibaba.wireless.security.open.securesignature.ISecureSignatureComponent
  signRequest(SecurityGuardParamContext, authCode)
```

命令：

```text
10101 init
10401 sign
10601 static encrypt
10602 getAppKeyByIndex
12501 create LiteVM / AVMP
```

配置：

```text
assets/mpaas.properties
WorkspaceId=default
AppId=0F09868011039
Platform=ANDROID
```

## 当前阻断

- DexHelper 的 `/proc/self/maps` 小型 rwx 检测导致 Frida 崩溃；
- 主 App 的 DEX 被壳加密，静态看不到 `IdentityAuthenticationActivity` 实现；
- `appKey` / `authCode` 是运行时值；
- `QWHD_SESSION_TOKEN` 来自 App 原生登录态；
- unidbg harness 仍是模板。

## 2026-11-19 进展（getYDRZToken / 自动续期）

### APK 样本

- 从腾讯应用宝取得 `com.greenpoint.android.mc10086.activity` **12.5.6**，132,400,723 字节。
- 腾讯侧 MD5 `f56aff2ef0f4d8506ccddc03ea2ca62a`，与下载文件一致；SHA-256 与本目录旧记录不同，腾讯包只有 `armeabi-v7a`，旧记录可能来自另一发行渠道的 arm64 包。
- 已解出 `libsgmain.so` → `libsgmainso-5.6.230509.so`（v7a）与 SecurityGuard 插件 `classes.dex`。

### SecurityGuard / unidbg

- unidbg 已用 32 位 emulator 加载 v7a `libsgmainso`，`JNI_OnLoad`、`10101` 均可执行。
- `10602 getAppKeyByIndex` 仍抛 `106440105`；换用 `0F09868011039`、`jtztty_sdk#GD70958956615`、`jtztty_sdk#ZH46048899506` 等 appKey 无效。
- 结论：独立插件缺少 App 运行时的 `authCode` / 完整 Context，静态替换 appKey 不能解决；继续 unidbg 需要真实 authCode 或补齐 App 的 Context/SharedPreferences 初始化。

### JSYD H5 登录链路（公开页面）

`https://wap.js.10086.cn/nact/resource/2510/html/index.html` 的 JS 已确认：

```text
leadeon.getYDRZToken({sourceId:"039014"}) → res3.token
POST wap.js.10086.cn/nact/action.do
  reqUrl=wapLogin&method=jtTokenLogin&busiNum=JTTokenLOGIN
  &jtToken=<res3.token>&loginType=3
→ Set-Cookie（cmtokenid / cmjsSSOCookie 等）
→ initIndexPage / doSign
```

`mywaytoopen` 由 H5 的 `browserFinger` 生成并写入 cookie；服务端是否强校验仍需实测。

### 可复用的会话续期方案

公开项目 `mli84/cmcc-auto-checkin` 已验证：

```text
POST client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin
```

- AES-128-CBC + `x-token`/`xs`/`x-sign`，离线自检已在本机通过。
- `autoLogin` 不校验来者 JSESSIONID，靠明文模板中的 `xk` 与 `reqBody.cellNum`（App RSA 生成）识别用户。
- 该模板需要从 App 冷启动抓包一次；之后可反复现签新会话，再走 `appTokenLogin`。
- 参考项目还实现了 `GET /qwhdhub/user/getYDRZToken?targetSourceId=017027` 的 HTTP 取票。若 `targetSourceId=039014` 同样可用，可用 QWHD 会话直接换 JSYD 的 `jtToken`，不必调用原生 `leadeon.getYDRZToken`。

### 下一步（已于 2026-11-19 完成）

1. [x] 用 mitmproxy 抓取 App 冷启动的 `autoLogin`。
2. [x] 解密模板，取得 `xk` / `cellNum`，验证 `autoLogin` 现签（retCode=000000）。
3. [x] 验证 `appTokenLogin` → `getYDRZToken(039014)` → `jtWx10086AuthLogin` → `initIndexPage` / `doSign`。
4. [x] 接入青龙 `cmcc_auto.py`，任务 ID 280 已切换并实测。

### JSYD 接口探测（2026-11-19）

本机 Python 原型（`out/work/jsyd_login.py`，忽略目录）已用 legacy TLS 跑通匿名探测：

```text
GET  wx.10086.cn/qwhdhub/user/getYDRZToken?targetSourceId=039014   -> 302 /qwhdhub/notice/404（无 QWHD 会话）
POST wap.js.10086.cn/nact/action.do method=initIndexPage           -> resultObj.isLogin=false
POST wap.js.10086.cn/nact/action.do method=jtTokenLogin dummy      -> errorCode=-40014
```

说明接口路径和参数正确。后续已用 `autoLogin` + `appTokenLogin` 取得 QWHD 会话，并通过 `getYDRZToken(039014)` 换到有效 `jtToken`；完整链路见 [jsyd-login-chain.md](jsyd-login-chain.md)。
