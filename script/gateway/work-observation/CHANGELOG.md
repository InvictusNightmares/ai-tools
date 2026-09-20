# CHANGELOG

## Unreleased

### 2026-09-20 / 正式入口持续采集恢复并固定

- candidate-r3 已在 GPU 正式接入 4000/4001：Nginx 内部路由分别为 `127.0.0.1:18400` 与 `127.0.0.1:18401`，Tokyo/US 两个 sidecar 与长期 live watchdog 均由 enabled systemd 实例托管；watchdog 使用 `--seconds 0 --interval 5 --max-5xx -1`，上游 5xx 只记录、不把业务失败误判为采集器故障。
- 修复 Nginx 只读 bind mount 原子替换后的网络命名空间失配：切换重启 Nginx 后，live wrapper 会重新创建 sidecar 并等待当前 namespace 的 18400/18401 探针恢复；watchdog 每个采样周期继续探测路径，失联时关闭采集并回退。
- 修复 candidate launcher 中少一个 `9` 的 63 位 RepoDigest。当前默认固定 GPU 已验证的本地 immutable image ID `sha256:f787d2269bb599297ef6e2fc50d690813821fa348870b62abfc6fa99112ad7d2`；正确的 registry digest 也已在历史证据中更正。Tokyo 重启实测 sidecar 可启动、ExecStop 成功、18400/4000 均200。
- GPU SELinux 环境下，宿主 systemd unit 移除 `NoNewPrivileges` 以允许 Docker 生命周期操作；collector 容器内部仍保留 `--security-opt=no-new-privileges`、非特权用户、只读根文件系统和能力剥离。四个 candidate 实例当前均 `enabled/active`。
- 为验证 US 重启恢复，先停止 live watchdog 让 4001 回退，再用修正 launcher 重建 sidecar、重新 enable；维护边界约产生 7 条 502，`--max-5xx=-1` 仅记录未触发回退，随后 18401/4001 均恢复200。该短暂维护窗口不代表采集器丢失计数。
- 01:54 UTC Tokyo 曾因一个被取消且正文不是完整JSON的约3MB `chat_completions` 请求产生1次 `projection_errors` 而按旧策略回退；事件已写入并保留`body_projection_failed`缺失标记，业务响应为400，sidecar/写盘没有故障。watchdog已修为把单条`projection_errors`与`truncated`作为可见质量告警（window JSON新增`projection_errors_delta`），仅丢弃、写入、缺失账本、采集不可用、队列/磁盘故障触发回退。
- 修复后 Tokyo 于01:59 UTC重新启用，观察至02:07 UTC两地 live/sidecar 仍active；Tokyo `captured/written=259/255`、US `736/23208`（Tokyo在重启后重新计数；一请求可产生多条记录），两地 capture=true、fatal counters与warning counters均为0，4000/4001及命名空间内18400/18401均200且计数继续增长。该数据只写采集卷；`semantic.py`、Guard/Auto正式调用和训练调度仍未启用，长期 p95 与离线标注评估待后续完成。

### 2026-09-18 / candidate-r3 正式接入 4000/4001

- 按用户要求将 GPU 上的 candidate-r3 采集旁路正式应用到两个入口：4000 的 Nginx `proxy_pass` 为 `127.0.0.1:18400`，4001 为 `127.0.0.1:18401`；两端容器内运行配置与宿主配置 SHA 一致（`1cd5a85f...`、`636b5896...`），原 upstream 备份保存在 `/data/work-observation/cutover-live-candidate-r3-final-20260918T093914Z/`。
- 生产 Nginx 的单文件配置是只读 Docker bind mount，原子替换宿主文件后旧容器仍会读取旧 inode；`short_window_cutover.py` 已修为检测 `RW=false` 后重启对应 Nginx 容器，再执行 `nginx -t`，避免出现“宿主已切换、容器仍走原 upstream”的假接入。
- 两地长期 watchdog 已改为无期限运行（`--seconds 0 --interval 5`），PID 由最终复核确认仍存活；sidecar `capture_enabled=true`，正式 `4000/4001` GET 均 HTTP 200，采集计数持续增长。最近复核 Tokyo `captured/written=8/5`、US `21/18`，`dropped/truncated/write_errors/projection_errors/loss_persist_errors` 全为0，watchdog日志为空。
- 本次只接入采集器；滚动分析定时器和 `semantic.py` 未启用，员工正文不会逐条发送给 Guard/Auto。未来训练需要从采集卷离线生成版本化数据集、标注和评估后再灰度发布。

