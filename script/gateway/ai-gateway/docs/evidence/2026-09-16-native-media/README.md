# 原生图片与文件双区域验收

2026-09-16 20:11历史快照：当时4004/4005为`candidate-20260916-r11-native-v4`，Guard r11、semantic-v7-native-media。Linux452项Go、Python13、vet和5构建通过，两地各17/17入口通过。版本化发布已完成两地实际更新，故障注入/回滚演练仍未关闭。

| 验收范围 | 实际结果 | 证据 |
| --- | --- | --- |
| 原生图片 | 两地OpenCode、Codex、Claude Code、Hermes Messages，另加US Hermes Chat，全部认对合成图片 | native-client-images*.json、Hermes关联与UA元数据 |
| PDF与Files | 上传/列表/元数据/原字节内容/三协议读取/删除通过 | files-lifecycle-r10.jsonl |
| Messages PDF工具 | 两地连续SSE工具调用和结果续接4/4正确 | messages-file-tools-r10.jsonl |
| TXT/CSV/DOCX/XLSX | native-v3两地10/10真正读出标记，上传/删除均200 | office-files-native-v3.jsonl |
| 图片生成/编辑 | 两地Flare生成、Sunburst编辑4次PNG；SSE/Responses工具/multipart再6/6 | images-entry-r9.jsonl、images-advanced-r9.jsonl |
| 小源真实开发 | 四客户端真实历史缺陷，最终HAP与5项行为检查通过；US Hermes Chat开发及原生评审也通过 | xiaoyuan-final-results.json、xiaoyuan-hermes-chat-results.json |
| Guard故障 | US Guard API停机：Chat/图片/Files均503，业务usage零增量，恢复后200 | guard-fault-r10.json、us-r10-recovered*.json |
| Guard历史增量 | 东京26条完整历史1.402秒；追加27条复用22条、0.531秒；跨Key/改历史/改envelope失效，新增凭据使用block | guard-history-r11-live.jsonl |
| Codex SSE终止 | r11原生图片请求完整成功，末尾正常EOF；未据此关闭旧开发任务异常 | codex-r11-stream-audit.json |
| 音频明确排除 | 两地Chat/Responses共4次400 audio_not_supported | audio-explicitly-unsupported-r11.jsonl |

图片编辑结果已目视检查。媒体Guard范围由用户明确选择：普通文本和附件元数据；原始附件透传，附件内容语义审核留待后续。音频模型在两地Codex OAuth账号实测不支持，用户明确取消本期音频支持。

保留的失败不能抹去：r9 Messages文档200却未读取内容，r10修复；r10 TXT/Office MIME导致分类503，native-v3修复；OpenCode/Hermes（含Chat）首轮扩大推送逻辑改动，必须经各自原生客户端复核收敛，最终仅Navigation修复并重新构建。未做HarmonyOS真机或模拟器UI验收。

20:11阶段专用接口探测（历史）另列：原生上游WebSocket两地成功；compact两地直连502，东京上游错误为404；`codex-auto-review`接受请求并返回allow，但响应模型实际为Luna，尚未视为专用模型完整验收。`special-api-upstream-initial.jsonl`早期探针的completed字段仅表示JSON解析非空，不能据此判断成功，以status、output及模型字段为准。相关网关适配和配置归因仍在进行。

原始客户端日志、测试Key、附件响应与小源源代码留私有临时目录，不进入仓库。源码/mock、真实端点、原生客户端及产物质量分别记录。冻结源码清单与旧版失败证据不随后续文档覆盖。

## 21:03 补验与候选

- [双实例真实共享状态](shared-state-two-instances-live.json)：缓存跨进程与重启命中；工具从A发起、B续接仍为Terra且返回正确合成内容。
- [真实SSE排空](shared-state-drain-completed.json)：在途流完成、active=0，排空中新增请求503；[150条用例首轮超时观察](shared-state-drain-observation-timeout.json)保留为未完成记录。
- [专用动作审核](action-review-native-contract-live.jsonl)：两地只读请求allow且schema/low保留；危险提议为Guard403，并非审核模型deny。
- [native-v6冻结制品](native-v6-release.json)：463项Go/15项Python，逐组件哈希/版本、共享文件事务与持久分类缓存、Codex模型目录、WebSocket跨重连会话与内存预算。部署结果另记，当前不作为已部署证明。

