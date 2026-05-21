import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { performance } from "node:perf_hooks";

const root = resolve(import.meta.dirname, "../..");
const API_BASE = process.env.API_BASE ?? "http://192.168.64.16:4000";
const API_KEY = (process.env.API_KEY ?? (await readFile(resolve(root, "key.txt"), "utf8"))).trim();
const MODEL = process.env.MODEL ?? "qwen3.6-flash";
const REQUESTS_PER_SCENARIO = Number(process.env.REQUESTS_PER_SCENARIO ?? 5);
const CONCURRENCY = Number(process.env.CONCURRENCY ?? 3);
const TIMEOUT_MS = Number(process.env.TIMEOUT_MS ?? 120000);
const MAX_OUTPUT_TOKENS = Number(process.env.MAX_OUTPUT_TOKENS ?? 96);
const BENCHMARK_MODE = process.env.BENCHMARK_MODE ?? "mapped";
const PROMPT_PROFILE = process.env.PROMPT_PROFILE ?? "default";
const LARGE_PROMPT_TARGETS = (process.env.LARGE_PROMPT_TARGETS ?? "110000,160000,220000")
  .split(",")
  .map((value) => Number(value.trim()));

const apiFormats = ["chat", "responses", "messages"];
const formatAgentMap = {
  chat: "opencode",
  responses: "codex",
  messages: "claude_code",
};
const basePromptSizes = {
  short: {
    label: "短",
    prompt:
      "Inspect this JavaScript function and return one concise fix suggestion as JSON: function add(a,b){return a-b}",
  },
  medium: {
    label: "中",
    prompt:
      "You are reviewing a pull request. Identify the top correctness issue and propose a patch in JSON. Context: a Node service accepts task objects with id, status, owner, updatedAt. The new code filters overdue tasks by comparing updatedAt strings directly, retries failed tasks immediately, and writes audit records after sending the response. Requirements: dates must be timezone safe, retries need exponential backoff, and audit writes must be observable.",
  },
  long: {
    label: "长",
    prompt:
      `You are acting as a coding agent on a repository. Return strict JSON with keys summary, risks, patch_plan.

Files:
- src/gateway/router.ts chooses a provider based on model prefix.
- src/gateway/retry.ts retries 429, 500, 502, 503 with fixed 1s delay.
- src/usage/billing.ts records prompt_tokens and completion_tokens.
- test/router.test.ts checks only the happy path.

Bug report:
Users report duplicate billing rows and occasional provider storms when an upstream model is rate limited. A recent patch added automatic retries around the whole request pipeline. The old code retried only the provider call. The new code also retries billing writes and does not preserve the original request id across attempts.

Constraints:
- Do not change public API shape.
- Make retries idempotent.
- Preserve observability for each provider attempt.
- Prefer a small patch.
- Include two focused tests.

Analyze the failure mode and propose the safest patch plan.`,
  },
};