### 2026-09-18 / GPU入口拓扑与sidecar短窗口工具

- 只读核对GPU真实入口：4000由`tokyo-sub2api-proxy`转发到`106.14.254.110:9881`，4001由`us-sub2api-proxy`转发到`106.14.254.110:9880`；记录现有配置SHA和可回退文件，线上配置未改。
- 在共享Nginx网络命名空间的隔离sidecar中验证dev.9候选采集器：两地回环端口均可访问原upstream并返回200，capture开启测试各写入1条完整事件、无丢失/截断/写入错误；实验sidecar已停止，事件仅为根路径smoke，不是员工流量。
- 新增sidecar systemd模板、严格单行Nginx切换/回退脚本和有界watchdog；GPU另行安装路径独立的candidate-r3 systemd实例并完成重启恢复验证。候选容器固定GPU实测镜像`nginx@sha256:feb6f75a08aa55b44576f98c15b8859819ecf54f3e4d2157f42c2d01cb58a3d2`，两地采集保持关闭且所有错误/丢失计数为0。正式wrapper、统一200GiB卷和4000/4001切换仍未执行；watchdog可监测采集计数、队列、磁盘和Nginx 5xx，延迟p95仍须窗口后离线核验。
- 在正式切换前补强回退事务：state目录锁、配置写入前二次SHA核验、prepared manifest 崩溃恢复、manifest/region/config校验、失败时立即恢复路由；watchdog启动异常、SIGTERM、预存损失和回退失败均形成显式结果。sidecar示例配置统一使用容器内`/data/store`，并在启动前检查65532可写。
- GPU已按新建文件安全边界创建并挂载200GiB ext4卷（UUID `a3326109-6292-4556-a9a9-eac848858290`），`volume.py status`校验通过；candidate-r3两地store已迁移到该卷，服务仍保持capture关闭。卷挂载未改fstab、Nginx或Sub2API。
- 迁移后的卷完成受控sidecar smoke：两地各新增1条事件，HTTP 200、`captured=1/written=1`，所有损失/错误计数为0；等待异步disable收敛后两地均为`capture_enabled=false`，随后systemd重启恢复仍为active。正式4000/4001路由和capture开关保持不变。
- Tokyo首轮短窗口前置切换曾触发watchdog缺陷：脚本错误读取不存在的`REGIONS["access_log"]`字段；切换事务已自动执行disable和Nginx回退，配置SHA恢复原值，未留下采集路由。已修为使用CLI访问日志路径并补充KeyError保护，修复后需重新做短窗口。
- 修复后完成Tokyo 60秒短窗口：12次watchdog采样、Nginx新增5xx为0，结束时自动disable并回退，回退错误为null；最终配置SHA、原upstream、candidate systemd active均恢复/保持正常。窗口只有采集器根路径自检事件，没有真实员工任务，p95仍需真实样本后离线复核。
- US随后完成同样的60秒短窗口（12次采样），Nginx新增5xx为0，自动disable和回退均成功；两地最终配置SHA、原upstream、capture=false和candidate systemd active均核对通过。两次窗口都只有自检事件，不能替代真实员工p95/质量验收。
- candidate unit的旧`ExecStop`曾因Docker socket权限返回1；已备份并改为systemd幂等忽略失败（unit SHA `31b3831f197cf0bdaa9154e65f7178822b82a3df6a1ed047288678d8d266a5e1`），daemon-reload后未重启当前实例，Tokyo/US仍active、Result=success、NRestarts=0。
- 按用户要求完成两地600秒观察窗口：watchdog各118次采样、5xx均为0、failure/rollback_error均为空、两地自动回退并恢复原Nginx SHA；结束后candidate systemd仍active、capture=false，错误/丢失计数全0。当前事件数Tokyo 3、US 2，未形成可验证的真实员工任务样本。

### 2026-09-18 / 独立采集 dev.9 性能优化与持久语义预览

