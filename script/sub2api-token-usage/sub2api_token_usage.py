#!/usr/bin/env python3
"""Read-only token usage report for the West and Tokyo Sub2API instances.

The script queries each instance's local PostgreSQL container through the
existing SSH aliases. It writes one Excel workbook with two sheets:

* 汇总    - one row per server and local calendar day
* 每个Key - one row per server and API key for the whole date range

The default time zone is Asia/Shanghai. The date range is inclusive at the
calendar-day level, for example --from 2026-08-01 --to 2026-08-17 includes
all of August 17 until midnight in the selected time zone.

Only usage_logs and non-secret user/API-key display fields are selected. The
API key value itself is never selected, printed, or written to the reports.
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


TOKEN_COLUMNS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "image_input_tokens",
    "image_output_tokens",
    "total_tokens",
    "total_tokens_with_image",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计美西和东京 Sub2API 的每日及每个 API Key token 用量。"
    )
    parser.add_argument(
        "--from",
        dest="start_date",
        metavar="YYYY-MM-DD",
        help="起始日期（含）；默认昨天。",
    )
    parser.add_argument(
        "--to",
        dest="end_date",
        metavar="YYYY-MM-DD",
        help="结束日期（含）；默认昨天。",
    )
    parser.add_argument(
        "--timezone",
        default="Asia/Shanghai",
        help="按哪个时区切分自然日；默认 Asia/Shanghai。",
    )
    parser.add_argument(
        "--server",
        choices=("west", "tokyo", "all"),
        default="all",
        help="统计哪台服务器；默认 all。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs",
        help="Excel 输出目录；默认当前脚本目录下的 outputs。",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="每台服务器 SSH 查询超时秒数；默认 120。",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="一台服务器失败时仍保存另一台服务器的结果，并以成功退出。",
    )
    args = parser.parse_args()

    if (args.start_date is None) != (args.end_date is None):
        parser.error("--from 和 --to 必须同时提供。")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds 必须大于 0。")
    if not SAFE_TIMEZONE_RE.fullmatch(args.timezone):
        parser.error("--timezone 含有不支持的字符。")
    try:
        ZoneInfo(args.timezone)
    except Exception as exc:  # ZoneInfoNotFoundError differs across Python versions.
        parser.error(f"无法识别时区 {args.timezone!r}：{exc}")
    if args.start_date is None and args.end_date is None:
        local_today = datetime.now(ZoneInfo(args.timezone)).date()
        yesterday = local_today - timedelta(days=1)
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
    """Return a single-quoted SQL literal after strict validation."""

    if "'" in value:
        raise ValueError("SQL literal must not contain a single quote")
    return "'" + value + "'"


def build_usage_sql(start_date: str, end_date: str, timezone: str) -> str:
    """Build one grouped query; no raw usage-log rows leave the server."""

    start_literal = sql_literal(start_date)
    end_exclusive = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
    end_literal = sql_literal(end_exclusive)
    timezone_literal = sql_literal(timezone)

    # The four standard token counters match the existing Sub2API dashboard
    # convention. Image counters are reported separately and also exposed in
    # total_tokens_with_image so the two interpretations remain visible.
    return f"""COPY (
WITH grouped AS (
    SELECT
        (ul.created_at AT TIME ZONE {timezone_literal})::date AS usage_date,
        ul.api_key_id,
        COALESCE(
            MAX(NULLIF(BTRIM(k.name), '')),
            'key-' || ul.api_key_id::text
        ) AS api_key_name,
        MAX(ul.user_id) AS user_id,
        MAX(COALESCE(
            NULLIF(BTRIM(u.username), ''),
            NULLIF(BTRIM(k.name), ''),
            'user-' || ul.user_id::text
        )) AS user_label,
        COALESCE(
            string_agg(
                DISTINCT COALESCE(
                    NULLIF(BTRIM(ul.requested_model), ''),
                    NULLIF(BTRIM(ul.model), ''),
                    NULLIF(BTRIM(ul.upstream_model), '')
                ),
                ', ' ORDER BY COALESCE(
                    NULLIF(BTRIM(ul.requested_model), ''),
                    NULLIF(BTRIM(ul.model), ''),
                    NULLIF(BTRIM(ul.upstream_model), '')
                )
            ) FILTER (
                WHERE COALESCE(
                    NULLIF(BTRIM(ul.requested_model), ''),
                    NULLIF(BTRIM(ul.model), ''),
                    NULLIF(BTRIM(ul.upstream_model), '')
                ) IS NOT NULL
            ),
            ''
        ) AS models,
        COUNT(*)::bigint AS request_count,
        COALESCE(SUM(ul.input_tokens::bigint), 0)::bigint AS input_tokens,
        COALESCE(SUM(ul.output_tokens::bigint), 0)::bigint AS output_tokens,
        COALESCE(SUM(ul.cache_creation_tokens::bigint), 0)::bigint AS cache_creation_tokens,
        COALESCE(SUM(ul.cache_read_tokens::bigint), 0)::bigint AS cache_read_tokens,
        COALESCE(SUM(ul.image_input_tokens::bigint), 0)::bigint AS image_input_tokens,
        COALESCE(SUM(ul.image_output_tokens::bigint), 0)::bigint AS image_output_tokens,
        COALESCE(SUM(ul.input_tokens::bigint + ul.output_tokens::bigint
            + ul.cache_creation_tokens::bigint + ul.cache_read_tokens::bigint), 0)::bigint
            AS total_tokens,
        COALESCE(SUM(ul.input_tokens::bigint + ul.output_tokens::bigint
            + ul.cache_creation_tokens::bigint + ul.cache_read_tokens::bigint
            + ul.image_input_tokens::bigint + ul.image_output_tokens::bigint), 0)::bigint
            AS total_tokens_with_image,
        COALESCE(SUM(ul.actual_cost), 0)::numeric AS actual_cost
    FROM public.usage_logs AS ul
    LEFT JOIN public.users AS u ON u.id = ul.user_id
    LEFT JOIN public.api_keys AS k ON k.id = ul.api_key_id
    WHERE ul.created_at >= (DATE {start_literal} AT TIME ZONE {timezone_literal})
      AND ul.created_at < (DATE {end_literal} AT TIME ZONE {timezone_literal})
    GROUP BY 1, 2
)
SELECT
    usage_date,
    api_key_id,
    api_key_name,
    user_id,
    user_label,
    models,
    request_count,
    input_tokens,
    output_tokens,
    cache_creation_tokens,
    cache_read_tokens,
    image_input_tokens,
    image_output_tokens,
    total_tokens,
    total_tokens_with_image,
    actual_cost
FROM grouped
ORDER BY usage_date, api_key_name, api_key_id
) TO STDOUT WITH (FORMAT CSV, HEADER true);
"""


def query_server(
    server: ServerConfig,
    sql: str,
    timeout_seconds: int,
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
        "-X",
        "-q",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        server.postgres_user,
        "-d",
        server.postgres_database,
    ]
    try:
        completed = subprocess.run(
            command,
            input=sql,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"SSH 查询 {server.display_name} 失败：{exc}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"SSH 查询 {server.display_name} 失败（退出码 {completed.returncode}）："
            f" {detail[:1000]}"
        )

    try:
        rows = list(csv.DictReader(io.StringIO(completed.stdout)))
    except csv.Error as exc:
        raise RuntimeError(f"解析 {server.display_name} 的 CSV 结果失败：{exc}") from exc

    if rows and "usage_date" not in rows[0]:
        raise RuntimeError(f"{server.display_name} 返回结果缺少 usage_date 列。")
    return server, rows


def integer(row: dict[str, str], field: str) -> int:
    return int(row.get(field) or 0)


def decimal(row: dict[str, str], field: str) -> Decimal:
    return Decimal(row.get(field) or "0")


def add_metrics(target: dict[str, Any], row: dict[str, Any]) -> None:
    target["request_count"] += integer(row, "request_count")
    for field in TOKEN_COLUMNS:
        target[field] += integer(row, field)
    target["actual_cost"] += decimal(row, "actual_cost")


def new_metric_bucket() -> dict[str, Any]:
    bucket: dict[str, Any] = {
        "request_count": 0,
        "actual_cost": Decimal("0"),
    }
    bucket.update({field: 0 for field in TOKEN_COLUMNS})
    return bucket


def sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("server", "")),
        str(row.get("usage_date", "")),
        str(row.get("api_key_name", "")),
        str(row.get("api_key_id", "")),
    )


def build_reports(
    server_rows: dict[str, tuple[ServerConfig, list[dict[str, str]]]],
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    key_daily: list[dict[str, Any]] = []
    daily_groups: dict[tuple[str, str], dict[str, Any]] = {}

    for server_key, (server, rows) in server_rows.items():
        current_date = date.fromisoformat(start_date)
        last_date = date.fromisoformat(end_date)
        while current_date <= last_date:
            daily_key = (server_key, current_date.isoformat())
            daily_groups[daily_key] = {
                "server": server.display_name,
                "server_key": server_key,
                "usage_date": current_date.isoformat(),
                "user_count": 0,
                "key_count": 0,
                "_user_ids": set(),
                "_api_key_ids": set(),
                "_models": set(),
                **new_metric_bucket(),
            }
            current_date += timedelta(days=1)

        for source in rows:
            row: dict[str, Any] = {
                "server": server.display_name,
                "server_key": server_key,
                "usage_date": source["usage_date"],
                "api_key_id": source["api_key_id"],
                "api_key_name": source["api_key_name"],
                "user_id": source["user_id"],
                "user_label": source["user_label"],
                "models": source.get("models", ""),
            }
            for field in ("request_count", *TOKEN_COLUMNS):
                row[field] = integer(source, field)
            row["actual_cost"] = decimal(source, "actual_cost")
            key_daily.append(row)

    key_groups: dict[tuple[str, str], dict[str, Any]] = {}

    for row in key_daily:
        daily_key = (row["server_key"], row["usage_date"])
        daily = daily_groups.setdefault(
            daily_key,
            {
                "server": row["server"],
                "server_key": row["server_key"],
                "usage_date": row["usage_date"],
                "user_count": 0,
                "key_count": 0,
                "_user_ids": set(),
                "_api_key_ids": set(),
                "_models": set(),
                **new_metric_bucket(),
            },
        )
        daily["_user_ids"].add(str(row["user_id"]))
        daily["_api_key_ids"].add(str(row["api_key_id"]))
        daily["_models"].update(
            model.strip() for model in row["models"].split(",") if model.strip()
        )
        add_metrics(daily, row)

        key_key = (row["server_key"], str(row["api_key_id"]))
        key = key_groups.setdefault(
            key_key,
            {
                "server": row["server"],
                "server_key": row["server_key"],
                "api_key_id": row["api_key_id"],
                "api_key_name": row["api_key_name"],
                "user_id": row["user_id"],
                "user_label": row["user_label"],
                "_models": set(),
                "active_days": 0,
                **new_metric_bucket(),
            },
        )
        key["active_days"] += 1
        key["api_key_name"] = row["api_key_name"]
        key["user_id"] = row["user_id"]
        key["user_label"] = row["user_label"]
        key["_models"].update(
            model.strip() for model in row["models"].split(",") if model.strip()
        )
        add_metrics(key, row)

    for row in daily_groups.values():
        row["user_count"] = len(row.pop("_user_ids"))
        row["key_count"] = len(row.pop("_api_key_ids"))
        row["models"] = ", ".join(sorted(row.pop("_models")))

    for row in key_groups.values():
        row["models"] = ", ".join(sorted(row.pop("_models")))

    daily = sorted(daily_groups.values(), key=sort_key)
    per_key = sorted(
        key_groups.values(),
        key=lambda row: (
            -int(row["request_count"]),
            row["server"],
            row["api_key_name"],
            str(row["api_key_id"]),
        ),
    )
    key_daily.sort(key=sort_key)
    return daily, per_key, key_daily


def write_workbook(payload: dict[str, Any], output_path: Path) -> None:
    """Stage the artifact-tool builder in an isolated directory and run it."""

    builder = Path(__file__).with_name("build_sub2api_token_usage.mjs")
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
    if not builder.is_file():
        raise RuntimeError(f"找不到 Excel 构建器：{builder}")
    if not node.is_file():
        raise RuntimeError(f"找不到 Node.js：{node}；可用 SUB2API_NODE 覆盖。")
    if not node_modules.is_dir():
        raise RuntimeError(
            f"找不到 artifact-tool 依赖目录：{node_modules}；可用 SUB2API_NODE_MODULES 覆盖。"
        )

    with tempfile.TemporaryDirectory(prefix="sub2api-token-usage-builder-") as staging:
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
    if server_option == "all":
        return [SERVERS["west"], SERVERS["tokyo"]]
    return [SERVERS[server_option]]


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
                print(
                    f"{completed_server.display_name}: {len(rows)} 条 Key-日期汇总记录",
                    file=sys.stderr,
                )
            except Exception as exc:  # Keep the other server's result if requested.
                errors[server.key] = str(exc)
                print(f"{server.display_name}: {exc}", file=sys.stderr)

    if errors and not args.continue_on_error:
        print("有服务器查询失败；如需保留成功服务器结果请加 --continue-on-error。", file=sys.stderr)
        return 1
    if not results:
        print("没有成功取得任何服务器的数据。", file=sys.stderr)
        return 1

    daily, per_key, key_daily = build_reports(
        results, args.start_date, args.end_date
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(ZoneInfo(args.timezone)).isoformat()
    summary = {
        "generated_at": generated_at,
        "from": args.start_date,
        "to": args.end_date,
        "timezone": args.timezone,
        "token_definition": {
            "total_tokens": "input + output + cache_creation + cache_read",
            "total_tokens_with_image": "total_tokens + image_input + image_output",
        },
        "servers": [
            {
                "key": server.key,
                "name": server.display_name,
                "ssh_alias": server.ssh_alias,
                "status": "ok" if server.key in results else "error",
                "key_daily_rows": len(results[server.key][1]) if server.key in results else 0,
                **({"error": errors[server.key]} if server.key in errors else {}),
            }
            for server in servers
        ],
        "files": [
            f"sub2api_token_usage_{args.start_date}_to_{args.end_date}.xlsx"
        ],
    }
    output_path = (
        args.output_dir
        / f"sub2api_token_usage_{args.start_date}_to_{args.end_date}.xlsx"
    ).resolve()
    payload = {
        "metadata": summary,
        "daily": daily,
        "per_key": per_key,
    }
    write_workbook(payload, output_path)
    print(
        f"已写入 {output_path}",
        file=sys.stderr,
    )
    if errors:
        print("注意：部分服务器失败，但已按 --continue-on-error 保存成功结果。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
