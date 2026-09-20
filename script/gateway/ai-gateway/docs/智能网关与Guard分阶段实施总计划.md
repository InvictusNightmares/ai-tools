# 智能网关与 Guard 分阶段实施总计划

文档更新：2026-09-20（R05/R06诊断；两地仍release v31，Auto v31/semantic-v10-r4，Guard复用v29/r19；work-observation candidate-r3 已仅作为采集旁路接入4000/4001）

**入口定位（2026-09-17 用户确认）：4004/4005 是可随时修改的多人测试入口。部分人员试用不代表正式切流；按发现问题→复现→修复→回归→更新测试入口持续迭代，保留失败证据和可回退制品，不额外等待正式入口审批。**

**当前入口：东京4004、美西4005均已部署 Auto+Guard。4000/4001/4003及原Guard8011/vLLM8001的业务路由保持；4000/4001另有独立 work-observation 旁路采集，4000→18400、4001→18401，不改变Sub2API鉴权或Auto/Guard决策。**

**2026-09-17新增已批准实施项：** 在不改变4000/4001业务鉴权及选型的前提下增加持续采集与滚动分析，独立放在[work-observation](../../work-observation/README.md)。用户后续明确改选GPU独立采集代理，Sub2API源码/镜像/升级流程不改；原两地缓冲和正文传输取消。用户最新确认：原始文本正文不脱敏、不做落盘加密，鉴权头不采集；正文30天滚动保留、附件仅元数据、GPU受限明文存储200GiB上限。采集核心是让Guard/Auto还原用户请求、模型回复、工具过程和后续纠正，开展完整上下文分析，不能以模型占比统计替代；内容契约见work-observation文档。5分钟检查、小时增量和每日报告。隔离验证和回退链路完成后，2026-09-20 已将采集旁路接到4000/4001内部转发，客户端地址不变；这仍不是正式Auto/Guard业务切流，semantic worker和训练调度保持关闭。

用户进一步要求**运行性能优先，不限定Go**。Rust/Pingora与Go代理基础对照已完成，完整采集的流式协议、p95、CPU、内存及丢失仍需验收；当前正式运行的是已通过隔离与回退验证的dev.9 candidate-r3，性能门槛仍未签收。[选型依据](../../work-observation/docs/性能选型.md)区分基础实验和完整采集验收。独立采集器的Go测试、race/vet和`CGO_ENABLED=0` Linux构建已在GPU隔离目录完成，详见[Go验证证据](../../work-observation/docs/evidence/2026-09-17-collector-r1/dev9-go-validation.json)。真实GPU smoke与Auto预览证据仍属于隔离分析平面；本地Guard/Auto语义worker默认关闭，正式8093/8094不承接采集流量。5分钟检查/小时增量/每日趋势模板未正式安装，正式200GiB同卷管理/导出生命周期、可靠完整上下文、WS远端压缩组合及发布回退仍需补齐。当前已有正式入口采集，但没有真实员工语义分析或训练结果，详见[work-observation阶段证据](../../work-observation/docs/evidence/2026-09-18-collector-r2/README.md)。

**当前新发现的未完成问题：** [R06](evidence/2026-09-17-guard-r06/README.md)付晓镇正常安装包分析被Qwen判为medium/Political，真实原请求复现；随后23次由24小时会话隔离直接拒绝。争议结果自动本地独立复核仅为待确认、待验证方案，尚未修复、部署或解除隔离。[R05](evidence/2026-09-17-codex-r05/README.md)夏斯建Windows CLI0.146.0超时仍未定位；health可达，同版macOS两种传输原生成功，不能替本人环境闭环。下述历史工作包通过范围不覆盖这两项新问题。

**2026-09-17 R04：多人流量复核及格式能力误判修复已两地采用v31。** 14:58快照，4005真实用户Key5/60共47次业务：DeepSeek4、Luna2、Terra41；分类/复核22次另计，内部验收Key4排除。付晓镇最新10次业务4次DeepSeek，均发生于v30，不能归因v31。产爱军主要为多步任务的工具续接，旧日志无正文不能替实际难度背书。修复普通text/verbosity误要求structured、Messages实际schema漏判；两地真实普通文本4场景Luna→DeepSeek，schema4场景仍Luna，初验脚本两项假失败及补验保留。736 Go/42 Python、两地入口各17/17，验收46/46精确账单/Token匹配；[R04证据](evidence/2026-09-17-routing-r04/README.md)。

**2026-09-17 R03：Codex旧模型名压缩兼容和普通阶段降档已修复并更新4004/4005。** 已知目录模型名作为Auto别名，原生旧式/v2压缩不再因保留旧模型名404；同一任务进入高置信度普通总结/问答阶段可在用户边界降档，保留工具、流、能力限制。719 Go/42 Python及六构建通过，两地原生Codex20/20、真实旧模型名压缩4/4、入口各17/17；三语六组从复杂Sol到同任务总结DeepSeek，均记录routine_phase_downshift。78/79次验收调用匹配账单、Token差异0；唯一未匹配为主分类Luna502且用量未知，Sol复核与业务成功，不补造零费用。另以真实Sol加密压缩状态完成两地跨入口再压缩与记忆恢复，首次夹具/传输失败保留。用户旧43次拒绝缺具体模型名/操作类型，不能宣称全部已逐条定位。见[R03完整证据](evidence/2026-09-17-codex-r03/README.md)。

**2026-09-17 R02：Markdown空值比较与原生复验发现的Kotlin函数参数误拦截均已修复，v29/r19已采用4004/4005。完整691 Go/42 Python、真实Guard103/103及故障矩阵通过；两地原生OpenCode读取同一Kotlin/Markdown项目后续问成功，业务均DeepSeek none，工具错误0。** [完整R02证据](evidence/2026-09-17-guard-r02/README.md)保留r18原生失败、r19修复、两地入口和33/33用量对账。东京入口17/17；美西首次health瞬时503、其余16项通过，随后各地health复查3/3为200，分列保留。

**2026-09-17 R01：Auto 选型规则修订已开发、验证并采用到4004/4005。** 用户真实 OpenCode 改动总结暴露三项缺口：只读任务难度随工具历史增长、独立复核只能维持更高估计、已锁定的工具续接仍逐轮付费分类。五轮业务使用 Luna low，分类账单 1.2082364 USD、业务 0.0170032 USD；分类一致率不能作为实际选型合理性的替代证明。R01已修复该路由缺陷；业务回答质量仍逐样本评审，不以选型或协议成功代替内容正确。

修订范围：语义上区分 summary/extraction 与实现、诊断、正确性审计；质量与原生能力达标后按候选成本档位选择，普通信息整理优先 DeepSeek；独立复核允许纠正高估；同任务、同策略且供应商工具绑定验证通过的纯工具结果复用分类，Guard、身份与能力检查每次保留。上下文长度不提高任务难度。不得根据关键词或客户端 effort 硬选低档；缺失绑定、改变目标、策略变化和多模态边界保守重分类。已完成真实三语、两地入口、原生OpenCode同类合成任务及精确用量/UA对账，见[完整R01报告](evidence/2026-09-17-routing-r01/README.md)。原保留组47/48=97.92%，前一新题24/24、后冻结边界题12/12。两地真实业务均DeepSeek none且工具续轮不再分类；最终东京回答存在文件数/类型及语言表述问题，美西覆盖正确，明确保留质量边界。旧v26证据及首次候选失败不覆盖。

