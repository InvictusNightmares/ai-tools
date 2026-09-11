#!/usr/bin/env python3
"""Comprehensive low-to-high model switching experiment.

This is a read-only experiment against the user-provided gateway. It reads the
API key from key.yaml, never prints it, and writes only sanitized JSON stats.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


MODELS = [
    "deepseek-flash",
    "gpt-5.6-luna",
    "gpt-5.6-terra",
    "gpt-5.6-sol",
    "gpt-6-astra",
]

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "gateway_architecture",
        "title": "智能网关架构重构",
        "context": """
你正在审查一个现有 Go 网关。目标是增加只暴露 auto 的智能路由层，同时保留
Responses、Chat Completions、Anthropic Messages、SSE、WebSocket、工具调用、
会话粘性、账号池、Redis、PostgreSQL 用量记录和失败切换。东京和美西是两个
独立区域，不能混用账号池。候选模型按低到高为 Flash、Luna、Terra、Sol、Astra。
硬约束：不能把 API Key 或 prompt 写入日志；流式响应中途不能换模型；模型切换
后需要隔离上游 prompt cache；Redis 路由状态故障时必须可解释降级。请把答案
当作真实生产设计评审，指出不成立的假设。
""",
        "turns": [
            "先提取目标、约束、关键风险和必须验证的事实，给出结构化清单。",
            "基于刚才的清单，提出可实施的路由状态机和缓存命名空间设计，并列出回滚点。",
            "审查该状态机在多次 Flash→Luna→Terra→Sol→Astra 升级、工具循环、WebSocket 断线时的边界行为。",
            "给出一份按阶段可独立发布的测试矩阵，覆盖质量、延迟、缓存、配额和故障。",
        ],
    },
    {
        "id": "production_debug",
        "title": "生产请求链路故障诊断",
        "context": """
线上出现以下现象：东京区域长上下文请求首 token 偶发超过 20 秒；同一会话先由
Flash 处理简单问答，随后升级到 Terra 和 Astra，用户反馈升级后上下文偶尔丢失。
部分响应的 usage 只有 prompt_tokens，没有 cached_tokens；另一些响应有
prompt_tokens_details.cached_tokens。Redis 路由记录显示 session TTL 为 1 小时，
但同一 API key 在不同协议入口产生了不同 session_hash。Nginx、Sub2API、上游
账号池和供应商缓存都可能是原因。不能重置计数器、不能泄露凭证、不能直接重启
生产服务。请按证据优先的方式诊断并设计低风险验证。
""",
        "turns": [
            "先建立分层假设树，区分路由、协议转换、上游排队、缓存和网络问题。",
            "设计一组不改配置的观测和对照实验，说明每个结果如何排除或支持假设。",
            "根据现有证据，给出多模型切换时保留会话连续性的具体数据结构和日志字段。",
            "写出故障升级、回滚和验收标准，特别说明何时必须停止自动升级。",
        ],
    },
    {
        "id": "agent_workflow",
        "title": "多步代码代理任务规划",
        "context": """
