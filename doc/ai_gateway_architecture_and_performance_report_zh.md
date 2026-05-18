# AI Code 工具网关架构与性能分析报告

日期：2026-05-18

范围：

- 内网 GPU/网关服务器：`192.168.64.16`
- 东京转发服务器：`8.216.44.189`
- 涉及工具：opencode、Claude Code、Codex
- 对比入口：`4000` LiteLLM 与 `4001` nginx/CPA 旁路

## 核心结论

当前公司内部实际有两个主要 API 入口：

- `4000`：LiteLLM 入口。负责 LiteLLM 自身的鉴权、模型路由、provider 适配、日志和用量统计。
- `4001`：nginx 入口，转到本机 `4002` 自研 CPA 网关。它绕开 LiteLLM 的主代理链路，但保留公司 key 鉴权和 LiteLLM 用量日志。

需要特别澄清：`4000` 和 `4001` 对于 `gpt-*` 这类海外模型，最终都会走东京服务器 `8.216.44.189:8317`。所以它们的区别不是“一个走本地、一个走海外”，而是：

```text
4000 链路：
客户端 -> 192.168.64.16:4000 LiteLLM -> 8.216.44.189:8317 CLIProxyAPI -> 海外模型/账号后端

4001 链路：
客户端 -> 192.168.64.16:4001 nginx -> 192.168.64.16:4002 cpa-gateway -> 8.216.44.189:8317 CLIProxyAPI -> 海外模型/账号后端
```

当前结论：

- 短 prompt 下，`4000` 通常更快、更稳定，尤其是 Codex `/v1/responses` 和 Claude Code `/v1/messages`。
- 大代码上下文下，`4001` 往往更有优势，或者 total latency 更稳定，尤其是 opencode 和 Codex。
- 海外模型共同瓶颈在东京 `8.216.44.189:8317` 的 `CLIProxyAPI`，特别是 `/v1/responses` 和大上下文请求。
- `4002` 不是多余的一层，它是为了在绕开 LiteLLM 主代理链路的同时，保留公司必须的鉴权、key 替换、用量日志和用户归因。

## 服务器角色

### 192.168.64.16

JumpServer 资产名：`开发GPU01-H100`

已观察到的服务：

| 端口 | 服务 | 作用 |
|---:|---|---|
| `4000` | `litellm-proxy-prod` Docker 容器 | LiteLLM 主代理入口 |
| `4001` | `cpa-proxy` nginx Docker 容器 | CPA 旁路的用户入口 |
| `4002` | `/data/cpa-gateway/gateway.py` Python 进程 | 公司鉴权、key 替换、日志写入、转发东京 CPA |
| `8000` | `vllm-qwen3.6-35b` Docker 容器 | 本地 vLLM 模型 `qy-coder:latest` |
| `5432` | `litellm-postgres-prod` Docker 容器 | LiteLLM 数据库 |
| `3000` | Grafana | LiteLLM 可观测性 |
| `9090` | Prometheus | 指标采集 |

重要容器：

| 容器 | 镜像 | 说明 |
|---|---|---|
| `litellm-proxy-prod` | `litellm/litellm:v1.84.0` | 暴露 `4000`；Docker health 显示 unhealthy 是因为 healthcheck 调用了容器内不存在的 `curl`，不是 API 不可用 |
| `cpa-proxy` | `nginx:alpine` | 暴露 `4001`；nginx 配置对流式响应是友好的 |
| `litellm-postgres-prod` | `postgres:16` | LiteLLM DB |
| `vllm-qwen3.6-35b` | `vllm/vllm-openai:v0.19.0` | 暴露 `8000`，本地模型服务 |

### 8.216.44.189

阿里云东京服务器。

已观察到的服务：

| 端口 | 服务 | 作用 |
|---:|---|---|
| `8317` | `cli-proxy-api` Docker 容器 | `CLIProxyAPI` 模型/账号代理 |
| `8085` | `cli-proxy-api` Docker 容器 | 管理端口 |

重要信息：

- 容器：`cli-proxy-api`
- 镜像：`eceasy/cli-proxy-api:latest`
- 版本：`CLIProxyAPI v7.0.4`
- 配置文件来源：`/opt/CLIProxyAPI/config.pool.yaml`
- 账号文件目录：`/opt/CLIProxyAPI/auths`
- 日志目录：`/opt/CLIProxyAPI/logs`
- 容器挂载：
  - `/opt/CLIProxyAPI/config.pool.yaml` -> `/CLIProxyAPI/config.yaml`
  - `/opt/CLIProxyAPI/auths` -> `/root/.cli-proxy-api`
  - `/opt/CLIProxyAPI/logs` -> `/CLIProxyAPI/logs`

