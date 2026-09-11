# Sub2API `auto` 智能网关规划

日期：2026-09-11  
状态：规划稿，未实施

## 1. 目标与边界

在东京、美西现有 Sub2API 实例上增加 `auto` 门面层。客户端只看到一个模型 `auto`，网关根据任务难度选择内部模型，同时复用现有的鉴权、Key/组配额、账号调度、会话粘性、协议转换、失败切换和用量记录能力。

东京和美西提供两个独立入口，各自使用本区域的账号池、Redis 和 PostgreSQL，不做跨区域实时择优，也不做自动跨区故障切换。

不在本计划内：

- 修改现有 Key、账号、分组或区域归属。
- 让客户端继续显式选择任意内部模型。
- 新建一个重复实现鉴权、计费和协议转换的 sidecar 代理。
- 在第一版实现东京到美西的跨区调度。

## 2. 现有基础设施依据

两地当前均运行 `sub2api`、Nginx、PostgreSQL 和 Redis。现有 Sub2API 已包含按能力选号、会话粘性、配额与限流、账号失败切换、Responses/Chat Completions/Messages 转换、SSE 和 Responses WebSocket 处理。

因此推荐把 `auto` 实现嵌入现有 Sub2API 请求链路，而不是在外面再加一层完整网关。这样可以避免重复鉴权和计费，减少流式与 WebSocket 状态丢失，也不会增加额外网络跳数。

```text
客户端
  │
  ▼
区域 Nginx
  │
  ▼
Sub2API Auto Gateway
  ├─ 鉴权、Key/组配额
  ├─ Auto 难度评分
  ├─ Redis 会话档位粘性
  ├─ 现有能力筛选与账号调度
  └─ PostgreSQL 用量与路由审计
          │
          ▼
当前区域 OAuth/API 账号池
```

## 3. 对外 API

### 3.1 模型列表和模型字段

- `GET /v1/models` 只返回 `auto`。
- `/v1/responses`、`/v1/chat/completions`、`/v1/messages` 接受 `model: "auto"`。
- 缺省模型按 `auto` 处理，兼容省略模型字段的客户端。
- 客户端显式传入其他模型时返回标准 `400 model_not_found`。
- OpenAI Responses WebSocket 的 `session.update` 和每轮请求接受 `auto`。
- 返回给客户端的公开模型名保持为 `auto`；真实内部模型只进入内部日志、指标和用量记录。

### 3.2 保留的协议行为

继续支持现有的：

- OpenAI Responses、Chat Completions 和 Anthropic Messages。
- JSON、SSE 流式响应和 Responses WebSocket。
- 工具调用、并行工具调用、图片输入、缓存、compact 和长上下文。
- `previous_response_id`、`conversation_id`、`prompt_cache_key` 和现有会话粘性。
- 认证失败、Key/组配额、上游 429/5xx、重试和失败切换语义。

## 4. 内部模型梯度

模型顺序只存在于配置中，不写死在业务代码：

```text
L0  deepseek-flash
L1  gpt-5.6-luna
L2  gpt-5.6-terra
L3  gpt-5.6-sol
L4  gpt-6-astra
```

每个模型条目需要配置：

- 上游模型别名。
- 文本、代码、工具、图片、Responses、Anthropic、WebSocket 能力。
- 上下文长度和输出上限。
- 允许使用的账号或资源组。
- 失败后的降级链。
- 是否参与 `auto`。

上线前必须在东京和美西分别建立能力矩阵。模型不存在、映射缺失、账号无资格或协议不兼容时，模型不得进入可调度集合。

## 5. 难度分类

采用“规则评分 + 本地轻量边界评分器”，不为每个请求额外调用远程大模型。

### 5.1 特征

评分器只处理请求结构和统计特征，不保存请求正文。特征包括：

- 输入 token 估算值和历史上下文长度。
- 多轮消息数量。
- 代码块、文件路径、补丁、堆栈和编译错误信号。
- 工具数量、工具 schema 大小和并行工具调用。
- 图片、音频和附件。
- 显式 reasoning effort。
- Responses compact、长上下文和任务连续性。
- 结构化输出和严格 schema 要求。

### 5.2 默认分层

```text
0–20    L0 deepseek-flash
21–35   L1 gpt-5.6-luna
36–55   L2 gpt-5.6-terra
56–75   L3 gpt-5.6-sol
76–100  L4 gpt-6-astra
```