- 澄清采集层与旧日志边界：4000/4001原有访问、用量和`policy-log`记录只能提供部分元数据/异常证据；`work-observation`本身就是待接入4000/4001的独立反向代理采集器，目标是保存网关可见的完整请求、回复、流事件和工具回合，再分别做统计与离线Guard/Auto复核。当前仍未接入正式入口。
- `Observe`正文副本复用4KiB/32KiB/128KiB/1MiB缓冲，完整未压缩WebSocket帧在采集所有权缓冲内就地解掩码；DiskStore改为分段写入封装，避免大事件落盘时再次分配整份正文。原始正文、附件元数据和鉴权边界不变；新增释放路径覆盖队列拒绝和后台完成。
- GPU隔离基准在优化二进制上完成Go测试，最终完整场景为63组/8,820次转发、14,364条记录，内容一致且无丢失/截断/写入错误。保留完整三轮与专项报告；共享GPU负载下部分单轮p95仍超过5%，因此不把性能写成通过，不接入4000/4001。报告见`docs/evidence/2026-09-18-collector-r2/`。
- 同一Auto release的离线语义预览已改为GPU上的持久systemd模板服务，东京8095、美西8096均只监听127.0.0.1；服务健康、回环认证和重启恢复通过。此前临时合成进程的Guard allow、Auto route-preview、`deepseek-flash`结果保留，但持久服务新会话仍需分类器调用方凭据透传，正式8093/8094继续关闭route-preview，正式采集/调度仍关闭。
- 复核持久服务时发现新会话分类器认证/可用性不稳定；两地专用semantic Key直连分类器的合成请求均200，但Auto regional模式明确禁止共享`AUTO_CLASSIFIER_TOKEN`。候选代码现增加仅route-preview可用的0600 `AUTO_CLASSIFIER_TOKEN_FILE`，启动器按东京/美西写入对应分类器端点；生产regional服务仍只透传调用方凭据。远端最新审计需待跳板恢复后复核，旧Python 3.6的`text=`兼容性失败日志保留，启动器已使用`universal_newlines`。
- 候选 Auto 已在GPU隔离目录完成`gofmt`、`go test ./...`、`go test -race ./...`、`go vet ./...`和静态构建（SHA见`docs/evidence/2026-09-18-collector-r2/semantic-preview-candidate-deployed.json`）。东京8095、美西8096已切换到候选二进制并通过健康/认证/合成route验证，两地均返回`deepseek-flash`；正式8093/8094、4000/4001和Sub2API未改动。性能5%门槛、200GiB/30天生命周期和正式调度仍未签收。
- 候选采集器在GPU完成Go测试、race、vet和静态构建；独立生命周期smoke覆盖Codex/OpenCode/Hermes/Claude协议形状，6条事件中5条完成、1条进程中断可见，正文完整且鉴权头未落盘。真实Codex脚本复测因GPU上的0.135.0-alpha.1不接受历史`--stdio`参数而单独阻断，保留为环境证据，不判为采集器失败。

### 2026-09-18 / 独立采集 dev.9（缺失账本）

- DiskStore新增`losses/YYYY-MM-DD.jsonl`持久缺失账本，写入事件ID、UTC时间和原因，不包含正文；账本计入存储上限并随30天清理。状态新增`loss_persist_errors`，账本失败只计数、不阻塞业务；`observe losses`提供独立元数据导出。
- 新增Go回归覆盖账本权限、正文不落盘、不安全ID拒绝和独立`observe losses`导出。GPU隔离目录使用`golang:1.27.1-bookworm`完成gofmt、`go test -race`、`go vet`和`CGO_ENABLED=0` Linux构建，退出标记为`__WO_EXIT__=0`；证据见`docs/evidence/2026-09-17-collector-r1/dev9-go-validation.json`及日志。macOS未执行本地Go构建；dev.8完整性能与四端证据继续作为历史基准。
- 同步加入`tools/semantic.py`本地复核worker：请求与可见回复分别调用私网Guard预检和Auto route-preview，block可记录且不改变业务，不可用或陈旧running任务可重试；regional Auto要求认证时支持0600专用`auth_file`，只在请求头使用，不落分析库或日志；正文不落分析库。默认关闭，52项Python回归通过。GPU合成 smoke 已确认 Guard 200 allow；正式8093/8094因关闭route-preview在认证后返回404，随后用同一release的临时回环8095/8096、独立状态/审计文件和两地专用Key完成认证分析，Guard 200/allow、Auto 200/complete、`deepseek-flash`、队列清零。临时进程已停止，未发送员工正文。

