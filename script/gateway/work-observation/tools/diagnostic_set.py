#!/usr/bin/env python3
"""Build a deterministic, body-free diagnostic sample manifest.

The manifest is an index of already captured ``http_exchange`` records.  It
contains no request/response text and never calls Guard, Auto, a model, or a
business endpoint.  The standalone review dashboard can use the event
references to load a verified source record only when an operator opens one
row.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

import rolling
import semantic


SCHEMA = "work-observation-diagnostic-v1"
DEFAULT_SEED = "diagnostic-200-20260922"
DEFAULT_COUNT = 200
PER_REGION = 100
BUCKET_QUOTAS = {
    "guard_block": 25,
    "normal_allow": 25,
    "technical_failure": 20,
    "request_failure": 15,
    "long_or_tools": 10,
    "protocol_client_diversity": 5,
}
TECHNICAL_STATES = {"unavailable", "http_error", "invalid", "failed", "deferred"}


def _private_digest(seed: str, region: str, event_id: str) -> str:
    return hashlib.sha256(f"{seed}\0{region}\0{event_id}".encode()).hexdigest()


def _json_bytes(value) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def _walk_count(value, keys: set[str]) -> int:
    if isinstance(value, dict):
        count = sum(len(value[key]) if isinstance(value[key], list) else 1 for key in keys if key in value)
        return count + sum(_walk_count(item, keys) for item in value.values())
    if isinstance(value, list):
        return sum(_walk_count(item, keys) for item in value)
    return 0


def _features(event: dict) -> dict:
    request = event.get("request") if isinstance(event.get("request"), dict) else {}
    response = event.get("response")
    messages = semantic._event_messages(event)
    tool_count = _walk_count(request, {"tools", "tool_calls", "tool_use", "tool_result"})
    tool_count += sum(1 for item in messages if item.get("role") in {"tool", "tool_result"})
    attachments = request.get("attachments") if isinstance(request.get("attachments"), list) else []
    request_bytes = _json_bytes(request)
    response_bytes = _json_bytes(response)
    message_count = len(messages)
    flags = []
    if message_count >= 8 or request_bytes >= 64 * 1024 or response_bytes >= 256 * 1024:
        flags.append("long_context")
    if tool_count:
        flags.append("tools")
    if attachments:
        flags.append("attachments")
    return {
        "message_count": message_count,
        "tool_count": tool_count,
        "attachment_count": len(attachments),
        "request_bytes": request_bytes,
        "response_bytes": response_bytes,
        "flags": flags,
    }


def _bucket(row: dict) -> tuple[str, str]:
    if row.get("guard_decision") == "block":
        return "guard_block", "Guard 曾明确拦截，检查是否有充分依据"
    if (
        row.get("guard_state") in TECHNICAL_STATES
        or row.get("auto_state") in TECHNICAL_STATES
        or row.get("job_state") in {"deferred", "failed"}
    ):
        return "technical_failure", "存在技术失败或暂停重试，不能当作安全标签"
    if row.get("outcome") != "completed":
        return "request_failure", "业务结果不是 completed，检查失败/取消归因"
    if row.get("features", {}).get("flags"):
        return "long_or_tools", "包含长上下文、工具或附件特征"
    known_clients = {"codex", "claude", "opencode", "hermes"}
    common_protocols = {"responses", "chat_completions", "messages"}
    if row.get("client") not in known_clients or row.get("protocol") not in common_protocols:
        return "protocol_client_diversity", "覆盖少见客户端或协议形态"
    if row.get("guard_decision") == "allow" and row.get("auto_state") == "complete":
        return "normal_allow", "Guard 放行且有离线 Auto 结果，作为正常基线"
    return "normal_allow", "作为正常基线样本"


def _stores(values: list[str]) -> dict[str, Path]:
    result = {}
    for value in values:
        if "=" not in value:
            raise ValueError("store_must_be_REGION_equals_PATH")
        region, path = value.split("=", 1)
        root = Path(path).expanduser()
        if not region or not root.is_absolute() or root.is_symlink():
            raise ValueError("store_root_must_be_absolute_non_symlink")
        result[region] = root
    return result


def _candidate_rows(db: sqlite3.Connection, stores: dict[str, Path]) -> list[dict]:
    db.row_factory = sqlite3.Row
    sql = """
        SELECT e.region,e.id,e.at,e.ingress,e.client,e.protocol,e.outcome,
               e.model,e.requested_model,e.reported_model,
               j.state AS job_state,j.attempts,j.source_path,j.sha AS job_sha,
               sr.source_sha,sr.state AS review_state,sr.guard_state,
               sr.guard_decision,sr.auto_state,sr.auto_model
        FROM events e
        JOIN review_jobs j ON j.region=e.region AND j.event_id=e.id
        LEFT JOIN semantic_reviews sr ON sr.region=e.region AND sr.event_id=e.id
        WHERE e.kind='http_exchange'
        ORDER BY e.at ASC,e.region ASC,e.id ASC
    """
    rows = []
    for raw in db.execute(sql):
        row = dict(raw)
        root = stores.get(row["region"])
        source_value = row.get("source_path")
        if root is None or not isinstance(source_value, str) or not source_value:
            continue
        source_path = Path(source_value)
        try:
            resolved_root = root.resolve(strict=True)
            resolved = source_path.resolve(strict=False)
            if resolved != resolved_root and resolved_root not in resolved.parents:
                continue
            event, digest = rolling.read_record(source_path)
        except (OSError, ValueError, KeyError, TypeError, UnicodeError):
            continue
        if event.get("kind") != "http_exchange":
            continue
        # The digest returned by read_record is the verified source identity.
        # Do not prefer a stale semantic row hash: the dashboard uses this
        # value for its integrity check when an operator opens a sample.
        row["source_sha"] = digest
        try:
            row["features"] = _features(event)
        except (AttributeError, KeyError, TypeError, ValueError, UnicodeError):
            # A malformed body is not a reason to expose it or abort the
            # complete set.  It remains eligible for the request-failure
            # bucket only when its envelope was otherwise valid.
            row["features"] = {
                "message_count": 0,
                "tool_count": 0,
                "attachment_count": 0,
                "request_bytes": 0,
                "response_bytes": 0,
                "flags": [],
            }
        row["bucket"], row["selection_reason"] = _bucket(row)
        rows.append(row)
    return rows


def _choose_region(rows: list[dict], region: str, seed: str, count: int) -> list[dict]:
    candidates = [row for row in rows if row["region"] == region]
    for row in candidates:
        row["_sort"] = _private_digest(seed, region, row["id"])
    by_bucket = defaultdict(list)
    for row in candidates:
        by_bucket[row["bucket"]].append(row)
    for values in by_bucket.values():
        values.sort(key=lambda item: item["_sort"])

    selected = []
    used = set()
    for bucket, quota in BUCKET_QUOTAS.items():
        for row in by_bucket.get(bucket, [])[:quota]:
            key = row["id"]
            if key in used:
                continue
            used.add(key)
            selected.append(row)

    if len(selected) < count:
        remainder = sorted((row for row in candidates if row["id"] not in used), key=lambda item: item["_sort"])
        for row in remainder[: count - len(selected)]:
            used.add(row["id"])
            row["bucket"] = row["bucket"] or "fallback"
            row["selection_reason"] = row["selection_reason"] or "补足区域配额"
            selected.append(row)
    if len(selected) < count:
        raise ValueError(f"insufficient_valid_events_for_{region}")
    selected.sort(key=lambda item: (item["at"], item["id"]))
    return selected[:count]


def build_manifest(db_path: Path, stores: dict[str, Path], count: int = DEFAULT_COUNT, seed: str = DEFAULT_SEED) -> dict:
    if count != DEFAULT_COUNT:
        raise ValueError("diagnostic_count_must_be_200")
    if set(stores) != {"tokyo", "us"}:
        raise ValueError("diagnostic_set_requires_tokyo_and_us")
    db = sqlite3.connect(db_path)
    try:
        rows = _candidate_rows(db, stores)
    finally:
        db.close()
    selected = _choose_region(rows, "tokyo", seed, PER_REGION) + _choose_region(rows, "us", seed, PER_REGION)
    selected.sort(key=lambda item: (item["at"], item["region"], item["id"]))
    manifest_rows = []
    for rank, row in enumerate(selected, 1):
        manifest_rows.append({
            "rank": rank,
            "region": row["region"],
            "event_id": row["id"],
            "at": row["at"],
            "ingress": row["ingress"],
            "source_sha": row["source_sha"],
            "client": row["client"],
            "protocol": row["protocol"],
            "outcome": row["outcome"],
            "requested_model": row["requested_model"],
            "actual_model": row["model"],
            "job_state": row["job_state"],
            "attempts": row["attempts"] or 0,
            "review_state": row["review_state"],
            "guard_state": row["guard_state"],
            "guard_decision": row["guard_decision"],
            "auto_state": row["auto_state"],
            "auto_model": row["auto_model"],
            "selection_bucket": row["bucket"],
            "selection_reason": row["selection_reason"],
            "features": row["features"],
        })
    bucket_counts = Counter(row["selection_bucket"] for row in manifest_rows)
    region_counts = Counter(row["region"] for row in manifest_rows)
    return {
        "schema": SCHEMA,
        "set_id": f"diagnostic-{count}-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "target_count": count,
        "selection": {
            "per_region": PER_REGION,
            "bucket_quotas_per_region": BUCKET_QUOTAS,
            "body_in_manifest": False,
            "guard_auto_called": False,
        },
        "counts": {"total": len(manifest_rows), "by_region": dict(region_counts), "by_bucket": dict(bucket_counts)},
        "rows": manifest_rows,
    }


def write_manifest(manifest: dict, output: Path) -> None:
    if not output.is_absolute() or output.is_symlink():
        raise ValueError("output_must_be_absolute_non_symlink")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, output)
    os.chmod(output, 0o600)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-db", required=True)
    parser.add_argument("--store", action="append", default=[], metavar="REGION=PATH")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    manifest = build_manifest(Path(args.analysis_db), _stores(args.store), args.count, args.seed)
    write_manifest(manifest, Path(args.output))
    print(json.dumps({"set_id": manifest["set_id"], "counts": manifest["counts"], "output": args.output}, ensure_ascii=False))


if __name__ == "__main__":
    main()
