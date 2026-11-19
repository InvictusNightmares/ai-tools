# 江苏 act2510 登录链路分析

本文记录 2026-11-19 对中国移动 App 江苏 `act2510` 签到链路的逆向结果。目标是让青龙在活动会话过期后自动重建会话，而不是每天手工抓 Cookie。

## 结论

原生 `leadeon.getYDRZToken()` 和 SecurityGuard 的运行时 `authCode` 不是唯一路径。通过 App 的 `autoLogin` + `appTokenLogin`，可以在没有原生签名的情况下取得 QWHD 会话，再通过 HTTP `getYDRZToken(sourceId=039014)` 换到江苏活动需要的 `jtToken`：

```text
autoLogin（client.app.coc.10086.cn）      现签 App 会话
→ appTokenLogin（wx.10086.cn/qwhdsso）    换 QWHD 会话
→ getYDRZToken(targetSourceId=039014)    换江苏 jtToken
→ jtWx10086AuthLogin（wap.js.10086.cn）  换江苏活动 Cookie
→ initIndexPage / doSign                 查状态、签到
```

这套链路已经在青龙容器中实测完成每日签到，生产脚本为 [`script/qinglong/cmcc-checkin/cmcc_auto.py`](../../qinglong/cmcc-checkin/cmcc_auto.py)。

## 公开 H5 页面

活动页：

```text
https://wap.js.10086.cn/nact/resource/2510/html/index.html
```

关键脚本：

```text
nact/resource/common/js/act_main_20211122.js
nact/resource/common/js/leadeon.js
nact/resource/2510/script/act2510.js
nact/resource/2510/script/act2510Challenge.js
```

`act_main_20211122.js` 中的登录流程：

```text
cmtokenid cookie 存在 → tokenValidate
→ leadeon.userStatus / checkSessionIsvalid / getUserInfo
→ leadeon.getYDRZToken({sourceId:"039014"})
→ POST nact/action.do
     reqUrl=wapLogin
     method=jtTokenLogin
     busiNum=JTTokenLOGIN
     jtToken=<token>
     loginType=3
→ Set-Cookie：cmtokenid、cmjsSSOCookie、userMobileForBigData 等
→ initIndexPage / doSign
```

`mywaytoopen` 由 H5 的 `browserFinger` 生成并写入 `.js.10086.cn` cookie；`act2510` 请求会同时带上它。

## 接口探测

匿名探测（无会话）可以确认路径和参数：

| 请求 | 结果 |
| --- | --- |
| `GET wx.10086.cn/qwhdhub/user/getYDRZToken?targetSourceId=039014` | `302` → `/qwhdhub/notice/404` |
| `POST wap.js.10086.cn/nact/action.do` `method=initIndexPage` | `resultCode=1`、`resultObj.isLogin=false` |
| `POST wap.js.10086.cn/nact/action.do` `method=jtTokenLogin`，`jtToken=test` | `errorCode=-40014` |

有 QWHD 会话后，`getYDRZToken` 返回：

```json
{"code":"SUCCESS","data":"YZsidsso..."}
```

`data` 即 `jtWx10086AuthLogin` 需要的 `jtToken`（42 字符，`YZsidsso` 前缀）。

## 等价原生登录

### autoLogin

```http
POST https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin
Content-Type: application/Json

<AES-128-CBC(base64) 明文模板>
```

签名头：

```text
x-qen: 14
xs:     md5(url + "_" + 明文JSON + "_Leadeon/SecurityOrganization")
x-token: base64(AES-CBC(key=bAIgvwAuA4tbDr9d, iv=9791027341711819)(xk + "_" + path + "_" + x-time + "_" + x-nonce))
x-sign:  md5(x-token + "_" + x-time + "_" + x-nonce + "_" + JSESSIONID)
```

请求体加密：

```text
AES-128-CBC(key=tVkdaRWRY0ZkV1Vr, iv=VjFSQ1ZtVkQxRTlQ) + PKCS7
```

`autoLogin` 不校验来者的 JSESSIONID，可用随机 UUID 占位；服务端靠明文模板里的 `xk` 和 `reqBody.cellNum` 识别用户。

模板关键字段：

```text
tel, sv, nt, packageName, prov, city, ctid, appKey, sp, en,
reqBody.cellNum, reqBody.devToken, reqBody.imei, cid, xk,
xc, componentID, ak, cv, sb, baseFrameVersion, st
```

其中 `xk` 与 `reqBody.cellNum` 由 App 运行时生成，无法从 APK 静态还原；首次必须从 App 冷启动抓一次 `autoLogin`。

### appTokenLogin

```http
GET  https://wx.10086.cn/qwhdsso/login?dlwmh=true&actUrl=<活动页>
→ 从 HTML 提取 loginPath

POST https://wx.10086.cn/qwhdsso/appTokenLogin?sid=...
{
  "provinceCode": "250",
  "cityCode": "0512",
  "userCheckId": "<手机号的十六进制>",
  "carrierOperator": "002",
  "appVersionCode": "12.5.6",
  "took": <随机数>,
  "jwtToken": null,
  "token": "<autoLogin 返回的 cookie>"
}
```