## 23:24 状态与故障证据补充

顶部20:11记录为历史快照；当前版本以[总计划](../../智能网关与Guard分阶段实施总计划.md)为准。东京release v10.1/Auto v10，美西release v9.1/Auto v9；Guard均v8。两地API夜间策略阻挡当前真实模型验收，不将503失败记为通过。

- `codex-native-v2-tokyo.json`、`codex-native-v2-us.json`：原生远端v2压缩/300条历史续接/取消/恢复各5/5；不能替代WebSocket验收。
- `native-v10-isolated-tokyo.json`、`native-v10-isolated-us.json`：旧compact适配经真实Guard/上游返回原生加密状态并正确续接；`codex-legacy-tokyo-night-window.json`保留完整客户端受夜间503阻挡的失败。
- `reconcile-native-v9-live.json`：两地当前入口各14条报告usage的成功调用与Sub2API独立client ID精确匹配；失败、图片、审核完整矩阵未被此证据覆盖。
- `operations-split-verification.json`：健康与导出解耦后的故障/恢复；东京显式受限路径404已验证，美西旧规则尚待推广。
- `release-concurrency-verification.json`、`release-validation-matrix.json`、`release-guard-readiness-fault.json`：实际互斥、制品拒绝、Guard连接故障前置退出；与离线回退失败测试分开记录。
- `historical-complete-errors.json`：全量轮转旧审计12条，缺少终止原因，只用于确认历史现象，不提供具体根因证明。

## 23:41 运维闭环与最新业务候选

- [两地最终运维部署](operations-final-deploy.json)、[精确入口边界](operations-final-boundary.json)、[任务和健康状态](operations-final-status.json)：东京release v10.2/Auto v10、美西release v9.2/Auto v9，Guard v8；零组件重建，正式服务保持。
- [真实双进程导出阻塞](operations-process-independence.json)健康14ms/10ms完成；[新版工具注入失败演练](operations-final-rollback-drill.json)保留现有配置/指针/状态/容器；[发布矩阵](release-acceptance-matrix.json)明确区分真实与离线范围。
- `native-v111-release.json`、`native-v111-verification.json`、`native-v11-fault-regressions.json`：Files错误脱敏与SSE客户端失败归因候选，494项Go/35项Python通过，尚未部署。不能与当前运维制品的零重建通过混为业务验收通过。
- P13/P14当前范围通过；P01/P02/P03/P04/P05/P11/P12/P15/P16及F01继续，夜间策略、保留期默认不删除和正式切流边界保持。

## 2026-09-17 01:38 最新候选与本机原生证据

- `native-v14-release.json`、`native-v14-verification.json`、`native-v14-source-manifest.json`：最新候选538项Go测试/子测试、37项Python、vet及六个Linux命令构建通过并冻结，尚未安装至4004/4005。
- `native-claude-gateway-v14-fixture.json`、`native-opencode-gateway-v14-fixture.json`、`native-hermes-gateway-v14-fixture.json`各7项；`native-codex-gateway-v14-fixture.json`为6项工具高级流程。四端使用真实原生客户端及同源码Mac网关，后端鉴权、Guard、分类及模型均为本地合成服务。原生取消各1条request_canceled、完整响应upstream_failed为0、恢复均通过。
- `native-codex-review-allow-gateway-v13-fixture.json`与`native-codex-review-deny-gateway-v13-fixture.json`：原生审批事件及私有文件写入/不写入合同通过；审核模型是合成结果，真实两地审核和账单仍待补。
- `test-resources-created.json`仅证明两地专用用户/Key/分组创建与原分组保持；随后两地资源预检通过，不表示额度/撤销/跨用户隔离的业务矩阵已经通过。保留夜间策略，真实模型验收继续。


## 2026-09-17 03:30：v15失败计量候选（未部署）