## 当前架构

### 4000 LiteLLM 链路

```text
opencode / Claude Code / Codex
  -> http://192.168.64.16:4000/v1
  -> litellm-proxy-prod
  -> LiteLLM 鉴权、模型路由、回调、用量日志
  -> 对于海外 gpt-* 模型：转到东京 8.216.44.189:8317
  -> 海外模型/账号后端
```

LiteLLM 容器内的 `/app/config/config.yaml` 只包含全局设置。模型路由配置在 LiteLLM Postgres 数据库 `LiteLLM_ProxyModelTable` 中，`litellm_params` 是加密字段，所以不能直接从静态文件看到明文 `api_base`。

LiteLLM 全局设置：

```yaml
request_timeout: 600
num_retries: 1
drop_params: true
use_chat_completions_url_for_anthropic_messages: false
route_all_chat_openai_to_responses: false
```

### 4001 nginx + CPA 旁路链路

```text
opencode / Claude Code / Codex
  -> http://192.168.64.16:4001/v1
  -> cpa-proxy nginx
  -> http://172.17.0.1:4002
  -> /data/cpa-gateway/gateway.py
  -> 公司 key 校验和缓存
  -> 将公司 key 替换成东京 CPA 上游 key
  -> http://8.216.44.189:8317
  -> 海外模型/账号后端
  -> 解析响应 usage
  -> 写入 LiteLLM Postgres spend logs
```

`4001` nginx 指向 `172.17.0.1:4002`：

```nginx
upstream cpa_upstream {
    server 172.17.0.1:4002;
    keepalive 64;
}

server {
    listen 4001;
    client_max_body_size 200m;

    location / {
        proxy_pass http://cpa_upstream;
        proxy_http_version 1.1;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-API-Key $http_x_api_key;
        proxy_set_header anthropic-version $http_anthropic_version;
        proxy_set_header anthropic-beta $http_anthropic_beta;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        send_timeout 3600s;
    }
}
```

nginx 本身不是主要瓶颈。它已经关闭 request/response buffering，对 SSE/流式响应是友好的。

## 为什么需要 4002

如果只有：

```text
4001 nginx -> 8.216.44.189:8317
```

确实更薄、更快，但无法满足两个硬要求：

```text
1. 使用公司自己的 LiteLLM key 做鉴权
2. 写入 LiteLLM 日志和用量记录
```

`4002` 的职责是：

- 校验公司 LiteLLM virtual key。
- 查询 LiteLLM 用户、team、key 信息。
- 将公司 key 替换为东京 CPA 上游 key。
- 兼容 OpenAI Chat Completions、OpenAI Responses、Anthropic Messages 三种接口。
- 解析 JSON 和 SSE 响应中的 usage/token 信息。
- 写入 LiteLLM spend logs。
- 记录 TTFT 和请求耗时。

所以 `4002` 是一个轻量业务网关/审计桥，不是单纯的反向代理。

## 4002 cpa-gateway 实现

文件：

```text
/data/cpa-gateway/gateway.py
```

优化前，每个请求都会：

- 调 LiteLLM `/v1/models` 做 key 校验。
- 执行 `docker exec litellm-postgres-prod psql ...` 查询 LiteLLM DB。
- 新建一个到东京的 `http.client.HTTPConnection`。
- 使用 `ThreadingHTTPServer` 默认 backlog 5。
- 响应结束后写 spend logs。

这些会造成固定开销和并发排队。

已做优化：

- 增加公司 key 鉴权缓存。
- 增加 `/v1/models` 响应缓存。
- 将 listen backlog 从 `5` 提高到 `512`。
- 将上游连接改为全局 `httpx.Client` 连接池。
- 增加上游首包耗时日志。

当前关键默认值：

```text
AUTH_CACHE_TTL=300s
AUTH_CACHE_MAX=4096
MODELS_CACHE_TTL=30s
REQUEST_QUEUE_SIZE=512
httpx max_keepalive_connections=128
httpx max_connections=256
```

优化后，`4001/4002` 的 `/v1/models` 在缓存命中后已经是亚毫秒级。

## 东京服务器 CLIProxyAPI 配置

配置文件：

```text
/opt/CLIProxyAPI/config.pool.yaml
```

已调整后的关键配置：