成功后返回活动页 URL，GET 该 URL 会下发 `QWHD_SESSION_TOKEN`。

### getYDRZToken

```http
GET https://wx.10086.cn/qwhdhub/user/getYDRZToken?targetSourceId=039014
Cookie: QWHD_SESSION_TOKEN=...
login-check: 1
```

返回的 `data` 就是江苏 `jtToken`。`017027` 是视频站 sourceId，`039014` 是江苏活动。

### jtWx10086AuthLogin

```http
POST https://wap.js.10086.cn/vw/gateway/auth/auth/jtWx10086AuthLogin
Content-Type: application/json

{
  "wapContext": {
    "bizCode": "JTWX10086LOGIN",
    "subBizCode": "login_KT",
    "optType": "1"
  },
  "jtToken": "<getYDRZToken 返回的 token>",
  "pageCode": "logintest",
  "tokenType": 3,
  "packageType": 2
}
```

成功时 `code=200`、`success="0"`、`message="authLogin success"`，并下发：

```text
CM_ORG_LOG, userMobileForBigData, userAreaNum,
JSESSIONID, cmtokenid, cmjsSSOCookie
```

之后在 `nact/action.do` 上调用 `initIndexPage` 和 `doSign` 即可。

## 签到状态字段

`initIndexPage` 的 `resultObj` 中：

```text
isLogin          是否登录
isSignToday      今日是否已签到
monthSignCnt     本月已签到天数
toolSignList     签到记录（signDate / signState / state）
weekList         当前周日期
today            服务器当天日期（YYYYMMDD）
```

活动 H5 没有单独的“连续签到”字段，连续天数按 `toolSignList` 中 `signState=1` 的日期从今天向前逐日计算。

## SecurityGuard / unidbg 状态

APK 12.5.6（腾讯 v7a 包）解出：

```text
lib/armeabi-v7a/libsgmain.so
  └── lib/armeabi-v7a/libsgmainso-5.6.230509.so
```

unidbg 已能加载 v7a `libsgmainso`、执行 `JNI_OnLoad`、调用 `10101`。`10602 getAppKeyByIndex` 仍抛 `106440105`；已尝试 `0F09868011039`、`jtztty_sdk#GD70958956615`、`jtztty_sdk#ZH46048899506` 等 appKey 和多个 authCode 组合，均失败。该错误来自独立插件缺少主 App 运行时的 `authCode` / 完整 Context，因此本链路改用等价原生登录，不再依赖 `10401` 签名。

## 脱敏抓包样本

仓库内保留了这次抓包的代表性片段，已去除 Cookie、token、手机号、设备标识和签名：

```text
analysis/samples/autoLogin.sanitized.json
analysis/samples/jtWx10086AuthLogin.sanitized.json
analysis/samples/hyl-sso.sanitized.json
analysis/samples/act2510-initIndexPage.sanitized.json
analysis/samples/act2510-initChallengeFloor.sanitized.json
analysis/samples/profile.example.json
```

原始 flow 仍在 `out/captures/`（gitignore），含真实凭证，不提交。重新生成样本：

```bash
python3 analysis/sanitize_flows.py --input out/captures/flows/<id>.json
```

## 一次性抓包

当前方案只需要一次 App 冷启动抓包，用于提取 `autoLogin` 模板：

1. mitmproxy 代理手机，安装并信任 CA；
2. 杀掉中国移动 App，冷启动，进入签到页；
3. 抓到 `POST client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin`；
4. 解密请求体，保存模板/profile（`0600`）。

原始抓包和 profile 含手机号、`xk`、`cellNum`、Cookie、token，不能提交或公开。生产 profile 只放在青龙 `data/config/`。

## 验证记录

2026-11-19 在青龙容器实测：

```text
autoLogin                 retCode=000000
appTokenLogin             code=SUCCESS
getYDRZToken(039014)      code=SUCCESS
jtWx10086AuthLogin        authLogin success
initIndexPage             isLogin=true
doSign                    resultCode=1
后续 initIndexPage        isSignToday=true
```

青龙任务日志：

```text
登录=成功 今日已签到=True 连续签到=1天 本月已签=5天
飞书通知已发送
```

## 相关代码

- 生产签到脚本：[`script/qinglong/cmcc-checkin/cmcc_auto.py`](../../qinglong/cmcc-checkin/cmcc_auto.py)
- 接口探测原型：[`analysis/jsyd_probe.py`](../analysis/jsyd_probe.py)
- HAR 导入 profile：[`analysis/import_auto_login.py`](../analysis/import_auto_login.py)
- unidbg harness：[`unidbg/SecurityGuardHarness.java`](../unidbg/SecurityGuardHarness.java)
- 分析记录：[`notes/findings.md`](findings.md)