`native-v15-release.json`、`native-v15-verification.json`、`native-v15-source-manifest.json`冻结578项Go测试/子测试、37项Python、vet及六构建；Guard复用v8。直接JSON的独立账单关联与读取失败响应元数据、SSE聚合已收usage/取消归因、分类失败已知计量、动作审核非2xx关联已补齐。`native-v15-failure-usage-regressions.json`保留旧版失败及修复后结果，均为离线测试。失败时中途观察到的值不作为最终账单。

`acceptance-driver-correlation-fixture.json`验证三个验收驱动改读响应中的X-Gateway-Request-ID，客户端自设ID另列；真实v14本机网关配合成后端，缓存6次、自然探测8次及多人成功/拒绝分支关联通过，不证明真实区域或最高推理强度。


四端`native-*-gateway-v15-fixture.json`随后通过同版本原生高级回归（7/7/7/6）；每端取消各1条request_canceled、完整响应upstream_failed为0。仍为本机合成后端范围，未扩大为区域模型通过。

- `fixed-effort-correlation-fixture.json`：两份固定最高effort脚本20次合成响应ID关联通过；旧版20次错配，真实探测尚未执行。

- `native-codex-review-v15-fixture.json`：实际Codex+v15的允许、拒绝、Guard不可用、审核不可用和格式错误五路径共20项通过；仅合成后端，不替代真实区域验收。

- `cancel-after-visible-output-fixture.json`：三协议在业务文本开始后取消，v15本机18项检查通过；真实两地运行和账单仍待完成。

2026-09-17开窗：`highest-effort-fixed-regions.json`与`highest-effort-additional-responses.json`为20次固定参数实测；`native-v14-isolated-morning.json`与`native-v15-isolated-morning.json`保留东京5/6失败；`deepseek-local-tool-history-diagnostic.json`及`gpt-local-tool-history-diagnostic.json`定位Responses本地工具历史兼容边界；`deepseek-low-static-build.json`说明独立实验静态重建，尚非分类质量通过。

## 2026-09-17 08:36：r15原生与故障复验

- `native-v20-{client}-{region}.json`：两地实际Claude/OpenCode/Hermes各7/7，Codex工具6/6；Auto v16、Guard r15。Hermes旧驱动误取工具前说明的失败保留为`native-v20-hermes-premature-read-failure.json`，正式检查等待父会话finish_reason=stop。
- `native-v20-verification.json`、`native-v20-release.json`、`native-v20-guard-real.json`、`native-v20-guard-faults.json`：614 Go/40 Python、实际Qwen 42/42，队列/审计/分词器故障失败关闭；两地仅升级Guard，负载仍在复验。
- `native-v20-review-deny-http-gate-failure.json`：客户端denied可能来自Guard提前阻断，增加真实审核HTTP200条件后明确失败，不再把这个结果当审核模型deny。允许路径已实际到达审核模型，完整预热及拒绝链路继续。
- 缓存和最高档完整报告见[报告](../../最高档与缓存验收报告-2026-09-17.md)，原值及归一化解释分别保留。

## 2026-09-17 v24 审核与用量闭环

- [东京真实拒绝](native-v23-tokyo-review-deny.json)、[美西真实拒绝](native-v23-us-review-deny.json)：官方 Codex 得到 HTTP200 的审核模型 typed deny，目标文件未创建；早期 Guard 拦截记录保留。
- [v24 effort 四项](native-v24-review-effort.json)：省略 effort 保留发送未知、上游默认 medium；显式 low 正常透传，不误报 mismatch。
- [最新21次精确账单](native-v24-final-reconciliation.json)：两地真实拒绝、入口探针和 effort 均逐 request UUID / 数字 Key 精确匹配，已知 Token 无差异。
- [东京入口](native-v24-tokyo-entrypoint.json)、[美西入口](native-v24-us-entrypoint.json)各17/17。
- [r15普通负载](guard-r15-normal-load.json) 30分钟18,000/18,000，p95 94.25ms；[资源窗口](guard-r15-normal-resources.json)无OOM、队列max0、显存余量20.38%。[混合长输入负载](guard-r15-mixed-load.json)的普通p95 483ms未达300ms，仍作为限制保留。
- [模型启动第二轮](model-profile-startup-round2.json)保留传输失败、Kotlin凭据规则误判及Astra轮数上限，不把基线构建成功当成完成；第三轮使用同一初始副本及同一预算，结果另列。