边界样本交给本地轻量评分器修正。评分器不可用或置信度不足时使用 `deepseek-flash`；如果 Flash 不具备当前请求所需能力，则选择最低能力匹配档位；没有匹配档位时返回 `503`。

## 6. 会话粘性与失败处理

- 复用现有 `GenerateSessionHash`、`prompt_cache_key`、`conversation_id` 和 `previous_response_id` 逻辑。
- Redis 保存 `api_key_id + session_hash + region` 对应的内部档位，默认沿用现有一小时粘性会话 TTL。
- WebSocket 连接生命周期内固定档位；HTTP 多轮在 TTL 内固定档位。
- 同档位优先使用现有 Sub2API 账号选择和失败切换。
- 同档位全部不可用时，按配置降级链选择下一档，默认最终降至 `deepseek-flash`。
- 鉴权、配额和能力错误不能被静默降级。
- 每次降级记录原因、原档位和最终档位。
- 东京请求只能使用东京账号池，美西请求只能使用美西账号池。

## 7. 配置接口

新增 `auto_gateway` 配置段，至少包含：

```yaml
auto_gateway:
  enabled: false
  public_model: auto
  classifier_mode: hybrid
  fallback_model: deepseek-flash
  session_ttl: 1h
  tiers:
    - name: deepseek-flash
      rank: 0
      enabled: true
      capabilities: [text, code, tools, stream]
      fallback: [gpt-5.6-luna]
    # 其他模型使用相同字段配置
```

阈值、能力、模型映射、降级链和灰度开关均应配置化，不能通过重新编译修改。

## 8. 审计、计费与指标

在现有用量记录或扩展元数据中增加：

- `requested_model=auto`
- `selected_model`
- `auto_tier`
- `complexity_score`
- `classifier_confidence`
- `fallback_reason`
- `region`
- `protocol`
- `session_sticky_hit`

计费按实际选中的内部模型计算，客户端展示模型仍为 `auto`。分类器不产生额外的用户模型用量。请求正文、API Key、OAuth Token 和代理凭证不得写入日志。

重点指标：

- 各档位请求数、成功率、降级率。
- 分类耗时、路由耗时、首 token 延迟和总延迟。
- 各账号 5 小时/7 天余量、并发和错误率。
- 模型能力不匹配、429、503 和 Redis 状态错误。
- 东京与美西分别统计，不混合区域容量。

## 9. 分阶段实施

### 阶段一：门面与分类器

增加 `auto` 白名单、五档配置、能力矩阵、规则评分、模型列表过滤和路由审计；默认关闭生产流量。完成单元测试和配置迁移测试后再进入灰度。

### 阶段二：HTTP 全协议

接入 Responses、Chat Completions 和 Anthropic Messages，加入 Redis 档位粘性、降级链、usage 记录和配额兼容性。先在一个区域用单个测试 Key 灰度。

### 阶段三：WebSocket 与双区域启用

接入 Responses WebSocket 的连接级档位固定、`session.update` 校验、断线和重试处理。完成东京灰度后，再独立启用美西。

每个阶段都可以独立合并、发布和回滚。

## 10. 测试与验收

- 单元测试：特征提取、分数阈值、边界评分、置信度不足、能力筛选和降级。
- API 测试：`/v1/models` 仅返回 `auto`；显式模型返回 `400`；缺省模型按 `auto`。
- 协议测试：Responses、Chat Completions、Messages、SSE、工具调用、图片、compact、缓存和 WebSocket。
- 会话测试：同一会话保持档位；TTL 过期重新分类；`previous_response_id` 不跨不兼容账号。
- 故障测试：模型不可用、账号池耗尽、Redis 不可用、上游 429/5xx、流式中断和重试。
- 配额测试：按真实内部模型计费，分类过程不产生额外用户用量。
- 性能验收：分类增加的 p95 延迟小于 10ms，路由决策可以关联到最终 `account_id` 和 `usage_logs`。
- 灰度验收：成功率、首 token 延迟、p95 总延迟、降级率、档位分布、账号余量和能力错误率均可观测。

## 11. 风险与上线闸门

当前文档确认了两地 Sub2API 和账号池拓扑，但规划时 SSH 别名出现 JumpServer DNS 解析失败，五个模型在两地的实时可用性尚未验证。实施前必须逐地区确认模型、协议、账号资格、模型映射和配额。

最脆弱的假设是五个目标别名能够在两地获得足够的协议能力和容量。如果该假设不成立，能力矩阵会禁用不可用模型，路由自动降级到可用档位；没有满足请求能力的模型时明确返回 `503`，不伪装成成功。