| 范围 | 当前证据 | 状态 |
| --- | --- | --- |
| 当前两地运行版本 | 两地release v31，Auto v31/semantic-v10-r4；Guard复用v29/r19 | R04完整736 Go/42 Python、格式能力与两地入口各17/17、46/46账单和Token匹配。R03原生Codex/压缩/三语降档、r19真实Guard及r17负载保留对应历史版本范围 |
| 分类与选型 | Luna主分类、Sol按规则复核；纯工具绑定复用评估；客户端effort不参与选型 | v10-r2原保留组47/48=97.92%，开发12/12、前一新题24/24、新边界12/12；第一候选93.75%失败保留。DeepSeek业务可选，主分类器仍Luna；F01另列 |
| UA | 认证、分类、计数、同步和SSE均透传真实客户端UA | 两地Sub2API本人Key/时间窗口已核实OpenCode UA，禁止把client UUID冒充网关request ID |
| 图片与文件 | 图片、PDF三协议、Files生命周期；TXT/CSV/Word/Excel保留原字节 | r10 Messages桥接已上线，两地文件SSE工具回合4/4；native-v3常用文件10/10通过 |
| 图片生成 | 仅Flare/Sunburst | 两地生成/编辑4次PNG，SSE/Responses工具/multipart共6/6通过，已检查图像内容 |
| 音频 | 新增gpt-4o-audio-preview在两地Codex OAuth账号均400；Luna拒绝audio/wav | 用户确认本期不支持音频，当前明确返回audio_not_supported |
| 四端开发流程 | 同一小源真实历史退出登录任务、独立副本 | 四端最终产物均通过HAP与5项行为检查；OpenCode在r10完成原生复核，其他三端证据保留实际版本 |

OpenAI兼容客户端使用`http://192.168.64.16:4004/v1`（东京）或`:4005/v1`（美西），模型`auto`，使用本人对应区域Sub2API Key；Claude Code根地址去掉`/v1`。

本文是唯一执行决策入口，历史统一保存在[CHANGELOG](CHANGELOG.md)。[上下文/UA/区域证据](evidence/2026-09-16-context-ua-regions/README.md)与[原生媒体证据](evidence/2026-09-16-native-media/README.md)分别记录版本和结果，不用旧版通过替代新版本验收。

## 本期交付结果

- 两地release v31、Auto v31/semantic-v10-r4、Guard复用v29/r19；R04输出格式能力、R03迁移压缩/普通阶段降档及R02误拦修复见顶部报告，R01分类与质量边界保留。普通10RPS连续30分钟：r15为18,000/18,000、p95 94.25ms；r16为18,000/18,000、p95 98.32ms、预检队列max0、无OOM、采样显存余量20.38%。r17同制品、同GPU真实模型与生产参数的独立18017负载：10RPS连续30分钟18,000/18,000，p95 93.61ms，预检队列max 0ms，窗口内OOM 0，分钟采样最低显存余量20.38%；结束后独立进程退出。混合长输入窗口普通p95 483ms超标的限制保留。
- P01/P02/P03两地四端高级矩阵、旧/v2压缩、原生审核允许/真实deny已闭环；审核拒绝有HTTP200 typed deny、文件未写入及账单证明，旧Guard403失败保留。
- P04三项目×五模型能力画像及产物评审完成。小源五者通过；提醒四者自行完成，Terra达到24轮上限；启动五者构建/21项既有测试通过，但全部有需求漏项，仅Terra自行结束。Astra第18回合硬规则误判经r17修复后共享原预算续跑，未增加提示或代改产物。见[模型验收报告](模型分类与开发任务验收报告-2026-09-17.md)。
- P05最高effort22次及P12真实缓存72次均已对账；最新入口/五模型范围再验165/165账单和Token精确匹配。模型画像失败、已证明取消部分值和未知用量分别记录，不以构建代替需求验收。
- F01线上保持Luna，v10-r2原保留组97.92%，前一新题和新边界题100%。DeepSeek在同一r2规则的新对照原保留组46/48=95.83%、前一新题24/24，达到单轮门槛，尚不代表连续稳定性。历史v9的93.75%及high实验91.67%保留；按既定选择不切主分类器。
- P16临时身份已退役：东京group729、USgroup704及专用用户/Key均停用，历史账单和原账户/业务分组保持。固定模型验收进程按精确身份停止，日志与状态保留。
- 附件原生透传，只审普通文本和元数据；生成图片仅Flare/Sunburst。音频、第二GPU故障域、附件语义审核和正式4000/4001切流按用户决定排除。

## 原计划工作包对账（2026-09-16提出）

**最新授权：用户明确要求除正式4000/4001的Auto/Guard业务切流之外，其余约定能力全部在4004/4005完成；work-observation旁路采集是单独授权的运行态接入。P01–P16除P08外是本次必做项，F01继续推进；P17的业务切流不执行。用户随后确认只有现有显卡，不做第二故障域，P08退出本期范围。不得以候选可用或文档列为待办代替完成。资源或上游缺口先核查、明确报告，其他独立项继续。**

按可独立验收的工作包合并重复表述，**本期P01–P16除用户排除的P08外，已完成表中开发与验收范围；P17的Auto/Guard业务切流未执行，4000/4001的work-observation旁路采集已按单独授权运行。P04完成的是能力画像，模型需求漏项和设备未验证明确保留，不代表所有模型都通过开发题。P07普通负载达标，混合长输入延迟限制保留。** 音频、附件语义审核和第二故障域不计本期欠项。