### 2026-09-17 / 独立采集 dev.8，隔离功能通过、性能未达标

- 修复重启时持久化采集开关生效窗口；减少记录封装重复扫描、复用WS缓冲并明确所有权；无附件/无转义的有效JSON直接保留原文，附件反例仍完整检查。采集正文预算由128MiB提高到512MiB，进程压测限额仍2CPU/2GiB。数据格式v1、正文不脱敏不加密、业务转发和上游策略保持。
- 36项Go测试、race/vet和Linux/macOS构建通过；四原生客户端33项流程、69条HTTP交换通过，含原生压缩、工具/子任务、取消恢复和图片。原生Codex WS另6项通过，31条消息/连接记录无缺口。图片原样到达上游，采集只存元数据。首次媒体验收器空行解析失败保留，修正后四端重跑通过。
- dev.5长输入压测出现25条截断/13次投影错误；dev.6及dev.8完整63组/8,820次内容一致、14,364条记录零缺失。dev.8合并p95的8MiB JSON总耗时+5.60%、64KiB WS+15.52%，仍阻止正式接入；dev.7仅WS专项结果另存，不作为完整验收。各轮失败和新增整条路径开销完整保留。
- 新增管理员元数据查询；请求/回报模型分列、HTTP与WS时长分列。滚动报告改SQL聚合，修复小样本p95计算，分布最多100项并标省略数量；100万条合成记录约6.8秒。扫描游标跨批恢复、周期重扫避免尾部饥饿；44项Python回归通过。费用、任务质量、未可靠关联会话均不补造结论。
- 独立固定容量数据卷工具仅格式化新建文件，核验UUID/回环镜像，拒绝覆盖已有路径。256MiB实验卷真实ENOSPC下业务响应不变，采集损失可见，释放填充文件后自动恢复；实验卷已卸载。旧losetup参数失败保留、修复及清理完成。正式200GiB卷和所有副本/临时文件同卷的服务部署尚未集成。
- dev.8服务启停、强杀恢复和滚动索引再次通过；6条合成事件幂等、正文不复制、语义任务仍pending。未改Sub2API、4000/4001或4004/4005，未安装正式分析定时器。仍欠最终性能、全局容量/导出生命周期、持久缺失定位、可靠上下文与本地语义worker、WS远端压缩组合和发布回退；见[阶段证据](docs/evidence/2026-09-17-collector-r1/README.md)。

### 2026-09-17 / 独立采集闭环 dev.4

- dev.2完整保存压测36组/7,020次响应一致，含预热2,724个交换/连接、8,100条记录，零丢失/截断/写入错误。合并样本的开关p95增幅均≤5%，但短JSON单轮最高+5.81%、WS单轮+9.64%；新增整个代理路径WS总耗时+36.70%，尚未达到最终性能稳定性验收。保留每轮及首次陈旧status失败。
- dev.3四原生客户端共27项检查通过，采集63/63交换；同时发现Hermes响应头前取消被误加上游失败/502。dev.4修复取消归因，新增Claude原生会话和子任务头的按Key隔离关联；原失败证据保留，dev.4原生复验进行中。
- 启动存储/身份/恢复失败时显式停采并继续转发，可选独立runtime_dir保存状态；enable不能绕过故障。30项Go顶层测试、race/vet和Linux/macOS构建通过。
- 新增滚动分析worker与未安装的5分钟systemd模板：校验原记录、幂等增量、独立限额队列、小时/每日统计、30天索引清理；不复制正文、不联网、不执行业务工具。34项Python通过，实际合成采集器→滚动分析6条记录不重入，质量/费用仍未知。修复Anthropic分段用量合并及WS临时usage重复计数。
- 无正式入口接入。真实Guard/Auto语义worker、上下文关联、全局200GiB与导出副本管理、故障持久缺失定位、完整性能/原生WS附件/发布回退仍待完成。证据见[阶段验收](docs/evidence/2026-09-17-collector-r1/README.md)。

### 2026-09-17 / 独立采集闭环 dev.2