## 2026-09-17 Guard r16 / release v25

- [完整验证](native-v25-verification.json)、[冻结制品](native-v25-release.json)：642项Go/40项Python及race/vet/六构建；Auto组件复用v24。后续只改画像工具，完整Python测试42项，[当前Go组件哈希](native-v25-current-source-components.json)仍与已部署制品一致。
- [真实Guard 55项](native-v25-guard-real.json)：Kotlin声明、成员/无参运行时引用放行，字面凭据仍保护；保留三角色恶意输入、真实客户端请求和长输入检查。
- [故障关闭](native-v25-guard-faults.json)：队列满、审计磁盘满、tokenizer故障均正确503，零业务上游。
- [两地部署](native-v25-deployment.json)仅Guard变更；[东京入口](native-v25-tokyo-entrypoint.json)、[美西入口](native-v25-us-entrypoint.json)各17/17。
- [第三轮传输中断](model-profile-startup-round3.json)五份均无源码改动，不评分；[真实SSH复用夹具](model-profile-persistent-relay.json)四回合完整，丢失响应不自动重放。第四轮模型产物另列。

## 2026-09-17 10:42：r17部署、模型画像与最终对账

- [v26制品](native-v26-release.json)、[完整验证](native-v26-verification.json)、[当前代码对应组件](native-v26-current-source-components.json)：644项Go/42项Python、race/vet与六构建；Guard r17修正null/布尔比较被当作凭据赋值，Auto仍v24。
- [真实Guard67项](native-v26-guard-real.json)、[故障矩阵](native-v26-guard-faults.json)均通过；[两地升级](native-v26-deployment.json)只重建Guard，密钥/状态/受保护容器保持，[东京](native-v26-tokyo-entrypoint.json)和[美西](native-v26-us-entrypoint.json)各17/17。
- [第四轮五模型产物评审](model-profile-quality-round4.json)：全部APK与21既有JVM通过，但全部存在启动需求漏项。Astra第18回合403在基础设施修复后仅续剩余6轮，共享24轮预算，不加提示、不代改产物。首轮/第二轮/第三轮失败各保留。
- [最终对账](native-v26-final-reconciliation-summary.json)：两地入口和五固定候选7个范围，165/165账单精确匹配，Token差异与已知成功账单缺失均0；完整逐请求原始元数据留GPU私有路径，并保留其SHA。
- [临时模型进程清理](model-evaluation-cleanup.json)：精确校验PID启动时间、命令、目录和二进制后停止10个loopback验收服务，Docker业务服务不变，日志/状态保留。远端Python不支持pidfd的首尝试未执行停止，确认后改用PID启动时间复核。
- [r16普通压测](guard-r16-normal-load.json)及[资源](guard-r16-normal-resources.json)：18,000/18,000、p95 98.32ms、预检队列max0、无OOM；后段分钟采样显存余量20.38%，不冒充全窗口连续采样。r17同制品独立端口接真实Guard模型的连续30分钟复验尚未结束；旧r15混合长输入延迟失败保留。

## 2026-09-17 10:59：r17连续负载完成

[30分钟结果](guard-r17-normal-load.json)与[资源及隔离制品](guard-r17-normal-resources.json)：r17同制品、同GPU真实模型与生产参数的独立18017负载：10RPS连续30分钟18,000/18,000，p95 93.61ms，预检队列max 0ms，窗口内OOM 0，分钟采样最低显存余量20.38%；结束后独立进程退出。独立18017接同一真实模型，未借用前版结果；两地实际入口验证另列。[运维快照](native-v26-operations-final.json)核实四个timer active、用量待补传0、无告警。历史混合长输入延迟失败和模型产物漏项保持。

[最终入口与清理核对](native-v26-final-boundary.json)：4004/4005健康均200，本次10个固定模型端口和独立压测18017均已关闭。