| ID | 原计划要求 | 当前缺口与关闭标准 | 状态 |
| --- | --- | --- | --- |
| P01 | 四客户端完整矩阵（6.2.3/6.3） | 同一小源历史任务四端均完成HAP与5项行为检查，已有两地原生图片；矩阵实测Auto v16+Guard r15，两地Claude/OpenCode/Hermes各7/7、Codex工具6/6，含压缩、工具、子任务、取消/恢复；Codex旧/v2压缩见P02。Hermes驱动从中间tool_calls回复改为等待父会话stop，旧失败保留 | 两地原生矩阵通过 |
| P02 | Responses WebSocket/compact（6.3及替换入口条件） | 两地原生WebSocket 101预热/增量/双工具续接已有真实证据。旧compact在东京Auto v16、Guard v16及美西Guard v18均5/5；v2在两地Guard v18各5/5，包含原生压缩、续接、取消和恢复。旧直连502/404及夜间503失败保留，适配后实测闭环 | 当前实现及两地原生通过 |
| P03 | codex-auto-review（6.2.3） | v23原生预热保留未信任上下文、实际动作完整Guard；实际两地允许写入及只读政策下模型deny且不写入通过。拒绝为HTTP200 typed decision，真实UA/Token和账单一致；v24省略effort发送unknown、上游默认medium不算不一致，两地4/4及账单通过 | 两地原生允许/拒绝与账单闭环 |
| P04 | 分任务模型能力画像（6.2.1） | 三项目×五模型相同历史副本和冻结口径已实跑评审；小源5/5通过，提醒4个自行完成/Terra轮数上限，启动均APK+21JVM通过但全部有需求漏项、仅Terra自行结束。第四轮Astra基础设施修复后只续原剩余预算；无评审者代改、无真机/AVD声明 | 画像与逐项评审完成；模型失败保留 |
| P05 | 最高实际effort（6.2） | 20次固定最高档与2次自然Auto Astra xhigh均完整，22/22精确账单关联；客户端none不参与选型。20条effort字面一致，DeepSeek Responses两条max账单记xhigh已由两地Sub2API 0.1.161准确源码解释，保留发送/回报/账单三个原值；Chat无回报、美西Sol别名单列 | 参数、自然路由与账单闭环 |
| P06 | Guard已检查历史增量复用（5.4） | r11已实现版本/身份隔离的已检查前缀摘要，完整Go扫描后复检新增内容及用户意图/边界；东京实测复用22条，身份/历史/envelope变化失效。美西同矩阵6项也通过，追加历史1.598s→0.567s，复用22条且原生正文完整 | 两地当前版本通过 |
| P07 | 最新完整输入版本负载与故障矩阵（5.5/5.6） | 当前r19真实103项、队列/审计/tokenizer故障失败关闭通过；本次规则边界修复未重跑30分钟负载。r17同制品、同GPU真实模型与生产参数的独立18017负载：10RPS连续30分钟18,000/18,000，p95 93.61ms，预检队列max 0ms，窗口内OOM 0，分钟采样最低显存余量20.38%；结束后独立进程退出。两地当前入口与r19复验见顶部R02（美西首次health瞬时503后复查通过）。旧混合96次长输入时普通p95 483ms超标，不能宣称所有负载均达300ms | r17普通负载历史通过；r19故障通过，未重跑30分钟；混合延迟限制保留 |
| P08 | 第二Guard故障域（5.6） | 用户确认只有现有显卡，本期不做第二故障域；保留单实例失败关闭、重启恢复演练，不声称高可用 | 用户明确排除 |
| P09 | 动态健康、熔断与失败降级（6.3/8） | v7按区域/Key/协议/模型采样、连续3次失败后熔断、冷却单请求恢复；两地真实Guard/上游配临时503代理：3次切Luna、第四次避开、31秒后恢复DeepSeek，计量逐attempt正确。只对明确未生成的临时状态最多切换一次，工具续接/流中途/模糊超时不重放；两地仅Auto升级，各17/17 | 当前实现和两地验收通过 |
| P10 | 多实例共享状态和缓存（6.3） | 共享本地卷文件事务/原子工具绑定/持久分类缓存候选已完成完整离线验证；四子进程100次更新无丢失，兼容v1状态。两真实实例缓存共享/重启命中及A→B的Terra工具续接内容均通过；v6已在两地采用，各17/17和原生Codex复验通过。适用同机共享本地卷，不是跨主机数据库 | 当前实现和两地采用通过 |
| P11 | 持久化每日用量及对账（5.5/6.3） | 独立gateway_usage分钟导入、身份映射、幂等每日桶及chunk/决策分账已部署。既有图片、原生审核及取消部分用量精确证明保留；最新两地入口与五模型7个范围共165/165准确账单匹配、Token差异0、已知账单缺失0。完整响应、取消中间值、未知用量分开 | 当前实现、两地真实账单闭环 |
| P12 | 真实Prompt Cache收益（6.2.1/6.3） | 两地5候选固定60次与自然切换12次均完整，72/72精确账单和token相符；固定50次重复均命中，Auto6次分类缓存命中，业务响应缓存0。成本和首可见延迟逐项列入缓存验收报告；美西Luna/Astra重复更慢，不能由命中推断必然加速 | 两地真实实验及账单闭环 |
| P13 | 生产监控与运维边界（5/8及维护指南） | 两地独立health/usage分钟任务、受限告警、日志轮转/权限及恢复已通过；真实双进程阻塞导出时健康14ms/10ms完成。两地内部回环、入口受限路径精确404、预检未认证401；最新任务成功、待补传0。默认只归档不删除，保留期以后按用户选择配置 | 当前两地通过；不声称第二故障域 |
| P14 | 版本化发布/升级/回滚（维护指南） | 实际安装/升级、激活失败回退、长SSE排空、仅Auto替换、零重建、并发锁、制品拒绝、Guard故障前置退出已通过；磁盘/缺密钥/回退自身失败/Guard单组件回退通过离线故障矩阵。最新两地运维制品均零重建采用，密钥/状态/保护服务不变。范围见release-acceptance-matrix.json；业务候选仍须独立真实验收 | 发布工具与当前演练通过 |
| P15 | Codex完整响应后的异常审计归因（当前接续） | Auto v16已两地采用；新版实际终止日志无完整响应被误记上游失败。三协议收到可见输出后取消，两地均request_canceled；美西Responses旧样本先耗尽4096额度，保留失败，用16384预算后完成真实取消。Anthropic部分用量与最终账单差异有唯一取消审计证明，不改原值；图片6条精确账单/token相符 | 当前实现与真实区域补验通过 |
| P16 | 多Key真实隔离及负载（6.3/7） | 两地每地两个独立用户/Key；文件原字节与跨Key/跨区域拒绝、工具绑定隔离、撤销401/过期403/额度429均在Guard前拒绝，热缓存仍鉴权；各12次4并发，p95东京6.501s/美西9.465s，全部检查通过，恢复临时身份并删除测试文件 | 两地真实通过 |
| P17 | 正式分区灰度与Auto/Guard业务切流（7/8） | 4000/4001仍保留原Sub2API鉴权、选型和业务上游；仅增加独立work-observation旁路（4000→18400、4001→18401）。Auto/Guard业务灰度、按Key扩大、仅Auto降级和完整回退仍未执行 | 业务切流未执行；采集旁路已单独完成 |

另列 **F01：DeepSeek分类优化**。历史基线91.67%、v9对照93.75%、high实验91.67%保留。最新v10-r2对照原保留组46/48=95.83%，开发12/12、新题24/24，单轮达到95%；剩余json-schema、scheduler-proof语言边界不一致，未声称连续稳定性或新增12组已验。线上按用户决定仍采用Luna；r3/r4保留v10-r2分类提示词/schema（此前97.92%），DeepSeek候选进展与原始失败均见[R01报告](evidence/2026-09-17-routing-r01/README.md)。

常用文件MIME修复两地10/10；Files/SSE存储故障503、缺失404、限额413与取消归因已验收。P04实际开发暴露的Kotlin声明和比较运算误判已补旧实现失败回归，r17曾两地采用；R02进一步修复Markdown与函数参数包装并采用r19，真实103项/故障及两地原生续问通过。30分钟普通负载结果仅对应r17制品。

后续每个工作包保留：原要求、实现状态、mock/真实接口/原生客户端/产物证据、当前缺口、关闭条件及对应版本。只有必需格全部通过才关闭；用户主动排除的范围单列，不算偷偷完成。

**上游窗口：** 两地Sub2API按现有策略在北京时间23:00–06:30停用API，夜间直连亦503。该策略保持；2026-09-17 06:31起真实测试已开始，不能将夜间失败与模型能力混算。

## 1. 已确定的边界

常规业务模型入口公开 `auto`，另列原生专用动作审核模型 `codex-auto-review`；为兼容 Claude Code，Messages 同时接受第 6.2.3 节列出的 Claude 名称作为同一 Auto 策略的入口。Gateway 根据任务能力、难度、上下文、会话粘性、模型健康度、缓存状态和内部推理强度选择实际模型与 `reasoning_effort`。

Guard 只做输入前置保护，不检查上游模型输出，不部署输出监控模型。输入校验完成后，`allow` 才能读取业务缓存、执行 Auto 路由和调用上游。

本期不做：业务模型响应安全审核、输出流式拦截、图片语义安全模型、把大模型加载进 Gateway Go 进程、把 vLLM 端口暴露到公网。

按最新要求持续执行“修改 → 本地回归 → 独立真实链路验收”。可使用其他项目历史重建脱敏场景；真实外发需满足具体数据授权。**本轮及后续验证不替换 4000/4001 的Auto/Guard业务路由；work-observation采集旁路作为独立、可回退的运行态已单列接入。** 未连接真实 Guard 的测试不能计入 Guard+Auto 全链路通过。

## 2. 当前依据

### 2.1 两地近 7 天用量

统计窗口为 2026-09-07 03:16:00 UTC 至 2026-09-14 03:16:00 UTC，来源是两地 `public.usage_logs` 的只读聚合。脱敏结果见 [`observed-summary.json`](evidence/2026-09-14-7d/observed-summary.json)。

| 区域 | 用量记录 | 活跃 API Key | 最高分钟记录 | 输入上下文代理 p95 |
| --- | ---: | ---: | ---: | ---: |
| 东京 | 89,570 | 100 | 159 | 228,579 |
| 美西 | 156,462 | 71 | 111 | 502,108 |
| 保守相加 | 246,032 | 171* | 270 | 不适用 |