```yaml
request-retry: 1
max-retry-credentials: 1
max-retry-interval: 3

routing:
  strategy: "round-robin"
  session-affinity: true
  session-affinity-ttl: "10m"
```

调整前：

```yaml
request-retry: 3
max-retry-credentials: 3
max-retry-interval: 15
routing:
  session-affinity-ttl: "6h"
```

调整原因：

- 原重试策略可能把一次账号不可用或上游波动放大成 30-60 秒长尾。
- 原 session affinity 会把用户粘到某个账号长达 6 小时。
- 新策略减少重试放大效应，并缩短账号粘性时间。

东京当前账号池包含 5 个 Codex auth 文件，位于：

```text
/opt/CLIProxyAPI/auths
```

## 性能测试结果

### 当前本机到服务器的大 prompt 对比

测试入口：

```text
4000 = http://192.168.64.16:4000/v1
4001 = http://192.168.64.16:4001/v1
```

模型：`gpt-5.5`

prompt 规模：

| 类型 | 字符数 | 说明 |
|---|---:|---|
| small | 7 | 极短请求 |
| medium | 8,619 | 中等代码上下文 |
| large | 148,792 | 大代码上下文 |

工具和协议：

| 工具 | Endpoint |
|---|---|
| opencode | `/v1/chat/completions` |
| Codex | `/v1/responses` |
| Claude Code | `/v1/messages` |

### Small Prompt

| 工具 | 4000 TTFT median | 4001 TTFT median | 4000 total median | 4001 total median | 结论 |
|---|---:|---:|---:|---:|---|
| opencode | `1.99s` | `1.90s` | `2.12s` | `2.00s` | 接近，`4001` 略快 |
| Codex | `1.03s` | `2.35s` | `2.25s` | `2.43s` | `4000` 更快 |
| Claude Code | `1.18s` | `5.10s` | `1.84s` | `5.18s` | `4000` 明显更快 |

短 prompt 结论：

- `4000` 更适合短请求。
- `4001` 在 opencode chat 上接近，但 Codex 和 Claude Code 短请求较慢。

### Medium Prompt

| 工具 | 4000 TTFT median | 4001 TTFT median | 4000 total median | 4001 total median | 结论 |
|---|---:|---:|---:|---:|---|
| opencode | `2.58s` | `7.42s` | `2.80s` | `7.51s` | `4000` 更快 |
| Codex | `1.89s` | `4.16s` | `5.17s` | `4.17s` | 首包 `4000` 快，total `4001` 好 |
| Claude Code | `1.69s` | `3.24s` | `4.00s` | `3.25s` | 首包 `4000` 快，total `4001` 好 |

中等 prompt 结论：

- `4000` 往往首包更快。
- `4001` 在 Codex/Claude 的 total latency 上可能更好。

### Large Prompt

| 工具 | 4000 TTFT median | 4001 TTFT median | 4000 total median | 4001 total median | 结论 |
|---|---:|---:|---:|---:|---|
| opencode | `7.95s` | `7.58s` | `8.34s` | `7.68s` | `4001` 略好 |
| Codex | `12.09s` | `9.80s` | `13.28s` | `9.90s` | `4001` 明显更好 |
| Claude Code | `7.93s` | `8.22s` | `9.89s` | `8.32s` | total `4001` 更好 |

大 prompt 结论：

- `4001` 对真实 code 工具大上下文更有优势。

### 东京 CLIProxyAPI 历史日志统计

东京日志显示，在调整前后都存在明显长尾，尤其是 `/v1/responses`：

| Endpoint | Median | P95 | Max |
|---|---:|---:|---:|
| `/v1/responses` | `11.802s` | `37.136s` | `59.018s` |
| `/v1/chat/completions` | `6.129s` | `29.384s` | `58.936s` |
| `/v1/messages` | `1.829s` | `3.460s` | `11.734s` |

这证明最大公共瓶颈仍在东京 `CLIProxyAPI` 和海外账号/模型后端，尤其是 `/v1/responses`。

## 结果解读

### 为什么短测 4000 更快

短请求下：

- LiteLLM 的额外开销相对不明显。
- `4000` 少了 `4001 -> nginx -> 4002` 这一跳。
- LiteLLM 对小请求的 OpenAI/Anthropic 兼容处理比较快。

所以短 prompt 测试经常显示 `4000` 更快。

### 为什么真实使用 4001 感觉更快

真实 code 工具使用时：