## 12. 参考资料

- [AI Code 工具网关架构与性能分析报告](ai_gateway_architecture_and_performance_report_zh.md)
- [Sub2API 东京、美西 API Key 资源分组方案](sub2api-东京美西API-Key资源分组方案-2026-08-20.md)
- [Sub2API 美西、东京账号池使用评估与整改方案](sub2api-美西东京账号池整改评估-2026-08-20.md)

## 13. 分类器深度设计（修订）

### 13.1 目标不是“按长度分档”

最适合的模型取决于任务类型、所需能力、上下文状态和失败代价，而不只是输入 token 数。分类器应先回答“这个请求必须具备什么能力”，再回答“哪个模型最可能把任务做好”，最后才用响应速度作为同等质量模型之间的决胜因素。

推荐采用四层决策：

1. **硬能力门**：协议、工具、图片、结构化输出、最大上下文、Responses/WebSocket 能力不满足时，直接排除模型。
2. **任务意图识别**：区分快速问答、翻译总结、代码解释、代码修改、调试、架构设计、长文档综合、多步工具代理和多模态任务。
3. **质量预测**：根据任务意图、上下文规模、工具复杂度、推理要求和历史结果，预测每个候选模型的成功概率。
4. **运行时择优**：在质量预测接近时比较该模型的近期 TTFT、P95、错误率、账号余量和会话缓存可复用性。

这比固定的 L0-L4 线性阶梯更可靠。五个模型仍可保留 rank 作为默认降级顺序，但 rank 不能代替能力矩阵和任务路由。

### 13.2 推荐的分类器形态

采用“硬规则 + 强语义路由器 + 在线反馈”的组合：

- 硬规则在进程内完成，延迟目标小于 2ms，负责能力排除和明显的轻/重任务。
- 对规则边界样本和复杂任务，调用专用语义路由器，要求结构化 JSON 输出，不让路由器直接生成用户答案。
- 路由器输出候选模型排序、任务类型、所需能力、置信度、理由码和不可选模型原因。
- 路由器不能绕过能力门，也不能选择当前区域不可用或健康度不足的模型。
- 记录实际结果：成功/失败、TTFT、总时延、工具调用是否完成、客户端重试、用户人工改用显式模型等，定期校准质量预测。

路由器本身不应固定绑定某个业务模型。默认使用当前可用的高质量推理模型作为 judge；如果该模型不可用，退化到下一候选 judge。`deepseek-flash` 适合作为快速任务模型和快速故障兜底，但“最快”本身不能证明它最适合代码调试、架构设计或复杂工具代理。

### 13.3 路由器输出契约

内部输出固定为：

```json
{
  "intent": "debugging",
  "required_capabilities": ["code", "tools", "long_context"],
  "ranked_models": ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra"],
  "confidence": 0.91,
  "reason_codes": ["stack_trace", "multi_file_context", "tool_loop"],
  "must_not_use": ["deepseek-flash"],
  "session_action": "keep_current_model"
}
```

网关只采纳模型排序和能力字段，理由文本不参与逻辑。解析失败、超时或置信度不足时，走能力门后的默认模型；如果请求没有复杂能力要求，默认优先 `deepseek-flash`。

### 13.4 模型画像与任务矩阵

不要先假定五个模型的能力高低，而应建立可版本化的模型画像：

| 维度 | 示例指标 | 验证方式 |
|---|---|---|
| 快速问答 | TTFT、短答案正确率 | 固定短问题集，冷/热缓存各测 |
| 代码理解 | 单元测试通过率、定位准确率 | 缺陷定位集 |
| 代码修改 | patch 可应用率、回归通过率 | 真实仓库任务集 |
| 复杂推理 | 结论正确率、约束满足率 | 带标准答案的推理集 |
| 长上下文 | 召回率、跨文件一致性 | 长上下文 needle 与真实任务 |
| 工具代理 | 工具选择、参数正确率、完成率 | 多步工具回放 |
| 多模态 | 图片/附件理解正确率 | 固定图片与文档集 |
| 运行质量 | TTFT、P95、5xx/429、断流率 | 分区域在线指标 |

每个模型得到的是多维画像，而不是一个总分。路由器按任务类型选择对应维度的最优模型；只有在质量差异不显著时，才使用 `deepseek-flash` 的速度优势。

### 13.5 训练和上线方式

