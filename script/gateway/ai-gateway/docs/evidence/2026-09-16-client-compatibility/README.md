# 原生客户端兼容验证（2026-09-16）

本目录保存独立4004的分阶段证据。**OpenCode、Hermes、Claude Code、Codex CLI已分别完成小源App真实历史任务的定位、改码、未签名HAP构建和产物复核。** 四份最终产物均通过5项导航/持久化行为检查；最后一轮原生客户端于16:25完成，16:31复核。基础问候、合成读取、历史失败和真实开发结果分开保留，真机UI未验证。

## 已部署修复与可追溯制品

| 版本 | 部署范围 | 离线回归（含Go子测试） | 源码归档SHA256 |
| --- | --- | --- | --- |
| r5 | 15:16 Auto与Guard8013 | Go376、Python8、vet、5静态构建 | 7958eec00b01f6a71a51e8c978744983f417c080b4bc7c4449f1c2beeece8ee2 |
| r6 | 15:26仅Guard8013 | Go377、Python8、vet、5静态构建 | a625006d41e6faf8fd340df225b8f2a94456eea5f600cca16b1dd993a6aad142 |
| r6工具续接 | 15:42仅Auto8093 | Go378、Python8、vet、5静态构建 | e0694dae1789435af83041e9eb320b491f39bff60a37de2c56ee381b9459e582 |
| r7代码引用 | 16:02仅Guard8013 | Go380、Python8、vet、5静态构建 | 9f96c539b3c02e3f4a05cbe837fdc19e3808a08534cbaf2c7260934f3e4bfe36 |
| r7输入预算 | 16:15 Auto与两服务超时配置；Guard程序不变 | Go382、Python8、vet、5静态构建 | cf2ca3de3af7692adb8795feeb2bbe3f1875e6afb3b06b26e4241e559ea81c87 |

对应`*-source-manifest.json`、`*-summary.json`、`*-go-race.jsonl`和`*-upgrade-result.json`记录清单、验证与部署元数据。源码冻结后文档改动单列验证，不重写冻结清单。

r5修正Basic普通词误报与三协议未知模型404；r6识别工具说明中的完整认证模板。r6工具续接在SSE完成批次交给客户端前持久化调用绑定，旧实现的针对性回归失败、新实现通过；不完整流不建立绑定。这三个阶段的规则为`preflight-r6`、正文契约`credential-redaction-v1`、分类策略`semantic-v5`，状态schema不变。

## 基础客户端结果（开发任务开始前）

| 客户端 | 原生版本 | 问候 | 只读工具回合 | 证据 |
| --- | --- | --- | --- | --- |
| OpenCode | 1.18.4 | r5通过 | r6失败；Qwen Controversial/Jailbreak | r5-opencode-summary.json、r6-opencode-tool-summary.json |
| Claude Code | 2.1.233 | r5通过 | r6通过，实际Read及正确结果 | r5-claude-summary.json、r6-claude-tool-summary.json |
| Codex CLI | 0.154.0 | r6通过 | r6曾503；15:42修复后通过 | r6-codex-summary.json、r6-codex-tool-summary.json、r6-tool-codex-summary.json |
| Hermes | 未连接真实进程 | 未验证 | 未验证 | 本机未安装；CTYun SSH两次返回connection closed |

`r5-entry-checks.json`包含三协议未知模型404、真实合成凭据使用403和工具说明普通Basic文字问候200，共6项。之前失败摘要不覆盖。

OpenCode失败发生在安全模型，Go凭据硬拦未触发。第一块20000字符判Controversial/Jailbreak，其余20000与18968字符均Safe。单独系统文本分段Safe；相同原始JSON分块可重复误判，尚未证明可靠修复。strict/fail-closed保留，不能通过跳过工具、删系统提示或关闭保护取得通过。

Codex采用Responses HTTP SSE；原生CLI对普通OpenAI模型列表缺少Codex专用元数据有fallback提示。图片、WebSocket、compact、超长上下文、取消、多工具/子agent及多人实流量不在这些基础结果内。

## 部署和数据边界

