# AI Gateway

一个 Go 项目，包含 Auto 智能路由、Guard 输入保护、部署工具和维护文档。Auto 与 Guard 是可独立启动的服务，共用源码版本、验证入口和变更记录；Qwen3Guard 仍由 GPU 上的 vLLM 独立运行。

东京4004、美西4005已部署Auto+Guard，Luna分类/Sol复核，真实UA透传。原生图片、文件及Flare/Sunburst生成编辑已有两地内容验收；两地四客户端高级矩阵已完成，原生动作审核允许/拒绝已闭环，五模型产物画像已完成并保留需求漏项，r17历史普通30分钟负载通过，后续Guard版本及各自验证范围以总计划为准，音频按用户决定暂不支持。进度、真实内容验证和限制见[总计划](docs/智能网关与Guard分阶段实施总计划.md)与[原生媒体证据](docs/evidence/2026-09-16-native-media/README.md)。

## 从哪里开始

| 需要了解 | 入口 |
| --- | --- |
| 当前进度、下一步和生产接入条件 | [实施总计划](docs/智能网关与Guard分阶段实施总计划.md) |
| 每次改了什么、测了什么、部署到哪里 | [CHANGELOG 最新记录](docs/CHANGELOG.md#unreleased) |
| 代码职责、上游升级、版本和缓存规则 | [维护指南](docs/维护指南.md) |
| 分类稳定性与多项目产物 | [模型验收报告](docs/模型分类与开发任务验收报告-2026-09-17.md) |
| 最高effort与缓存成本 | [缓存及最高档报告](docs/最高档与缓存验收报告-2026-09-17.md) |
| 真实结果与历史失败 | [验收证据索引](docs/evidence/README.md) |
| Auto 的请求、路由和日志行为 | [Auto 说明](auto/README.md) |
| Guard 的输入保护和接口契约 | [Guard 说明](guard/README.md) |
| GPU 模型/API 部署；独立联合验收部署 | [Guard 部署](deploy/guard/README.md)、[联合验收部署](deploy/acceptance/README.md) |

## 项目结构

```text
ai-gateway/
├── go.mod                 # 唯一 Go module：local/ai-gateway
├── cmd/                   # auto-server、preflight-api、预览与评估程序
├── auto/                  # 分类、路由、协议、缓存、会话、审计和用量
│   └── testdata/          # Go 回归使用的冻结历史题集
├── guard/                 # 输入契约、Go 规则、脱敏和判定主流程
│   └── model/             # Qwen3Guard HTTP 客户端
├── config/                # 配置说明样例；当前程序实际读取环境变量
├── deploy/                # Guard 部署、独立联合验收部署
├── tools/                 # Python 验收工具及 pilot 启动脚本
├── docs/                  # 总计划、CHANGELOG、维护指南、evidence
├── verify.sh              # 本地完整验证
└── verify-on-linux.sh     # Docker Linux 完整验证
```

## 构建与验证

在本目录执行，Go 测试只使用本机临时 HTTP 服务：

```bash
go test ./...
bash verify.sh
# Go 不在 PATH 时：GO=/path/to/go bash verify.sh
# Linux 主机使用已缓存的固定 Go 镜像：bash verify-on-linux.sh
```

统一验证执行格式检查、vet、全部 race 测试、Python 测试和六个 Linux amd64 程序的静态构建。`verify.sh` 输出测试日志、摘要和源码清单到新的私有临时目录，不启动真实服务，不调用模型。当前验证工具链为 Go 1.27.1，`go.mod` 的语言版本为 1.22；其他工具链需单独验证。

需要在本机运行时，构建本机架构的服务到 `bin/`：

```bash
mkdir -p bin
CGO_ENABLED=0 go build -o bin/auto-server ./cmd/auto-server
CGO_ENABLED=0 go build -o bin/preflight-api ./cmd/preflight-api
```

## 当前运行边界

`auto-server` 支持区域入口 `regional` 与历史单Key测试 `pilot` 两种模式，均只监听回环地址。regional透传各人的Sub2API Key，不保存用户Key或另建账号系统。4004/4005作为可随时更新的多人测试入口，部分用户试用不代表正式切流，保留网页、账号和用量路径，模型请求进入Auto+Guard；程序与策略复用，区域上游、端口、状态/日志按区域配置。实际部署状态见总计划。

区域服务每次业务请求均经过Sub2API最终权限与计费检查，关闭网关整段响应缓存，与既有Nginx的`proxy_cache off`一致；供应商Prompt Cache和隔离的分类缓存保留。

既有 VPN 入口 `4000` 对应东京、`4001` 对应美西，验收通过后才切换。`4003` 已有其他服务占用。新版 Auto 要求 Guard 的 `credential-redaction-v1` 脱敏正文契约；不能把旧版 allow-only Guard 与新版 Auto 混用。具体服务器状态以总计划中注明时间的核验为准，本地整理不代表已同步部署。

已有客户端会话中的目录内模型名（DeepSeek Flash、Luna、Terra、Sol、Astra）可作为 `auto` 的输入别名，用于迁移、压缩和子任务兼容；实际模型仍由 Auto 根据任务与能力选择，传入名称不固定业务模型。对外模型列表仍以 `auto` 为主。
