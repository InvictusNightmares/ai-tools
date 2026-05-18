# AI Code Tools Gateway Architecture and Performance Report

Date: 2026-05-18

Scope:

- Internal GPU/server gateway: `192.168.64.16`
- Tokyo forwarding server: `8.216.44.189`
- Tools: opencode, Claude Code, Codex
- Entrypoints compared: `4000` LiteLLM and `4001` nginx/CPA path
- Test key source: `key.txt` in this repository, not repeated in this document

## Executive Summary

The current production design has two user-facing API entrypoints on `192.168.64.16`:

- `4000`: LiteLLM proxy. It performs LiteLLM-native auth, model routing, provider adaptation, logging, and spend tracking.
- `4001`: nginx entrypoint to a custom CPA gateway on `4002`. It keeps company key auth and LiteLLM spend logging, but bypasses LiteLLM's main request path for overseas models.

Both `4000` and `4001` ultimately route `gpt-*` overseas models to the Tokyo CPA server `8.216.44.189:8317`. Therefore the correct comparison is not local-vs-overseas. The correct comparison is:

```text
4000 path:
client -> 192.168.64.16:4000 LiteLLM -> 8.216.44.189:8317 CLIProxyAPI -> overseas model/account backend

4001 path:
client -> 192.168.64.16:4001 nginx -> 192.168.64.16:4002 cpa-gateway -> 8.216.44.189:8317 CLIProxyAPI -> overseas model/account backend
```

Current conclusion:

- For short prompts, `4000` is usually faster and more reliable, especially Codex `/v1/responses` and Claude Code `/v1/messages`.
- For large code-context prompts, `4001` can be faster or more stable, especially total latency for opencode and Codex.
- The shared bottleneck for overseas models is `8.216.44.189:8317` `CLIProxyAPI`, particularly Codex/OpenAI `responses` and large code-agent requests.
- The custom `4002` gateway exists because company auth and LiteLLM spend logs are mandatory. Plain nginx forwarding to Tokyo would not satisfy those requirements.

## Server Roles

### 192.168.64.16

JumpServer asset name: `开发GPU01-H100`

Observed services:

| Port | Service | Role |
|---:|---|---|
| `4000` | `litellm-proxy-prod` Docker container | LiteLLM proxy entrypoint |
| `4001` | `cpa-proxy` nginx Docker container | User-facing nginx entrypoint for CPA bypass path |
| `4002` | `/data/cpa-gateway/gateway.py` Python process | Company auth, key swap, logging bridge to Tokyo CPA |
| `8000` | `vllm-qwen3.6-35b` Docker container | Local vLLM model endpoint for `qy-coder:latest` |
| `5432` | `litellm-postgres-prod` Docker container | LiteLLM database |
| `3000` | Grafana | LiteLLM observability |
| `9090` | Prometheus | Metrics |

Important containers:

| Container | Image | Status / Notes |
|---|---|---|
| `litellm-proxy-prod` | `litellm/litellm:v1.84.0` | Port `4000`; Docker health shows unhealthy because healthcheck calls missing `curl`, not because API is down |
| `cpa-proxy` | `nginx:alpine` | Port `4001`; nginx config is stream-friendly |
| `litellm-postgres-prod` | `postgres:16` | LiteLLM DB |
| `vllm-qwen3.6-35b` | `vllm/vllm-openai:v0.19.0` | Port `8000`; local `qy-coder:latest` |

### 8.216.44.189

Alibaba Cloud Tokyo server.

Observed services:

| Port | Service | Role |
|---:|---|---|
| `8317` | `cli-proxy-api` Docker container | `CLIProxyAPI` model/account proxy |
| `8085` | `cli-proxy-api` Docker container | Management UI/API |

Important details:

- Container: `cli-proxy-api`
- Image: `eceasy/cli-proxy-api:latest`
- Version: `CLIProxyAPI v7.0.4`
- Config source: `/opt/CLIProxyAPI/config.pool.yaml`
- Auth files: `/opt/CLIProxyAPI/auths`
- Logs: `/opt/CLIProxyAPI/logs/main.log`
- Container mounts:
  - `/opt/CLIProxyAPI/config.pool.yaml` -> `/CLIProxyAPI/config.yaml`
  - `/opt/CLIProxyAPI/auths` -> `/root/.cli-proxy-api`
  - `/opt/CLIProxyAPI/logs` -> `/CLIProxyAPI/logs`

