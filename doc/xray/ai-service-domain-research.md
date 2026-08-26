# AI 服务域名扩展研究记录

日期：2026-08-26

目标文件：[`config/xray/ai-service-rules.json`](../../config/xray/ai-service-rules.json)

本记录只整理经过一方文档、官方源代码或公开维护规则核对的域名；运行时目标是 Xray/3x-ui 的 JSON 路由规则。

Xray 映射：`DOMAIN` → `full:`，`DOMAIN-SUFFIX` → `domain:`，`DOMAIN-KEYWORD` → `keyword:`，`DOMAIN-REGEX` → `regexp:`。原本的 IP-CIDR/IP-ASN 项不放入这条域名 WARP 规则：Xray 的 `domain` 字段不接受 ASN，且本文件用途是给 3x-ui 的 `routing.rules[]` 使用。`DOMAIN-SUFFIX,example.com` 已覆盖 `example.com` 及其子域名，因此表中会区分“当前文件已经覆盖”和“需要补充”的项目。

## 结论摘要

本次核对重点集中在：

- OpenAI/ChatGPT 的登录、WorkOS、静态资源、监控和 WebSocket 辅助域名；
- Claude Code 的 Console、MCP、插件更新、Datadog 日志和错误上报域名；
- Google Vertex AI 的 `aiplatform.googleapis.com`（当前由 `domain:googleapis.com` 覆盖）；
- Microsoft Copilot 新的 `copilot.com`、`copilot.cloud.microsoft` 和 `*.cloud.microsoft` 体系；
- Cursor 的更新下载、CursorVM 和二进制下载域名；
- Meta 的新开发者入口 `dev.meta.ai`、`ai.developer.meta.com`。

OpenAI Voice 使用的是动态 IP 段和 UDP 3478，不适合硬编码到本域名规则文件；应维护独立的 IP 规则集。Gemini CLI、xAI SDK 等的 OpenTelemetry 目标可以由用户配置，不能凭空推导固定的第三方监控域名。

## 一方文档核对结果

### OpenAI / ChatGPT / Codex

官方 ChatGPT 网络建议列出以下域名（来源：[OpenAI Network recommendations](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)）：

```text
*.ct.sendgrid.net
cdn.openaimerge.com
cdn.workos.com
android.chat.openai.com
forwarder.workos.com
humb.apple.com
images.workoscdn.com
js.stripe.com
o207216.ingest.sentry.io
prodregistryv2.org
rum.browser-intake-datadoghq.com
setup.workos.com
workos.imgix.net
```

其中下面这些在当前规则中已经通过更宽的后缀规则覆盖，不需要重复添加：

```text
*.auth.openai.com       → DOMAIN-SUFFIX,openai.com
*.chatgpt.com            → DOMAIN-SUFFIX,chatgpt.com
*.intercom.io            → DOMAIN-SUFFIX,intercom.io
*.intercomcdn.com        → DOMAIN-SUFFIX,intercomcdn.com
*.oaistatic.com          → DOMAIN-SUFFIX,oaistatic.com
*.oaiusercontent.com     → DOMAIN-SUFFIX,oaiusercontent.com
*.openai.com             → DOMAIN-SUFFIX,openai.com
*.oaistatsig.com         → DOMAIN-SUFFIX,oaistatsig.com
auth0.openai.com         → DOMAIN-SUFFIX,openai.com
chat.openai.com          → DOMAIN-SUFFIX,openai.com
desktop.chatgpt.com      → DOMAIN-SUFFIX,chatgpt.com
ios.chat.openai.com      → DOMAIN-SUFFIX,openai.com
setup.auth.openai.com    → DOMAIN-SUFFIX,openai.com
tcr9i.chat.openai.com    → DOMAIN-SUFFIX,chatgpt.com
```

