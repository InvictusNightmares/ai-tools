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