function buildLargeContextPrompt(sizeKey, targetTokens) {
  const base = basePromptSizes[sizeKey].prompt;
  const header = `You are reviewing a very large repository context. The target input size for this benchmark case is about ${targetTokens} tokens. Use the synthetic repository context below as if it were pasted by an agent tool. Focus only on the final bug report and return compact JSON.\n\nOriginal task:\n${base}\n\nSynthetic repository context starts here.\n`;
  const unit = `
// FILE: packages/gateway/src/provider/provider_{N}.ts
export interface ProviderRequest_{N} {
  requestId: string;
  tenantId: string;
  model: string;
  promptTokens: number;
  completionBudget: number;
  retryAttempt: number;
  traceparent?: string;
}

export async function callProvider_{N}(request: ProviderRequest_{N}) {
  const routeKey = request.model + ":" + request.tenantId;
  const auditKey = request.requestId + ":" + request.retryAttempt;
  if (request.retryAttempt > 0) {
    await writeAttemptMetric("provider_retry", routeKey, auditKey);
  }
  return fetchProvider({
    routeKey,
    auditKey,
    body: request,
    timeoutMs: 120000,
  });
}

// TEST NOTE {N}
// The gateway must not duplicate billing rows when provider calls are retried.
// The request id must stay stable across attempts, while attempt ids must stay distinct.
// Large prompts exercise request body parsing, routing, token accounting, timeout handling, and provider backpressure.
`;
  // English/code text averages roughly 4 characters per token for this benchmark payload.
  // The service usage field is the source of truth after a run.
  const targetChars = targetTokens * 4.2;
  const parts = [header];
  let charCount = header.length;
  let i = 0;
  while (charCount < targetChars) {
    i += 1;
    const next = unit.replaceAll("{N}", String(i));
    parts.push(next);
    charCount += next.length;
  }
  parts.push(`

Synthetic repository context ends here.

Final bug report:
The gateway is used by coding agents with prompts above 100k tokens. Under high context load, requests sometimes time out, usage accounting may drift, and retries can amplify upstream pressure. Analyze the likely bottlenecks and return strict JSON with keys summary, risks, and patch_plan.
`);
  return parts.join("");
}

function makePromptSizes() {
  if (PROMPT_PROFILE !== "large") return basePromptSizes;
  const [shortTarget, mediumTarget, longTarget] = LARGE_PROMPT_TARGETS;
  return {
    short: {
      label: `短(~${Math.round(shortTarget / 1000)}k tokens)`,
      target_input_tokens: shortTarget,
      prompt: buildLargeContextPrompt("short", shortTarget),
    },
    medium: {
      label: `中(~${Math.round(mediumTarget / 1000)}k tokens)`,
      target_input_tokens: mediumTarget,
      prompt: buildLargeContextPrompt("medium", mediumTarget),
    },
    long: {
      label: `长(~${Math.round(longTarget / 1000)}k tokens)`,
      target_input_tokens: longTarget,
      prompt: buildLargeContextPrompt("long", longTarget),
    },
  };
}

const promptSizes = makePromptSizes();

if (process.env.DRY_RUN === "1") {
  console.log(
    JSON.stringify(
      {
        model: MODEL,
        benchmark_mode: BENCHMARK_MODE,
        prompt_profile: PROMPT_PROFILE,
        prompt_sizes: Object.fromEntries(
          Object.entries(promptSizes).map(([key, value]) => [
            key,
            {
              label: value.label,
              target_input_tokens: value.target_input_tokens ?? null,
              prompt_chars: value.prompt.length,
            },
          ]),
        ),
      },
      null,
      2,
    ),
  );
  process.exit(0);
}

const agentProfiles = {
  opencode: {
    label: "opencode",
    system:
      "You are opencode, a terminal coding agent. Be concise, practical, and return machine-readable JSON only.",
  },
  codex: {
    label: "codex",
    system:
      "You are Codex, a senior coding agent. Reason about repository changes and return machine-readable JSON only.",
  },
  claude_code: {
    label: "claude code",
    system:
      "You are Claude Code, an agentic coding assistant. Focus on safe edits, tests, and return machine-readable JSON only.",
  },
};

function percentile(values, p) {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[idx];
}

