#!/usr/bin/env python3
"""Read-only token usage report grouped by Sub2API group for West and Tokyo.

The report uses ``usage_logs.group_id`` so every request is attributed to the
effective group recorded at the time it was served.  API-key values and group
IDs are never selected for the workbook output.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SAFE_TIMEZONE_RE = re.compile(r"^[A-Za-z0-9_+./:-]+$")
METRIC_COLUMNS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "image_input_tokens",
    "image_output_tokens",
)


@dataclass(frozen=True)
class ServerConfig:
    key: str
    display_name: str
    ssh_alias: str
    postgres_container: str = "sub2api-postgres"
    postgres_user: str = "sub2api"
    postgres_database: str = "sub2api"


SERVERS = {
    "west": ServerConfig("west", "美西", "qiyuan-us"),
    "tokyo": ServerConfig("tokyo", "东京", "qiyuan-tokyo"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计美西和东京 Sub2API 每个分组的 token 用量。"
    )
    parser.add_argument("--from", dest="start_date", metavar="YYYY-MM-DD")
    parser.add_argument("--to", dest="end_date", metavar="YYYY-MM-DD")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--server", choices=("west", "tokyo", "all"), default="all")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    if (args.start_date is None) != (args.end_date is None):
        parser.error("--from 和 --to 必须同时提供。")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds 必须大于 0。")
    if not SAFE_TIMEZONE_RE.fullmatch(args.timezone):
        parser.error("--timezone 含有不支持的字符。")
    try:
        ZoneInfo(args.timezone)
    except Exception as exc:
        parser.error(f"无法识别时区 {args.timezone!r}：{exc}")

    if args.start_date is None:
        yesterday = datetime.now(ZoneInfo(args.timezone)).date() - timedelta(days=1)
        args.start_date = args.end_date = yesterday.isoformat()

    for option_name, value in (("--from", args.start_date), ("--to", args.end_date)):
        if not DATE_RE.fullmatch(value):
            parser.error(f"{option_name} 必须是 YYYY-MM-DD。")
        try:
            date.fromisoformat(value)
        except ValueError:
            parser.error(f"{option_name} 不是有效日期：{value}。")
    if args.start_date > args.end_date:
        parser.error("--from 不能晚于 --to。")
    return args


def sql_literal(value: str) -> str:
    if "'" in value:
        raise ValueError("SQL literal must not contain a single quote")
    return "'" + value + "'"


def build_usage_sql(start_date: str, end_date: str, timezone: str) -> str:
    start_literal = sql_literal(start_date)
    end_exclusive = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
    end_literal = sql_literal(end_exclusive)
    timezone_literal = sql_literal(timezone)
    return f"""COPY (
WITH grouped AS (
    SELECT
        ul.group_id,
        COALESCE(MAX(NULLIF(BTRIM(g.name), '')), '未分组') AS group_name,
        COUNT(DISTINCT ul.api_key_id)::bigint AS key_count,
        COUNT(*)::bigint AS request_count,
        COALESCE(SUM(ul.input_tokens::bigint), 0)::bigint AS input_tokens,
        COALESCE(SUM(ul.output_tokens::bigint), 0)::bigint AS output_tokens,
        COALESCE(SUM(ul.cache_creation_tokens::bigint), 0)::bigint AS cache_creation_tokens,
        COALESCE(SUM(ul.cache_read_tokens::bigint), 0)::bigint AS cache_read_tokens,
        COALESCE(SUM(ul.image_input_tokens::bigint), 0)::bigint AS image_input_tokens,
        COALESCE(SUM(ul.image_output_tokens::bigint), 0)::bigint AS image_output_tokens,
        COALESCE(SUM(ul.actual_cost), 0)::numeric AS actual_cost
    FROM public.usage_logs AS ul
    LEFT JOIN public.groups AS g ON g.id = ul.group_id
    WHERE ul.created_at >= (DATE {start_literal} AT TIME ZONE {timezone_literal})
      AND ul.created_at < (DATE {end_literal} AT TIME ZONE {timezone_literal})
    GROUP BY ul.group_id
)
SELECT
    group_id,
    group_name,
    key_count,
    request_count,
    input_tokens,
    output_tokens,
    cache_creation_tokens,
    cache_read_tokens,
    image_input_tokens,
    image_output_tokens,
    actual_cost
FROM grouped
ORDER BY group_name, group_id NULLS FIRST
) TO STDOUT WITH (FORMAT CSV, HEADER true);
"""


def query_server(
    server: ServerConfig, sql: str, timeout_seconds: int
) -> tuple[ServerConfig, list[dict[str, str]]]:
    command = [
        "ssh",
        "-T",
        server.ssh_alias,
        "docker",
        "exec",
        "-i",
        server.postgres_container,
        "psql",
        "-q",
        "-U",
        server.postgres_user,
        "-d",
        server.postgres_database,
        "-v",
        "ON_ERROR_STOP=1",
    ]
    completed = subprocess.run(
        command,
        input=sql,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"查询失败（退出码 {completed.returncode}）：{detail[:1000]}")
    reader = csv.DictReader(io.StringIO(completed.stdout))
    expected_columns = {"group_name", "key_count", "request_count", *METRIC_COLUMNS, "actual_cost"}
    if not expected_columns.issubset(set(reader.fieldnames or [])):
        actual_columns = ", ".join(reader.fieldnames or []) or "无"
        raise RuntimeError(f"查询返回列不完整：{actual_columns}")
    return server, list(reader)


def integer(row: dict[str, str], field: str) -> int:
    return int(row.get(field) or 0)


def decimal(row: dict[str, str], field: str) -> Decimal:
    return Decimal(row.get(field) or "0")


def blank_metrics() -> dict[str, int | Decimal]:
    return {**{field: 0 for field in ("request_count", *METRIC_COLUMNS)}, "actual_cost": Decimal("0")}


def add_metrics(target: dict[str, Any], source: dict[str, Any]) -> None:
    for field in ("request_count", *METRIC_COLUMNS):
        target[field] += int(source[field])
    target["actual_cost"] += source["actual_cost"]


def build_reports(
    server_rows: dict[str, tuple[ServerConfig, list[dict[str, str]]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    per_group: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}

    for server_key, (server, rows) in server_rows.items():
        summary = {
            "server": server.display_name,
            "server_key": server_key,
            "group_count": 0,
            **blank_metrics(),
        }
        for source in rows:
            row: dict[str, Any] = {
                "server": server.display_name,
                "server_key": server_key,
                "group_name": source["group_name"],
                "key_count": integer(source, "key_count"),
                "actual_cost": decimal(source, "actual_cost"),
            }
            for field in ("request_count", *METRIC_COLUMNS):
                row[field] = integer(source, field)
            per_group.append(row)
            summary["group_count"] += 1
            add_metrics(summary, row)
        summaries[server_key] = summary

    summary_rows = sorted(summaries.values(), key=lambda row: row["server"])
    per_group.sort(
        key=lambda row: (-int(row["request_count"]), row["server"], row["group_name"])
    )
    return summary_rows, per_group


def write_workbook(payload: dict[str, Any], output_path: Path) -> None:
    builder = Path(__file__).with_name("build_sub2api_group_token_usage.mjs")
    node = Path(
        os.environ.get(
            "SUB2API_NODE",
            "/Users/invictus/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node",
        )
    )
    node_modules = Path(
        os.environ.get(
            "SUB2API_NODE_MODULES",
            "/Users/invictus/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules",
        )
    )
    if not builder.is_file() or not node.is_file() or not node_modules.is_dir():
        raise RuntimeError("找不到 Excel 生成所需的构建器或 artifact-tool 运行环境。")

    with tempfile.TemporaryDirectory(prefix="sub2api-group-token-usage-builder-") as staging:
        staging_dir = Path(staging)
        staged_builder = staging_dir / builder.name
        data_path = staging_dir / "usage_data.json"
        shutil.copy2(builder, staged_builder)
        (staging_dir / "node_modules").symlink_to(node_modules, target_is_directory=True)
        data_path.write_text(
            json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8"
        )
        completed = subprocess.run(
            [str(node), str(staged_builder), str(data_path), str(output_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"Excel 生成失败：{detail[:2000]}")
        inspect_output = Path(f"{output_path}.inspect.ndjson")
        if inspect_output.exists():
            inspect_output.unlink()
        if completed.stdout.strip():
            print(completed.stdout.strip(), file=sys.stderr)


def selected_servers(server_option: str) -> list[ServerConfig]:
    return [SERVERS["west"], SERVERS["tokyo"]] if server_option == "all" else [SERVERS[server_option]]


def main() -> int:
    args = parse_args()
    servers = selected_servers(args.server)
    sql = build_usage_sql(args.start_date, args.end_date, args.timezone)
    results: dict[str, tuple[ServerConfig, list[dict[str, str]]]] = {}
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(servers)) as executor:
        futures = {
            executor.submit(query_server, server, sql, args.timeout_seconds): server
            for server in servers
        }
        for future in as_completed(futures):
            server = futures[future]
            try:
                completed_server, rows = future.result()
                results[completed_server.key] = (completed_server, rows)
                print(f"{completed_server.display_name}: {len(rows)} 条分组汇总记录", file=sys.stderr)
            except Exception as exc:
                errors[server.key] = str(exc)
                print(f"{server.display_name}: {exc}", file=sys.stderr)

    if errors and not args.continue_on_error:
        print("有服务器查询失败；如需保留成功服务器结果请加 --continue-on-error。", file=sys.stderr)
        return 1
    if not results:
        print("没有成功取得任何服务器的数据。", file=sys.stderr)
        return 1

    summary_rows, per_group = build_reports(results)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        args.output_dir
        / f"sub2api_group_token_usage_{args.start_date}_to_{args.end_date}.xlsx"
    ).resolve()
    payload = {
        "metadata": {
            "from": args.start_date,
            "to": args.end_date,
            "timezone": args.timezone,
            "generated_at": datetime.now(ZoneInfo(args.timezone)).isoformat(),
            "servers": [server.display_name for server in servers if server.key in results],
        },
        "summary": summary_rows,
        "per_group": per_group,
    }
    write_workbook(payload, output_path)
    print(f"已写入 {output_path}", file=sys.stderr)
    if errors:
        print("注意：部分服务器失败，但已按 --continue-on-error 保存成功结果。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
