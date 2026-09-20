# 输入脱敏贯穿链路验收

截至 **2026-09-16 11:59（北京时间）**：r4真实复验17/17检查通过，其中包括5步混合语言非流式递增；三协议同步/SSE、计数、凭据拦截、签名保持和截断失败对照均通过。44次外发捕获无合成明文残留。已回收日志、逐文件SHA和清理/健康证据；源码99份与验收清单一致，当前本地Go/脚本与服务器一致。生产Guard8011及4000/4001未替换。全局生产验收仍未完成。

## 已确认根因与代码修改

旧 Guard 只对供 Qwen3Guard 使用的副本脱敏；allow 后，Auto 继续用原始请求进行分类、token 计数、业务请求和缓存。旧正则对带空格的 JSON 密码会破坏结构，还漏掉刷新令牌、私钥、Cookie、Basic 认证和数据库连接串。

| 范围 | 修改 | 本地验证 |
| --- | --- | --- |
| Guard Go 检查 | 新增结构化 JSON 脱敏，递归检查嵌套文本/工具参数；保留数字精度、schema、环境变量引用、已有占位符及未改变的供应商状态；补齐附件和 metadata 扫描 | 新增用例先复现 JSON 损坏、漏扫和非幂等问题，修复后通过 |
| Guard HTTP 契约 | `provider_payload` 接收完整规范化正文字符串；allow 返回 `sanitized_payload`、`input_sha256`、`redaction_version=credential-redaction-v1`；规则版本 `preflight-r3` | 相同脱敏内容可复用安全判定，但每次重新绑定原始输入摘要；明文凭据使用仍在缓存前拦截 |
| Auto Guard 客户端 | 校验版本、原始正文 SHA-256、有效 JSON 和 stream 一致性；旧版 allow-only Guard 返回503 | 旧代码回归先失败，修复后通过；无效结果不进入分类、业务缓存或上游 |
| Auto 全部外发路径 | 分类、非流式、三协议 SSE、Messages/count_tokens 和缓存统一使用 Guard 返回的正文；原始认证头仅用于业务身份传递 | 三协议同步/流式及计数7条路径通过；同步重复请求确认仍先检查 Guard、业务上游只调用一次 |
| 验收脚本 | `verify-redaction-live.py`：真实Qwen3Guard加东京测试Key，外发前拦住合成明文残留；负向样本使用独立会话 | r4真实17/17检查通过；详见最后一节，不把前两轮失败改成通过 |

Auto 全量 `go test -race ./...` 与 `go vet ./...` 通过；Guard 全模块 `go test ./...` 通过。新增测试位于 `redaction_test.go`、`preflight_http_test.go`、`redaction_boundary_test.go`，原有阶段 D HTTP 集成测试同步新契约。这里不将局部 detector 的用例覆盖宣称为任意凭据格式均可识别。

## 服务器记录与失败

- SSH 两次非交互连接被堡垒机关闭。底层 SSH banner 和 VPN 内 Guard health200正常；用户确认可连接后，直接 `ssh qiyuan-gpu` 在 **10:57:38** 成功。没有修改 Clash/VPN 或服务器网络配置，尚不足以确定前两次失败的原因。
- 第一份上传包 SHA-256：`d44caa23049c89e7b0222b292d424347fcad623f2151637981c7fc0ba80b062b`。GPU路径 `/tmp/gateway-redaction-20260916/source.tgz`，传输摘要一致。
- **第一次 Linux 验证失败**：归档过滤器漏掉 `auto-gateway/testdata/history-cases.json`，`TestHistoricalProjectCheckpoints` 报文件不存在。因此这一包不能记为 Linux 验证通过，未用它启动新服务。补齐测试数据后需要重新打包、校验和测试。
- 本轮合成凭据测试不读取真实业务密码；Key 仅从0600私有文件读取。脚本不记录正文或认证头，仅记录路径、请求 ID、模型、effort、HTTP状态、摘要和标记是否残留。

## 尚未完成