只更新`/data/ai-gateway/acceptance-tokyo`，入口4004。更新前进入维护503并等待8093连接排空，留存配置、二进制、源码及状态备份；内部密钥与重开入口前状态相同，其他容器ID/镜像/启动时刻/重启计数相同。4000/4001未切换。一次性带锁脚本没有替代总计划尚待实现的通用发布/升级/回滚工具。

16:15当前Auto SHA256为`2394ea339c9edf0d63b326f7f18dbe348dd6dfb813c1de6a819fc34da01128b6`，Guard为`19f33884ea5682b34d34dcec1614e51cb7d328fde461dfd0b412e0c6e5cf9664`；回退备份为`/data/ai-gateway/acceptance-tokyo/backups/r7-budget-20260916-161459`。此记录只证明本次备份与更新检查通过，未演练执行回退。

仓库只保存元数据、合成单元回归和清单；不保存真实Key、原始请求、工具正文或思考签名。客户端原始调试输出仅位于受限临时目录，Guard脱敏审计仍留服务器。

## 小源真实历史开发流程（最终结果）

来源是用户任务“修复退出登录状态未清除”，任务ID `019fcb9a-55e9-70b1-99d6-60912a1c9bab`。四份副本均来自修复提交`5b3a9d1`的父版本`2e394cb6b0847619dad1e52d99662ffb0a2e8b0b`，保留真实ArkTS工程与Android导航参考；未给客户端历史答案。只排除签名/发布材料并替换无关第三方Key为契约占位符，允许生成未签名HAP，未修改原小源项目。来源/准备变更见`xiaoyuan-source.json`。

r6首轮四客户端均完成了实际代码读取，但被凭据误报拦截；`xiaoyuan-r6-first-runs.json`保留失败。r7识别interface类型、带可选链/明确fallback的成员引用及完整反引号认证模板；真实字面量仍保护。r7于16:02只更新Guard，380项Go/Python8/vet/5构建通过，源码119文件，元数据见`r7-*`。

四个进程均使用原生CLI及自己的文件/终端工具，通过4004的`auto`模型执行任务；没有用协议请求脚本替代客户端，也没有由验收方直接替客户端改App代码。Hermes使用临时目录内的官方0.21.0固定提交`29112bef099274229cadff79cdff7bf7b99c4b77`，未改既有CTYun服务或全局配置。Claude使用Messages，Codex使用Responses HTTP SSE，Hermes本轮使用其Messages传输；本轮不是Hermes Chat传输验收。

| 客户端 | 原生版本 | 实际开发与评审 | 最终改动 | 最后一次HAP构建 | 行为检查 |
| --- | --- | --- | --- | --- | --- |
| OpenCode | 1.18.4 | 独立定位、修改、构建；与历史最小修复一致 | Navigation，4增1删 | 成功，22.183秒 | 5/5 |
| Hermes | 0.21.0 | 首次构建遇到ArkTS重载顺序错误，自己修正后重建 | Navigation，13增6删 | 成功，10.416秒 | 5/5 |
| Claude Code | 2.1.233 | 首版增加推送逻辑；收到评审反馈后由原生CLI收回并重建 | Navigation，5增1删 | 成功，3.563秒 | 5/5 |
| Codex CLI | 0.154.0 | 首版削弱HTTP独立清理且增加推送逻辑；原生CLI按评审恢复并重建 | Navigation，19增7删 | 成功，11.427秒 | 5/5 |

所有最终副本只有`entry/src/main/ets/capabilities/Navigation.ets`变动；HttpClient及Login与各自Git index基线逐字节相同，原小源仓库仍干净。Codex最终清理逻辑还覆盖未注册导航栈和单个键删除失败的情况，未删除HTTP原有独立清理。构建时间包含增量构建差异，不能用来比较客户端速度。四端接入的是同一个`auto`策略，审计本轮有效模型均为`gpt-5.6-terra`，不是四家原生模型质量横评。

行为检查实际执行转译后的Navigation源码，使用合成持久化存储/导航适配器验证四个会话键在导航前清除、冷启动登录标志消失、其他页面和无关偏好保留。修复前同一检查失败，四份最终产物通过；它不等于HarmonyOS真机UI测试。HAP和构建日志时间均晚于最后源码修改，保存SHA以关联产物。Codex最后构建遇到hvigor守护进程端口不足，自动转为无守护进程构建成功。

