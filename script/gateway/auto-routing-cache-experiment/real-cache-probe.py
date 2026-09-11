#!/usr/bin/env python3
"""Read-only cache probe for the user-provided Sub2API gateway.

The API key is read from key.yaml and is never printed or written to output.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


def call(base_url: str, api_key: str, model: str, turn: int, prefix: str) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prefix},
            {
                "role": "user",
                "content": f"Cache probe turn {turn}: reply with the turn number only.",
            },
        ],
        "temperature": 0,
        "max_tokens": 32,
        "stream": False,
    }
    request = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=90) as response:
            payload = json.load(response)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        usage = payload.get("usage") or {}
        prompt_details = usage.get("prompt_tokens_details") or {}
        cache_hit_tokens = usage.get("prompt_cache_hit_tokens", usage.get("cached_tokens", prompt_details.get("cached_tokens")))
        cache_miss_tokens = usage.get("prompt_cache_miss_tokens")
        if cache_miss_tokens is None and cache_hit_tokens is not None and usage.get("prompt_tokens") is not None:
            cache_miss_tokens = usage["prompt_tokens"] - cache_hit_tokens
        return {
            "model_requested": model,
            "model_returned": payload.get("model"),
            "turn": turn,
            "elapsed_ms": elapsed_ms,
            "prompt_tokens": usage.get("prompt_tokens"),
            "cache_hit_tokens": cache_hit_tokens,
            "cache_miss_tokens": cache_miss_tokens,
            "usage_keys": sorted(usage.keys()),
            "prompt_details_keys": sorted(prompt_details.keys()),
            "completion_tokens": usage.get("completion_tokens"),
            "status": "ok",
        }
    except HTTPError as error:
        # Keep error output non-sensitive and bounded.
        detail = error.read(512).decode("utf-8", "replace")
        return {"model_requested": model, "turn": turn, "status": f"http_{error.code}", "detail": detail[:160]}
    except (URLError, TimeoutError) as error:
        return {"model_requested": model, "turn": turn, "status": type(error).__name__}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://106.14.254.110:9880/v1")
    parser.add_argument("--key-file", default="key.yaml")
    parser.add_argument("--prefix-tokens", type=int, default=1800)
    parser.add_argument("--run-id", default=str(time.time_ns()))
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.key_file).read_text())
    api_key = config["key"]
    prefix = f"Stable cache prefix for run {args.run_id}. " * args.prefix_tokens

    # Same model twice, switch to another model, then switch back. This makes
    # cache continuity and the cost of a model switch visible in one run.
    sequence = [
        ("deepseek-flash", 1),
        ("deepseek-flash", 2),
        ("gpt-5.6-terra", 1),
        ("gpt-5.6-terra", 2),
        ("deepseek-flash", 3),
        ("deepseek-flash", 4),
    ]
    results = [call(args.base_url, api_key, model, turn, prefix) for model, turn in sequence]
    print(json.dumps({"base_url": args.base_url, "prefix_repetitions": args.prefix_tokens, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
