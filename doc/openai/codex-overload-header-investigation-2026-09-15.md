# 美西、东京 Codex overload 与请求头方案核查

日期：2026-09-15；线上观测时间使用北京时间。

## 结论

找到可核验的请求头修复，涉及 `User-Agent`、`originator` 和 `version`。最相关的一手材料是 Sub2API 的 [PR #5233](https://github.com/Wei-Shaw/sub2api/pull/5233)，已于 2026-08-04 合并。它能证明项目已有针对这类症状的兼容性修复，不能单凭它认定今天两地故障的根因。X 原帖尚未定位。

**用户随后提供的论坛链接补充了更直接的近期证据：OpenAI Staff 在同帖 #87 明确提到基于账号活动的临时模型访问限制。因而这批 9 月的错误不能只按容量不足或旧请求头解释；需要同时核查账号访问状态。**

本次只读检查没有更改生产配置、程序、账号或代理规则。

## 用户提供的论坛证据

用户给出的 [#86](https://community.openai.com/t/issue-selected-model-is-at-capacity-please-try-a-different-model/1396264/86) 是故障反馈。紧接着的 [#87](https://community.openai.com/t/issue-selected-model-is-at-capacity-please-try-a-different-model/1396264/87) 于 9 月 14 日 12:39 UTC 发布：Prashant_Pardesi 表示，即使付费订阅有效，部分模型或功能也可能因账号活动而暂时受限；系统会自动重新评估，在影响可用性的活动停止后可能恢复，并且不会提供这些检查的更多细节。其[公开资料](https://community.openai.com/u/Prashant_Pardesi.json)显示 title 为 OpenAI Staff。

回复链接到官方[模型访问故障排查](https://help.openai.com/en/articles/10258669-troubleshooting-model-feature-access-issues)，该文列出工作区权限、使用上限、安全问题及账号变更等多种可能原因，并建议持续异常时联系支持。

这使“账号级访问限制”成为有官方依据的排查分支，但没有证明两地具体哪个账号触发检查、触发原因是什么，也没有证明用户违规。未找到该回复提供改请求头解除限制的方法。对当前故障仍须区分请求头兼容性、暂时容量不足、账号访问限制三种情况。

## 线上证据与边界

2026-09-15 17:57:53 的实时快照：

| 项目 | 美西 | 东京 |
| --- | --- | --- |
| Load average，1/5/15 分钟 | 0.24 / 0.19 / 0.16 | 0.01 / 0.10 / 0.19 |
| Sub2API 容器 | healthy，运行约 6 天 | healthy，运行约 6 天 |
| Nginx、PostgreSQL、Redis | healthy | healthy |

随后使用 `docker logs --since 30m --tail 3000 sub2api` 采样。美西获得一条匹配日志：17:50:04，模型 `gpt-5.6-sol`，账号 ID 42，`/v1/responses` 流式请求；日志事件为 `openai.forward_failed`，错误为上游返回的 overloaded 文案，且标记上游错误响应已写出。

东京同次限量采样没有匹配项。样本最多覆盖最近 3000 行，不能据此断言东京没有错误，也不能计算两地完整错误率。该美西记录没有原始 HTTP 状态或完整 SSE 事件，不能单凭这条日志声称已实证 HTTP 200 内嵌 overload。

后续读取线上二进制摘要、数据库结构、版本设置及更完整统计时，SSH 跳板连接持续被关闭。GPU 管理入口也出现相同关闭。没有取得线上版本设置与最终出站头；不得把本地源码当作已部署行为。

## 公开方案的演变

1. CLIProxyAPI [v7.2.110](https://github.com/router-for-me/CLIProxyAPI/releases/tag/v7.2.110) 在 7 月 30 日发布请求头管理改动；[对应提交](https://github.com/router-for-me/CLIProxyAPI/commit/a80e8082ef759aa172d23e948fe51578e0b90abf)调整官方身份头，并提供 `codex.disable-codex-cloaking` 开关。它不是可以直接复制到 Sub2API 的配置项。
2. Sub2API [#5198](https://github.com/Wei-Shaw/sub2api/pull/5198) 曾把原因归于 originator，并尝试归一化客户端名称。
3. 后续 [#5233](https://github.com/Wei-Shaw/sub2api/pull/5233)指出先前对照混入版本差异，改为统一三个身份字段，并维护客户端版本的新鲜度。作者所述内部调度机制属于项目调查结论，没有在本次找到 OpenAI 官方确认。

因此，旧教程中“只把 originator 改成 codex_cli_rs”不能作为完整处置。

## 对当前部署应核查什么

本地定制源码已经包含身份统一入口：

- `script/gateway/policy-log/source/backend/internal/service/openai_gateway_forward.go:1478`
- `script/gateway/policy-log/source/backend/internal/service/openai_gateway_passthrough.go:715`
- `script/gateway/policy-log/source/backend/internal/service/openai_gateway_service.go:64` 的编译期兜底版本为 `0.146.0`；它不是线上生效版本的证据。

上游[身份解析代码](https://github.com/Wei-Shaw/sub2api/blob/main/backend/internal/service/openai_codex_identity.go)将 UA、originator、version 作为同源字段生成；[设置解析代码](https://github.com/Wei-Shaw/sub2api/blob/main/backend/internal/service/setting_gateway_runtime.go)允许后台版本设置覆盖默认值。

建议恢复管理连接后依次核实：

1. 运行程序是否包含 #5233，以及 `gateway.disable_codex_identity_enforcement` 是否被显式关闭。
2. 后台 `openai_codex_client_version` 是否固定了旧版本，`openai_codex_client_version_synced` 与自动同步状态是否正常。
3. 最终发往上游的三个身份字段是否一致。只记录这三个非凭证字段，不导出 Authorization、Cookie 或完整请求正文。
4. 若上述已经正常，再按模型、账号、时间和协议统计 overload；检查流式终态与有界重试，避免只统计 HTTP 503。

检索时 [OpenAI 官方最新稳定版](https://github.com/openai/codex/releases/tag/rust-v0.154.0)为 `0.154.0`。应核对当前部署的兼容性与同步结果，不能仅把版本字符串改新就宣称修复。

## 官方处理与验证方案

OpenAI 的[错误码文档](https://developers.openai.com/api/docs/guides/error-codes)将 `503 / server_is_overloaded` 定义为暂时容量不足，建议遵循响应中的 `Retry-After`，缺失时增加重试间隔。[状态页](https://status.openai.com/)本次显示 fully operational，同时说明个体账号和模型的可用性可能与聚合状态不同。

下一步应先比较同一受影响账号在官方客户端中的最小纯文本请求与网关请求。若官方客户端也持续失败，优先收集时间、模型、请求 ID 与账号访问提示，联系 OpenAI 支持核查，不应将改头当作解除账号限制的办法。

若官方路径稳定成功，且发现网关头部或版本确有偏差，再做单账号小范围对照：保持模型、推理强度、网络出口与最小输入一致，交替测试现有配置和修正配置，记录原始 HTTP 状态、流式错误码、首个有效输出及最终完成结果。一次成功不足以证明修复；只有受控对照才能把请求头影响与上游容量波动分开。此项主动请求测试及配置修改尚未执行。
