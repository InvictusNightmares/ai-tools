# Guard 输入保护组件

这是 AI Gateway 内的输入前置保护服务，代码位于 `guard/`，Qwen HTTP 客户端位于 `guard/model/`，部署配置位于 `deploy/guard/`。它的业务代码不连接东京、美西服务器；Qwen3Guard 通过 GPU 上的 vLLM 调用。提问中的疑似凭据先脱敏，认证密钥不写入文档或模型输入。

## 当前能力

- `guard`：协议中立输入、Go 规则硬闸门、凭据脱敏、会话隔离、账号熔断、审计接口和 fail-closed。
- `guard/model` 和 `cmd/preflight-api`：Qwen3Guard HTTP 客户端、可运行的 `preflight-api`、JSONL 审计落盘和 GPU/vLLM 部署编排，不发送 RawBody 或认证凭据。
- 已验证并采用的版本及后续修复状态见[总计划](../docs/智能网关与Guard分阶段实施总计划.md)。r18曾采用到4004/4005的8013/8014：历史摘要复用、按真实token容量检查完整文本、Kotlin运行时引用及null/布尔比较识别均已采用；r18补齐Markdown反引号结束边界。r18的88项真实正反例（含原请求三次复验）及队列/审计/tokenizer故障失败关闭通过，随后原生Kotlin流程发现参数类型误拦，参数类型修复及最终验收见[R02记录](../docs/evidence/2026-09-17-guard-r02/README.md)。Unsafe/Controversial与不可用仍拒绝，原生产8011未替换。

- 凭据处理：概念性提问可继续；疑似真实值先脱敏；要求使用、发送、验证或提取真实凭据时返回 `secret_input_not_allowed`。Kotlin `val/var` 的类型声明、成员引用与无参调用不包含实际凭据；带类型的字面值赋值仍检查，不按文件类型整体放行。

## 本地验证

```bash
cd script/gateway/ai-gateway
go test ./guard/...
CGO_ENABLED=0 go build -o bin/preflight-api ./cmd/preflight-api
```

服务器部署编排位于 `deploy/guard/docker-compose.yaml`，会在 GPU1 启动 Qwen3Guard vLLM，并在 8011 启动 Go Preflight API。正式执行前仍需按总计划核对镜像、权重路径、私网 ACL、压测和回滚条件；本地不会自动连接或修改服务器。

## 与 Auto 的脱敏契约

`/v1/preflight` 可接受 `provider_payload` 完整 JSON 正文字符串。allow 时返回 `sanitized_payload`、原始字符串的 `input_sha256` 和 `redaction_version=credential-redaction-v1`。block/unavailable 不返回正文。安全缓存只复用判定，每次重新绑定输入摘要；凭据使用硬拦截在缓存之前执行。旧 messages/tools 输入继续兼容，但新版 Auto 必须使用正文契约。

结构化脱敏检查 JSON 值和内嵌文本，覆盖常见密码、API/OAuth token、Cookie、Basic/Bearer、私钥和带凭据连接串；保留安全 schema、环境变量引用、占位符、数字精度和未改变的协议状态。Qwen 输入与异常审计也使用脱敏副本。覆盖是启发式且有限的，仍需真实误拦、漏扫验收。

整理前r4归档在本地/GPU通过33项race和vet/build；真实凭据解释5类、凭据使用403、合成签名与原失败签名重放均符合预期，配套Auto的17项隔离检查通过。2026-09-16 11:59记录确认临时服务停止、远端Key副本删除。[输入脱敏验收明细](../docs/evidence/2026-09-16-input-redaction/README.md)记录失败、修改和待验收项；生产8011及4000/4001保持原状。

Guard非allow安全日志保存脱敏后的raw_body，JSON中的base64仅是编码，不是加密；文件应按受限审计数据管理。导出到仓库的证据不包含该正文或思考签名。

当前规则版本和原生验收状态见总计划；Guard预算30秒、Auto传输35秒，二进制采用版本见总计划。两地历史增量复用均已实测；跨Key、改写历史或envelope全部重新检查，新增凭据使用仍block。历史r17制品独立真实模型普通10RPS连续30分钟18,000/18,000，p95 93.61ms、队列max 0ms、无OOM；分钟采样最低显存余量20.38%。r18本轮没有重跑30分钟负载，不能沿用r17成绩作为新二进制压测通过。r15混合长输入时普通p95 483ms超标，限制保留。负载和故障注入边界见总计划P07，不能将命中缓存负载等同于每次完整模型推理。

历史缓存只保存有TTL和容量上限的有序SHA256摘要，绑定Key、区域、会话、完整envelope、规则及模型版本。所有用户/系统/开发者意图和两条边界消息仍重复送检；新工具输出必检。完整Go凭据扫描在任何缓存前执行，最终allow正文仍绑定整请求并保持全部原生内容。重启/压缩/修改历史失效后完整复检，当前Guard历史摘要仍是进程内缓存；P10已完成的共享状态是Auto会话/工具绑定和分类缓存，不包含Guard摘要或跨主机容灾。

用户确认没有额外显卡，本期取消第二故障域；现有单实例保持fail-closed并继续故障恢复演练。附件按已确认范围仅检查元数据，内容透传，不宣称已通过语义安全审核。

当前实现通过vLLM `/tokenize`（实际消息模板）计算完整脱敏文本的token预算；模型可容纳时保留完整上下文，超限按字段拆分，大字段按Unicode并重叠最多256字符，保留全部内容。输入JSON转为路径加原文字串，未知字段/重复键/精确数字均保留；不是选择性摘取用户问题。任何tokenizer故障或无效结果都返回Guard不可用，strict标签不变。当前vLLM0.19.0的[Tokenizer API](https://docs.vllm.ai/en/v0.19.0/serving/openai_compatible_server/)已实测；`/readyz`仍检查模型目录可用，分词器故障由真实预检探针及请求失败关闭覆盖。新版本负载和原生矩阵按总计划单独记录，不能沿用旧压测通过声明。