`*` 活跃 Key 是区域计数相加，不是跨区域去重。270 条/分钟约等于 4.5 条/秒，只是两个区域峰值相加的保守上界，不代表同时发生。`usage_logs` 是已完成用量记录，不能替代完整入口请求数和重试数。

### 2.2 GPU 服务器

qiyuan-gpu 有两张约 80GB 的 H100。GPU0 正运行 `Qwen3.6-35B-A3B` 业务 vLLM，约占 79GB；GPU1 专供 Guard 使用，GPU0 不停机、不共享显存预算。Guard 的并发参数可以独立向上调优，但每档都必须实测显存、水位、队列和延迟。

## 3. 目标架构

公司 VPN 用户使用以下既有入口。东京、美西 Sub2API 本身不直接对外；`106.14.254.110` 是 GPU 访问的已购前置服务，不能把它与 GPU 用户入口或 Guard 地址混用。

| 区域 | 用户入口（公司 VPN） | GPU 当前 Nginx 容器 | GPU 向外转发的前置地址 |
| --- | --- | --- | --- |
| 东京 | `192.168.64.16:4000` | `tokyo-sub2api-proxy` | `http://106.14.254.110:9881` |
| 美西 | `192.168.64.16:4001` | `us-sub2api-proxy` | `http://106.14.254.110:9880` |

当前链路为「VPN 用户 → GPU Nginx → 前置服务 → 区域 Sub2API」。目标链路为：

```text
公司 VPN 用户
  → GPU Nginx（东京 4000 / 美西 4001）
      → GPU 上对应区域的 Gateway（鉴权与身份隔离）
          → 本机 Go 输入前置校验 API（8011）
              → Guard 决策缓存
              → 本机 Qwen3Guard-Gen-8B（8001，仅输入）
          → allow 才执行 Auto 分类与模型选择
          → 按区域、API Key、实际模型、有效 reasoning 和协议查业务响应缓存
          → 已购前置服务（东京 9881 / 美西 9880）
          → 对应区域 Sub2API（鉴权、配额、分组、账号选择及上游用量）
          → 业务模型供应商
```

Guard 服务由两部分组成：GPU1 上的 vLLM 模型容器，以及独立的 Go Security Preflight API。GPU 上的 Gateway 调用本机 Go API，不直接调用 vLLM；东京、美西 Sub2API 无需通过 VPN 访问 GPU。Gateway 部署为容器时须使用经验证的同机容器网络地址，容器内 `127.0.0.1` 不能直接代表宿主机。

两条区域链路分别配置上游，Auto 的上游只能指向对应的 9881/9880，不能再指回 4000/4001，防止反代循环。保留客户端认证在两地 Sub2API 的最终校验；进入共享缓存前仍须完成每请求身份校验、区域/API Key 隔离及额度策略验证。现有临时程序中的静态 `AUTO_GATEWAY_API_KEY_ID` 仅适用于单测试 Key，不能作为多人生产身份。

## 4. 总执行顺序

| 阶段 | 做什么 | 是否接用户流量 | 通过后才能做什么 |
| --- | --- | --- | --- |
| A | Guard 本地代码和接口 | 否 | 部署 Guard |
| B | Guard GPU 部署、压测、审计和回滚 | 否 | 开始 Auto |
| C | Auto 本地代码和独立测试 | 否 | 做最终接口接入 |
| D | Guard 与 Auto 的单点接口接入 | 测试 Key | 区域灰度 |
| E | 东京、美西分区灰度和全量 | 逐步 | 正式运行 |

Guard 未通过验收时不开发 Auto 的生产接入。Auto 未通过独立测试时不改变 Guard 的部署和策略。

## 5. 阶段 A 和 B：先完成 Guard

### 5.1 Guard 的职责

Go 规则扫描完整规范化输入，处理 JSON、大小、附件、凭据、危险执行信号、多轮会话状态和 fail-closed。规则无法确定的语义再交给 `Qwen3Guard-Gen-8B`，判断防御研究与实际攻击意图、真实目标、组合式攻击链和规避策略。

文本Guard输入使用完整脱敏文本视图，包括用户文本、工具文本与历史、metadata等字段；原生附件内容按用户确认排除，以摘要绑定的元数据代替，不声称扫描图片或文件语义。2026-09-16隔离回归明确：Go的代码块/production/persistence等弱词组合只作为语义复核线索，不能直接覆盖Qwen3Guard的Safe结论；Unsafe/Controversial和不可用仍拒绝。密码、API key、OAuth token、Cookie、私钥和数据库连接串在模型调用、日志和错误响应之前替换成占位符。**外发脱敏三协议已通过GPU针对性实测，完整安全验收仍在继续**：Guard r4 返回经过检查的完整脱敏正文、原始正文 SHA-256 和脱敏版本；Auto 校验后统一用于分类、同步/SSE业务、计数及缓存。缺少或不匹配的结果返回503，旧版Guard不能直接与新版Auto混用。结构化扫描保留JSON、工具结构和数字精度，但启发式规则不能保证识别任意凭据格式；不能把针对性回归宣称为完整明文保护。见[本轮证据](evidence/2026-09-16-input-redaction/README.md)。

### 5.2 GPU 部署基线

模型固定为 `Qwen/Qwen3Guard-Gen-8B`，8B BF16，GPU1，vLLM 端口 8001。Go Security API 使用 8011，8001 只允许 8011 访问；8011 当前按既有 GPU 服务方式监听 `0.0.0.0`，依赖公司 VPN 网络边界访问，正式接入前仍需补充 VPN 网段 ACL 或等价访问控制。

权重目录：

```text
/data/vllm/models/Qwen/Qwen3Guard-Gen-8B
```

容器命令基线如下，执行前必须用当前镜像的 `vllm serve --help` 核对参数：

```bash
docker run -d \
  --name qwen3guard-vllm \
  --restart unless-stopped \
  --gpus '"device=1"' \
  --ipc=host \
  -p 127.0.0.1:8001:8001 \
  -v /data/vllm/models/Qwen/Qwen3Guard-Gen-8B:/models/Qwen/Qwen3Guard-Gen-8B:ro \
  m.daocloud.io/docker.io/vllm/vllm-openai:v0.19.0 \
  /models/Qwen/Qwen3Guard-Gen-8B \
    --host 0.0.0.0 \
    --port 8001 \
    --served-model-name qwen3guard-gen-8b \
    --max-model-len 32768 \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.70 \
    --max-num-seqs 192
```

当前服务器验证配置为 `max-num-seqs=192`、`gpu-memory-utilization=0.70`。由于 GPU1 专供 Guard，调优顺序是先逐步提高 `max-num-seqs`，再在每个并发档位评估 `gpu-memory-utilization`；候选档位为 `64/96/128/192/256`，必要时继续向上。最终选择可持续吞吐最高的档位，同时满足至少 10% 显存余量、无 OOM、队列等待小于 1 秒，并分别记录正常负载和饱和负载的 p95。当前 `192` 已通过 30 分钟正常负载、32K token 分块和队列满载验证；审计故障也已验证，版本化发布工具已具备；第二故障域按用户明确决定排除。`0.85` 和 `0.90` 显存配置已实测：`0.85` 在高并发时余量约 10.5%，`0.90` 约 4.5GB，且延迟收益不稳定，因此不作为当前配置。模型只生成短分类结果，固定 `temperature=0`、`stream=false`。

服务器模型接口当前按 Qwen3Guard 实际 chat-completions 输出解析两行标签：`Safe` 映射为 `allow`，`Unsafe` 映射为高风险 `block`，`Controversial` 映射为中风险并由 strict 策略拦截。输出格式错误统一按 Guard 不可用处理，不能误放行。

### 5.3 Go Security API