## Architecture

### 4000 LiteLLM Path

```text
opencode / Claude Code / Codex
  -> http://192.168.64.16:4000/v1
  -> litellm-proxy-prod
  -> LiteLLM auth, model routing, callbacks, spend logs
  -> for overseas gpt-* models: Tokyo CPA at 8.216.44.189:8317
  -> overseas model/account backend
```

LiteLLM config file in the container only contains global settings. Model routing is stored in the LiteLLM Postgres DB (`LiteLLM_ProxyModelTable`) with encrypted `litellm_params`, so static file inspection does not show plaintext `api_base`.

Relevant LiteLLM settings observed:

```yaml
request_timeout: 600
num_retries: 1
drop_params: true
use_chat_completions_url_for_anthropic_messages: false
route_all_chat_openai_to_responses: false
```

### 4001 nginx + CPA Path

```text
opencode / Claude Code / Codex
  -> http://192.168.64.16:4001/v1
  -> cpa-proxy nginx
  -> http://172.17.0.1:4002
  -> /data/cpa-gateway/gateway.py
  -> company key validation and caching
  -> key replacement with Tokyo CPA upstream key
  -> http://8.216.44.189:8317
  -> overseas model/account backend
  -> response usage parsing
  -> LiteLLM spend logs in Postgres
```

`4001` nginx config points to `172.17.0.1:4002`:

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

The nginx config is not the main bottleneck. It already disables response and request buffering.

### Why 4002 Exists

`4002` exists because a direct nginx proxy to Tokyo cannot satisfy the mandatory company requirements:

- Validate company LiteLLM virtual keys.
- Map requests to LiteLLM user/team/key metadata.
- Replace company key with the Tokyo CPA upstream key.
- Preserve OpenAI-compatible, Responses, and Anthropic-compatible request formats.
- Parse token usage from JSON and SSE responses.
- Write LiteLLM spend logs and request metadata to Postgres.
- Record TTFT and request duration for reporting.

In short, `4002` is a lightweight business gateway and audit bridge. It is designed to keep mandatory auth/logging while bypassing part of LiteLLM's full proxy path.

## 4002 Gateway Implementation

File:

```text
/data/cpa-gateway/gateway.py
```

Before optimization, it did this on every request:

- Call LiteLLM `/v1/models` for key validation.
- Execute `docker exec litellm-postgres-prod psql ...` to query LiteLLM DB.
- Create a new `http.client.HTTPConnection` to Tokyo.
- Use `ThreadingHTTPServer` default backlog of 5.
- Write spend logs after the response.

This caused avoidable fixed overhead and queueing under concurrency.

Optimizations applied:

- Added company key auth cache.
- Added `/v1/models` response cache.
- Increased server listen backlog from `5` to `512`.
- Switched upstream connection to global `httpx.Client` with connection pooling.
- Added upstream first-byte timing logs.

Current notable settings:

```text
AUTH_CACHE_TTL=300s default
AUTH_CACHE_MAX=4096 default
MODELS_CACHE_TTL=30s default
REQUEST_QUEUE_SIZE=512 default
httpx max_keepalive_connections=128
httpx max_connections=256
```

After optimization, `/v1/models` on `4001/4002` becomes sub-millisecond after cache warm-up.

## Tokyo CLIProxyAPI Configuration

File:

```text
/opt/CLIProxyAPI/config.pool.yaml
```

Important current values after tuning:

```yaml
request-retry: 1
max-retry-credentials: 1
max-retry-interval: 3

routing:
  strategy: "round-robin"
  session-affinity: true
  session-affinity-ttl: "10m"
```

Before tuning:

```yaml
request-retry: 3
max-retry-credentials: 3
max-retry-interval: 15
routing:
  session-affinity-ttl: "6h"
```

Reason for changing:

- Old retry policy could amplify a single slow/unavailable account into 30-60 second request latency.
- Old session affinity could pin users to slow accounts for 6 hours.
- New policy reduces retry amplification and shortens account stickiness.

Auth pool currently includes five Codex auth files under `/opt/CLIProxyAPI/auths`.

## Performance Test Results