- 新增独立代理/管理命令，默认关闭且只监听回环；入口身份来自配置，真实UA与业务内容保持转发，鉴权头只在内存用于关联。
- 后台保存HTTP/SSE及WS有序消息，原生附件仅元数据；受限明文记录带校验摘要、原子写、单写入者锁、容量检查和30天到期清理。重启标记未完成请求，不重放业务。
- 打通init/serve/enable/disable/status/export/prune与证据/分析工具；合成生命周期6条记录（5正常、1强杀中断）完整导入，费用和任务质量未知值保持。
- 关闭开关的旧实现只挡新请求，已有交换仍采集；定向回归失败后修复为停止后续正文且不跨缺口接续。保留失败日志。补充SSE元信息、API流内错误归因、跨鉴权写法的Key关联及WS结束队列丢失的缓存回收。
- 初次完整压测请求内容均正确，但逐组采集状态存在一秒陈旧窗口；结果只作探索，修正为核对预期采集请求总数后复测。最终性能验收和原生四客户端仍待闭环。
- 尚未接入4000/4001，Sub2API/Auto/Guard及正式入口配置不变。启动存储降级、导出统一额度/保留、故障逐条持久定位、正式发布回退和真实语义分析尚未完成。


### 2026-09-17 / 原文采集与完整工作过程分析

- 用户明确取消正文脱敏和落盘加密。原始普通文本、工具参数和工具返回存入受限明文目录；鉴权头不采集，附件仅元数据，30天/200GiB边界保持。早期脱敏草稿不再作为当前实现要求。
- 明确首要目标为Guard/Auto结合上下文分析用户请求及模型回复；不能以模型占比和费用统计替代内容分析。保留消息角色、引用/工具来源、流事件顺序及缺失范围，离线模拟与生产事实分开。
- 以附件元数据投影替换旧正文脱敏实现，普通文本/工具字符串/流式碎片保持字面内容；新增独立证据包导出及9项测试，与统计/健康检查共19项Python回归通过。证据包保留全事件及来源索引，不编造候选判断；6项Go投影测试和go vet通过。
- 同步内容契约、采集说明、分析命令、总计划；未部署到4000/4001，未改变现有Guard/Auto策略。

### 2026-09-17 / 性能优先选型

- 按用户要求取消Go语言预设，暂停Go正式实现；增加成熟代理能力核查和独立基准实验。
- 基础代理对照已完成120组、37,560次请求，内容校验全部成功；双方仍有采集增量超过5%的场景，尚未达到完整采集发布条件，未选择正式制品。完整结果见性能选型证据。
- 对比需覆盖Nginx原路径、增加代理但关闭采集、增加代理并开启采集；单独报告协议正确性、p95、吞吐、CPU、内存及丢失。轻量采集实验不能代替完整采集全链路验收（以最新内容契约为准）。
- 新增独立本地分析命令：采集导出幂等入库、滚动元数据统计、费用未知值、按已验证会话分组保留集、实际/模拟隔离及30天索引清理；6项合成回归通过，尚未连接真实采集或启用调度。
- 新增只读健康检查，区分新增/历史丢失、进程重启、队列/磁盘压力及陈旧状态；与分析共10项回归通过。旧要求下Go脱敏初稿5项通过（已被原文采集要求替代），首次测试夹具语法错误已修复；仅为未部署初稿的范围。

### 2026-09-17 / 持续采集计划实施中

- 用户批准4000/4001持续采集、30天滚动保留、附件仅元数据、滚动分析及测试入口验证，并要求独立目录。
- 用户随后明确改选GPU独立采集代理：先隔离验证四端、性能及回退，通过后接入4000/4001。Sub2API源码/镜像/升级不改，取消两地缓冲与正文传输；当前未部署、未开启采集。
- 基线为两地实际运行0.2.4+policy-log.8，原异常记录与业务转发保持；不执行正式Auto/Guard切流。
## 2026-09-18（分析网络边界与 UA 透传）

- 滚动语义 worker 在使用受限专用认证文件回放 Auto 时保留采集事件中的真实 `User-Agent`，鉴权仍只来自 0600 文件，不从正文或事件字段拼接凭据；无认证的测试替身调用形状保持兼容。
- 分析 systemd 模板不再使用与宿主隔离的独立网络命名空间，改为仅允许回环地址、拒绝其它地址，确保启用语义 worker 时能访问 GPU 回环 8095/8096，同时不能访问公共或正式业务网络。模板仍未安装，正式入口和采集开关保持关闭。
- 本地 Python 回归更新为 54 项全通过；GPU route-preview 的间歇性 `classifier_unavailable` 仍待远端审计日志确认，未绕过 regional Auto 的调用方凭据约束。