先收集一批脱敏、人工标注的真实任务，标签至少包括任务类型、所需能力、最低可接受质量和是否允许降级。对每个候选模型做离线成对评测，再让路由器在 shadow mode 预测，不改变真实流量。只有当“路由器选择的模型”在质量和失败率上优于固定强模型与固定 Flash 基线后，才启用在线决策。

在线启用后保留 5% shadow 采样：实际只由当前策略调用一个模型，同时异步记录其他候选的路由判断，不复制调用其他模型。发现模型画像、上游版本或账号池变化时，重新评测，不直接沿用旧阈值。

## 14. `deepseek-flash` 的速度依据与实测方案

仓库原先只有 `qwen3.6-flash` 的历史压测；本次已用张成的 Key 在东京和美西完成 `deepseek-flash` 及四个候选模型的首轮对比。因此“Flash 在本次短问答和简单代码场景最快”已有实测依据，但仍不能直接外推为复杂任务的全场景结论。

实测必须把速度和质量分开：

1. 每个区域、每个候选模型分别测试短问答、中等代码、长上下文、工具调用、流式和 WebSocket。
2. 每个场景至少记录冷缓存首轮、热缓存连续轮、TTFT、P50/P95 总时延、成功率、断流率和 usage 中的缓存读取量。
3. 代码和代理任务同时记录测试通过率、工具参数正确率和需要人工重试的比例。
4. 固定请求正文、工具 schema、推理参数、并发和超时；模型切换测试不能混用不同 prompt。
5. 每个模型每个场景至少 30 次，分别压测并发 1、5、10、20，避免一次短测被偶然排队影响。

仓库现有基准脚本可作为起点：

```bash
API_BASE=<区域入口> \
MODEL=deepseek-flash \
BENCHMARK_MODE=full \
REQUESTS_PER_SCENARIO=30 \
CONCURRENCY=5 \
node script/benchmark/ai-api-benchmark.mjs
```

本次已通过已配置 SSH 别名完成两地带凭证压测，Key 只在远端进程内读取，未输出或落盘。正式实施前仍必须把场景扩展到长上下文、工具调用、WebSocket 和质量评测，并把重复测量结果写入模型画像。

## 15. 模型切换与请求缓存控制

### 15.1 先区分三种“缓存”

- **路由缓存**：Redis 中保存会话当前选中的档位，控制后续请求是否重评。
- **上游 Prompt Cache**：模型供应商保存的 KV 前缀缓存，只能由上游按模型、区域、机器和前缀匹配，网关无法直接读取或清空。
- **响应结果缓存**：把完整答案按请求哈希复用。由于工具调用、时间、权限和随机性，第一版不启用通用响应缓存。

路由缓存命中不代表 Prompt Cache 命中；模型保持不变也不保证上游一定命中。

### 15.2 模型切换时的规则

1. 同一会话在一小时粘性 TTL 内保持模型，除非发生能力错误、连续上游失败或明确的任务升级信号。
2. 只能在请求边界或 WebSocket turn 边界切换，不能在流式响应中途切换。
3. 同一会话从模型 A 切到模型 B 时，保留逻辑会话历史，但建立新的上游缓存命名空间；不能假设 A 的 KV 缓存可被 B 复用。
4. `previous_response_id`、`conversation_id`、`session_id` 继续用于会话连续性；它们不能被当作跨模型缓存凭证。
5. 工具循环中一旦已经产生工具调用，当前 turn 固定模型直到结束；下一 turn 才允许重新分类。
6. 模型升级、模型别名重新映射或能力矩阵变化时，主动使该会话的模型绑定失效，下一请求重新分类。

### 15.3 `prompt_cache_key` 命名

保留客户端提供的稳定 `prompt_cache_key` 语义，但网关向上游生成隔离后的值：

```text
HMAC(server_secret,
  region + provider + effective_model + model_revision + api_key_id + client_prompt_cache_key
)
```

这样可以同时满足：

- 同一用户、同一模型、同一稳定前缀可以复用缓存。
- 模型切换不会把不同模型的缓存统计和身份混在一起。
- 不把原始 Key、用户标识或 prompt 写入日志。
- 东京和美西不会共享缓存命名空间。

没有客户端 `prompt_cache_key` 时，使用 `api_key_id + workspace/session` 的稳定哈希；不要使用每次请求生成的随机值，否则会主动破坏缓存复用。

### 15.4 前缀布局

把稳定内容放在前面，把变化内容放在后面：