接口：

```text
POST /v1/preflight
GET  /healthz
GET  /readyz
GET  /metrics
```

基线配置：

```text
GUARD_VLLM_BASE_URL=http://127.0.0.1:8001/v1
GUARD_MODEL=qwen3guard-gen-8b
PREFLIGHT_LISTEN_ADDR=0.0.0.0:8011
PREFLIGHT_FAIL_CLOSED=true
PREFLIGHT_DIAL_TIMEOUT=200ms
PREFLIGHT_QUEUE_TIMEOUT=1s
PREFLIGHT_REQUEST_TIMEOUT=3s # 原Guard8011基线；4004完整输入检查使用30s，Auto等待35s
PREFLIGHT_MAX_QUEUE=128
PREFLIGHT_AUDIT_REQUIRED=true
```

`/readyz` 必须确认模型可访问、served model name 正确、规则版本和模型版本已加载。Go 服务不可用时不自动选择其他业务模型。

### 5.4 Guard 缓存和长输入

安全决策缓存键由脱敏规范化输入哈希、会话哈希、规则版本、策略版本和模型版本组成。Go 规则先于缓存执行，命中时才跳过 Guard；版本变化时失效。缓存中不保存真实凭据和未经脱敏的请求体。当前通过vLLM `/tokenize` 按实际消息模板计数，保留256个输出token和64个模板余量；能容纳时检查完整文本，超限按字段分块，大字段按Unicode拆分并重叠最多256字符。未知字段、重复键与精确数字均保留。每个分块都检查，任一Unsafe/Controversial即拒绝；分词失败返回503，不回退截断。

Go 仍然扫描完整请求。r11对已校验历史维护版本化摘要，新增消息/工具调用连同全部用户意图和边界上下文分块送检（P06两地实测已通过），不能因为 Guard 的 32K 上限静默截断内容。长历史另测分块数/秒，不能只看请求数/秒。

### 5.5 Guard 不可用时的固定行为

连接失败、模型未就绪、排队超时、推理超时、输出格式错误和版本不匹配统一返回：

```text
HTTP 503
code: preflight_unavailable
decision: unavailable
upstream_called: false
business_usage_written: false
retry_suppressed: true
```

同时写入 `preflight-security` 和 `security_model_usage_daily.unavailable`，记录原因码、请求/会话哈希、区域、模型版本、队列等待、推理延迟和错误类别。不能换模型、换账号、重试或写业务缓存。审计 sink 写入失败时继续 fail-closed 并报警。

### 5.6 Guard 验收

使用脱敏固定样本和两地近 7 天请求形状，测试短输入、8K、32K，以及请求并发 1、5、10、20、40、64、96、128、192、256（必要时继续向上）。对每个 `max-num-seqs` 档位记录吞吐、p50/p95/p99、队列等待、显存峰值、GPU 利用率、错误和 OOM。通过条件：在至少 10% 显存余量和无 OOM 的前提下，选出可持续吞吐最高的稳定档位；正常负载 p95 小于 300ms、队列等待小于 1 秒，连续 30 分钟无 OOM。超过稳定档位的请求必须排队或快速返回 503，不能拖垮服务。还要验证停止 vLLM、满队列、错误格式和审计 sink 故障时的 503 与记录。

单一 qiyuan-gpu 仍是单一故障域。2026-09-16用户确认没有额外显卡并明确不做第二故障域，本期取消第二副本要求；仍演练现有Guard故障关闭和重启恢复，不宣称高可用。

Guard 阶段完成条件是：服务版本固定、指标可查、审计可查、不可用行为通过测试、压测达标、回滚包准备完成。GPU 保持公司 VPN 网络边界，业务 Gateway 在 GPU 本机调用 Guard；不要求东京、美西服务器回连 GPU，也不新增公网 Guard 入口。完成后冻结 Guard API，不再和 Auto 同时改动。

## 6. 阶段 C：再完成 Auto

### 6.1 Auto 的职责

Auto 只负责选择业务模型和内部推理强度，不负责安全判断。选择顺序为：协议和能力门、任务类型、上下文和会话粘性、质量需求、推理强度、实时健康度，最后才用速度作为同等质量模型的决胜因素。

生产模型池移除 `deepseek-v4-pro`。`deepseek-flash` 作为最快模型候选，但每次实际调用仍以响应模型和 usage 为准。其他候选按能力画像配置，不把模型别名当成真实模型。

### 6.2 Auto 自动生成 reasoning_effort

客户端不传也不控制 `reasoning_effort`。即使客户端带了这个字段，Gateway 也不把它作为路由输入，默认剥离后由 Auto 自己生成内部值。这样同一个 `auto` 接口的行为由统一策略决定，避免不同客户端把低难度任务强行升到高推理，或把复杂任务压到快速档。

Auto 为每个请求生成内部目标 `effort_requested`，由语义难度产生 none/low/medium/high/xhigh；模型能力表另外支持 max，minimal 仅作适配兼容值。当前语义策略尚不自动产生 max，不把 max 参数探测写成自动选型已覆盖。最终发送值记为 `effective_reasoning_effort` / `effort_applied`，再单列供应商报告值。生成依据为当前任务的语义复杂度；上下文长度、工具数量和客户端自带 effort 不直接决定难度。推理强度先于最终模型选择确定，再过滤掉不支持该强度或能力的模型。

模型切换时，`effective_reasoning_effort` 也要经过滞回和会话粘性控制。除非任务阶段、能力要求或健康度发生变化，否则不在相邻轮次来回改变推理强度。

供应商适配器维护每个真实模型的支持矩阵和参数位置：OpenAI Responses 使用 `reasoning.effort`，兼容 Chat Completions 的供应商使用其声明的 `reasoning_effort`；DeepSeek 只在对应模型和协议明确支持时发送该字段。供应商不支持时，Gateway 不透传客户端字段，而是使用适配器定义的等价默认行为，并在 route audit 记录 `effort_requested`、`effort_applied`、`effort_status=applied|mapped|unsupported|defaulted`。参数映射以供应商当前文档和真实响应为准，不能只按模型别名猜测。

`effective_reasoning_effort` 必须写入路由记录、缓存决策记录和业务 usage。响应缓存键包含模型和有效推理强度，避免同一输入的不同推理强度复用错误答案；Prompt Cache 是否需要按强度隔离由各供应商实测决定，不能把响应缓存规则直接套到 Prompt Cache。

stage12 曾使用关键词与长度计分原型；2026-09-16 已将语义分类 v5 同步到 GPU 全新临时目录并在 8092 独立验证，生产入口仍未替换。stage12 当时对东京 `test`（API Key ID 141）的近 3 小时只读核对共 15 条：`none` 8、`low` 5、未传 2，Auto GPT 成功请求只有一条 `gpt-5.6-luna/low`。该历史样本见 [effort 核对](evidence/2026-09-15-auto-stage3/tokyo-test-effort-summary.json)，不能代表后续直连参数探测。数据库中的 effort 是参数记录，不能据此断言模型内部实际推理计算量。

stage12 观察到的质量缺口包括：简短复杂任务被评为 `low` 或 `none`，复杂请求在冷却期保持 flash、简单翻译请求在冷却结束后升级为 luna。新版仍须用独立标注的真实任务集验证难度、有效 effort 与切换时机，覆盖中高档、客户端 effort 忽略、同一任务续接和新任务重置。不得通过堆砌关键词、固定指定 effort 或单纯降低阈值制造通过结果。

#### 6.2.0 参数能力表（2026-09-15 核验）