最终证据：

- [四端最终结果](xiaoyuan-final-results.json)：版本、执行时间、首版/评审run ID、修改文件、行为检查、HAP/日志/diff SHA和验收边界。
- [网关会话汇总](xiaoyuan-final-route-summary.json)：只按session摘要或响应request ID关联，导出次数、模型、完成状态等元数据；无提问或工具正文。
- [来源与准备](xiaoyuan-source.json)、[修复前失败基线](xiaoyuan-baseline-behavior.json)、[行为检查程序](verify-navigation.cjs)。
- [r6首轮失败](xiaoyuan-r6-first-runs.json)、[r7前三端首版](xiaoyuan-r7-first-three.json)、[Codex首版评审不接受](xiaoyuan-codex-budget-first-result.json)均保留；旧文件的workflow_pass指当时完成改码/构建，最终质量以最终结果为准。
- 私有副本及原始输出位于`/private/tmp/gateway-xiaoyuan-20260916`，分别为`opencode`、`hermes`、`claude`、`codex`；每份HAP在`entry/build/default/outputs/default/entry-default-unsigned.hap`。临时目录不是长期归档，仓库只保留脱敏元数据。

Codex r7真实开发阶段遇到`9e089070cd00af2d9ea611d3496effd4`的503：131942字符/7块，入口耗时3.103秒；单独暖缓存重放992ms、全Safe。16:15部署4004专用Guard30秒/Auto35秒完整输入预算后，Codex完成任务及评审修正，未再出现该Guard阻断。用户取消及fail-closed保留；这不代表并发容量达标。OpenCode/Hermes完整任务发生在r7的旧预算下，Claude首轮使用旧预算、评审使用新预算；Guard规则和SSE绑定代码一致，不能宣称四个完整任务都在16:15版本从头重跑。

16:18在最终部署版本重跑6项入口正反检查全部通过，见`r7-budget-entry-checks.json`；实际容器配置/二进制/就绪检查见`r7-budget-live-state.json`。Hermes原生过程包含一次3秒Guard 503后恢复，14次上游完成记录；不将SDK恢复隐藏成无错误运行。

服务器对Codex成功开发首轮和评审轮分别记录3次、2次`upstream_failed`，这些条目同时为HTTP200、`response_complete=true`，客户端均正常续接并完成。当前审计将流式转发错误统一归为upstream_failed，没有记录具体错误类别；已有元数据不足以认定5次都是正常关闭，传输末尾错误归因仍待细分。这不影响已核验的四份App产物，但不能将本轮写成零传输错误。

尚未验收：HarmonyOS真机/模拟器UI、完整客户端压缩/取消/子agent、图片/WebSocket/超长上下文、Hermes Chat传输、多用户真实Key、全部模型及最高effort、生产4000/4001切换。OpenCode早期合成工具请求的Qwen语义误报仍保留为已知质量限制。一次历史开发任务通过不替代这些项目。

## 用户随后测试：简单问候的模型选择（16:49只读诊断）

16:44、16:45 OpenCode原会话的两次问候已成功，原生本地记录与4004用量的时间/token对齐。[诊断元数据](opencode-greeting-diagnosis.json)只保存布尔确认、模型、分类结果、次数及用量，不复制用户正文或工具内容。

| 用途 | 第一次 | 第二次 |
| --- | --- | --- |
| 固定分类Sol/none | 输入15120、输出82token | 输入15151、输出82token |
| 分类结果 | simple、5分、0.99，无复核 | simple、5分、0.99，无复核 |
| 实际回答Terra/none | 输入10945、输出12token | 输入10964、输出6token，缓存读10752 |

分类器正确识别为简单任务，但完整请求≥8000 UTF-8字节即添加long_context，当前目录不给Flash/Luna该能力，因此能力筛选强制从Terra起步。该门槛包括OpenCode自带系统/工具背景，未按各模型真实上下文容量判断；Sol则来自固定分类配置。此次证明链路可用，并暴露预算筛选过粗和分类开销较大的问题，尚未修正。下一步需核实各模型容量再修改预算匹配，分类开销单独评估；不能把这两次成功记作选型合理性的证明。