```text
[稳定 developer/system 指令]
[稳定工具定义与 schema]
[稳定项目/工作区上下文]
<显式 cache breakpoint>
[会话历史与本轮用户输入]
[工具结果和动态附件]
```

对支持显式断点的 GPT-5.6 及以后模型，默认使用 `prompt_cache_options.mode=explicit`，在稳定 developer 内容和工具定义之后设置断点；动态用户内容不写入长期可复用前缀。对不支持显式断点的模型使用隐式缓存，并保持消息、工具顺序和字段序列化稳定。

官方 Prompt Caching 文档说明：缓存按模型和前缀匹配，模型或工具定义变化会影响命中；GPT-5.6 及以后模型的默认 TTL 为 30 分钟，不能手动清空，且缓存只存在于具体机器和处理区域。网关应记录 `cached_tokens`、缓存写入量、命中率和模型切换原因，而不是自行伪造命中状态。

### 15.5 缓存验收

- 同一模型、同一稳定前缀连续请求，缓存读取量应上升。
- 仅改变动态用户输入时，稳定前缀仍可命中。
- 切换模型后，缓存命中从新模型重新建立，不能继续报告旧模型缓存命中。
- 改变工具 schema、developer 指令或模型版本后，命中率下降必须可解释。
- Responses、Messages 转换和 WebSocket turn 的 `prompt_cache_key`、`session_id`、`conversation_id` 必须保持同一隔离规则。
- 监控按 `region + effective_model + api_key_id` 聚合，不能只看全站缓存读取量。

## 16. 2026-09-11 首轮实测结果

### 16.1 测试范围

- 美西使用张成的 Codex Key `id=4`；东京使用张成的 Key `id=140`。
- 两个 Key 的值均只在远端进程内读取，没有输出或落盘。
- 每个模型执行一个短算术问题和一个简单 Python 修复问题。
- 请求使用 Chat Completions、`temperature=0`、流式输出、`max_tokens=120`。
- 这是单次探测，不是最终排名；账号排队、上游机器和时间窗口都会影响结果。

### 16.2 TTFT 与总时延

| 区域 | 模型 | 简单任务 TTFT/总时延 | 代码任务 TTFT/总时延 |
|---|---|---:|---:|
| 美西 | `deepseek-flash` | 299 / 617 ms | 290 / 1014 ms |
| 美西 | `gpt-6-astra` | 622 / 1805 ms | 793 / 2476 ms |
| 美西 | `gpt-5.6-sol` | 620 / 1273 ms | 627 / 1235 ms |
| 美西 | `gpt-5.6-terra` | 547 / 1178 ms | 632 / 1892 ms |
| 美西 | `gpt-5.6-luna` | 599 / 2098 ms | 1792 / 3424 ms |
| 东京 | `deepseek-flash` | 228 / 949 ms | 196 / 1306 ms |
| 东京 | `gpt-6-astra` | 1511 / 1819 ms | 788 / 9289 ms |
| 东京 | `gpt-5.6-sol` | 819 / 15342 ms | 793 / 1030 ms |
| 东京 | `gpt-5.6-terra` | 938 / 7623 ms | 677 / 13544 ms |
| 东京 | `gpt-5.6-luna` | 916 / 1081 ms | 1006 / 1414 ms |

### 16.3 结论和限制

1. `deepseek-flash` 在两地两个场景均取得最低 TTFT，支持把它作为简单任务的首选、分类不确定时的默认模型和低延迟故障兜底。
2. 速度差异不等于能力差异。当前两个任务所有模型都给出了正确结果，无法据此判断复杂代码、架构、工具代理和长上下文质量。
3. 东京 GPT 模型出现明显的总时延长尾，说明账号排队、上游机器或当前时间窗会显著影响结果；模型静态排名不能脱离实时 TTFT、P95 和错误率。
4. 因此 `auto` 不应继续使用简单的线性“难度分数 → 模型”映射。正确做法是“能力硬门 + 任务意图 + 质量画像 + 实时性能”，Flash 的速度作为实时性能先验和同质量决胜项。

## 17. 推荐的最终分类策略

### 17.1 选择顺序

```text
第一步：硬能力过滤
第二步：识别任务意图和质量要求
第三步：读取模型画像，得到候选模型排序
第四步：用当前区域实时 TTFT/P95、错误率和会话缓存状态打破平局
第五步：同档位失败后按能力匹配的降级链重试
```