### Initial Short Prompt Results

With very short prompts, `4000` usually looked faster, especially for Codex and Claude Code. This initially made `4001` appear worse.

However, short prompts are not representative of code tools, because real opencode/Codex/Claude Code requests often carry large repository context.

### Current Local Large Prompt Comparison

Test from local machine to `192.168.64.16` after all optimizations.

Entrypoints:

```text
4000 = http://192.168.64.16:4000/v1
4001 = http://192.168.64.16:4001/v1
```

Model: `gpt-5.5`

Prompt sizes:

| Prompt | Size | Purpose |
|---|---:|---|
| small | 7 chars | Minimal ping |
| medium | 8,619 chars | Medium code context |
| large | 148,792 chars | Large code context |

Tool/protocol mapping:

| Tool | Endpoint |
|---|---|
| opencode | `/v1/chat/completions` |
| Codex | `/v1/responses` |
| Claude Code | `/v1/messages` |

#### Small Prompt

| Tool | 4000 TTFT median | 4001 TTFT median | 4000 total median | 4001 total median | Faster |
|---|---:|---:|---:|---:|---|
| opencode | `1.99s` | `1.90s` | `2.12s` | `2.00s` | close, `4001` slight |
| Codex | `1.03s` | `2.35s` | `2.25s` | `2.43s` | `4000` |
| Claude Code | `1.18s` | `5.10s` | `1.84s` | `5.18s` | `4000` |

Short prompt conclusion:

- `4000` is generally better for small requests.
- `4001` is close for opencode chat but worse for Codex and Claude Code.

#### Medium Prompt

| Tool | 4000 TTFT median | 4001 TTFT median | 4000 total median | 4001 total median | Result |
|---|---:|---:|---:|---:|---|
| opencode | `2.58s` | `7.42s` | `2.80s` | `7.51s` | `4000` |
| Codex | `1.89s` | `4.16s` | `5.17s` | `4.17s` | mixed; `4001` total better |
| Claude Code | `1.69s` | `3.24s` | `4.00s` | `3.25s` | mixed; `4001` total better |

Medium prompt conclusion:

- `4000` often has faster first byte.
- `4001` can have better total latency for Codex and Claude Code.

#### Large Prompt

| Tool | 4000 TTFT median | 4001 TTFT median | 4000 total median | 4001 total median | Result |
|---|---:|---:|---:|---:|---|
| opencode | `7.95s` | `7.58s` | `8.34s` | `7.68s` | `4001` slight |
| Codex | `12.09s` | `9.80s` | `13.28s` | `9.90s` | `4001` clear |
| Claude Code | `7.93s` | `8.22s` | `9.89s` | `8.32s` | `4001` total better |

Large prompt conclusion:

- `4001` is better or more stable for large code-context workloads.
- This matches user reports that `4001` feels better in real code-tool usage.

### Current Short Prompt Post-Tuning Comparison

From `192.168.64.16` server-side short prompt test after optimizations:

| Tool | Protocol | Better entrypoint |
|---|---|---|
| opencode | `/v1/chat/completions` | close; `4001` is more stable in max latency in some runs |
| Codex | `/v1/responses` | `4000` for short prompts |
| Claude Code | `/v1/messages` | `4000` for short prompts |

### Tokyo CLIProxyAPI Historical Log Stats

Before/around tuning, Tokyo logs showed substantial long tails:

| Endpoint | Median | P95 | Max |
|---|---:|---:|---:|
| `/v1/responses` | `11.802s` | `37.136s` | `59.018s` |
| `/v1/chat/completions` | `6.129s` | `29.384s` | `58.936s` |
| `/v1/messages` | `1.829s` | `3.460s` | `11.734s` |

This proves the biggest shared bottleneck is Tokyo `CLIProxyAPI` and the overseas account/backend layer, especially `/v1/responses`.

## Interpretation

### Why Short Tests Favored 4000

For small requests:

- LiteLLM overhead is relatively small.
- `4000` avoids the extra `4001 -> nginx -> 4002` hop.
- LiteLLM may handle small OpenAI/Anthropic-compatible requests efficiently.

Therefore short prompt tests often show `4000` as faster.

### Why Real Users May Prefer 4001

For real code-agent usage:

