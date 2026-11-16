# unidbg harness（SecurityGuard）

目标：在 Mac 上用 unidbg 模拟 `libsgmainso-5.6.230509.so`，调用 mPaaS SecurityGuard
的 `JNICLibrary.doCommandNative`，完成：

```text
10101 init
10602 getAppKeyByIndex
10401 sign
```

## 前置

```bash
# Java 17+
java -version

# 编译 unidbg
git clone --depth 1 https://github.com/zhkl0228/unidbg.git
cd unidbg
./mvnw -q -pl unidbg-android -am -DskipTests package
```

本目录的 `SecurityGuardHarness.java` 是模板，不是完成品。  
需要先把 `libsgmain.so` 解包出的以下文件放到工作目录：

```text
classes.dex
libsgmainso-5.6.230509.so
libsgmainso.ucb.so
```

用 `../native/extract_securityguard.sh` 生成。

## 已知参数

```text
AppId      = 0F09868011039
Package    = com.greenpoint.android.mc10086.activity
AppKey     = 运行时获取（或 10602 查询）
authCode   = 运行时获取
```

## 调用链

```text
JNICLibrary.doCommandNative(10101, {
  context, appId, appKey, authCode, pkgName, ver, osVer, processName
})

JNICLibrary.doCommandNative(10602, {index, authCode})       // getAppKeyByIndex

JNICLibrary.doCommandNative(10401, {
  paramMap, appKey, requestType, authCode
})                                                          // sign
```

`10401` 的 `paramMap` 通常包含：

```text
INPUT = 待签名内容
```

## 当前进度（本机 unidbg）

已经跑通：

```text
加载 libsgmainso-5.6.230509.so
执行 JNI_OnLoad
调用 JNICLibrary.doCommandNative(10101, ...)
```

为了跑起来，harness 里补了这些 JNI 回调：

```text
SecurityGuardMainPlugin.getMainPluginClassLoader
java/lang/ClassLoader.findClass / loadClass
SPUtility2.readSS / writeSS / read / write
Context.checkSelfPermission / checkCallingOrSelfPermission
Context.getPackageName / getApplicationContext / getFilesDir
```

当前结果：

```text
10101 init      -> 返回 null（不再抛异常）
10602 getAppKey -> SecException code=106440105
10401 sign      -> 返回 null
```

## 当前阻塞

- `appKey` / `authCode` 是主 App 运行时给的值，独立 SecurityGuard 插件里没有；
- `SPUtility2` 的 SharedPreferences 目前是 stub，init 可能没有真正完成设备注册；
- 需要从主 App 的 DEX / 私有数据 / 真机 hook 里取 `appKey`、`authCode`，或者让 init 走完整 Android Context；
- `10401` 需要真实 `paramMap` 和测试向量；
- `libsgmainso` 有自解密/环境检测。

## 参考

- <https://github.com/sgInnora/alipay-securityguard-analysis>
- `analysis/command_map_complete.md`
- `analysis/architecture.md`
- `tools/sg_avmp_gadget.c`