模型画像由离线评测和线上反馈共同维护，不再假定 `gpt-5.6-sol` 或 `gpt-6-astra` 在所有任务上天然高于其他模型。

### 17.2 任务类别到模型的初始策略

以下是待评测确认的初始策略，不是永久绑定：

| 任务类别 | 初始首选 | 升级条件 |
|---|---|---|
| 简短问答、翻译、格式转换 | `deepseek-flash` | 需要严格推理、复杂 schema 或多模态能力 |
| 短代码解释、单点修复 | `deepseek-flash` 或 `gpt-5.6-luna` | 涉及多文件、隐含约束或测试失败 |
| 中等代码修改、调试 | `gpt-5.6-terra` / `gpt-5.6-sol` | 工具链复杂、回归风险高或需要深层推理 |
| 架构设计、复杂推理、长上下文综合 | `gpt-6-astra` / `gpt-5.6-sol` | 仅在能力门和质量画像允许时降级 |
| 多步工具代理 | 通过工具成功率最高的模型 | 工具参数错误、循环失败或上下文超限 |
| 图片、特殊协议或结构化输出 | 首先按能力矩阵筛选 | 不满足能力时禁止速度优先 |

当任务质量要求无法从请求结构确定时，调用专用语义路由器输出候选排序；路由器自身不能直接替代业务模型，也不能绕过能力门。

## 18. 缓存方案的最终决策

### 18.1 模型切换不会共享 KV 缓存

请求缓存是模型和前缀相关的。模型 A 切换到模型 B，即使完整会话文本相同，也不能假设 A 的 KV 状态能被 B 使用。网关必须保留会话历史，但为每个有效模型建立独立缓存身份：

```text
cache_namespace = HMAC(
  region + provider + effective_model + model_revision + api_key_id + client_prompt_cache_key
)
```

切回旧模型时，只有在上游机器、前缀、工具定义和缓存保留时间都匹配的情况下才可能重新命中；网关不能把它当作确定行为。

### 18.2 路由缓存和 Prompt Cache 分开

- Redis 路由缓存：保存“这一会话当前选哪个模型”，建议一小时 TTL。
- 上游 Prompt Cache：保存模型前缀的 KV 状态，生命周期和命中规则由供应商控制。
- 响应结果缓存：第一版关闭，不缓存带工具、权限、时间或随机性的完整答案。

路由缓存命中只表示不重新分类，不表示 Prompt Cache 命中。

### 18.3 请求字段处理

- 保留客户端稳定的 `prompt_cache_key` 语义，但增加区域、供应商、有效模型和模型版本隔离。
- 没有客户端 key 时使用稳定的 `api_key_id + workspace/session` 哈希，不能每次随机生成。
- `session_id`、`conversation_id`、`previous_response_id` 继续负责会话连续性，不把它们当作缓存清除或跨模型复用凭证。
- 模型切换只发生在 turn 边界；工具调用进行中保持同一模型。
- 不能通过网关手动清空供应商 Prompt Cache；需要“清理”时只能改变命名空间、停止发送显式缓存标记或等待上游过期。

### 18.4 稳定前缀布局

```text
[稳定 developer/system 指令]
[稳定工具定义和 schema]
[稳定项目上下文]
<显式 cache breakpoint>
[会话历史]
[本轮用户输入、工具结果和动态附件]
```

对支持显式断点的 GPT-5.6 及以后模型，采用显式断点并把动态内容放在断点之后。对不支持显式断点或不返回缓存 usage 的 DeepSeek 账号，保持消息顺序稳定，并将缓存命中标记为 `unknown`，不伪造命中率。

首轮长前缀实测中，Flash 在美西第二轮报告约 1024 个 cached tokens，东京也观察到 1024 个 cached tokens；GPT-6 Astra 在美西观察到第二轮 1024 个 cached tokens。其他模型的当前兼容层没有返回可用的 cached-token 字段，需要在协议转换层补齐后再比较。

