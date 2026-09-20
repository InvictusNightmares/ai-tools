# Auto 路由组件

AI Gateway 内的 `auto` Go 包，由项目根目录 `cmd/auto-server` 启动。生产 4000/4001 尚未切换到 Auto。唯一执行计划是 [智能网关与 Guard 分阶段实施总计划](../docs/智能网关与Guard分阶段实施总计划.md)。当前部署与验证结果见 [CHANGELOG](../docs/CHANGELOG.md#unreleased)；[2026-09-15语义评估](../docs/evidence/2026-09-15-auto-semantic)和[2026-09-16隔离实测](../docs/evidence/2026-09-16-input-redaction/README.md)分别对应其原版本。

## 实际请求顺序

本源码的选型策略为 `semantic-v10-task-routing-r2`（运行版本见总计划）： 区分 summary/extraction 与代码实现、审计、诊断；普通信息整理满足低不确定性、无失败、无复杂推理及非开发/审计混合标签时，优先 DeepSeek none。其余语义任务按 simple/bounded/multi_step/complex/exceptional 对应 0/1/2/3/4 的质量下限筛选，原生能力、上下文、effort 和健康度仍先检查，不足时向上选择或明确不可用。下限是当前可审查策略，不是普遍能力排名；实际任务失败仍须回到能力画像修订。

独立复核可纠正高估和低估。同一供应商工具回合只在任务及之前历史摘要、策略版本一致，且输入为纯工具结果时复用已验证分类；不跨目标、媒体、身份或协议复用，不代替 Guard。增加工具定义仍重算能力/上下文。旧工具状态缺少新字段时保守重分类；旧版本可忽略新增可选字段。新的用户轮次若超过当前模型质量/effort 下限立即升级，不受冷却阻挡。路由审计记录任务类型、策略与目标档位；`tool_binding_reused` 与分类缓存命中分别记录。

`身份校验 → Guard → 语义分类或分类缓存 → 能力过滤与会话路由 → 业务响应缓存或供应商 → 结果审计与用量`

- `auto-server` 要求显式配置固定分类端点、主分类模型与独立复核模型。中文、英文和混合输入使用同一 schema 和难度定义；词表分类只保留在 `auto-preview` 与旧单元测试中。
- 分开分析当前任务、系统约束、历史和工具结果。输出任务标签、阶段、约束/推理依赖/失败尝试、影响范围、不确定性、验证要求和续接状态。除高置信且满足上述全部约束的普通信息整理外，非simple任务、低置信或主分类失败时独立复核；都失败返回 `503 classifier_unavailable`。自报 confidence 不是正确率。
- 主分类默认目标 `none`，再经过各模型能力表映射（Astra 实际 `low`）；复核目标 `low`，输出上限 2048；业务请求的 effort 由任务复杂度生成。客户端的 `reasoning_effort`、`reasoning`、`thinking` 均不参与选择或透传。
- 分类 cache 默认 5 分钟/1024 项，HMAC 包含区域、Key、会话、完整规范化上下文、工具和模型/策略版本；只存分类结果，不存提示词。完整业务请求另外保留并计入响应缓存摘要，输出上限等参数变化会失效。
- 规范化请求保留工具调用和结果、Responses instructions、工具描述及原始业务字段。供应商 payload 注入网关生成的路由参数，并将已结束回合转为可跨模型传递的历史；当前工具回合的私有思考和调用 ID 原样保留。原生图片/文件由具备对应能力的分类/业务模型读取，附件字节不进入文本Guard；仅有provider存储历史且无法恢复的请求仍失败关闭。
- Token 预算暂用 UTF-8 字节保守估计，兼容字段名为 `byte_budget_upper_bound`；它不是实际token计数，也不是包含供应商内部framing的严格上界，不决定难度。五档目录与最低档位是可调整的路由策略；三项目五模型产物已实测，复杂启动任务均有漏项，不代表普遍能力排名。
- 任务变复杂可跨档升级。工具结果按区域、Key、协议和调用 ID 绑定原供应商回合；父/子 agent 即使共用会话头，也按各自调用 ID 续接。工具结果伴随新要求时，分类器会读取新要求，但这一工具回合仍保持原模型。缺失、跨 Key 或过期绑定返回明确不可用，不凭当前会话状态猜测模型。
- 会话来源依次支持 `X-Gateway-Session-ID`、Claude Code 的 `X-Claude-Code-Session-Id`、Codex 的 `session-id`、OpenCode 的 `x-session-id`、`session_id`/`conversation_id`，以及 Claude `metadata.user_id` JSON 中显式的 `session_id`。`X-Gateway-Agent-ID` 和原生 `x-claude-code-agent-id` 用于隔离子agent，父线程引用不作为自身身份。普通用户 ID、首条提示词、prompt_cache_key 都不当作会话 ID；缺少标识时按独立请求处理，已登记的工具回合仍可按调用 ID 续接。两地四端已按总计划P01记录实际版本的高级矩阵，后续客户端升级仍须复验。
- v16起对Responses末尾的OpenCode用户本地task/bash完整记录增加`local_tool_history`能力约束，仅在没有已有供应商工具绑定时生效。东京真实通道中的DeepSeek对此形状要求原模型推理记录，东京原Key和无映射Key均400；四个GPT候选对相同历史200。保留原始历史，按可用能力选择模型；已有供应商绑定仍优先。该约束在读取分类缓存后应用，不改缓存里的语义分类或客户端effort；两地当前版本已采用。

## 日志与缓存

同一请求使用 `X-Gateway-Request-ID` 关联 `route_decided`、`upstream_started`、`upstream_completed/failed`、`response_cache_hit`。结果日志包含实际响应模型、ID、HTTP 状态、完整性和 token；SSE 结束/断开后才写结果。仅有选择日志不能证明模型调用成功。日志不写 Key、提示词、代码正文或响应正文。审计落盘失败在进程日志记录同一脱敏事件；上游调用前审计失败则不调用上游。

`usage.jsonl` 和 UTC 每日桶按 `purpose=classification|business` 分开；业务缓存命中不重复计供应商 token。分类缓存、业务响应缓存、供应商 Prompt Cache 是三套独立统计。响应缓存不跨模型、协议、有效 effort、Key 或版本复用，工具/流式/图片请求不缓存。JSONL 使用 0600 权限并 fsync；进程内每日聚合供当前状态查看；独立usage任务将事件导入各区域gateway_usage库，以event_id去重并断点重放，包含安全分块/决策和动作审核等用途。 `usage_reported`表示收到输入计量；失败attempt中的已知值可能仅是中途快照，不能当作最终账单。独立Sub2API账单按响应中的X-Client-Request-ID关联，保留网关request_id和供应商response ID各自含义；未知项不补造。

即使未重传工具列表，含工具历史或实际返回工具调用的响应也不进入响应缓存。会话与工具绑定写盘失败会返回错误，失败状态不发布到进程内；路由不可用写 `routing_unavailable`。Guard 请求携带同一个 request_id 和隔离后的 session_hash，需同步本地 Guard 更新后才能在 Guard 异常日志中按 request_id 对账。SSE 支持多行 data 和 CRLF，畸形事件不会因后续 `[DONE]` 被统计为成功。

`effort_requested` 是 Auto 生成的目标；`effective_reasoning_effort` 是适配器实际发送值；`upstream_reported_effort` 仅在响应明确提供时记录。三者不能混用。供应商回报值与发送值不同会记录 `effort_mismatch`，并禁止写入该次业务响应缓存。未回报的协议不能据此证明实际执行强度。东京 test 所属分组存在 xhigh/max→high 映射，详见 [实测证据](../docs/evidence/2026-09-15-auto-semantic/tokyo-test-effort-policy.json)。

## Claude Code 兼容入口

`/v1/messages` 接收 `auto`、`claude-opus-5`、`claude-sonnet-5`、`claude-haiku-4` 和 `claude-haiku-4-5-20251001`；后四个名称作为兼容入口进入同一 Auto 策略，实际模型由任务选择。`/v1/models`列出`auto`与专用`codex-auto-review`，同时提供Codex模型描述符。审计分别保留请求名、所选模型和响应模型。

归一化保留 system 数组、工具 schema、tool_use/tool_result ID、cache_control 及原始传输字段；工具结果作为续接上下文，不误当作新的用户任务。Messages 的自动 effort 写入 `output_config.effort`，保留其中的格式要求；即使映射为 none，也显式发送 `output_config.effort=none`。这是东京 Sub2API 0.1.161 桥接合同：它忽略 thinking.type，缺省 effort 会变成 medium；不能将这一扩展参数宣称为原生 Claude API 能力。

`/v1/messages/count_tokens` 同样先做身份校验、Guard 和分类，再按当前路由状态选择计数模型；不推进会话轮次，不发起业务生成，不写响应缓存。配置 `AUTO_UPSTREAM_COUNT_TOKENS_URL`，响应头 `X-Gateway-Count-Model` 标明所选计数模型。分类调用仍计入 classification 用量。计数后再发送消息时，如果任务、状态或健康度改变，可能选到其他模型。

上述边界已有本地回归；实际Claude Code的完整工具循环、SSE取消、压缩和主/子agent已完成两地GPU链路验收。图片生成/编辑已启用Flare/Sunburst；`codex-auto-review`原生契约已部署，两地原生动作审批允许/拒绝及精确账单已闭环。

[历史任务回放](../docs/evidence/2026-09-15-history-replay/README.md)包含四个项目、16 个任务检查点和 48 个三语输入。来源为历史用户请求与已报告证据，工具消息为重建，不能冒充原始客户端抓包。`auto/testdata/history-cases.json` 必须随源码打包；`semantic-eval` 按每个用例的 protocol 解析。2026-09-16 已获本批外发确认并完成真实分类修订回归，结果见 [三语历史回归](../docs/evidence/2026-09-16-history-live/README.md)。semantic-v5 明确局部编辑条数不直接提高复杂度。GPU 独立链路已完成48次真实开发工具流程及15次三语/三协议SSE递增任务，走到Astra/xhigh（Sub2API映射high）；它们不代表完整客户端或产物质量验收。证据保留前两轮的误拦、503/400和非流式504。

## 构建与试运行

在 AI Gateway 项目根目录执行：

```bash
go test ./...
go vet ./...
go test -race -count=1 ./...
CGO_ENABLED=0 go build -o bin/auto-server ./cmd/auto-server
```

在项目根目录使用 `bash verify.sh` 验证整个module；Linux主机可用 `bash verify-on-linux.sh`（宿主机需 Python 3，Go 由 Docker 提供）：检查评估脚本、Go 格式、测试、vet、race 并构建服务器与评估程序；不修改生产服务。`config/auto.example.yaml` 只是参考，程序只读取环境变量。

`auto-server`允许`regional`和`pilot`，均须loopback监听。以下`run-pilot.sh`专用于单个授权测试Key的隔离流程，需要私有Key文件、真实Key ID和每请求校验URL；多人区域入口使用文末regional模式，不能把pilot当作多人实现。

`tools/run-pilot.sh` 只启动东京测试进程 `127.0.0.1:8092`。运行前设置 `AUTO_GATEWAY_PILOT_TOKEN_FILE`、`AUTO_CLASSIFIER_MODEL`、`AUTO_CLASSIFIER_REVIEW_MODEL`、配套正文契约的`AUTO_GUARD_ENDPOINT`、全新的 `AUTO_PILOT_WORKDIR`；脚本生成临时 cache secret，将日志和状态写到该私有目录。不要把 Key 写进命令行、源码或归档。美西需独立配置上游 9880 和对应授权 Key。

真实分类评估工具：

```bash
go build -o bin/semantic-eval ./cmd/semantic-eval
./bin/semantic-eval -cases /path/cases-60.json \
  -endpoint http://106.14.254.110:9881/v1/chat/completions \
  -primary "$AUTO_CLASSIFIER_MODEL" -reviewer "$AUTO_CLASSIFIER_REVIEW_MODEL" \
  -token-file "$AUTO_GATEWAY_PILOT_TOKEN_FILE" \
  -out /tmp/new-redacted-results.jsonl -classification-only -parallel 3
```

`-classification-only` 明确表示不调用 Guard 或业务模型，不能用作全链路验收。指定 `-guard-url` 可测试真实 Guard→分类顺序，仍不证明业务模型完成。分类模型未获生产选型结论前必须显式指定，不默认采用最快候选。

当前工作包状态以总计划P01–P16表为准。四端高级矩阵、多用户、最高effort、媒体/审核/失败账单、缓存收益和三项目五模型产物画像已完成对应范围；画像中的失败如实保留。r17同制品真实模型30分钟普通负载已通过，混合长输入限制见总计划。4000/4001正式切流和第二Guard故障域由用户明确排除。

## 已结束回合与私有思考状态

Guard 始终先扫描完整文本和附件元数据；原生附件内容按用户决定透传。分类器不把 Responses reasoning item 当用户任务。转发时，已结束回合保留公开文本、phase、工具调用及结果，去掉旧供应商私有思考/签名和服务器本地 item ID；当前工具回合完整保留，仍由已有工具绑定保持模型。当前工具回合保持思考连续性；已结束回合不跨供应商复用私有思考或签名，不承诺跨回合私有状态认证。供应商Prompt Cache收益已独立实测，见模型缓存报告。

`tools/live-history.py` 测试固定历史开发样本，`tools/live-routing-ladder.py --stream` 测试五档递增的实际输出，两者只接受固定 loopback pilot、从私有文件读取 Key、把模型正文留在临时目录。SSE 缺少结束标记或带失败事件不能记为通过。它们不执行模型给出的代码或工具命令。

## Guard 脱敏正文契约（2026-09-16）

HTTP Guard 收到完整规范化 `provider_payload` 字符串。allow 必须返回 `sanitized_payload`、原始正文的 `input_sha256` 和 `redaction_version=credential-redaction-v1`；缺失、摘要不匹配、无效 JSON 或 stream 改变统一返回 `503 preflight_unavailable`，原因码 `guard_payload_contract_invalid`。因此新版 Auto 需要配套支持该契约的 Guard；当前两地Guard版本见总计划，契约版本保持不变，不能直接指向只返回 allow 的旧版生产 Guard。

验证通过后，语义分类器、三协议同步/SSE、Messages/count_tokens、工具状态和缓存都使用这一份脱敏请求；SanitizedRequest/PreparedRequest 不进入JSON审计。认证头不属于提问正文，仍按原身份逻辑传递。Guard block/unavailable 仍在这些环节之前终止。

2026-09-16本地/GPU Auto303、Guard33项race及vet/build通过，Python8项通过；r4真实17/17检查通过，包含凭据/签名/截断正反对照、三协议同步/SSE、计数及混合语言五步递增，44次外发无合成明文残留。`tools/verify-redaction-live.py` 用真实Qwen3Guard和东京测试Key验证，捕获器若发现合成凭据标记会在外发前拒绝；只记录元数据。当前脚本的 `--root` 指向统一项目根目录，需先构建 `bin/auto-server` 与 `bin/preflight-api`，再准备私有Key文件和空闲loopback端口8012/8092/8022；结束后关闭临时进程。上述真实结果属于整理前归档，后续各版本已有双区域真实入口回归，4000/4001不切换。

## 计数来源与同步长请求

东京当前Deepseek的count_tokens返回404，pilot只对此模型显式使用完整脱敏JSON的UTF-8字节估算，响应头 `X-Gateway-Count-Method=utf8_bytes_estimate`；其他模型标记 `upstream_reported`。审计包含 `token_count_method`、`counted_input_tokens`、`upstream_http_status`。估算不作为真实用量或账单，也不宣称为严格token上界；它可能让客户端较早压缩上下文。身份检查和Guard仍先执行，不把其他HTTP失败静默转换为估算。

`AUTO_GATEWAY_BUFFERED_SSE=1` 开启同步请求的SSE上游聚合，默认关闭。客户端收完整JSON，上游只调用一次，不因504再发起第二次生成；审计 `upstream_transport=sse_buffered`，直接JSON为buffered_json，原生流式为sse_relay。完整成功才可按原策略缓存；工具响应及effort不符仍不缓存。大小、取消和终止检查失败返回错误。三协议同步聚合短请求已实测；r3中英文五级及r4混合语言五级长任务均完整返回，其中Astra约140–202秒。各版本证据分开保留，不视为r4全量15条或完整客户端通过；客户端自己的超时和生产Nginx仍需单独核对。

2026-09-16 11:59验收记录确认临时服务停止、远端测试Key副本删除、生产Guard健康；本次文档补齐没有重新检查服务器。后续本地整理与部署状态见项目CHANGELOG。上述为历史时点；最高effort、原生客户端及多人能力的后续结果见总计划。

目录迁移与后续升级统一记录在 [CHANGELOG](../docs/CHANGELOG.md)；文件职责和兼容回归见[维护指南](../docs/维护指南.md)。当前两个服务从同一个 `go.mod` 构建，运行时仍通过 Guard HTTP 契约协作。


## 区域入口

`AUTO_GATEWAY_MODE=regional`使用`Sub2APIIdentityResolver`按请求委托区域`/v1/models`校验，透传同一Key进行分类、计数和业务调用。撤销/过期/额度策略由Sub2API管理，不缓存认证结果。固定ID、pilot Key、共享token在启动时拒绝，认证和上游地址须同源；客户端伪造ID被覆盖。

区域模式关闭整段业务响应缓存，保留供应商Prompt Cache；分类缓存、会话状态和网关用量按`key-hmac-v1:`标识隔离。此标识不是数据库数字ID，Sub2API自身仍按原Key记录实际模型用量。HMAC密钥须持久保存，升级不重新生成。部署及替换前兼容项见[联合部署](../deploy/acceptance/README.md)。

离线 route-preview 的持久服务可额外设置 `AUTO_GATEWAY_ROUTE_PREVIEW=1` 和权限为0600的 `AUTO_CLASSIFIER_TOKEN_FILE`。这只允许候选预览进程用两地专用 semantic Key 调分类器；生产 regional 进程设置该文件会拒绝启动，仍禁止 `AUTO_CLASSIFIER_TOKEN` 共享注入。预览分类器地址可以是专门配置的区域 Sub2API endpoint，业务上游和身份检查仍必须同源；token 文件内容不写入环境、命令行、审计或用量日志。

## 原生开发客户端与检查预算

4004已验证OpenCode、Hermes、Claude Code、Codex CLI分别执行小源历史任务的实际读代码、改代码、构建流程；Claude/Codex还由各自原生CLI完成评审修正。四份最终HAP及5项行为检查通过，真机UI未验证。[原生客户端证据](../docs/evidence/2026-09-16-client-compatibility/README.md)分别记录版本、首轮失败、评审和最终产物。旧证据初查5条Codex完整响应误记upstream_failed，后续覆盖轮转历史共发现东京12条、美西0条；旧日志不足以还原终止原因。v14补齐主动取消与客户端交付失败归因，本机四端取消回归通过，Auto v16的真实两地可见输出后取消与恢复已完成，详见总计划P15。两地四端高级矩阵已补齐；旧/v2压缩见P02，动作审核仍见P03。

`AUTO_GUARD_TIMEOUT_SECONDS`配置Auto等待Guard的时间，默认5秒，允许1至120秒，非法值回到默认。4004的Guard整份输入预算为30秒，Auto为35秒；必须让传输预算大于Guard预算。请求取消仍生效，超时仍fail closed；队列等待仍1秒/128个名额，不截断长输入。SSE完成事件交给客户端前先保存工具绑定，避免客户端立即发送工具结果时丢失原回合。

## 上下文预算与客户端身份（semantic-v6）

完整系统/工具/历史和当前请求均保留。语义路径不再用8000字节的long_context标签筛掉低档模型；按每个候选的最大输入、最大输出及总窗口匹配。长度不会改变任务复杂度或effort。legacy preview的旧标签仅用于原型回归，不作为线上语义路由依据。

| 模型 | 总窗口 | 最大输入 | 最大输出 |
| --- | ---: | ---: | ---: |
| DeepSeek Flash | 1,000,000 | 1,000,000，总窗口另扣输出 | 384,000 |
| Luna / Terra / Sol / Astra | 1,050,000 | 922,000 | 128,000 |

2026-09-16核对官方[DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/)、[Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)、[Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra)、[Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)、[Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)。DeepSeek官方1M/384K采用十进制保守值；这些是目录上限，不表示区域代理已完成上限压力实测。

预算方法`utf8_bytes_with_framing_v1`取完整规范化请求和provider正文序列化字节数较大者，加1024及每消息64、每工具256的封装余量。它是保守估算，不是准确tokenizer或计费token，也不保证任意供应商隐藏格式的严格上界。显式输出上限取三协议字段最大值，非法值拒绝选型，未指定则预留候选模型的最大输出；不删除字段、不截断正文。不再适配当前模型容量时，普通回合可切换到有容量的模型，当前工具回合拒绝跨模型切换。Guard仍先检查完整输入。

路由审计新增`context_budget`数值、方法及非法标记，便于区分任务复杂度和容量过滤。主分类/复核模型变化与semantic-v6使分类缓存重新建名空间；整段业务响应缓存继续关闭。

原始User-Agent从客户端传到Sub2API的身份校验、分类、计数和所有业务传输；没有UA时明确抑制Go默认值。只增加这一头的透传，不扩展任意请求头白名单，用户Key和可信客户端IP逻辑保持。

## 原生媒体与部署状态

运行版本与最新候选统一见总计划顶部表，冻结候选不代表已部署。历史v7两地各17/17、v6原生Codex图片/WebSocket复验结果继续保留，不作为当前候选全量通过证明。会话/工具状态采用同机共享本地卷文件事务，分类缓存跨实例/重启复用；共享卷不适用于NFS，不能当作跨主机容灾。图片和PDF三协议、Files上传/列出/元数据/原字节下载/删除、TXT/CSV/DOCX/XLSX通过真实内容验收。Messages文件走保持工具ID和增量SSE的兼容桥接；原始文件保留，Guard只检查普通文本及附件元数据，审计标明`text_and_attachment_metadata_only`。文件按Key与区域隔离，默认30天留存；50MiB/文件、128文件或512MiB/Key、4GiB/实例，整个模型请求64MiB。

图片生成/编辑仅Flare与Sunburst；普通JSON、SSE、Responses image_generation工具、multipart编辑均有两地证据。音频按用户确认不支持，Chat/Responses真实返回400 `audio_not_supported`。附件语义安全审核明确留待后续。

r11提供历史增量摘要、SSE终止阶段审计、私有版本/排空接口与SIGTERM优雅退出。原生Codex图片实测正常EOF；v14起为取消和交付失败单列阶段，并分开图片上游完整响应与客户端成功交付。发布制品、源码和状态schema见`tools/release.py`及`tools/deploy-release.py`，不再用一次性脚本作为维护入口。详见[原生媒体证据](../docs/evidence/2026-09-16-native-media/README.md)。

## 运行时健康与失败切换

v7按区域、Key、协议和模型记录真实调用结果。连续三次暂时故障后冷却30秒，重复故障逐步延长至5分钟，冷却后只放行一个真实请求检测恢复；不另行消费用户token做后台探测。只有明确429/502/503/504且尚未生成时允许最多一次换模型，原Guard结果和完整脱敏输入保持。权限错误、模糊网络超时、工具结果续接和已输出SSE不重放，每次实际尝试单独审计/计量。当前熔断状态为有容量上限的进程内状态，重启后重新采样；多Auto各自观察，不宣称跨进程共享熔断。

## 原生压缩与文件并发

原生Responses `compaction_trigger`在Guard之后选择支持压缩的OpenAI候选，加密状态保留原字节，分类器使用原生Responses读取上下文；Guard只检查普通文本及状态元数据，不声称能够检查密文语义。压缩不进入整段响应缓存。两地原生Codex远端v2压缩、续接、取消和恢复均有实测。

v10新增`/v1/responses/compact`到真实原生压缩的适配，输出经检查的用户/指令消息及原始加密摘要；普通回答或缺失摘要视为失败。旧接口的原生客户端全流程验收与实际区域部署见总计划，不能用隔离协议通过代替客户端通过。

Files上传/读取/列举/删除使用同一共享卷稳定锁，配额检查与写入跨进程串行化；已验证4进程160次上传只接受单Key上限128次。文件ID、原字节和Key/区域隔离保持，锁不适用于NFS或跨主机存储。

Files存储故障（包含跨进程锁、损坏元数据/内容）返回脱敏的`503 file_store_unavailable`；不泄露本地路径，也不将列表中的损坏项静默省略。正常缺失/到期返回404，大小和配额超限返回413。客户端写出SSE失败记`client_delivery_failed`，未完整生成时主动取消记`request_canceled`；保留已知用量，未知用量不补零，两者均不计为供应商熔断失败。终止事件已成功交付后的正常取消不把完整响应改为失败；无法确认的上游读取错误仍算失败。上述新增修复的采用版本以总计划为准。

### 原生审核与分类复核

`semantic-v10-task-routing-r2` 使用 Luna 主分类、Sol 独立复核；复核可以纠正高估或低估。高置信 simple 和满足完整约束的普通信息整理保持一次主分类；已验证工具绑定按本页规则复用。客户端 effort 不参与选型。历史 v9 使用保留较高难度的规则，其通过结果只代表旧版；当前候选三语及实际任务结果见总计划 R01。DeepSeek 业务模型与主分类器选型是两项独立决策，主分类器仍须保持 95% 门槛。

`codex-auto-review`的WebSocket无生成预热仅缓存连接内的未信任审核上下文，审计为`deferred`；只有明确由system/developer组成的设置帧适用。后续实际动作请求恢复全部上下文后必须正常通过Guard，再调用审核模型。普通HTTP和包含用户/助手/未知项的帧不能借此跳过检查。原生审核的合法effort原值只用于透传与独立计量，不参与Auto映射或选型。两地实际入口的原生允许及真实typed deny均已通过，分别核实目标文件写入/未写入和精确账单。v24省略effort时保留发送未知；上游默认medium只记回报值，不据此误报不一致。

### 多人测试迭代（2026-09-17）

已知业务模型名接受为 Auto 输入别名，覆盖保留旧模型名的 Codex 会话、压缩和子任务；未知名称仍404。所有别名仍先Guard，再由Auto选择实际模型。客户端传入的模型名和effort不能强制选型。

当前任务进入高置信度、低不确定性、无失败的总结/提取/翻译/格式整理或简单问答阶段时，允许在用户回合边界降到满足能力与上下文要求的低成本档位；未结束工具回合、流式输出中、诊断/审计混合目标仍保持原约束。降档原因记录为`routine_phase_downshift`，不要求另开会话。

拒绝审计记录协议、压缩/普通请求类别、会话摘要和模型名摘要；不保存未知模型名或原始正文。路由审计增加验证后的结构化任务判断，便于检查降档与粘滞原因。

输出能力只根据实际format判定：普通text、verbosity和空配置不要求structured；JSON模式、JSON Schema及未知格式仍要求对应能力。Messages的output_config.format纳入相同判定。请求参数保持原样，审计output_format仅记录text/json_object/json_schema/unknown枚举。