- prompt 通常很大。
- LiteLLM 主代理链路在大请求 body、通用 provider 适配、回调、日志记录上开销更明显。
- `4001/4002` 是一条更薄的海外 CPA 旁路，同时保留公司鉴权和日志。
- 经过缓存和连接池优化后，`4002` 的固定开销已经较低。

因此，大上下文测试中 `4001` 更容易胜出，也更符合使用反馈。

### 4001 不能解决什么

`4001` 不能消除东京和海外后端的瓶颈。两条链路最终共享：

```text
8.216.44.189:8317 CLIProxyAPI -> 海外 Codex/OpenAI 后端
```

如果东京 `CLIProxyAPI` 或海外账号/模型本身慢，`4000` 和 `4001` 都会受到影响。

## 当前推荐

### 按工具和场景选择入口

| 工具 | 短 prompt | 大代码上下文 | 推荐默认策略 |
|---|---|---|---|
| opencode | `4000/4001` 接近 | `4001` 略好 | 真实代码任务可优先 `4001` |
| Codex | `4000` 更快 | `4001` 明显更好 | 大代码任务走 `4001`，短任务走 `4000` |
| Claude Code | `4000` 更快 | `4001` total 更好 | 需要结合真实 workload A/B 测试 |

实际建议：

- 不要用极短 prompt 决定默认入口。
- 公司 code-agent 场景应以大上下文测试为准。
- `4001` 作为重代码任务入口是合理的。
- `4000` 保留为稳定 fallback 和短请求入口。

### 关于 4002

建议保留 `4002`。

它是公司鉴权和审计桥，负责：

- 公司 key 鉴权。
- key 替换。
- usage 解析。
- LiteLLM spend logs。
- 用户/team 归因。

如果没有这些要求，可以直接 nginx 到东京；但只要这些要求存在，`4002` 就是必要的。

### 关于东京 CLIProxyAPI

建议继续：

- 观察降低 retry 后的效果。
- 按工具/协议拆账号池：
  - Codex `/v1/responses`
  - opencode `/v1/chat/completions`
  - Claude `/v1/messages`
- 如果仍有用户被慢账号粘住，可 A/B 测试：
  ```yaml
  session-affinity: false
  ```
- 增加 per-account latency 和 in-flight request 指标。

## 已完成的改动

### 192.168.64.16

文件：

```text
/data/cpa-gateway/gateway.py
```

备份：

- `gateway.py.bak-cache-*`
- `gateway.py.bak-httpx-*`

已应用：

- 公司 key 鉴权缓存。
- `/v1/models` 缓存。
- backlog 提高到 `512`。
- `httpx.Client` 连接池。
- 上游首包日志。

### 8.216.44.189

文件：

```text
/opt/CLIProxyAPI/config.pool.yaml
```

备份：

- `config.pool.yaml.bak-retry-*`

已应用：

```yaml
request-retry: 1
max-retry-credentials: 1
max-retry-interval: 3
session-affinity-ttl: "10m"
```

已重启：

```text
docker restart cli-proxy-api
```

## 回滚方式

### 回滚 4002

在 `192.168.64.16` 上：

```bash
cd /data/cpa-gateway
cp gateway.py.bak-cache-<timestamp> gateway.py
pkill -f '/data/cpa-gateway/gateway.py'
nohup python3 /data/cpa-gateway/gateway.py >> /data/cpa-gateway/gateway.log 2>&1 &
```

如果只想回滚 httpx 连接池改动，可使用对应的 `gateway.py.bak-httpx-*` 备份。

### 回滚东京 CLIProxyAPI 配置

在 `8.216.44.189` 上：

```bash
cd /opt/CLIProxyAPI
cp config.pool.yaml.bak-retry-<timestamp> config.pool.yaml
docker restart cli-proxy-api
```

## 最终总结

当前正确理解是：

- `4000` 和 `4001` 都会把海外 `gpt-*` 流量转到东京 `CLIProxyAPI`。
- `4000` 是 LiteLLM 完整代理链路。
- `4001` 是更轻量的自研 CPA 旁路，但通过 `4002` 保留公司鉴权和日志。
- 短 prompt 测试通常 `4000` 更好。
- 大代码上下文测试验证了 `4001` 的价值，也解释了为什么同事实际使用时感觉 `4001` 更快。
- 当前最大剩余瓶颈是东京 `CLIProxyAPI` 和海外账号/后端，尤其 `/v1/responses`。

后续默认入口选择应以真实 code 工具大上下文场景为准，而不是只看短 prompt。 