本轮修复的计数、脱敏边界、签名误拦和指定非流式长任务已有针对性真实证据。仍需独立新样本的安全误拦/漏扫评估、真实Codex/Claude Code客户端压缩与取消、产物质量、共享组最高effort映射、上下文容量与Prompt Cache收益、多人身份/额度和事务型持久化。r4只重跑了新增/失败边界及混合语言五级，未把r3中英文结果伪写为r4全量15条。不同版本与失败过程分别保留。

## 11:08 完整包复验

补齐测试JSON和验收脚本后，完整包SHA-256为 `67aa40696c1ea541fba21c88f1d7a947c94d18b93491b8312743edcdb46373a6`，97份源文件见[source-manifest.json](source-manifest.json)。GPU两模块race/vet/build全部通过。开始运行真实模型验收，最终结果待回收；此前失败包保留，不能从记录中删掉。

## 11:19 实测与新增修复

首轮[逐项实测及外发元数据](live-first.json)：Guard五类形状5/5，三协议同步/SSE六次HTTP200完整返回，耗时7.428–13.550秒。21次捕获请求（含模型认证查询）无合成明文标记；14次有正文的外发均包含脱敏标记。count_tokens已携带脱敏正文到东京，但Deepseek404导致Auto503，故总体验收11/12，不能写成全部通过。脚本已停止临时服务并删除远端Key副本。