你要为一个大型 TypeScript monorepo 设计一次跨包迁移：把旧的 HTTP client
替换成统一 transport，保留重试、超时、流式 backpressure、工具调用、幂等键、
审计字段和向后兼容。仓库有 80 个包、约 2,000 个测试，部分包运行在 Node 20，
部分包运行在边缘 runtime。迁移必须支持分批合并和随时回滚，不能一次性改完。
用户希望模型在任务变复杂时逐级升级，但同一工作阶段不能因为分类抖动而降档；
每次升级都要保留可验证的中间产物。
""",
        "turns": [
            "提取迁移不变量、依赖图、风险最高的接口和第一批可验证切片。",
            "设计分阶段迁移方案，给出每阶段的输入、输出、测试和回滚条件。",
            "模拟一次迁移中出现流式 backpressure 回归，给出定位顺序和最小修复面。",
            "做最终 adversarial review：找出会导致数据丢失、重复请求或无法回滚的漏洞。",
        ],
    },
]


def request(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    turn_id: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 700,
        "stream": False,
    }
    req = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(req, timeout=180) as response:
            body = json.load(response)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        usage = body.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        hit = usage.get(
            "prompt_cache_hit_tokens",
            usage.get("cached_tokens", details.get("cached_tokens")),
        )
        miss = usage.get("prompt_cache_miss_tokens")
        if miss is None and hit is not None and usage.get("prompt_tokens") is not None:
            miss = usage["prompt_tokens"] - hit
        choices = body.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        content = message.get("content") or ""
        return {
            "turn_id": turn_id,
            "requested_model": model,
            "returned_model": body.get("model"),
            "elapsed_ms": elapsed_ms,
            "prompt_tokens": usage.get("prompt_tokens"),
            "cache_hit_tokens": hit,
            "cache_miss_tokens": miss,
            "completion_tokens": usage.get("completion_tokens"),
            "finish_reason": choices[0].get("finish_reason") if choices else None,
            "response_chars": len(content),
            "response_excerpt": re.sub(r"\s+", " ", content)[:240],
            "usage_keys": sorted(usage.keys()),
            "prompt_details_keys": sorted(details.keys()),
            "status": "ok",
            "content": content,
        }
    except HTTPError as error:
        detail = error.read(512).decode("utf-8", "replace")
        return {"turn_id": turn_id, "requested_model": model, "status": f"http_{error.code}", "detail": detail[:160]}
    except (URLError, TimeoutError) as error:
        return {"turn_id": turn_id, "requested_model": model, "status": type(error).__name__}


def run_scenario(base_url: str, api_key: str, scenario: dict[str, Any]) -> dict[str, Any]:
    system = (
        "你是一个严谨的工程协作模型。不要声称执行了没有执行的命令；"
        "对未知事实明确标记 unknown；优先给出可验证的中间产物。\n\n"
        + scenario["context"].strip()
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    results: list[dict[str, Any]] = []
    for model in MODELS:
        for local_turn in range(2):
            task_index = len(results) % len(scenario["turns"])
            user_prompt = (
                f"当前路由阶段模型是 {model}。这是该阶段第 {local_turn + 1} 轮。"
                f"此前阶段的回答属于上下文，不要丢失其中已经确认的约束。\n"
                f"本轮目标：{scenario['turns'][task_index]}"
            )
            messages.append({"role": "user", "content": user_prompt})
            turn_id = f"{scenario['id']}:stage-{model}:turn-{local_turn + 1}"
            print(f"[probe] {turn_id}", file=sys.stderr, flush=True)
            result = request(base_url, api_key, model, messages, turn_id)
            full_content = result.get("content", "")
            result.pop("content", None)
            results.append(result)
            if result.get("status") == "ok":
                # Keep the assistant response in the next request's history.
                messages.append({"role": "assistant", "content": full_content})
            else:
                messages.append({"role": "assistant", "content": "[previous stage failed; continue with known facts]"})
    return {"scenario": scenario["id"], "title": scenario["title"], "results": results}


def summarize(report: dict[str, Any]) -> None:
    for scenario in report["scenarios"]:
        rows = [row for row in scenario["results"] if row.get("status") == "ok"]
        hits = [row for row in rows if row.get("cache_hit_tokens") is not None]
        switches = sum(
            1
            for prev, cur in zip(rows, rows[1:])
            if prev.get("requested_model") != cur.get("requested_model")
        )
        print(
            scenario["scenario"],
            "ok=", len(rows),
            "switches=", switches,
            "cache_observed=", len(hits),
            "avg_ms=", round(sum(row["elapsed_ms"] for row in rows) / len(rows)) if rows else None,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://106.14.254.110:9880/v1")
    parser.add_argument("--key-file", default="key.yaml")
    parser.add_argument("--output", default="script/gateway/auto-routing-cache-experiment/comprehensive-switch-result.json")
    args = parser.parse_args()

    api_key = yaml.safe_load(Path(args.key_file).read_text())["key"]
    started = time.time()
    report = {
        "base_url": args.base_url,
        "models": MODELS,
        "started_at_epoch": started,
        "scenarios": [run_scenario(args.base_url, api_key, scenario) for scenario in SCENARIOS],
        "finished_at_epoch": time.time(),
    }
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    summarize(report)
    print("result_file=", args.output)


if __name__ == "__main__":
    main()