- Astra：`low/medium/high/xhigh/max`，不支持 `none/minimal`；低于最低支持强度时显式映射为 low，记录 requested/applied/status。
- Luna、Terra、Sol：`none/low/medium/high/xhigh/max`，不发送 minimal。
- DeepSeek Flash：原生 `none/low/high/max`；minimal→low，medium/xhigh→high，按官方兼容语义显式映射。Responses 使用 reasoning.effort；Chat 使用 reasoning_effort；Messages 使用 output_config.effort 或 thinking.type=disabled。
- 分类调用的 effort 与业务调用的有效 effort 分开。分类主模型使用低开销目标，经能力表映射；独立复核目标 low。业务复杂任务仍按语义结果产生 medium/high/xhigh，不能把复核 Low 当作业务路由结果。
- 分类 trace 明确记录主模型、主分类是否通过 schema、复核模型和决策来源。主模型 HTTP 400、结构失败后备用模型成功，只能计作备用成功。

DeepSeek 依据：[Chat 参数](https://api-docs.deepseek.com/api/create-chat-completion/)、[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)。

五个文本模型按全部原生 effort、三种语言、Chat/Responses/Messages 已完成 [243 次真实参数探测](evidence/2026-09-15-auto-semantic/effort-probe-summary.json)，均 HTTP 200 且传输完整。Responses 有 27 次回报 effort 与发送值不一致，均为高档回报 high。只读查看 [东京 test 所属 codex-E 配置](evidence/2026-09-15-auto-semantic/tokyo-test-effort-policy.json)确认全模型 `xhigh→high`、`max→high` 映射；未修改共享组。这是2026-09-15的历史失败；2026-09-17已用专用无映射分组完成22次最高档和精确账单核对，详见P05。临时分组已退役，原共享分组保持。

本地日志分别记录目标、发送和供应商回报 effort；回报与发送值不一致时记录 `effort_mismatch` 并禁止写入业务响应缓存。没有回报字段时保留未知状态，不把 HTTP 200 当作实际强度证明。

官方依据：[Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)、[Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)、[Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra)、[Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)。东京 Astra/none 的 HTTP 400 与官方说明一致；此前未经核验的全模型共用 effort 表已修正。

**真实端点限制（2026-09-15）。** 五个文本模型、所有原生 effort、Chat/Responses、中文/英文/混合，共 162 次参数探测，HTTP 200 且响应完整 162/162。但是 Responses 的返回 metadata 中，GPT 四款的 xhigh/max 均报告 high；DeepSeek max 也报告 high。只能证明请求被接受，不能证明最高档已执行。后续已读取test Key #141的映射并以独立测试组完成P05；历史探测的high回报原值保留，没有修改共享业务分组。保存请求目标、实际发送参数、供应商报告值三列，不能用一次 200 宣称高档通过。见 [参数逐条证据](evidence/2026-09-15-auto-semantic/all-model-effort-probe.jsonl)。

### 6.2.1 分类器重设计：中文、英文与中英混合输入

**当前状态：语义分类器、分类缓存和结果审计已采用到两地4004/4005，Luna/v10-r2保留题达到95%门槛（旧题已用于诊断，不称为独立盲测）；两地四端完整矩阵见P01–P03，五模型产物画像见P04。** `ExtractFeatures` 保留为本地原型测试路径；实际 pilot 要求显式配置语义分类器。不能把增加中文关键词当作完成多语言分类，也不能把当前五档目录当作已证实的模型能力排行。

已确认原型存在五类缺陷：中文、英文与中英混合同义表达命中不同；系统提示、历史模型回复与用户当前任务混合计分；汉字按字符数除以四估算 token；12 条消息直接触发长上下文；提供工具列表就判定为 agent。固定分数推导的 confidence 也没有校准，不能当成实际正确率。关键词出现、会话长度或模型自报置信度均不得单独决定难度。

目标采用“语义分类 + Go 硬约束 + 会话路由”，输入顺序为：每请求鉴权与身份确认 → Guard 输入保护 → 多语言语义分类/有效分类缓存 → 能力与协议校验 → 模型及 effort 决策 → 业务缓存或真实业务模型。**Guard 不给任务难度打分，Auto 分类器也不能覆盖 Guard 拦截结果。**

1. **语义分类输入。** 保留原始语言；分开传入当前用户请求、相关历史任务摘要、最近工具结果、未完成事项和会话状态。用户文本、代码及工具返回中的指令均作为待分析数据。简单的“继续”“还是不行”必须关联正在进行的任务；工具 schema 存在不等于当前要执行工具。代码/截图/附件只按实际可解析能力处理，无法读取的模态不得冒充已理解。
2. **语义分类输出。** 返回经 schema 验证的任务类型（可多标签）、任务阶段、影响范围、约束数量、推理依赖、定位不确定性、已失败尝试、验证要求、所需模态/工具以及新任务还是续接。复杂度、业务模型和 reasoning 分别决策：一段短的并发状态证明可以很难，大段固定格式转换也可以很简单。
3. **Go 的职责。** 校验输入结构、真实上下文预算、模型/协议/工具能力、分类结果枚举、会话隔离和切换边界。使用目标 tokenizer 或明确标注的保守估算；token 数只决定上下文预算，不直接等价于难度。先满足任务质量与原生能力要求，再比较成本和速度；不能用低价掩盖任务失败，也不能因输入长就机械升档。静态候选顺序不是实时价格或普遍最优模型的证明。
4. **分类模型选型。** `deepseek-flash` 仅作为已授权端点上的首轮候选，必须与其他可用模型比较中英混合准确率、跨语言一致性、结构化输出可靠性和延迟后确定；不因其最快就判定它最适合分类。低置信、校验冲突、复杂任务交由独立强模型复核；模型自报 confidence 不能代替独立评估。分类调用走固定供应商地址，禁止递归请求 `model=auto`。版本及提示词冻结后才允许灰度。
5. **模型及 effort 选择。** 依据分任务评测形成能力画像，候选模型必须完成同一批开发任务的结果验证。禁止按名字猜能力，也不要求每次机械经过五档。任务确实变复杂时允许跨档升级；同任务短续问保持上下文，新任务重新评估。客户端 `reasoning_effort` 一律不用于选择；同义中、英、混合输入在相同能力、健康度和会话状态下应得到一致的难度与 effort。
6. **缓存与失败。** 分类缓存包含身份边界、相关上下文摘要、当前任务、工具状态和分类模型/提示词/策略版本；相关上下文改变必须失效，不只用最后一句作 key。分类缓存、业务响应缓存和供应商 Prompt Cache 独立计量。语义分类不可用/结构错误时先尝试配置好的独立分类器；均失败则返回 `503 classifier_unavailable` 并记录，不能静默落到最低档。Guard 不可用仍严格 `503 preflight_unavailable`，不得复核绕过。

**验证方式与门槛。** 首批诊断集为 12 个语义场景 × 中文/英文/混合 3 种表达，共 36 条，覆盖小源历史任务重建、短复杂问题、术语解释和无关工具列表，见 [样本](evidence/2026-09-15-multilingual-classifier/cases.json)。历史重建与新增合成反例单独标注，不冒充原始会话原文。正式验收集已扩充至 60 个独立任务 × 3 种表达（12 个开发任务、48 个独立保留任务），见 [冻结题集](evidence/2026-09-15-auto-semantic/cases-60.json)。标签由本次实现者在测试前给定，未经过独立人工复核，不构成最优模型证明；并按原始任务分组划分开发/保留测试集，不能把同一任务的译文分到训练与测试两侧。

- 在固定健康度、独立新会话条件下比较三种语言；预设跨语言难度与 effort 一致率 ≥95%，硬能力遗漏为 0，高复杂度标注任务被分到简单档为 0。2026-09-15基线保留集三语难度一致率为 Flash→Sol 91.67%、Luna→Sol 95.83%、Sol→Astra 和 Astra（low）→Sol 均 97.92%。后三者只达到本项一致率门槛，不能据此判定整体选型验收通过。分语言数据和不一致样本见 [分类对比](evidence/2026-09-15-auto-semantic/comparison.json)。
- 多轮任务覆盖真实回复续接、工具调用与结果、失败后重新定位、任务切换、缓存复用/失效、流式中断和最高档。附带冗长无关历史、12 轮简单对话、术语同义改写、简短复杂输入等反例，不能靠堆砌关键词制造升级。
- 分类标签不能证明哪个模型“最好”。需对候选模型的实际产物运行与任务相关的构建/测试/验收；工具或界面运行未验证必须单列。审核者预期复杂度只是初始标签，不是测得的能力结论。
- 每次声称某模型完成必须同时拥有：Guard allow；Auto 选型/effort 决策；供应商请求与响应状态/完整性；对应 Sub2API request_id、实际模型和 usage。选型日志、401/503、响应解析失败、合成数据和直连对照都不能标记为全流程通过。

### 6.2.2 路由日志与真实上游记录的对账

stage12 历史版本的 `route-audit.jsonl` 在上游执行前写入，只能证明“选择了哪个模型”；`usage.jsonl` 的 `attempt/success` 区分尝试与成功，当时缺少统一 request_id、上游状态码和完整响应证据。临时进程停止不代表历史请求成功。Sub2API 业务用量与 `ops_error_logs` 需分别核对；没有成功业务记录时，不能用本地选型日志替代。

本地已实现统一请求 ID，分别记录 `route_decided`、`upstream_started`、`upstream_completed/failed` 和 `response_cache_hit`。字段包括身份/会话哈希、区域、分类器与策略版本、选中模型、有效 effort、上游返回模型、HTTP 状态、错误类别、响应完整性、上游 request_id 和 token 用量；不记录凭据或原始请求内容。SSE 必须在结束或异常时补写结果，不得只写开流前的决策。按日统计分类模型与业务模型的调用，并用 `purpose=classification|business` 区分；本地响应缓存命中不重复计供应商 token。

### 6.2.3 新模型与 Claude Code 兼容（新增范围）

东京 `/v1/models` 已核对：名称为 `codex-auto-review`、`gpt-image-2.5-flare`、`gpt-image-2.5-sunburst`。不得使用误拼 codex-auto-view/sunbrust。

| 类型 | 接入要求 | 当前状态 |
| --- | --- | --- |
| codex-auto-review | 先核实它是否为专用动作审核接口、输入 schema 与响应契约；名称不能证明其适合一般代码审查或替代 Qwen3Guard | 专用Responses动作审核契约已实现并部署，保留原生model/effort/schema且先走Guard；不进入普通自动候选池，完整原生审核验收见P03 |
| Flare / Sunburst | 图片生成、图片编辑独立能力分支；使用 quality，不套用文本 reasoning_effort。Responses 顶层仍为主模型，图片模型放 tools.image_generation.model；Image API 直接选图片模型 | 两地Image API生成/编辑及SSE、Responses工具、multipart共10次返回有效PNG；附件内容按用户决定不做语义审核 |
| Claude Code 主会话/子 agent | 接收 claude-opus-5、claude-sonnet-5、claude-haiku-4-5-20251001；claude-haiku-4 作为用户要求的兼容入口。统一进入 Auto，不按名称强制原有静态映射；/v1/models 不列实际业务候选，只列 auto 和专用 codex-auto-review | 四端历史开发任务和两地原生图片已通过；两地高级矩阵Claude/OpenCode/Hermes各7/7、Codex工具6/6，见P01 |

[官方图片说明](https://developers.openai.com/api/docs/guides/image-generation)定位 Flare 为快速日常生成、Sunburst 为精确编辑候选。图片质量参数与主模型 effort、两者用量分别记录。图片编辑的图像输入保护必须另验，现有 Qwen3Guard-Gen 文本模型不能自动宣称覆盖像素内容；用户已明确原生附件内容先透传，只检查普通文本和附件元数据；附件语义审核后续增加，不新增输出审核阶段。

东京管理员近 7 天模型映射视图实际记录：Opus→Sol 3,480 次、Sonnet→Terra 1,523 次、Haiku 4.5→Luna 110 次；入站 /v1/messages，有同步及流式，样本 UA 为 claude-cli/2.1.266。属于现有 Sub2API 的请求名→上游映射，不能把请求名当作 Claude 原生模型已调用。美西尚未取得同范围证据。[脱敏映射记录](evidence/2026-09-15-auto-semantic/claude-code-observed-mappings.json)。

Claude Code 验收还须覆盖：x-api-key/Authorization 与 anthropic-version/beta、/v1/messages/count_tokens、system 数组和 cache_control、thinking/signature、tool_use/tool_result ID 与错误结果、多工具并发、SSE 事件及取消、压缩后续接、主/子 agent 独立会话和跨 Key 隔离。不能只验证消息字符串解析。东京对同一输入计数的实测为Deepseek404、其余4个GPT200；pilot对Deepseek明确使用utf8_bytes_estimate并写入响应头和审计，不能记为真实token或账单。其他模型使用上游报告值，该值也可能来自Sub2API内部估算，不能默认视为精确tokenizer结果。已支持显式 `X-Claude-Code-Session-Id`、Codex `session_id`/`conversation_id`、网关会话头及结构化 metadata 中的 session_id；四端实际版本与验证记录见维护指南和P01。普通用户 ID 和 prompt_cache_key 不作为会话。缺少会话时按独立请求处理，已登记工具结果按 Key/区域/协议/调用 ID 找回原回合，不能把多个 agent 强行合并。日志保留 requested_model、effective_model、response_model 和 request_id，不包含原始 Key/提示词/工具正文。

四个兼容名称分别直连东京 Messages 与 count_tokens 的 [8 次探测](evidence/2026-09-15-auto-semantic/claude-alias-count-probe.json)均 HTTP 200；这不是新版 Auto 链路验证。本地计数接口先鉴权、Guard、分类，再按当前状态选择计数模型，不推进会话或生成业务响应，返回 `X-Gateway-Count-Model`；实际消息发送时状态改变仍可能重新选型。token_count_started/completed/failed 写入路由审计。

### 6.2.4 历史开发任务的修改验证循环

[第二轮固定回放集](evidence/2026-09-15-history-replay/README.md)覆盖鸿蒙登录清理、Android 启动链路、前端发布排查和提醒字段修正，分别验证初始任务、工具返回、用户修正、新任务切换；三种表达共 48 个检查点，协议覆盖 Chat、Responses、Messages。它使用真实历史要求和重建工具消息，未冒充原始客户端抓包；该历史回放当时未覆盖实际业务产物和原生工具循环；后续实测分别见P01与P04。

当前语义输入版本为semantic-v8-native-compaction；下述历史回放来源仍按原版本保留。工具结果中的用户补充要求作为当前任务处理，但尚未结束的供应商工具回合保持模型和 effort；不能因 new_task 或 TTL 重新选择。工具绑定丢失、过期、跨 Key 或冲突返回明确不可用并写 routing_unavailable。文件状态写入失败回滚内存并返回错误，不静默认为已经持久化。该实现已采用同机共享卷文件事务和持久分类缓存，双实例真实续接通过；跨机器存储不在此次证明范围。

本地 Guard 增加 request_id 审计字段，Auto 发送同一 request_id 及区域/Key 隔离后的 session_hash；ID 不进入安全决策缓存键，不降低同输入缓存复用。缺少 Guard 配置时在分类前直接 fail-closed。该请求关联修改曾在隔离 Guard8012 验证，真实异常与 Auto 路由审计 request_id 已匹配；验收临时进程已清理。按11:59记录，生产 Guard8011 尚未替换；本地合并没有新增部署。

### 6.3 Auto 独立开发和测试

Auto与真实Guard已在独立4004/4005入口联调并运行；4000/4001尚未切换。Responses、Chat Completions、Anthropic Messages保留原始内容片段及工具schema，并注入Auto生成的路由参数。SSE、WebSocket、受控失败切换、同机共享状态及分类缓存已有区域实测；当前仍欠四客户端高级矩阵、旧compact原生复验、真实Prompt Cache比较和最高effort证据，逐项见P01/P02/P05/P12。effort验收须区分客户端字段、内部目标、实际发送值与供应商回报，覆盖未传/任意客户端值、不同难度、能力不匹配和供应商重写。

Auto 的业务缓存、上游 Prompt Cache 和路由决策缓存分开。模型切换只在请求或 WebSocket turn 边界发生，不能在流式响应中途切换。一次切换允许多次必要升级，但用模型粘性、升级冷却、滞回阈值和任务阶段重置避免振荡。

每个实际模型按 `effective_model` 和 `effective_reasoning_effort` 统计每日请求、attempt、输入 token、cache hit、cache miss、输出 token、成功失败、升级和降级。`requested_model=auto` 和客户端传入的 `reasoning_effort` 都不作为最终模型分组依据。

业务响应缓存命中用 `response_cache_hits` 单独统计：请求数和成功数增加，attempt 以及供应商输入、输出、Prompt Cache token 不重复累计。当前固定 mock 用例验证两次请求仅一次上游调用，累计输入 10、输出 2、供应商缓存 hit 6/miss 4；修复前这些 token 被重复累计为 20、4、12/8。这是记账正确性实验，不是供应商实际命中率或两地生产收益测量。

响应缓存只写入无传输错误的 HTTP 2xx、满足大小策略的完整结果，TTL 从响应完成后起算；跨协议、实际模型、reasoning、版本和 API Key 隔离，缺少缓存身份字段时跳过缓存。Guard block/unavailable/无效 verdict 不进入业务缓存、路由或业务 usage。内存缓存按值复制响应体和 usage，避免调用者修改缓存内共享对象。

当前 `Pipeline` 支持同机共享卷事务型会话/工具状态、持久分类缓存、同步HTTP与SSE/WebSocket生命周期，并提供0600 fsync usage/审计spool。受控失败切换和两地区域usage数据库分钟导入已有实测；P11已完成图片、动作审核和失败attempt的精确账单核对，未知和取消部分值仍单列。进程内模型健康状态不跨实例共享；同机共享卷不等于跨主机数据库或容灾。真实请求缓存摘要必须覆盖全部会影响回答的字段，不能直接复用分类器删减后的输入。

Auto阶段完成条件仍是：固定测试集质量达标，模型选择可解释，切换无振荡，缓存字段能对账，失败降级不改变安全状态，每日用量能按区域、模型和API Key查询。共享状态/分类缓存及区域数据库导入已完成当前范围；模型产物比较、完整客户端、多用户、最高effort及缓存收益已按顶部表记录结果和限制。既有指定测试Key的结果不能代替所有用户和能力验收。

## 7. 阶段 D：只做一次接口接入

两阶段各自通过后，在 GPU 的既有用户入口链路中接入 Gateway，复用本机 Guard。网络方向固定为「GPU → 两地前置 → 区域 Sub2API」，不需要两地访问 GPU。第二Guard故障域已由用户明确排除，本期不要求区域Guard副本或反向relay。

接入顺序（先独立4004验收，再切既有入口）：

1. 在 GPU 唯一临时目录构建，临时 Gateway 仅监听本机独立端口；分别配置东京 9881、美西 9880 和包含正文契约的独立 Guard8012，先校验健康、认证透传、Guard 顺序和真实模型响应。
2. 只用已授权的测试 Key 完成非流式、SSE、跨模型切换、缓存及 usage/异常日志对账。Key 仅通过受限文件或进程输入提供，不写到源码、命令输出、归档或文档。
3. 4004按正式区域入口建设，按请求复用Sub2API鉴权及额度检查、隔离Key，不另建Key系统。区域模式关闭整段响应缓存，业务逐次交Sub2API最终校验/计费；保留Prompt Cache及隔离的分类缓存。通过后启用独立4004供大家用各自东京Key验收，Auto8093和配套Guard8013只在本机监听；共享状态和用量落库等生产前置项继续验证。
4. 临时链路验收后，备份 GPU 两个 Nginx 的实际挂载配置，验证新配置和回滚命令，再按先东京单 Key、后美西单 Key的顺序灰度。管理页面、健康接口及尚未灰度请求保持各自已有路径；已有 4000/4001 用户地址保持不变。

```text
输入规范化
  → Go 硬规则
  → Guard 脱敏并决策
  → 校验 allow 正文、输入摘要和脱敏版本
  → Auto 只消费脱敏正文
  → 业务缓存
  → 账号选择和上游
```

端到端测试只使用测试 Key：

- Guard `block`：不进入 Auto，不读写业务缓存，不调用上游。
- Guard `unavailable`：返回 503，写入审计，不重试，不换账号或模型。
- Guard `allow`：Auto 正常生成 `effective_reasoning_effort` 并选择模型，业务 usage 和安全 usage 分开记录。
- 同一个输入再次出现：只命中版本匹配的安全决策缓存，不重复调用 Guard。

## 8. 阶段 E：灰度、监控和回滚

先东京，再美西。每个区域先一个测试 Key，再逐步扩大。观察 Guard allow/block/unavailable、队列、p95、上游 `cyber_policy`、账号隔离、Auto 模型分布、缓存命中和业务成本。

Auto 出问题时只关闭 Auto，回到固定模型，Guard 继续保护输入。Guard 出问题时保持 fail-closed，不能为了恢复 Auto 绕过 Guard。需要完整回滚时，停止 Gateway 到 8011 的调用，保留审计和指标，不修改 GPU0 业务模型、业务数据库或既有缓存。

## 9. 文档和代码位置

全部智能网关内容位于 [AI Gateway 项目](../README.md)。

- [CHANGELOG](CHANGELOG.md)：本地变更、上游适配、验证、部署及历史执行表。
- [维护指南](维护指南.md)：代码职责、版本/缓存失效、升级步骤和回归矩阵。
- [Auto](../auto/README.md)、[Guard](../guard/README.md)：当前组件行为。
- [Guard 部署](../deploy/guard/README.md)、[联合验收部署](../deploy/acceptance/README.md)：构建、运行和回退。
- [验收证据索引](evidence/README.md)：所有历史版本、真实结果、失败和源码清单。

## 本期完成状态与保留边界

2026-09-17 R02：两地release v29、Auto复用v27、Guard v29/r19。691项Go/42项Python、真实Guard103/103、两地原生读取/续问通过；入口与首次失败复查范围见顶部。R01及此前的原生四端、多用户、模型画像、最高effort、缓存、用量及版本回退均已按对应范围记录证据。

r17同制品、同GPU真实模型与生产参数的独立18017负载：10RPS连续30分钟18,000/18,000，p95 93.61ms，预检队列max 0ms，窗口内OOM 0，分钟采样最低显存余量20.38%；结束后独立进程退出。旧r15混合长输入p95 483ms失败保留；最新普通负载不能覆盖该限制。[最新负载](evidence/2026-09-16-native-media/guard-r17-normal-load.json)与[资源及制品对应](evidence/2026-09-16-native-media/guard-r17-normal-resources.json)可复核。

P04五模型启动题均有需求漏项，没有真机/AVD；画像完成不等于模型全部成功。F01最新DeepSeek/r2对照单轮95.83%，不等于连续稳定性或已部署；线上按用户选择保持Luna/v10-r2。R01原生东京总结仍有计数/类型/语言缺陷，美西覆盖正确；选型改进不等于回答质量保证。

临时分组、用户、Key均退役，10个固定模型验收进程已退出；日志/账单/原账户保持。4000/4001正式切流、第二故障域、音频和附件语义审核未执行，按用户明确范围保留。
