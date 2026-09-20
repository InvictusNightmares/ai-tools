# 历史项目回放与第二轮修复

日期：2026-09-15。以下为当日归档：当时仅完成本地修改和回归，外发审批被拒绝后停止，GPU 不可达。2026-09-16 用户已确认外发、三轮分类已完成，SSH/Guard 也已恢复；最新结果见 [后续回归](../2026-09-16-history-live/README.md)。4000/4001 未修改。

## 历史样本来源

通过 Codex 历史任务读取以下四个项目场景，使用历史用户要求和已有排查证据重建测试。英语、混合表达及工具消息封装是本次编写；不宣称完整重放原始客户端请求，也不把历史任务中的命令当作当前操作授权。

| 历史任务名称 | 测试重点 |
| --- | --- |
| 修复退出登录状态未清除 | 从页面退出扩展到统一导航清理，持久化和启动恢复 |
| 排查 Android 12 离线包白屏 | 在线 VIN、独立更新检查、回调重复导航及需求修正 |
| 补齐两款App数据统计拉取 | 接口正常但前端旧包，构建成功与部署生效的区别 |
| 更新故障提醒列表取值 | 字段修正、空值、布局保留及测试同步 |

[固定题集](../../../auto/testdata/history-cases.json)包含 4 个任务 × 4 个检查点 × 3 种表达，共 48 条。检查点分别为初始要求、工具结果、用户修正和切换到新任务。工具结果包含用户修正时，新要求仍是分类对象；协议中尚未完成的工具回合则保持原模型，二者分开判断。

题集删除了凭据、个人信息和内网地址，保留必要的开发逻辑。任务标题和来源任务 ID 仅用于追溯，评估程序不会把这些来源元数据发给分类模型。标签由实现者指定，尚未独立人工复核。

## 本轮修复与本地验证

| 缺陷或边界 | 修复后行为 | 测试 |
| --- | --- | --- |
| 工具结果与用户补充要求同条发送，补充要求被忽略 | 新要求进入当前任务，工具结果仍保留 | TestToolResultWithUserCorrectionIsCurrentTask |
| 新任务标记或 TTL 导致待完成工具回合换模型 | 工具回合不重置；供应商故障不在该回合换模型 | TestToolRoundCannotResetOrFailover |
| 父/子 agent 共用会话，工具结果跟随其他请求选型 | 按 Key、区域、协议、工具调用 ID 找回原回合 | TestInterleavedAgentsResumeTheirOwnToolProvider |
| 工具结果内图片被当作文本 | 明确拒绝无法检查的模态，不假装已理解图片 | TestNestedToolResultImageIsNotSilentlyClassifiedAsText |
| 未配置 Guard 时默认 allow | 在分类、缓存和上游前返回 preflight_unavailable | TestMissingPreflightStopsAllRouting |
| Guard 使用静态/空会话，日志无法关联 Auto 请求 | 发送隔离 session_hash 和统一 request_id；本地 Guard 异常审计保留 ID | TestGuardReceivesIsolatedSessionAndRequestID、TestRequestCorrelationDoesNotInvalidateSafetyCache |
| 原有客户端会话头被忽略 | 支持显式 Codex/Claude 会话信号，普通用户 ID 和缓存前缀不作为会话 | TestClientSessionSignalsAndIsolation |
| 文件状态写入失败但内存已显示成功 | 写入失败回滚内存并返回错误，写 routing_unavailable | TestFailedStateWriteDoesNotPublishMemoryState |
| 畸形 SSE 后遇到 DONE 被记为成功；多行 data 无法解析 | 按事件帧解析，多行/CRLF 正常，畸形数据保持失败 | TestMalformedStreamCannotBecomeSuccessfulAfterDone、TestSSEMultilineDataAndCRLF |
| 工具历史没有 tools 列表时可能写响应缓存 | 工具历史与供应商实际工具响应均排除 | TestToolHistoryWithoutCatalogCannotUseResponseCache |

上述表中的已发现缺陷均有实际失败测试或对应旧代码路径作为依据；客户端会话信号和请求关联属于新增兼容覆盖。[Auto race](auto-gateway-race.jsonl)记录 258 个测试/子测试通过、0 失败；[Guard race](guard-gateway-race.jsonl)记录 16 个通过、0 失败。两模块 test/vet/race 通过，Auto、Guard Linux amd64 静态构建通过。Auto 旧一轮 race 另存为 iteration1，避免混用源码时点。

[源码归档清单](source-manifest.json)记录 87 个文件及 SHA-256，源码包为 `/tmp/gateway-history-v4.tgz`，含 Auto、Guard 两个独立模块及固定题集，不含 Key、运行日志和编译产物。Auto 相对上一版新增 7、修改 22 个文件；Guard 新增请求关联字段与测试。恢复 GPU 连接后须先校验归档和逐文件哈希，不能把本地构建视作服务器已更新。

## 仍需真实验收

1. 明确授权本批题集向东京测试端点外发后，先跑分类对照；测试不使用原始生产提示词。
2. GPU 管理连接恢复后，在全新临时目录解压、核对源码哈希并执行 Linux 验证。Auto 仅使用独立回环端口，本机真实 Guard 不可用时必须停止，不能用 mock 补齐真实验收数字。
3. 用真实供应商返回的工具调用 ID 连续回放，覆盖同步、SSE、取消、异常、并发子 agent、缓存命中及 usage/Guard 日志关联。题集中合成工具 ID 只供解析与分类检查，不能直接当作已有真实供应商回合。
4. 验证复杂任务的业务产物、构建/测试结果，与固定模型对照；分类合法、一致或 HTTP 200 都不等于任务完成。
5. 继续补齐多人鉴权/额度、事务型共享状态、每日用量落库、多模态与专用 review 契约、真实高档 effort 和回滚演练后再评估生产资格。

最高 effort 仍受东京 codex-E 的 xhigh/max→high 映射限制，专用测试分组未获批准，未修改共享组。当前本地文件状态只支持单进程；工具绑定过期/丢失会返回明确不可用，多实例恢复能力尚未完成。

**本轮及下一轮测试均不替换 4000/4001。真正验收通过后，生产切换仍作为独立操作。**