function avg(values) {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

function buildPayload(format, sizeKey, agentKey) {
  const system = agentProfiles[agentKey].system;
  const user = `${promptSizes[sizeKey].prompt}\n\nReturn compact JSON only.`;
  if (format === "chat") {
    return {
      url: `${API_BASE}/v1/chat/completions`,
      headers: {
        Authorization: `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      body: {
        model: MODEL,
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
        temperature: 0,
        max_tokens: MAX_OUTPUT_TOKENS,
      },
    };
  }
  if (format === "responses") {
    return {
      url: `${API_BASE}/v1/responses`,
      headers: {
        Authorization: `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      body: {
        model: MODEL,
        instructions: system,
        input: user,
        temperature: 0,
        max_output_tokens: MAX_OUTPUT_TOKENS,
      },
    };
  }
  return {
    url: `${API_BASE}/v1/messages`,
    headers: {
      "x-api-key": API_KEY,
      "anthropic-version": "2023-06-01",
      "Content-Type": "application/json",
    },
    body: {
      model: MODEL,
      system,
      messages: [{ role: "user", content: user }],
      temperature: 0,
      max_tokens: MAX_OUTPUT_TOKENS,
    },
  };
}

function getUsage(format, json) {
  if (!json?.usage) return {};
  if (format === "responses") {
    return {
      input_tokens: json.usage.input_tokens,
      output_tokens: json.usage.output_tokens,
      total_tokens: json.usage.total_tokens,
    };
  }
  return {
    input_tokens: json.usage.prompt_tokens ?? json.usage.input_tokens,
    output_tokens: json.usage.completion_tokens ?? json.usage.output_tokens,
    total_tokens: json.usage.total_tokens,
  };
}

async function oneRequest(scenario, index) {
  const payload = buildPayload(scenario.format, scenario.size, scenario.agent);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const started = performance.now();
  try {
    const res = await fetch(payload.url, {
      method: "POST",
      headers: payload.headers,
      body: JSON.stringify(payload.body),
      signal: controller.signal,
    });
    const text = await res.text();
    const latency_ms = performance.now() - started;
    let json = null;
    try {
      json = JSON.parse(text);
    } catch {
      // Keep the raw text preview below for non-JSON errors.
    }
    const ok = res.ok && !json?.error;
    return {
      ...scenario,
      index,
      ok,
      status: res.status,
      latency_ms,
      usage: getUsage(scenario.format, json),
      error: ok ? null : json?.error?.message ?? text.slice(0, 300),
    };
  } catch (error) {
    return {
      ...scenario,
      index,
      ok: false,
      status: null,
      latency_ms: performance.now() - started,
      usage: {},
      error: error?.name === "AbortError" ? `timeout after ${TIMEOUT_MS}ms` : String(error),
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function runPool(items, worker) {
  const results = [];
  let cursor = 0;
  const workers = Array.from({ length: Math.min(CONCURRENCY, items.length) }, async () => {
    while (cursor < items.length) {
      const item = items[cursor++];
      results.push(await worker(item));
    }
  });
  await Promise.all(workers);
  return results;
}

function summarizeScenario(rows) {
  const okRows = rows.filter((r) => r.ok);
  const latencies = okRows.map((r) => r.latency_ms);
  const scenario = rows[0];
  return {
    format: scenario.format,
    size: scenario.size,
    size_label: promptSizes[scenario.size].label,
    target_input_tokens: promptSizes[scenario.size].target_input_tokens ?? null,
    prompt_chars: promptSizes[scenario.size].prompt.length,
    agent: scenario.agent,
    agent_label: agentProfiles[scenario.agent].label,
    requests: rows.length,
    success: okRows.length,
    errors: rows.length - okRows.length,
    success_rate: okRows.length / rows.length,
    avg_ms: avg(latencies),
    p50_ms: percentile(latencies, 50),
    p95_ms: percentile(latencies, 95),
    min_ms: latencies.length ? Math.min(...latencies) : null,
    max_ms: latencies.length ? Math.max(...latencies) : null,
    avg_total_tokens: avg(okRows.map((r) => r.usage.total_tokens).filter(Number.isFinite)),
    error_samples: [...new Set(rows.filter((r) => !r.ok).map((r) => r.error).filter(Boolean))].slice(0, 3),
  };
}

function fmtMs(value) {
  return value == null ? "-" : String(Math.round(value));
}

function fmtPct(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function markdownReport(summary, rawPath) {
  const generatedAt = new Date().toISOString();
  const sorted = [...summary].sort((a, b) => a.p95_ms - b.p95_ms);
  const overallRows = summary.flatMap((s) => Array.from({ length: s.requests }, () => s));
  const totalRequests = summary.reduce((n, s) => n + s.requests, 0);
  const totalSuccess = summary.reduce((n, s) => n + s.success, 0);
  const best = sorted.find((s) => s.errors === 0) ?? sorted[0];
  const worst = [...summary].sort((a, b) => (b.p95_ms ?? -1) - (a.p95_ms ?? -1))[0];

  const byFormat = apiFormats.map((format) => {
    const rows = summary.filter((s) => s.format === format);
    return {
      format,
      requests: rows.reduce((n, s) => n + s.requests, 0),
      success: rows.reduce((n, s) => n + s.success, 0),
      avg_ms: avg(rows.map((s) => s.avg_ms).filter(Number.isFinite)),
      p95_ms: avg(rows.map((s) => s.p95_ms).filter(Number.isFinite)),
    };
  });

  const byAgent = Object.keys(agentProfiles).map((agent) => {
    const rows = summary.filter((s) => s.agent === agent);
    return {
      agent: agentProfiles[agent].label,
      requests: rows.reduce((n, s) => n + s.requests, 0),
      success: rows.reduce((n, s) => n + s.success, 0),
      avg_ms: avg(rows.map((s) => s.avg_ms).filter(Number.isFinite)),
      p95_ms: avg(rows.map((s) => s.p95_ms).filter(Number.isFinite)),
    };
  });

  const bySize = Object.keys(promptSizes).map((size) => {
    const rows = summary.filter((s) => s.size === size);
    return {
      size: promptSizes[size].label,
      requests: rows.reduce((n, s) => n + s.requests, 0),
      success: rows.reduce((n, s) => n + s.success, 0),
      avg_ms: avg(rows.map((s) => s.avg_ms).filter(Number.isFinite)),
      p95_ms: avg(rows.map((s) => s.p95_ms).filter(Number.isFinite)),
    };
  });

  const table = [
    "| API格式 | 输入 | 目标输入tokens | Prompt字符 | Agent | 请求 | 成功率 | 平均ms | P50ms | P95ms | 平均tokens | 错误样例 |",
    "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ...summary.map(
      (s) =>
        `| ${s.format} | ${s.size_label} | ${s.target_input_tokens ?? "-"} | ${s.prompt_chars} | ${s.agent_label} | ${s.requests} | ${fmtPct(s.success_rate)} | ${fmtMs(s.avg_ms)} | ${fmtMs(s.p50_ms)} | ${fmtMs(s.p95_ms)} | ${s.avg_total_tokens == null ? "-" : s.avg_total_tokens.toFixed(1)} | ${s.error_samples.join("; ").replaceAll("|", "\\|") || "-"} |`,
    ),
  ].join("\n");

  const compactTable = (rows, firstKey) =>
    [
      `| ${firstKey} | 请求 | 成功率 | 平均ms | 平均P95ms |`,
      "|---|---:|---:|---:|---:|",
      ...rows.map((r) => {
        const name = r[firstKey === "维度" ? "format" : firstKey === "Agent" ? "agent" : "size"];
        return `| ${name} | ${r.requests} | ${fmtPct(r.success / r.requests)} | ${fmtMs(r.avg_ms)} | ${fmtMs(r.p95_ms)} |`;
      }),
    ].join("\n");

  return `# AI API 压测报告

- 目标地址：\`${API_BASE}\`
- 模型：\`${MODEL}\`
- 生成时间：\`${generatedAt}\`
- 压测模式：\`${BENCHMARK_MODE}\`
- Prompt 档位：\`${PROMPT_PROFILE}\`
- Agent 映射：\`chat=opencode\`，\`responses=codex\`，\`messages=claude code\`
- 压测矩阵：${BENCHMARK_MODE === "full" ? "3 种 API 格式 × 3 种输入长度 × 3 种 agent 工作负载" : "3 种 API/Agent 映射 × 3 种输入长度"}
- 每场景请求数：\`${REQUESTS_PER_SCENARIO}\`，全局并发：\`${CONCURRENCY}\`，超时：\`${TIMEOUT_MS}ms\`
- 原始结果：\`${rawPath}\`

## 总览

- 总请求：${totalRequests}
- 成功：${totalSuccess}
- 总成功率：${fmtPct(totalSuccess / totalRequests)}
- 最佳稳定场景：\`${best.format} / ${best.size_label} / ${best.agent_label}\`，P95 ${fmtMs(best.p95_ms)}ms，成功率 ${fmtPct(best.success_rate)}
- 最慢场景：\`${worst.format} / ${worst.size_label} / ${worst.agent_label}\`，P95 ${fmtMs(worst.p95_ms)}ms，成功率 ${fmtPct(worst.success_rate)}

## 按 API 格式汇总

${compactTable(byFormat, "维度")}

## 按 Agent 工作负载汇总

${compactTable(byAgent, "Agent")}

## 按输入长度汇总

${compactTable(bySize, "输入")}

## 明细

${table}

## 结论

本次压测覆盖 OpenAI Chat Completions、OpenAI Responses、Anthropic Messages 三种兼容格式，并按实际 agent 工具映射统计：chat 对应 opencode，responses 对应 codex，messages 对应 claude code。结果主要反映网关在轻量并发下的端到端非流式响应延迟、成功率和 token 计量表现；它不是极限容量测试。

建议下一轮把 \`REQUESTS_PER_SCENARIO\` 提高到 20-50，并分别测试并发 5、10、20，以观察错误率和 P95/P99 是否出现拐点。生产验收时还应补充流式 TTFT、长输出、工具调用和多模型路由场景。
`;
}

const scenarios = [];
for (const format of apiFormats) {
  for (const size of Object.keys(promptSizes)) {
    if (BENCHMARK_MODE === "full") {
      for (const agent of Object.keys(agentProfiles)) {
        scenarios.push({ format, size, agent });
      }
    } else {
      scenarios.push({ format, size, agent: formatAgentMap[format] });
    }
  }
}

const allResults = [];
for (let i = 0; i < scenarios.length; i += 1) {
  const scenario = scenarios[i];
  const items = Array.from({ length: REQUESTS_PER_SCENARIO }, (_, index) => ({ scenario, index }));
  console.log(
    `[${i + 1}/${scenarios.length}] ${scenario.format}/${scenario.size}/${scenario.agent} x${REQUESTS_PER_SCENARIO}`,
  );
  const rows = await runPool(items, ({ scenario: itemScenario, index }) => oneRequest(itemScenario, index));
  allResults.push(...rows);
}

const summary = scenarios.map((scenario) =>
  summarizeScenario(
    allResults.filter((r) => r.format === scenario.format && r.size === scenario.size && r.agent === scenario.agent),
  ),
);

const outDir = resolve(root, "doc");
await mkdir(outDir, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, "-");
const rawPath = resolve(outDir, `ai_api_benchmark_raw_${stamp}.json`);
const reportPath = resolve(outDir, `ai_api_benchmark_report_${stamp}.md`);
await writeFile(
  rawPath,
  JSON.stringify(
    {
      api_base: API_BASE,
      model: MODEL,
      requests_per_scenario: REQUESTS_PER_SCENARIO,
      concurrency: CONCURRENCY,
      timeout_ms: TIMEOUT_MS,
      max_output_tokens: MAX_OUTPUT_TOKENS,
      benchmark_mode: BENCHMARK_MODE,
      prompt_profile: PROMPT_PROFILE,
      large_prompt_targets: LARGE_PROMPT_TARGETS,
      format_agent_map: formatAgentMap,
      summary,
      results: allResults,
    },
    null,
    2,
  ),
);
await writeFile(reportPath, markdownReport(summary, rawPath), "utf8");

console.log(`raw=${rawPath}`);
console.log(`report=${reportPath}`);