官方还列出了 ChatGPT/Codex 的 WebSocket 目标 `ws.chatgpt.com` 和 Codex 在 `chatgpt.com` 上的 WebSocket 升级；当前 `DOMAIN-SUFFIX,chatgpt.com` 已覆盖它们，但 Xray 路由必须允许 TCP 443 的 WebSocket Upgrade。[OpenAI WebSocket requirements](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps#websocket-requirements-for-chatgpt-and-codex)

ChatGPT Voice 连接使用 UDP 3478，IP 范围由官方 [`chatgpt-voice.json`](https://openai.com/chatgpt-voice.json) 持续更新。不要把这类动态 IP 当成固定域名条目；若要支持语音，应单独生成/更新 IP-CIDR 规则。

### Anthropic / Claude / Claude Code

当前 Claude Code 企业网络文档要求访问以下主机（来源：[Anthropic Claude Code corporate proxy](https://code.claude.com/docs/en/corporate-proxy)）：

```text
platform.claude.com
mcp-proxy.anthropic.com
http-intake.logs.us5.datadoghq.com
browser-intake-us5-datadoghq.com
```

当前文件已经有 `DOMAIN-SUFFIX,anthropic.com`、`DOMAIN-SUFFIX,claude.ai`、`DOMAIN-SUFFIX,claude.com`、`DOMAIN-SUFFIX,claudeusercontent.com`，因此 `mcp-proxy.anthropic.com`、`downloads.claude.ai`、`bridge.claudeusercontent.com`、`*.frame.claudeusercontent.com`、`assets-proxy.anthropic.com` 等已被覆盖。

官方文档对用途的说明：

- `platform.claude.com`：Console 登录、OAuth token 交换/刷新/撤销；
- `mcp-proxy.anthropic.com`：Claude.ai 的 MCP connectors；
- `http-intake.logs.us5.datadoghq.com`：Claude Code 直接使用 Anthropic API 时的运行 telemetry；
- `browser-intake-us5-datadoghq.com`：Claude Code 的运行错误上报，受 rollout gate 和 telemetry 开关控制。

Anthropic 官方文档没有把 `claudemcpcontent.com` 列入当前 Claude Code 网络要求。该域名出现在公开维护的 [MetaCubeX anthropic.list](https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/anthropic.list) 中，建议先作为“待实测候选”，不要在没有实际日志时扩大到更多未知域名。

### Google AI / Gemini / Vertex AI

Google 官方 Vertex/Gemini 文档使用：

```text
aiplatform.googleapis.com
```

来源：[Google Gemini Enterprise Agent Platform quickstart](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/start) 和 [Agent Platform API reference](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rpc)。当前 JSON 已有 `domain:googleapis.com`，因此不再单独写一条 `domain:aiplatform.googleapis.com`。

当前文件已经包含 `generativelanguage.googleapis.com`、`cloudcode-pa.googleapis.com`、`cloudaicompanion.googleapis.com` 等 Gemini API/Code Assist 主机。Gemini CLI 的 Google OAuth 还会访问 `oauth2.googleapis.com` 和 `www.googleapis.com/oauth2/v2/userinfo`；由于当前文件已有 `DOMAIN-SUFFIX,googleapis.com`，这两者已经被覆盖，不建议重复加入。

Gemini CLI 的 OpenTelemetry 目标由 `GEMINI_TELEMETRY_OTLP_ENDPOINT` 或配置文件指定，默认可为本地 collector；官方文档没有一个固定的“Gemini telemetry 域名”。因此不要把任意 Datadog、Jaeger 或第三方 OTLP 主机泛化加入 AI 规则。[Gemini CLI telemetry](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/telemetry.md)

### Microsoft Copilot / Bing AI

Microsoft 官方网络要求明确列出 Copilot 的：

```text
copilot.cloud.microsoft
*.cloud.microsoft
*.office.com
```

来源：[Microsoft Copilot network requirements](https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-requirements)。当前 JSON 已加入 `domain:copilot.com` 和 `full:copilot.cloud.microsoft`；更宽的 `domain:cloud.microsoft` 仍然没有加入。

当前 JSON 已对应为：

```text
domain:copilot.com
full:copilot.cloud.microsoft
```

如果目标是 Microsoft 365 Copilot，而不仅是消费版 Copilot，再考虑：

```text
DOMAIN-SUFFIX,cloud.microsoft
DOMAIN-SUFFIX,office.com
```

这两个后缀会匹配大量非 AI 的 Microsoft 365 流量，应单独评估，不建议无条件并入严格的 AI-only 规则集。Microsoft 官方也说明 Copilot 依赖 WSS，必须允许 TCP 443 的 WebSocket 升级。

### Cursor

Cursor 官方企业网络文档给出了完整的通配符和细粒度主机列表（来源：[Cursor Network Configuration](https://prod.cursor.com/docs/enterprise/network-configuration)）。当前文件的 `cursor.sh`、`cursor-cdn.com`、`cursorapi.com` 后缀已经覆盖大部分 API、认证和 marketplace 子域名。

当前 JSON 保留、或由父级后缀覆盖的项目：

```text
domain:cursorvm.com
domain:cursor.com              # 已覆盖 downloads.cursor.com
full:anysphere-binaries.s3.us-east-1.amazonaws.com
```

官方用途：

- `*.cursorvm.com` / `*.*.cursorvm.com`：Cursor 后端/Cloud Agent 相关服务；
- `downloads.cursor.com`：客户端更新下载；
- `anysphere-binaries.s3.us-east-1.amazonaws.com`：客户端更新和 extension marketplace 下载。

以下官方细粒度主机虽在当前文件中通过 `DOMAIN-SUFFIX,cursor.sh` 已覆盖，但可用于故障排查：

```text
api2.cursor.sh             api3.cursor.sh
api4.cursor.sh             api5.cursor.sh
repo42.cursor.sh           us-asia.gcpp.cursor.sh
us-eu.gcpp.cursor.sh       us-only.gcpp.cursor.sh
agent.api5.cursor.sh       agentn.api5.cursor.sh
agent.us.api5.cursor.sh    agentn.us.api5.cursor.sh
agent.global.api5.cursor.sh
agentn.global.api5.cursor.sh
adminportal42.cursor.sh    authenticate.cursor.sh
authenticator.cursor.sh    prod.authentication.cursor.sh
authentication.cursor.sh
```

Cursor 官方强调其 AI/Agent 使用 HTTP/2 双向流或 HTTP/1.1 SSE；分流规则本身不能解决代理缓冲问题，需要保留长连接和流式响应。

### xAI / Grok

官方 xAI 文档使用 `https://api.x.ai`、WebSocket `wss://api.x.ai/v1/realtime`，企业 mTLS 使用 `https://mtls.api.x.ai`，团队管理 API 使用 `https://management-api.x.ai`，控制台为 `console.x.ai`。[xAI Inference API](https://docs.x.ai/developers/rest-api-reference/inference)、[xAI mTLS](https://docs.x.ai/developers/advanced-api-usage/mtls)、[xAI Management API](https://docs.x.ai/developers/rest-api-reference/management)

当前的 `DOMAIN-SUFFIX,x.ai` 已覆盖上述所有主机；因此没有需要新增的 xAI 域名。实时语音/响应同样是 `api.x.ai` 下的 WebSocket，重点是允许 TCP 443 的 Upgrade，而不是另造域名。

### Perplexity

Perplexity 官方 SDK/API 使用 `https://api.perplexity.ai`（包括 `/v1/agent`、`/v1/models`、Search 和 Sonar），当前 `DOMAIN-SUFFIX,perplexity.ai` 已覆盖。[Perplexity Search API](https://docs.perplexity.ai/api-reference/search-post)、[Perplexity Agent API](https://docs.perplexity.ai/docs/agent-api/quickstart)

当前文件中的 `perplexity.ai`、`perplexity.com`、`pplx.ai`、S3 上传和 Cloudinary 资源已经覆盖公开规则中的主要项目，没有足够一方证据再添加未知 CDN/埋点主机。

### Meta AI / Llama

Meta 官方页面确认 Meta AI Web 入口是 `meta.ai`；Llama 官方入口是 `llama.com`。当前文件已经覆盖这两个后缀。Meta 2026 年官方 Muse Code/Muse Spark 公告还使用：

```text
dev.meta.ai
```

用于安装 Muse Code，来源：[Meta AI Research: Introducing Muse Code and Muse Spark](https://research.meta.ai/blog/introducing-muse-code-and-muse-spark-1-2)。当前 `domain:meta.ai` 已覆盖 `dev.meta.ai`，无需重复写一条规则。

Meta 的开发者 API 文档入口当前位于：

```text
ai.developer.meta.com
```

来源：[Meta AI Developer API reference](https://ai.developer.meta.com/docs/api-reference/messages/)。这是 Meta API 的新增开发者域名，建议作为独立候选加入；不要把 MetaCubeX `meta.list` 中几百个 Facebook/Instagram/Meta 通用域名整体搬入 AI 规则，因为会把普通社交流量一起送入 WARP。

### 创意与媒体生成平台

为覆盖网页端的图像、视频和音乐生成服务，补入官方产品域名；这类产品的上传/CDN/实时协作主机可能随版本变化，后续仍应以真实访问日志补充：

```text
midjourney.com       suno.com
runway.com            runwayml.com
lumalabs.ai           ideogram.ai
leonardo.ai           recraft.ai
pika.art
```

其中 Ideogram 官方首页同时公开了 `api.ideogram.ai` API 入口（来源：[Ideogram](https://ideogram.ai/)）。Midjourney、Suno、Runway 和 Luma 的产品入口分别见其官方站点：[Midjourney](https://www.midjourney.com/)、[Suno](https://suno.com/)、[Runway](https://runway.com/)、[Luma Dream Machine](https://lumalabs.ai/dream-machine)。

## 公开维护规则的交叉核对

MetaCubeX 的公开 geosite 列表可用于核对本机规则是否漏项，但不能替代一方文档：

| 服务 | 官方维护列表 | 交叉核对结果 |
| --- | --- | --- |
| OpenAI | [`openai.list`](https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/openai.list) | 与当前文件基本一致；OpenAI 官方网络建议额外增加 WorkOS、SendGrid、Sentry、Datadog 等辅助域名 |
| Anthropic | [`anthropic.list`](https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/anthropic.list) | 发现 `claudemcpcontent.com`，但官方 Claude Code 网络文档尚未列出，需实测后决定 |
| xAI | [`xai.list`](https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/xai.list) | 当前文件完整覆盖 |
| Perplexity | [`perplexity.list`](https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/perplexity.list) | 当前文件完整覆盖 |
| Bing/Copilot | [`bing.list`](https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/bing.list) | 发现 `copilot.com`、`copilot.cloud.microsoft`，与 Microsoft 官方新网络体系一致 |
| Cursor | [`cursor.list`](https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/cursor.list) | 当前文件主要后缀已覆盖；官方文档补充 CursorVM、下载和二进制 S3 主机 |
| Meta | [`meta.list`](https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/meta.list) | 仅保留 `meta.ai`、`llama.com`；其余为普通 Meta/Facebook 生态，不应整体并入 AI 规则 |

## 高置信候选与当前 Xray 映射

下面保留一方文档明确的候选项及其 Xray 写法；其中已被父级 `domain:` 覆盖的项目只作为审计记录，不重复写入 JSON：

```text
# OpenAI / ChatGPT
domain:ct.sendgrid.net
full:cdn.openaimerge.com
full:cdn.workos.com
full:forwarder.workos.com
full:humb.apple.com
full:images.workoscdn.com
full:js.stripe.com
full:o207216.ingest.sentry.io
full:prodregistryv2.org
full:rum.browser-intake-datadoghq.com
full:setup.workos.com
full:workos.imgix.net

# Anthropic / Claude Code
domain:claude.com              # 已覆盖 platform.claude.com
domain:anthropic.com           # 已覆盖 mcp-proxy.anthropic.com
full:http-intake.logs.us5.datadoghq.com
full:browser-intake-us5-datadoghq.com

# Google Vertex AI
domain:googleapis.com          # 已覆盖 aiplatform.googleapis.com

# Microsoft Copilot
domain:copilot.com
full:copilot.cloud.microsoft

# Cursor
domain:cursorvm.com
domain:cursor.com               # 已覆盖 downloads.cursor.com
full:anysphere-binaries.s3.us-east-1.amazonaws.com

# Meta AI / Muse Code / Meta Model API
domain:meta.ai                   # 已覆盖 dev.meta.ai
domain:ai.developer.meta.com
```

当前 Xray JSON 会优先保留已有的父级 `domain:`；如果父级已经覆盖某个官方精确主机，就不再重复写 `full:host`。例如 `api.openai.com` 由 `domain:openai.com` 覆盖，`aiplatform.googleapis.com` 由 `domain:googleapis.com` 覆盖。

## 不建议现在直接加入的项目

- `*.cloud.microsoft`、`*.office.com`、`*.googleapis.com`、`storage.googleapis.com`、`registry.npmjs.org` 等宽泛共享依赖：会把大量非 AI 流量带入 WARP；当前文件已经有部分宽泛 Google 规则，新增前应确认是否要拆成单独的“AI 依赖”规则集。
- `claudemcpcontent.com`：目前只有公开维护规则来源，没有对应的当前 Anthropic 网络文档；先在实际 Claude Desktop/Claude Code 日志中确认。
- Gemini、xAI、Cursor 的第三方 Datadog/Sentry/OTLP 端点：这些产品可能由用户或版本动态配置，不能按“常见监控服务”猜测。
- OpenAI Voice 的 IP：官方明确会持续更新，应通过独立 IP 规则自动同步，而不是复制某一次查询结果。

## 验证建议

1. 将 `config/xray/ai-service-rules.json` 中的 TCP、UDP 两条 `routing.rules[]` field rule 合并到 3x-ui，入站标签对应 `in-443-tcp` 和 `in-443-udp`，保持现有普通流量 `direct`。
2. Xray 开启 TLS/HTTP/QUIC sniffing，并确认 WebSocket Upgrade 和长连接不被代理层缓冲。
3. 在 DMIT 上分别测试 API、网页、登录、上传、流式响应和语音/实时功能；检查 Xray 访问日志是否命中 `warp`（3x-ui 内置 WARP 出站标签）。