[五模型计数对照](token-count-model-probes.json)采用相同无敏感输入：Deepseek404、GPT四款200且返回9。东京[该版本计数实现](https://github.com/Wei-Shaw/sub2api/blob/19149ca196eeae4a4482e5299dc6fa4ba0b06c8c/backend/internal/service/openai_gateway_count_tokens.go)本身也存在OAuth本地token估算，所以即使200，也不能一律称精确供应商token数。

当前pilot对Deepseek显式配置本地估算，数值为完整脱敏provider JSON的UTF-8字节数。响应头 `X-Gateway-Count-Method=utf8_bytes_estimate`，审计记录 `token_count_method`、`counted_input_tokens`、`upstream_called=false`；只为客户端预算提供保守参考，不保证内部framing的严格上界，不作为业务usage。其余模型为 `upstream_reported`，仍校验真实身份/Guard，其他HTTP错误继续失败，不从任意404推断可降级。计数针对性回归已通过，真实复测待完成。

非流式504修复使用 `AUTO_GATEWAY_BUFFERED_SSE=1` 显式开启：客户端仍收JSON，上游只发一次SSE并聚合；默认关闭，禁止超时后重复生成。三协议工具ID/参数、签名、usage、大整数、CRLF、终止状态、畸形帧、大小限制和取消已通过本地针对性测试；尚未在GPU验证，不能宣称真实504已解决。参考[OpenAI流式事件](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events)与[Claude流式协议](https://platform.claude.com/docs/en/build-with-claude/streaming)。不改变客户端自身超时，也不改变4000/4001的Nginx配置。

## 11:22 完整本地回归及新包

Auto全量race为302项通过、vet通过，Python8项通过；[机器结果](local-race.jsonl)。随后补齐传输方式审计赋值与对应断言，目标race通过。`run-pilot.sh`改为必须显式传入配套Guard端点，避免硬编码旧生产8011。

99文件新包摘要 `e1628f07b9db00c280cf627fece16c9c2224926ea0e6c1648e2e3da16c9e8556`，见[清单](buffered-source-manifest.json)。第一次SSH上传被堡垒机关闭；当时跟随的构建命令因目录不存在而未启动Go检查。重试后已取得匹配的远端摘要，开始Linux复验。首轮97文件的真实结果保留不变，不以新版本覆盖旧证据。

Deepseek业务可用性与计数分开：首轮六次真实业务（Chat/Responses/Messages各同步、流式一次）实际模型均为 `deepseek-flash`，全部HTTP200完整返回。404仅来自当前东京链路的 `messages/count_tokens`，不能解释为Deepseek模型无法访问。计数估算不改变业务选模，业务用量仍读取响应usage。

## 11:25 新包Linux验证

99文件包重传摘要一致，GPU两模块race/vet/build完成，build_exit=0。验收脚本另行同步更新，增加同进程执行15次固定三语递增非流式任务；测试客户端等待设为300秒，因为JSON需等完整结果。该调整不证明客户端原有超时已改善；要验证的是此前约70秒的上游前置504是否仍出现。生产Nginx超时和4000/4001未改。

## 11:30 第二轮进行中

真实Guard五类形状5/5；三协议同步聚合3/3；原生SSE2/3，Responses一例HTTP200但缺少成功结束，保留失败，正在补元数据诊断。计数两条都200：Deepseek/utf8_bytes_estimate=189，Luna/upstream_reported=43。15次非流式递增长任务尚在运行，不能用短任务结果判定504已解决。

## 11:33 中间结果及另一个正文完整性修复

Sol英文/中文非流式结果分别81.128秒、153.304秒HTTP200完整返回。Astra尚在运行，不能提前记满15条。Responses原生SSE失败的诊断复现为 `response.incomplete` / `max_output_tokens`：输出256，其中reasoning224。最初失败的结果审计也记载HTTP200、response_complete=false、CompletionTokens256，未伪报成功。后续仅将本验收脚本输出预算提高到1024；不回写首轮结果，不修改用户原始请求上限。实际返回reasoning token也说明不能仅由网关发送none推断供应商内部没有推理。

贯穿payload检查还发现大整数会在Auto的provider重新编码处被float64舍入，且stream_options被整体覆盖。新增回归复现后，改用UseNumber并只设置include_usage；本地修复待同步，当前正在运行的99文件版仍不包含这两项，验收版本保持区分。

## 11:43 第二轮结果与签名边界

[第二轮完整元数据](live-second.json)保留15条结果及Guard/Auto审计（排除请求正文和签名）。12/15完成，中英文各Deepseek→Luna→Terra→Sol→Astra全通过。长任务Sol81.128/153.304秒、Astra185.352/201.880秒完整200，证明这些样本上单次SSE聚合跨过此前504窗口；不等于完整客户端或所有代理超时已验收。69次捕获请求无合成明文标记。临时8012/8092/8022已停止、远端Key副本已删除。

混合语言第三步的上游思考签名共1572字符，在第1465位出现随机Ghp前缀；正则词边界把前面的连字符视为分隔符，将签名误改为脱敏标记，再结合login触发硬拦截。第4/5步因为同一会话被隔离而拒绝。新增合成签名回归先失败后通过；r4要求已知token前缀不能紧接编码串字符，不按signature字段名跳过扫描；完整独立token和显式password字段仍脱敏，补齐ghp_等GitHub前缀。契约版本不变，规则缓存版本升为preflight-r4。

最新完整本地Auto303、Guard33项race及vet通过；Python8项通过。下一轮只重测新增/失败边界和混合语言五级链路，保留已完成的中英文结果及其源码版本。脚本新增独立隔离会话的明文使用403对照、签名保持对照、1-token输出预算耗尽对照；短任务上限从256调为1024。

## 11:45 r4构建脚本纠正

新99文件归档SHA为 `45629e99ebc1a5b71337a1338eb929a152fd6e9270013f6061545e840d4078ce`，GPU `/tmp/gateway-r4-20260916/source.tgz` 摘要一致。Guard Linux race/vet通过后，临时构建命令误写 `./cmd/preflight-api`，应为 `./guard-deployment/cmd/preflight-api`，故构建退出1；没有启动服务。失败日志保留于该目录build-first.log，修正命令后继续验证。

## 11:47 r4 Linux通过

临时构建入口纠正后，GPU Auto303、Guard33项race通过、两模块vet/build通过、Python8项通过，build_exit=0。[r4源码清单](r4-source-manifest.json)记录该验收版本。真实复验开始，生产服务未替换。

11:48补充：首次启动r4验收的SSH连接在堡垒机处关闭；重新只读检查确认final-live目录不存在、测试未启动，故未产生重复业务请求。确认后才重试启动。

## 11:50 真实短链路与数据库证据

r4的七条Guard正反对照通过：五类凭据解释、签名保持、明文使用403（外发POST为0）。三协议同步/流式6/6完整200、计数2/2通过；输出上限刻意设为1的Responses返回incomplete，负向用例通过。混合语言五级递增正在运行，不能提前记成功。

[东京只读用量汇总](tokyo-usage-snapshot.json)窗口为11:20至11:49:51，test Key141有18条Deepseek用量；Sol/high两条、Terra/medium两条、Astra/xhigh映射high两条。另有31条Sol/none、4条Astra/low，与分类器调用形态一致，但本汇总不做逐请求身份断言。Auto请求ID和Sub2API请求ID尚无稳定直接关联，时间/模型汇总不是严格一对一对账。Deepseek Responses的数据库effort仍为空；这不能表示模型无法访问，也不能据此推断内部没有推理。

## 11:56 r4复验完成

[完整r4元数据](live-r4.json)共有17项检查：7个Guard正反对照、三协议同步/SSE6项、计数2项、1-token输出预算负向1项、混合语言五步递增1项；17/17通过。业务部分是6个短请求、5个递增请求和1个刻意截断请求，不把预期403/incomplete称为业务成功。44次外发检查无合成明文残留；这是限定样本的检测结果，不能保证任意未知凭据均被识别。

同一真实1572字符签名和原登录任务另在GPU本机Guard重放：allow、正文逐字节未变、199ms，没有发往外部业务模型。这与合成签名用例相互验证，不能只凭新一轮随机签名没有撞前缀就判问题已解决。

| 模型 | Auto发送effort | 中文Chat（r3，秒） | 英文Responses（r3，秒） | 混合Messages（r4，秒） |
| --- | --- | ---: | ---: | ---: |
| deepseek-flash | none | 6.343 | 10.818 | 6.483 |
| gpt-5.6-luna | low | 13.131 | 8.826 | 10.099 |
| gpt-5.6-terra | medium | 44.813 | 8.435 | 19.932 |
| gpt-5.6-sol | high | 153.304 | 81.128 | 33.368 |
| gpt-6-astra | xhigh | 201.880 | 185.352 | 139.531 |

表中都是非流式客户端、上游一次SSE聚合，全部HTTP200完整返回；前两列来自r3、最后一列来自r4，不是单一版本15/15。r4混合语言实际发送none→low→medium→high→xhigh；东京共享组仍将Astra xhigh映射high，最高推理强度未验收。这里只证明路由、传输、历史续接和用量，不证明生成代码质量。

日志对账已机械核验：

- 凭据使用403的Guard与Auto异常日志request_id相同，upstream_called=false，没有分类或业务usage。
- 1-token预算耗尽请求HTTP200，但结果为upstream_failed、response_complete=false；business usage的success=false、output_tokens=1，未把失败伪记成功或丢掉已消耗token。
- 五条递增请求均有upstream_completed、sse_buffered、完整响应与对应模型/发送effort。最新[东京数据库汇总](tokyo-usage-final.json)仍是时间窗口汇总，不能替代跨系统逐请求ID关联。

日志位置：本轮GPU `/tmp/gateway-r4-20260916/final-live/audit.jsonl`、`usage.jsonl`、`guard-security.jsonl`；生产Guard原安全日志仍为 `/data/ai-gateway/logs/preflight-security.jsonl`。Auto还没有生产日志服务。Auto文件不含正文，Guard非allow记录会保存**脱敏后的**raw_body（JSON中的base64只是编码，不是加密），应按受限审计文件管理；仓库导出仅有字段白名单，不包含raw_body/签名/回答正文。

99份验收源码SHA全部匹配[r4清单](r4-source-manifest.json)，本地Go/脚本与服务器一致；Auto303/Guard33项race、vet/build、Python8项在本地及Linux通过。[本地Auto结果](local-r4-auto-race.jsonl)、[Guard结果](local-r4-guard-race.jsonl)保留。临时8012/8092/8022均无监听，远端Key副本不存在，生产8011/8001健康200。生产Nginx和共享分组未修改。

## 11:59 最终交接一致性

验收结束后仅更新3份组件README，Go与脚本未变；[最终清单](final-source-manifest.json)与[服务器逐文件校验](final-source-verification.json)为99/99一致，归档SHA `43894a85fc28591179ad8dfba5fe851542a55034b80ae25e705ae9fc8fdf6260`。GPU仍保留验收时source.tgz与最终source-final.tgz，两者版本可追溯。文档时序、表格、链接和测试Key未进入制品的检查见[文档验证](document-verification.json)。