官方 [Prompt Caching 文档](https://developers.openai.com/api/docs/guides/prompt-caching)：缓存按模型和前缀匹配，GPT-5.6 及以后默认缓存 TTL 为 30 分钟，可使用显式断点；缓存不能手动清除，并且只存在于具体机器和处理区域。网关应记录 `cached_tokens`、缓存写入量、命中率和模型切换原因。

## 19. 缓存命中下降与成本保护

### 19.1 风险判断

模型切换确实可能让输入成本上升，但原因不是“Redis 路由缓存失效”，而是新模型需要重新建立自己的上游 Prompt Cache。尤其是长对话、固定项目上下文和大工具 schema，如果每轮都重新分类并在模型之间来回切换，同一份历史会被多个模型分别按 cache miss 计费。DeepSeek 官方说明其上下文缓存默认开启、按完整前缀匹配且仅 best effort；响应中的 `prompt_cache_hit_tokens` 和 `prompt_cache_miss_tokens` 才是成本核算依据。[Context Caching](https://api-docs.deepseek.com/guides/kv_cache/)

因此第一版不采用“每轮重新选择最优模型”的策略，而采用“首轮决策、会话内保持、必要时升级”的策略：质量优先仍然成立，但不为了很小的预测收益反复破坏缓存。若完全不做会话粘性而每轮切换，长上下文会话的输入成本可能按每个候选模型重复经历冷缓存，出现明显放大；采用下述策略后，额外冷缓存成本只在确有质量或能力收益时产生，并且不会因模型来回振荡而重复放大。

### 19.2 推荐的防护策略

1. **会话模型粘性**：首轮选定模型后，在 HTTP 会话 TTL 和 WebSocket 连接生命周期内保持不变。普通后续轮次不重新分类；只有检测到能力不足、明确的任务升级信号或连续失败时才允许升级。
2. **升级后保持**：升级完成后，后续轮次继续使用新模型，直到任务阶段结束或会话 TTL 到期。允许同一会话再次升级，但不允许在相邻轮次之间上下振荡。
3. **路由阶段和滞回**：会话保存 `route_epoch`、当前模型和最近切换时间。模型只能在 turn 边界切换；自动升级默认至少间隔 3 个已完成 turn，或由硬能力错误立即触发。自动降级需要比升级更大的质量差阈值，并且只在检测到新任务阶段、长时间空闲后恢复，或当前模型健康度持续异常时发生。
4. **工具循环锁定**：工具调用开始后锁定当前模型直到该工具循环结束；循环中的失败只走同能力降级链，不重新运行全量分类器。
5. **缓存感知的平局决策**：当两个候选模型的质量预测差异低于阈值时，优先选择当前会话模型；只有质量收益足够大才承担新模型的冷缓存成本。缓存状态只能打破平局，不能绕过能力门。
6. **稳定前缀**：分类结果、路由理由、请求时间和随机 trace id 不得写入上游 system/developer 前缀；消息顺序、工具 schema 和序列化格式必须稳定，避免网关自己制造 cache miss。
7. **不做预热请求**：不为可能被选中的模型发送 speculative/prewarm 请求，也不对同一用户请求并行调用多个模型；这类请求会直接增加输入和输出用量。
8. **切换时的一次性成本**：发生必要切换时可以完整携带会话历史以保证质量，但切换后必须保持新模型一段时间，让后续轮次重新积累命中；不能为了省一次 miss 而丢失上下文。

“任务阶段结束”由新主题、上一任务已完成、用户明确开始新任务或长时间空闲等信号共同判断。进入新阶段后可以重新从 `deepseek-flash` 开始评估；同一阶段内允许 Flash → Terra → Sol → Astra 的多次必要升级，但默认不自动反向降档。这样既不会把模型切换次数硬编码成 1 次，也不会因为短期分类抖动反复清空缓存优势。

### 19.3 成本核算和熔断

网关按请求记录以下字段，并按 `region + api_key_id + effective_model + session_id` 聚合：

- `prompt_tokens`
- `prompt_cache_hit_tokens`
- `prompt_cache_miss_tokens`
- `completion_tokens`
- `cache_status`：`hit`、`miss`、`unknown`
- `estimated_upstream_cost`
- `route_switch`、`route_switch_reason`

模型或协议不返回缓存 usage 时，成本估算按全部输入 token 为 miss 的保守值计算，不能把未知当成命中。每 15 分钟计算缓存命中率、每次请求平均 miss tokens 和相对固定模型基线的输入成本；当命中率持续下降或估算成本超过基线告警线时，进入 **cache-preserving mode**：保持当前会话模型、停止非必要自动升级和 shadow 复制请求，只允许硬能力错误或质量风险达到强制阈值时触发切换。恢复条件是连续多个窗口回到正常范围。

这是一道保护闸门，不把系统永久降级到便宜模型。质量硬门仍然优先，无法满足能力时必须切换或返回明确的 `503`。成本熔断只限制“可选的模型切换”和重复探测。

### 19.4 DeepSeek-V4.1-Flash 对成本判断的影响

DeepSeek 于 2026-09-10 官方宣布 V4.1-Flash 已上线，并称其 benchmark 领先包括上一代旗舰模型在内的主要模型；官方同时说明其 KV cache 只需上一代的 1/4 HBM 和 1/8 SSD。网关直接使用 `deepseek-flash` 作为唯一的 DeepSeek 候选，不再维护旧版 Pro 别名。[官方公告](https://www.deepseek.com/en/news/deepseek-v4-1-flash/)

这会降低“切到 Flash 本身”的成本风险，但不会消除跨供应商切换的缓存损失。当前网关里的 `deepseek-flash` 是否已经稳定映射到 V4.1-Flash，仍需从 Sub2API 的 provider 映射和上游响应 `model` 字段确认；在确认前，成本核算按实际返回的模型和 cache usage 计算，不按别名猜测。

### 19.5 协议差异

DeepSeek 的 Chat Completions 会在 `usage` 中返回 `prompt_cache_hit_tokens` 与 `prompt_cache_miss_tokens`；其 Responses API 文档目前标注 `prompt_cache_key` / `prompt_cache_retention` 不支持，因此不能把 OpenAI 的显式缓存参数直接假设为 DeepSeek 全协议通用能力。网关需要按协议记录 `unknown`，并以实际返回的 usage 为准。

### 19.6 上线验收门槛

- 固定模型的多轮基线与 `auto` 对照测试：输入 token、命中 token、miss token、输出 token 和质量结果逐请求对齐。
- 长上下文会话在不升级时，`auto` 的 cache miss tokens 不得显著高于固定模型基线。
- 人为触发连续两次必要升级后，确认每次只产生对应模型的一次冷缓存，后续轮次不会在模型之间来回振荡。
- 人为制造缓存 usage 缺失，确认系统按 miss 保守估算并触发可观测告警。
- 命中率下降时确认进入 cache-preserving mode，恢复后才重新开放可选升级。

## 20. 真实入口缓存探测结果（2026-09-11）

已使用 `key.yaml` 中的授权 Key 对 `http://106.14.254.110:9880/v1` 做只读测试，详细记录见 [`script/gateway/auto-routing-cache-experiment/real-cache-probe-2026-09-11.md`](../script/gateway/auto-routing-cache-experiment/real-cache-probe-2026-09-11.md)。

同一段约 2.3 万 token 的稳定前缀按 `deepseek-flash → deepseek-flash → gpt-5.6-terra → gpt-5.6-terra → deepseek-flash → deepseek-flash` 顺序请求。Flash 第二轮命中 23,296 tokens，推导出的 miss 仅 149 tokens；切到 Terra 后再切回 Flash，Flash 仍命中 23,296 tokens。这个结果说明模型切换不会必然清空旧模型缓存，旧模型缓存可能在供应商侧继续保留；真正新增的是新模型首次请求的冷缓存。

因此缓存策略调整为：允许同一任务阶段多次必要升级，不再用“最多一次升级”作为成本保护；使用模型粘性、升级冷却、任务阶段重置和滞回阈值避免振荡。对不返回缓存 usage 的模型或协议，仍按 `unknown` 处理并按 miss 保守估算。

## 21. 复杂任务低到高切换实测

为验证多次升级而不是简单短问答，已在真实入口执行 30 次请求：3 类复杂任务（网关架构、生产故障诊断、跨包代码迁移），每类按 `deepseek-flash → gpt-5.6-luna → gpt-5.6-terra → gpt-5.6-sol → gpt-6-astra` 顺序切换，每个模型连续两轮并携带完整历史。详细逐轮数据见 [`comprehensive-switch-report-2026-09-11.md`](../script/gateway/auto-routing-cache-experiment/comprehensive-switch-report-2026-09-11.md)，原始脱敏统计见 `comprehensive-switch-result.json`。

本轮 30 次请求成功 25 次、失败 5 次：Terra 出现 1 次上游 HTTP/2 502，Sol 出现 4 次超时。成功请求中，Flash 平均约 5.3 秒；Luna 约 86 秒；Terra 约 130 秒；Astra 的长上下文第二轮观察到 22,912–29,440 cached tokens。结果说明：模型升级必须与实时健康度和超时率联动；高档模型的缓存命中可以很好，但字段缺失的模型不能假定命中；多次升级策略需要保留，但必须有能力门、冷却、滞回和同能力降级链。