- Prompts can be tens of KB to hundreds of KB.
- LiteLLM's full proxy path has more generic routing/provider/callback/logging overhead.
- `4001/4002` is a thinner path for overseas CPA while still keeping company auth and spend logs.
- After caching and connection pooling, `4002` fixed overhead is low.

Therefore large prompt tests show `4001` can be faster or more stable, matching user reports.

### What 4001 Does Not Solve

`4001` does not remove the Tokyo/overseas bottleneck. Both paths still share:

```text
8.216.44.189:8317 CLIProxyAPI -> overseas Codex/OpenAI backend
```

If Tokyo `CLIProxyAPI` or overseas accounts are slow, both `4000` and `4001` can be slow.

## Current Recommendations

### Tool Routing

| Tool | Short prompt | Large code-context prompt | Recommended default |
|---|---|---|---|
| opencode | `4000` or `4001` close | `4001` slight advantage | `4001` if users do real code work |
| Codex | `4000` | `4001` clear advantage in large prompt test | Use `4001` for large code tasks; `4000` for small/quick tasks |
| Claude Code | `4000` | `4001` total latency advantage | Mixed; test with real Claude workloads |

Practical recommendation:

- Do not use one benchmark with tiny prompt to decide the default.
- For company code-agent usage, benchmark with large repo-context prompts.
- It is reasonable to keep `4001` as the preferred entrypoint for heavy coding workloads.
- Keep `4000` as stable fallback and for smaller requests.

### 4002 Gateway

Keep `4002`. It is required for:

- Company key validation.
- Usage/spend logging.
- User/team attribution.
- Key replacement before calling Tokyo CPA.

Do not replace it with plain nginx unless company auth/logging requirements are removed.

### Tokyo CLIProxyAPI

Recommended follow-ups:

- Continue observing with the reduced retry settings.
- Consider splitting account pools by protocol/tool:
  - Codex `/v1/responses`
  - opencode `/v1/chat/completions`
  - Claude `/v1/messages`
- Consider A/B testing `session-affinity: false` if users still get stuck on slow accounts.
- Add per-account latency and in-flight request metrics if `CLIProxyAPI` supports it.

## Changes Already Applied

### On 192.168.64.16

File:

```text
/data/cpa-gateway/gateway.py
```

Backups created:

- `gateway.py.bak-cache-*`
- `gateway.py.bak-httpx-*`

Applied changes:

- Auth cache.
- `/v1/models` cache.
- Backlog increased to `512`.
- `httpx.Client` upstream connection pooling.
- Upstream first-byte logging.

### On 8.216.44.189

File:

```text
/opt/CLIProxyAPI/config.pool.yaml
```

Backup created:

- `config.pool.yaml.bak-retry-*`

Applied changes:

```yaml
request-retry: 1
max-retry-credentials: 1
max-retry-interval: 3
session-affinity-ttl: "10m"
```

Container restarted:

```text
docker restart cli-proxy-api
```

## Rollback

### Roll Back 4002 Gateway

On `192.168.64.16`:

```bash
cd /data/cpa-gateway
cp gateway.py.bak-cache-<timestamp> gateway.py
pkill -f '/data/cpa-gateway/gateway.py'
nohup python3 /data/cpa-gateway/gateway.py >> /data/cpa-gateway/gateway.log 2>&1 &
```

Use the relevant backup timestamp depending on whether you want to roll back only the httpx change or all cache/backlog changes.

### Roll Back Tokyo CLIProxyAPI Settings

On `8.216.44.189`:

```bash
cd /opt/CLIProxyAPI
cp config.pool.yaml.bak-retry-<timestamp> config.pool.yaml
docker restart cli-proxy-api
```

## Final Summary

The correct conclusion is nuanced:

- `4000` and `4001` both route overseas `gpt-*` traffic to Tokyo `CLIProxyAPI`.
- `4000` is LiteLLM's full proxy path.
- `4001` is a lighter custom CPA path that still preserves company auth and logging via `4002`.
- Tiny prompt benchmarks favor `4000`.
- Large code-context benchmarks favor or validate `4001`, which matches user reports.
- The remaining hard bottleneck is Tokyo `CLIProxyAPI` and overseas account/backend latency, especially `/v1/responses`.

For real code tools, use large-context benchmark results when deciding defaults.
