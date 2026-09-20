# 小源 App 历史任务脱敏回放

时间：2026-09-15 17:03–17:06（Asia/Shanghai）  
环境：qiyuan-gpu 临时 Auto `127.0.0.1:8092` → 本机 Guard `127.0.0.1:8011` → 东京前置 `106.14.254.110:9881`。未修改生产 `4000/4001`。

## 回放来源

从历史小源鸿蒙 App 会话提炼了登录 UI 对齐、网络传输异常、长文本省略、退出登录持久化、PRO 发布审计和跨模块架构设计六类任务。仅保留任务类型和脱敏摘要，不包含账号、密码、API key、真实日志、域名或代码片段。

## 鉴权失败的路由诊断结果（未通过全流程验收）

| 回放 | Guard | 分类分数 | 实际路由 | 内部 effort | HTTP | 说明 |
| --- | --- | ---: | --- | --- | ---: | --- |
| 登录 UI 对齐 | allow | 1 | deepseek-flash | none | 401 | 请求已到达东京前置；本次命令未携带认证凭据，401 是上游认证边界 |
| 网络传输异常处理 | allow | 1 | deepseek-flash | none | 401 | 同上 |
| 长文本省略 | allow | 1 | deepseek-flash | none | 401 | 同上 |
| 退出登录持久化 | allow | 1 | deepseek-flash | none | 401 | 同上 |
| PRO 发布审计（抽象描述） | allow | 1 | deepseek-flash | none | 401 | 同上 |
| 架构设计（单轮摘要） | allow | 33 | gpt-5.6-terra | low | 401 | `quality_upgrade` |
| 架构设计（12 条多轮上下文） | allow | 100 | gpt-6-astra | xhigh | 401 | `long_context` + code/debug/architecture/agent 信号 |
| 同一 12 条上下文重复请求 | allow | 100 | gpt-6-astra | xhigh | 401 | 会话保持最高档位；本次因上游 401 未产生响应缓存命中 |
| 含持久化与混淆词的正常开发重建任务 | block | — | — | — | 403 | Guard `cyber_boundary_sample`；已阻断，但不能据此认定任务恶意，需做误拦复核 |

allow 后尝试上游的请求写入 Auto audit/usage；block 只写审计，不进入业务 usage。usage 使用 `api_key_id=test`，记录实际模型、effort、attempt、success。401 请求的 `success=false`，没有虚构 token 用量。此前使用授权 Tokyo test Key 的真实 200 与响应缓存命中证据仍见 [stage12 retest](../2026-09-15-auto-stage3/stage12-retest.md) 和 [stage12 cache runtime](../2026-09-15-auto-stage3/stage12-cache-runtime.md)。

## 更正后的结论

本轮只有 Guard 与路由决策、上游鉴权失败证据，没有成功业务模型回复。flash→terra 出现在 `xiaoyuan-replay-20260915` 会话；astra 出现在另一个新会话 `xiaoyuan-high-safe-20260915` 的 `initial_selection`，之后两次 keep。**不能称为同一会话 flash→terra→astra 的连续成功升级，也不能称为最高档全流程验收完成。** 12 条上下文由历史任务摘要重建并追加英文术语，属于合成探针，不是原始会话逐条重放；其高分只能用于检查路由分支，不能证明分类质量。

原报告把 403 称为“敏感任务被正确拦截”也不严谨：Go 规则会把“持久化”和 `obfuscat` 同时计为安全信号，Strict 模式聚合为 block。应用登录状态存储与发布混淆都是正常开发活动，应列为疑似误拦反例，保留拦截机制，独立复核规则/Guard 结果；不得改写同一被拦输入来制造放行证据。

分类器不只缺中文：真实开发摘要的英文改写也可能被判为普通问答；语言对照实测见 [多语言诊断](../2026-09-15-multilingual-classifier/README.md)。后续按总计划的多语言语义分类重设计验收，不能以追加关键词作为完成标志。
