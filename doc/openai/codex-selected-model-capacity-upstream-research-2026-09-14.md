# Codex `Selected model is at capacity` 上游故障核查（2026-09-14）

## 结论

**高置信度判断：这是 OpenAI 上游 Codex / ChatGPT Work 的模型服务容量或路由问题，不是当前图片文件损坏、图片上传格式错误或本地代理配置导致的典型症状。**

最直接的证据是：OpenAI 官方状态页在 **2026-09-14 当天**记录了 [`Elevated error rates for Codex and ChatGPT Work`](https://status.openai.com/incidents/01M2EWYR55J47M2BPG9WC76VEG)。事件从 02:46 开始调查，03:42 应用缓解，03:57 标记恢复。当前[状态总览](https://status.openai.com/)已显示 fully operational，但官方同时声明，状态数据是跨套餐、模型和错误类型的聚合指标，个别账户、模型及功能的可用性可能不同。

OpenAI 的[官方 API 错误码文档](https://developers.openai.com/api/docs/guides/error-codes)也明确区分：

- `503` + `service_unavailable_error` + `server_is_overloaded`：所请求模型当前没有足够容量，应遵循 `Retry-After` 或稍后重试；
- `429`：速率、额度、组织/项目用量或余额问题；
- 网络、代理、TLS 等问题通常归入连接错误，而不是 `server_is_overloaded`。

因此，界面提示 `Selected model is at capacity. Please try a different model.` 与官方定义的“模型暂时过载”一致。它可能来自全局容量压力，也可能只影响某些模型、账户或后端路由；公开证据不足以再精确到某一内部调度原因。

## 为什么不像图片上传故障

1. 今天的官方事件范围是 **Codex 和 ChatGPT Work 的 elevated error rates**，不是单独的 file upload 或 image generation 组件。
2. OpenAI 在 9 月 8 日确实分别记录过[文件上传失败/延迟](https://status.openai.com/incidents/01M20QBACYZMK2PRCJQCBSWTYJ)和[图片生成错误率升高](https://status.openai.com/incidents/01M20PYYYGRT9303VHAPA7YNT2)，但两者都已在当天恢复，且其错误描述是上传处理失败、图片请求失败，而不是模型容量提示。
3. `openai/codex` 的 [#43337](https://github.com/openai/codex/issues/43337) 用全新临时会话、禁用用户配置、仅要求返回 `OK` 的纯文本最小请求，也在多个模型上得到同一容量错误。这直接说明该错误不要求图片输入才能触发。
4. 2026-09-11 至 09-12 官方还记录过[部分既有 ChatGPT Work 会话 turn 失败](https://status.openai.com/incidents/01M28MEQWTQJDRCRPFD9FWQ0H3)，与“旧会话报错、新会话有时可继续”的现象一致，但不能据此断言旧会话本身已损坏。

图片可能增加请求体和推理负载，从而更容易撞上紧张的服务路径；这是合理推断，不是官方确认的根因。仅凭“上传图片后开始报错”不能证明图片上传链路有故障。

## 官方与一手证据

### OpenAI 状态页

- [2026-09-14：Codex 和 ChatGPT Work 错误率升高](https://status.openai.com/incidents/01M2EWYR55J47M2BPG9WC76VEG)：与本次发生日期和产品表面完全重合，已标记恢复。
- [2026-09-11 至 09-12：约 1% 的既有 ChatGPT Work 会话 turn 失败](https://status.openai.com/incidents/01M28MEQWTQJDRCRPFD9FWQ0H3)：说明故障可能偏向既有会话。
- [2026-09-11：GPT-5.6 Sol API elevated errors](https://status.openai.com/incidents/kyrqx6zs)：官方称增补容量后错误开始改善，证明近期确有模型容量扩容与过载事件。
- [2026-09-04：APAC 的 ChatGPT、Work、图片生成、文件上传、语音和 Codex Cloud 错误增加](https://status.openai.com/incidents/01M1NKFZH5EEYEREC54HNAHY35)：表明亚太地区近期也发生过多组件上游故障，已恢复。
- [2026-07-09：多模型出现同一 `Selected model is at capacity` 文案](https://status.openai.com/incidents/01KX46HHYJ0YB8VPBZTB0KZ03V)：官方原文明确承认多个模型收到该错误。
- [2026-06-16：Codex `Selected Model is at Capacity` 事件](https://status.openai.com/incidents/01KV7ZT644J4V94GSXMFPY2ANR)及[2026-07-17：Codex 5.6 Sol server-overload](https://status.openai.com/incidents/01KXRHE25717D2WQ1WFMT2B7WZ)：证明这类文案此前已被 OpenAI 作为服务端事件处理。

### OpenAI Developer Community

- [2026-07-17 集中报告](https://community.openai.com/t/codex-desktop-repeatedly-shows-selected-model-is-at-capacity-during-active-tasks/1387316)：OpenAI Support 回复“sounds like an issue on our end”，随后指向官方状态事件并宣布恢复。
- [GPT-5.6 Sol 持续容量问题](https://community.openai.com/t/gpt-5-6-sol-repeatedly-hits-selected-model-is-at-capacity-in-codex-desktop/1388332)：有人更换热点、关闭 VPN 和 Secure DNS 后仍复现；可用于削弱“只由本地网络造成”的假设，但仍属用户个案。
- [2026-09-11 Astra 继续出现同一报错](https://community.openai.com/t/codex-desktop-selected-model-is-at-capacity-again-on-gpt-6-astra-sept-2026/1396564)：说明近期问题不局限于 Sol。

论坛内容除 OpenAI Support 明示外均视为用户报告，不等于官方根因认定。

### `openai/codex` GitHub Issues

- [#41810](https://github.com/openai/codex/issues/41810)：付费账户的长任务执行中途被容量错误打断，仍为 open。
- [#43337](https://github.com/openai/codex/issues/43337)：在周额度 100% 可用、临时会话、禁用用户配置的情况下，纯文本最小请求仍在多个模型失败。
- [#43398](https://github.com/openai/codex/issues/43398)：Linux 环境无代理变量，GPT-5.5、5.6 Sol、GPT-6 Astra 等多个模型同日失败，仍为 open。
- [#43786](https://github.com/openai/codex/issues/43786)：多名 Pro 用户的集中可靠性报告；issue 本身没有 OpenAI 根因回复，因此只能作旁证。
- [#44113](https://github.com/openai/codex/issues/44113)：同一机器、网络、应用版本和项目下，一个 Plus 账户全模型失败、另一个账户正常。该对照更支持“账户级后端路由/容量分配也可能参与”，但尚未获官方确认。
- [#44395](https://github.com/openai/codex/issues/44395)：2026-09-10 的 Pro 20x 新报告，说明近期仍有持续复现。

## 中文社区交叉核对

- [LINUX DO：2026-09-07 客户端更新后多模型报 capacity](https://linux.do/t/topic/2866290)：正规 Pro/Plus 用户集中反馈，部分账户正常、部分异常；帖子后来更新“恢复了”。
- [LINUX DO：2026-06-25 集中出现同一报错](https://linux.do/t/topic/2473360)：官方订阅和第三方中转用户均有报告，说明不能把所有案例统一归咎于某个中转站。
- [V2EX：2026-09-11 `Codex 是不是炸了？`](https://www.v2ex.com/t/1240974)：报告同一容量提示及 502，时间接近近期官方故障窗口。
- [V2EX：2026-09-03 `你们的 Codex 还好吗？`](https://www.v2ex.com/t/1238817)：帖子贴出了 `service_unavailable_error / server_is_overloaded` 上游结构，并有 Sol 异常、Terra 可用的交叉报告。

这些中文社区帖子只能证明现象并非单机孤例；其中关于风控、封号、降智、IP 或账号新旧的推测没有官方证据，不能作为结论。检索 V2EX、LINUX DO、掘金、知乎、Hostloc 等公开索引时，后面三者未找到足够相关且可核验的近期材料。

## 概率判断

| 假设 | 判断 | 依据 |
| --- | --- | --- |
| OpenAI 上游模型服务/调度容量异常 | **高** | 当天官方 Codex/Work 故障；官方错误码定义；跨平台、跨模型集中复现 |
| 账户级或区域级后端路由/容量分配 | **中** | 同环境不同账户结果不同；APAC 曾有单独事件；官方状态明确说个体可用性会不同 |
| 图片输入专用链路故障 | **低到中** | 图片可能提高负载，但纯文本最小请求也会出现同一错误；当天事件并非图片专项 |
| 本地代理/网络是主要根因 | **低** | 同一文案有官方事件；无代理环境和更换网络仍有复现。若中转篡改错误文案，则仍需以原始 HTTP 状态和错误体复核 |
| 周额度/账单耗尽 | **低** | 官方文档将 503 overload 与 429 配额/余额问题分开；有 100% 剩余额度的最小复现 |

## 建议的非破坏性处置

1. 保留原会话和本地改动，不删除会话、不清缓存、不改代理规则。
2. 先重试一次同一会话；若仍失败，临时换模型或在新会话继续。这是绕过，不是根治。
3. 核对 Codex Usage 页面，确认没有明确显示额度用尽；容量提示与额度提示不要混为一谈。
4. 持续失败时记录：本地时间和时区、所选模型/推理强度、应用版本、任务 ID、`/feedback` ID、是否纯文本也失败。不要公开账户令牌或完整日志。
5. 如能拿到原始错误，优先看 HTTP 状态及 `error.type` / `error.code`：`503 + server_is_overloaded` 基本坐实服务端过载；`429` 才转向速率/额度排查；连接/TLS 错误才优先查代理。

## 结论边界

OpenAI 已把今天的聚合事件标记为恢复，所以无法仅凭公开资料证明当前某个具体账户仍处于官方未解决事件中。结合相同日期、相同产品面以及近期大量一手复现，足以判断本次首先应按上游容量/路由异常处理；但要区分“全局容量”“特定模型池”“账户级路由”或“区域调度”，仍需 OpenAI 依据任务/feedback ID 查询内部日志。
