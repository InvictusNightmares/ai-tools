#!/usr/bin/env python3
"""Generate the daily AI gateway business-group and person token workbook.

Current resource groups no longer represent the reporting organization,
so API Key IDs are joined to a separately maintained business-group mapping.
API Key secrets are never selected, stored, or exported.

The default report covers yesterday in Asia/Shanghai, excludes 张成 and the
研发Claude business group, and renames the historical 研发Codex group to 研发.
The date range is inclusive at the local-calendar-day level.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
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

BUSINESS_GROUP_ALIASES = {"研发Codex": "研发"}
ALWAYS_EXCLUDED_GROUPS = ("研发Claude",)
DEFAULT_MAPPING_FILE = Path(__file__).resolve().parent / "person_group_mapping.csv"
DEFAULT_TENCENT_DOCS_ENV_FILE = (
    Path(__file__).resolve().parent / ".env.tencent-docs"
)
TENCENT_DOCS_BASE_URL = "https://docs.qq.com"
TENCENT_DOCS_CLIENT_ID_ENV = "TENCENT_DOCS_CLIENT_ID"
TENCENT_DOCS_CLIENT_SECRET_ENV = "TENCENT_DOCS_CLIENT_SECRET"
TENCENT_DOCS_ACCESS_TOKEN_ENV = "TENCENT_DOCS_ACCESS_TOKEN"
TENCENT_DOCS_OPEN_ID_ENV = "TENCENT_DOCS_OPEN_ID"
TENCENT_DOCS_FOLDER_ID_ENV = "TENCENT_DOCS_FOLDER_ID"
TENCENT_DOCS_PUBLIC_READ_POLICY = "publicRead"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "统计美西和东京的业务组、每人 Token 用量，"
            "默认剔除张成和研发Claude，生成 Excel 后上传腾讯文档。"
        ),
        epilog=(
            "腾讯文档上传需要 TENCENT_DOCS_CLIENT_ID，以及个人开发者的 "
            "TENCENT_DOCS_ACCESS_TOKEN（TENCENT_DOCS_OPEN_ID 可选，会自动查询）或"
            "第三方应用的 TENCENT_DOCS_CLIENT_SECRET；可选 TENCENT_DOCS_FOLDER_ID "
            "指定目标文件夹。"
            "上传转换完成后会将文档设为任何人可查看；权限校验成功并取得文档 "
            "ID/URL 后，脚本才会删除本地 Excel。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        "--exclude-person",
        action="append",
        default=[],
        metavar="NAME",
        help="额外按 API Key 显示名称精确排除人员；可重复，始终排除张成。",
    )
    parser.add_argument(
        "--exclude-group",
        action="append",
        default=[],
        metavar="GROUP",
        help="额外排除业务组；可重复，始终排除研发Claude。",
    )
    parser.add_argument(
        "--mapping-file",
        type=Path,
        default=DEFAULT_MAPPING_FILE,
        help="API Key ID 到业务组的映射 CSV；默认使用脚本目录下的映射表。",
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
    parser.add_argument(
        "--skip-tencent-upload",
        action="store_true",
        help="仅生成本地 Excel，不上传腾讯文档，也不删除本地文件。",
    )
    parser.add_argument(
        "--tencent-upload-timeout-seconds",
        type=int,
        default=300,
        help="等待腾讯文档完成导入的最长秒数；默认 300。",
    )
    parser.add_argument(
        "--tencent-env-file",
        type=Path,
        default=DEFAULT_TENCENT_DOCS_ENV_FILE,
        help="腾讯文档本地凭据文件；默认读取 daily/.env.tencent-docs。",
    )
    args = parser.parse_args()

    if (args.start_date is None) != (args.end_date is None):
        parser.error("--from 和 --to 必须同时提供。")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds 必须大于 0。")
    if args.tencent_upload_timeout_seconds <= 0:
        parser.error("--tencent-upload-timeout-seconds 必须大于 0。")
    if not SAFE_TIMEZONE_RE.fullmatch(args.timezone):
        parser.error("--timezone 含有不支持的字符。")
    try:
        ZoneInfo(args.timezone)
    except Exception as exc:  # ZoneInfoNotFoundError varies across Python versions.
        parser.error(f"无法识别时区 {args.timezone!r}：{exc}")

    if args.start_date is None:
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

    excludes = ["张成", *args.exclude_person]
    args.exclude_person = list(
        dict.fromkeys(name.strip() for name in excludes if name.strip())
    )
    excluded_groups = [*ALWAYS_EXCLUDED_GROUPS, *args.exclude_group]
    args.exclude_group = list(
        dict.fromkeys(name.strip() for name in excluded_groups if name.strip())
    )
    return args


def sql_literal(value: str) -> str:
    """Return a safely escaped PostgreSQL string literal."""

    return "'" + value.replace("'", "''") + "'"


def build_usage_sql(
    start_date: str,
    end_date: str,
    timezone: str,
    excluded_people: list[str],
) -> str:
    """Build a read-only grouped query; raw request rows stay on the server."""

    start_literal = sql_literal(start_date)
    end_exclusive = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
    end_literal = sql_literal(end_exclusive)
    timezone_literal = sql_literal(timezone)
    person_expression = (
        "COALESCE(NULLIF(BTRIM(k.name), ''), 'key-' || ul.api_key_id::text)"
    )
    exclude_clause = ""
    if excluded_people:
        excluded_sql = ", ".join(sql_literal(name) for name in excluded_people)
        exclude_clause = f"\n      AND {person_expression} NOT IN ({excluded_sql})"

    return f"""COPY (
SELECT
    (ul.created_at AT TIME ZONE {timezone_literal})::date AS usage_date,
    ul.api_key_id,
    {person_expression} AS person_name,
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
    COALESCE(SUM(
        ul.input_tokens::bigint + ul.output_tokens::bigint
        + ul.cache_creation_tokens::bigint + ul.cache_read_tokens::bigint
    ), 0)::bigint AS total_tokens,
    COALESCE(SUM(
        ul.input_tokens::bigint + ul.output_tokens::bigint
        + ul.cache_creation_tokens::bigint + ul.cache_read_tokens::bigint
        + ul.image_input_tokens::bigint + ul.image_output_tokens::bigint
    ), 0)::bigint AS total_tokens_with_image,
    COALESCE(SUM(ul.actual_cost), 0)::numeric AS actual_cost
FROM public.usage_logs AS ul
LEFT JOIN public.api_keys AS k ON k.id = ul.api_key_id
WHERE ul.created_at >= (DATE {start_literal} AT TIME ZONE {timezone_literal})
  AND ul.created_at < (DATE {end_literal} AT TIME ZONE {timezone_literal}){exclude_clause}
GROUP BY 1, 2, 3
ORDER BY usage_date, person_name, api_key_id
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


def integer(row: dict[str, Any], field: str) -> int:
    return int(row.get(field) or 0)


def decimal(row: dict[str, Any], field: str) -> Decimal:
    return Decimal(row.get(field) or "0")


def new_metric_bucket() -> dict[str, Any]:
    bucket: dict[str, Any] = {"request_count": 0, "actual_cost": Decimal("0")}
    bucket.update({field: 0 for field in TOKEN_COLUMNS})
    return bucket


def add_metrics(target: dict[str, Any], source: dict[str, Any]) -> None:
    target["request_count"] += integer(source, "request_count")
    for field in TOKEN_COLUMNS:
        target[field] += integer(source, field)
    target["actual_cost"] += decimal(source, "actual_cost")


def finalize_group(row: dict[str, Any]) -> dict[str, Any]:
    if "_servers" in row:
        row["servers"] = "、".join(sorted(row.pop("_servers")))
    if "_key_ids" in row:
        row["key_count"] = len(row.pop("_key_ids"))
    if "_people" in row:
        row["person_count"] = len(row.pop("_people"))
    if "_groups" in row:
        row["group_count"] = len(row.pop("_groups"))
    return row


def load_group_mapping(mapping_path: Path) -> dict[tuple[str, str], dict[str, str]]:
    """Load and validate the non-secret API Key ID to business-group mapping."""

    resolved = mapping_path.expanduser().resolve()
    if not resolved.is_file():
        raise RuntimeError(f"找不到业务组映射文件：{resolved}")

    mapping: dict[tuple[str, str], dict[str, str]] = {}
    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"server", "api_key_id", "person_name", "business_group"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(
                f"业务组映射缺少列：{', '.join(sorted(missing))}；文件：{resolved}"
            )
        for line_number, row in enumerate(reader, start=2):
            server_key = (row.get("server") or "").strip()
            api_key_id = (row.get("api_key_id") or "").strip()
            person_name = (row.get("person_name") or "").strip()
            business_group = (row.get("business_group") or "").strip()
            if server_key not in SERVERS:
                raise RuntimeError(
                    f"业务组映射第 {line_number} 行 server 无效：{server_key!r}"
                )
            if not api_key_id or not person_name or not business_group:
                raise RuntimeError(f"业务组映射第 {line_number} 行存在空字段。")
            identity = (server_key, api_key_id)
            if identity in mapping:
                raise RuntimeError(
                    f"业务组映射存在重复 Key：{server_key}/{api_key_id}"
                )
            mapping[identity] = {
                "person_name": person_name,
                "business_group": business_group,
            }
    return mapping


def build_reports(
    server_rows: dict[str, tuple[ServerConfig, list[dict[str, str]]]],
    mapping: dict[tuple[str, str], dict[str, str]],
    excluded_groups: set[str],
) -> dict[str, Any]:
    summary_groups: dict[str, dict[str, Any]] = {}
    business_groups: dict[tuple[str, str], dict[str, Any]] = {}
    person_groups: dict[tuple[str, str], dict[str, Any]] = {}
    unmapped: dict[tuple[str, str], dict[str, str]] = {}
    name_mismatches: dict[tuple[str, str], dict[str, str]] = {}
    excluded_group_usage: dict[str, Any] = {
        "_key_ids": set(),
        **new_metric_bucket(),
    }

    for server_key, (server, _) in server_rows.items():
        summary_groups[server_key] = {
            "server": server.display_name,
            "_groups": set(),
            "_key_ids": set(),
            "_people": set(),
            **new_metric_bucket(),
        }

    for server_key, (server, rows) in server_rows.items():
        for source in rows:
            api_key_id = str(source.get("api_key_id", "")).strip()
            person_name = source.get("person_name", "").strip() or (
                f"key-{api_key_id or 'unknown'}"
            )
            key_identity = (server_key, api_key_id)
            mapping_row = mapping.get(key_identity)
            historical_group = (
                mapping_row["business_group"] if mapping_row else "未映射"
            )
            business_group = BUSINESS_GROUP_ALIASES.get(
                historical_group, historical_group
            )

            typed: dict[str, Any] = {
                "server": server.display_name,
                "server_key": server_key,
                "api_key_id": api_key_id,
                "person_name": person_name,
                "business_group": business_group,
            }
            for field in ("request_count", *TOKEN_COLUMNS):
                typed[field] = integer(source, field)
            typed["actual_cost"] = decimal(source, "actual_cost")

            if mapping_row is None:
                unmapped[key_identity] = {
                    "server": server.display_name,
                    "api_key_id": api_key_id,
                    "person_name": person_name,
                }
            elif mapping_row["person_name"] != person_name:
                name_mismatches[key_identity] = {
                    "server": server.display_name,
                    "api_key_id": api_key_id,
                    "mapping_name": mapping_row["person_name"],
                    "current_name": person_name,
                }

            if historical_group in excluded_groups or business_group in excluded_groups:
                excluded_group_usage["_key_ids"].add(key_identity)
                add_metrics(excluded_group_usage, typed)
                continue

            summary = summary_groups[server_key]
            summary["_groups"].add(business_group)
            summary["_key_ids"].add(key_identity)
            summary["_people"].add(person_name)
            add_metrics(summary, typed)

            group_key = (server_key, business_group)
            group = business_groups.setdefault(
                group_key,
                {
                    "server": server.display_name,
                    "business_group": business_group,
                    "_key_ids": set(),
                    "_people": set(),
                    **new_metric_bucket(),
                },
            )
            group["_key_ids"].add(key_identity)
            group["_people"].add(person_name)
            add_metrics(group, typed)

            person_key = (business_group, person_name)
            person = person_groups.setdefault(
                person_key,
                {
                    "business_group": business_group,
                    "person_name": person_name,
                    "_servers": set(),
                    "_key_ids": set(),
                    **new_metric_bucket(),
                },
            )
            person["_servers"].add(server.display_name)
            person["_key_ids"].add(key_identity)
            add_metrics(person, typed)

    summary = [finalize_group(row) for row in summary_groups.values()]
    summary.sort(key=lambda row: str(row["server"]))

    per_group = [finalize_group(row) for row in business_groups.values()]
    per_group.sort(
        key=lambda row: (
            -int(row["total_tokens"]),
            str(row["server"]),
            str(row["business_group"]),
        )
    )

    per_person = [finalize_group(row) for row in person_groups.values()]
    per_person.sort(
        key=lambda row: (
            -int(row["total_tokens"]),
            str(row["person_name"]),
            str(row["business_group"]),
        )
    )
    for index, row in enumerate(per_person, start=1):
        row["rank"] = index

    finalize_group(excluded_group_usage)
    return {
        "summary": summary,
        "per_group": per_group,
        "per_person": per_person,
        "unmapped": list(unmapped.values()),
        "name_mismatches": list(name_mismatches.values()),
        "excluded_group_usage": excluded_group_usage,
    }


def write_workbook(payload: dict[str, Any], output_path: Path) -> None:
    """Run the artifact-tool builder in an isolated staging directory."""

    builder = Path(__file__).with_name("build_sub2api_daily_person_token_usage.mjs")
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
            f"找不到 artifact-tool 依赖目录：{node_modules}；"
            "可用 SUB2API_NODE_MODULES 覆盖。"
        )

    with tempfile.TemporaryDirectory(prefix="sub2api-person-usage-builder-") as staging:
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
            raise RuntimeError(f"Excel 生成失败：{detail[:3000]}")
        inspect_output = Path(f"{output_path}.inspect.ndjson")
        if inspect_output.exists():
            inspect_output.unlink()
        if completed.stdout.strip():
            print(completed.stdout.strip(), file=sys.stderr)


def _tencent_docs_json_request(
    method: str,
    url: str,
    *,
    action: str,
    headers: dict[str, str] | None = None,
    form: dict[str, Any] | None = None,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Call Tencent Docs without exposing credential-bearing URLs in errors."""

    request_headers = dict(headers or {})
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        request_headers.setdefault(
            "Content-Type", "application/x-www-form-urlencoded"
        )
    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(
            f"{action}失败（HTTP {exc.code}）：{detail or '无响应内容'}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{action}网络错误：{exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"{action}超时。") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{action}返回了无法解析的响应。") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{action}返回格式不正确。")
    return payload


def _tencent_docs_data(payload: dict[str, Any], action: str) -> dict[str, Any]:
    ret = payload.get("ret")
    if ret not in (None, 0):
        message = str(payload.get("msg") or "未知错误")
        raise RuntimeError(f"{action}失败（ret={ret}）：{message}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"{action}未返回 data。")
    return data


def _file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _tencent_docs_open_id_for_token(access_token: str) -> str:
    """Validate a personal-developer token and resolve its Open ID."""

    query = urllib.parse.urlencode({"access_token": access_token})
    user_info = _tencent_docs_json_request(
        "GET",
        f"{TENCENT_DOCS_BASE_URL}/oauth/v2/userinfo?{query}",
        action="验证腾讯文档个人开发者访问令牌",
    )
    data = _tencent_docs_data(user_info, "验证腾讯文档个人开发者访问令牌")
    open_id = str(
        data.get("openID") or data.get("open_id") or data.get("user_id") or ""
    )
    if not open_id:
        raise RuntimeError("腾讯文档用户信息响应缺少 Open ID。")
    return open_id


def _tencent_docs_api_headers(
    *,
    client_id: str,
    client_secret: str | None,
    access_token: str | None,
    open_id: str | None,
) -> tuple[dict[str, str], str]:
    """Resolve OpenAPI headers for personal or third-party app credentials."""

    if access_token:
        resolved_open_id = open_id or _tencent_docs_open_id_for_token(access_token)
        return (
            {
                "Access-Token": access_token,
                "Client-Id": client_id,
                "Open-Id": resolved_open_id,
                "Accept": "application/json",
            },
            "personal_access_token",
        )

    if not client_secret:
        raise RuntimeError(
            "缺少腾讯文档访问凭据：请配置 TENCENT_DOCS_ACCESS_TOKEN 或 "
            "TENCENT_DOCS_CLIENT_SECRET。"
        )

    auth_query = urllib.parse.urlencode(
        {"client_id": client_id, "client_secret": client_secret}
    )
    auth = _tencent_docs_json_request(
        "GET",
        f"{TENCENT_DOCS_BASE_URL}/oauth/v2/app-account-token?{auth_query}",
        action="获取腾讯文档访问令牌",
    )
    if auth.get("ret") not in (None, 0):
        app_auth_error = RuntimeError(
            "获取腾讯文档访问令牌失败"
            f"（ret={auth.get('ret')}）：{auth.get('msg') or '未知错误'}"
        )
        # Personal developer pages expose access_token rather than client_secret.
        # Keep the original local variable usable, but only after the value proves
        # itself against the official user-info endpoint.
        try:
            resolved_open_id = open_id or _tencent_docs_open_id_for_token(
                client_secret
            )
        except RuntimeError:
            raise app_auth_error
        return (
            {
                "Access-Token": client_secret,
                "Client-Id": client_id,
                "Open-Id": resolved_open_id,
                "Accept": "application/json",
            },
            "personal_access_token_legacy_env",
        )

    resolved_access_token = str(auth.get("access_token") or "")
    resolved_open_id = str(auth.get("user_id") or "")
    if not resolved_access_token or not resolved_open_id:
        raise RuntimeError("腾讯文档访问令牌响应缺少 access_token 或 user_id。")
    return (
        {
            "Access-Token": resolved_access_token,
            "Client-Id": client_id,
            "Open-Id": resolved_open_id,
            "Accept": "application/json",
        },
        "app_account",
    )


def _set_tencent_docs_public_read(
    document_id: str,
    api_headers: dict[str, str],
) -> dict[str, Any]:
    """Set a document to publicRead and verify the effective policy."""

    encoded_document_id = urllib.parse.quote(document_id, safe="")
    permission_url = (
        f"{TENCENT_DOCS_BASE_URL}/openapi/drive/v2/files/"
        f"{encoded_document_id}/permission"
    )
    updated = _tencent_docs_json_request(
        "PATCH",
        permission_url,
        action="设置腾讯文档为任何人可查看",
        headers=api_headers,
        form={"policy": TENCENT_DOCS_PUBLIC_READ_POLICY},
    )
    update_error = None
    if updated.get("ret") not in (None, 0):
        update_error = (
            "设置腾讯文档为任何人可查看返回错误"
            f"（ret={updated.get('ret')}）：{updated.get('msg') or '未知错误'}"
        )

    # The PATCH endpoint can report an RPC error even when the policy has already
    # changed. Treat the read-after-write result as the source of truth.
    permission_payload = _tencent_docs_json_request(
        "GET",
        permission_url,
        action="校验腾讯文档分享权限",
        headers=api_headers,
    )
    permission = _tencent_docs_data(
        permission_payload, "校验腾讯文档分享权限"
    )
    policy = str(permission.get("policy") or "")
    if policy != TENCENT_DOCS_PUBLIC_READ_POLICY:
        prefix = f"{update_error}；" if update_error else ""
        raise RuntimeError(
            f"{prefix}腾讯文档分享权限校验失败："
            f"期望 {TENCENT_DOCS_PUBLIC_READ_POLICY}，实际 {policy or '未返回'}。"
        )
    return permission


def upload_to_tencent_docs(
    workbook_path: Path,
    *,
    client_id: str,
    client_secret: str | None,
    access_token: str | None = None,
    open_id: str | None = None,
    parent_folder_id: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Upload XLSX, set publicRead, and verify the effective permission."""

    if not workbook_path.is_file():
        raise RuntimeError(f"待上传文档不存在：{workbook_path}")
    if workbook_path.suffix.lower() != ".xlsx":
        raise RuntimeError(f"腾讯文档上传仅接受生成的 XLSX：{workbook_path}")

    api_headers, auth_mode = _tencent_docs_api_headers(
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token,
        open_id=open_id,
    )
    file_md5 = _file_md5(workbook_path)
    file_name = workbook_path.name
    file_size = workbook_path.stat().st_size

    # https://docs.qq.com/open/document/app/openapi/v2/file/import/pre_import.html
    pre_import = _tencent_docs_json_request(
        "POST",
        f"{TENCENT_DOCS_BASE_URL}/openapi/drive/v2/files/upload",
        action="创建腾讯文档导入任务",
        headers=api_headers,
        form={
            "fileMD5": file_md5,
            "fileName": file_name,
            "fileSize": file_size,
        },
    )
    cos_info = _tencent_docs_data(pre_import, "创建腾讯文档导入任务")
    cos_put_url = str(cos_info.get("COSPutURL") or "")
    cos_file_key = str(cos_info.get("COSFileKey") or "")
    custom_headers = cos_info.get("CustomHeader")
    if not cos_put_url or not cos_file_key or not isinstance(custom_headers, dict):
        raise RuntimeError("腾讯文档预导入响应缺少 COS 上传信息。")

    cos_request = urllib.request.Request(
        cos_put_url,
        data=workbook_path.read_bytes(),
        headers={str(key): str(value) for key, value in custom_headers.items()},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(cos_request, timeout=60) as response:
            status = getattr(response, "status", 200)
            response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"上传文档文件失败（HTTP {exc.code}）。") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"上传文档文件网络错误：{exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("上传文档文件超时。") from exc
    if status not in (200, 201, 204):
        raise RuntimeError(f"上传文档文件失败（HTTP {status}）。")

    # https://docs.qq.com/open/document/app/openapi/v2/file/import/async_import.html
    import_form: dict[str, Any] = {
        "fileMD5": file_md5,
        "fileName": file_name,
        "COSFileKey": cos_file_key,
    }
    if parent_folder_id:
        import_form["parentfolderID"] = parent_folder_id
    async_import = _tencent_docs_json_request(
        "POST",
        f"{TENCENT_DOCS_BASE_URL}/openapi/drive/v2/files/async-import",
        action="启动腾讯文档转换",
        headers=api_headers,
        form=import_form,
    )
    import_data = _tencent_docs_data(async_import, "启动腾讯文档转换")
    progress_query_id = str(import_data.get("progressQueryID") or "")
    if not progress_query_id:
        raise RuntimeError("腾讯文档异步导入响应缺少 progressQueryID。")

    # https://docs.qq.com/open/document/app/openapi/v2/file/import/import_progress.html
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        query = urllib.parse.urlencode({"progressQueryID": progress_query_id})
        progress_payload = _tencent_docs_json_request(
            "GET",
            (
                f"{TENCENT_DOCS_BASE_URL}/openapi/drive/v2/files/"
                f"import-progress?{query}"
            ),
            action="查询腾讯文档导入进度",
            headers=api_headers,
        )
        progress_data = _tencent_docs_data(
            progress_payload, "查询腾讯文档导入进度"
        )
        progress = int(progress_data.get("progress") or 0)
        document_id = str(progress_data.get("ID") or "")
        document_url = str(progress_data.get("url") or "")
        if progress >= 100:
            if not document_id or not document_url:
                raise RuntimeError(
                    "腾讯文档导入进度已完成，但未返回文档 ID 或 URL。"
                )
            permission = _set_tencent_docs_public_read(
                document_id,
                api_headers,
            )
            return {
                "id": document_id,
                "url": document_url,
                "title": str(progress_data.get("title") or file_name),
                "progress": progress,
                "auth_mode": auth_mode,
                "permission_policy": str(permission["policy"]),
            }
        time.sleep(2)
    raise RuntimeError(f"等待腾讯文档导入完成超时（{timeout_seconds} 秒）。")


def load_tencent_docs_env_file(env_path: Path) -> list[str]:
    """Load supported Tencent Docs variables without overriding process env."""

    resolved = env_path.expanduser().resolve()
    if not resolved.exists():
        return []
    if not resolved.is_file():
        raise RuntimeError(f"腾讯文档凭据路径不是文件：{resolved}")

    allowed = {
        TENCENT_DOCS_CLIENT_ID_ENV,
        TENCENT_DOCS_CLIENT_SECRET_ENV,
        TENCENT_DOCS_ACCESS_TOKEN_ENV,
        TENCENT_DOCS_OPEN_ID_ENV,
        TENCENT_DOCS_FOLDER_ID_ENV,
    }
    loaded: list[str] = []
    for line_number, raw_line in enumerate(
        resolved.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not separator or key not in allowed:
            raise RuntimeError(
                f"腾讯文档凭据文件第 {line_number} 行格式或变量名无效。"
            )
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif value.startswith(("'", '"')) or value.endswith(("'", '"')):
            raise RuntimeError(
                f"腾讯文档凭据文件第 {line_number} 行引号不匹配。"
            )
        if value and not os.environ.get(key):
            os.environ[key] = value
            loaded.append(key)
    return loaded


def publish_workbook_to_tencent_docs(
    workbook_path: Path,
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Upload, verify publicRead and the online document, then remove local."""

    client_id = os.environ.get(TENCENT_DOCS_CLIENT_ID_ENV, "").strip()
    client_secret = os.environ.get(TENCENT_DOCS_CLIENT_SECRET_ENV, "").strip()
    access_token = os.environ.get(TENCENT_DOCS_ACCESS_TOKEN_ENV, "").strip()
    open_id = os.environ.get(TENCENT_DOCS_OPEN_ID_ENV, "").strip()
    parent_folder_id = os.environ.get(TENCENT_DOCS_FOLDER_ID_ENV, "").strip() or None
    if not client_id:
        raise RuntimeError(f"缺少环境变量：{TENCENT_DOCS_CLIENT_ID_ENV}")
    if not access_token and not client_secret:
        raise RuntimeError(
            "缺少腾讯文档访问凭据：请配置 TENCENT_DOCS_ACCESS_TOKEN 或 "
            "TENCENT_DOCS_CLIENT_SECRET。"
        )

    uploaded = upload_to_tencent_docs(
        workbook_path,
        client_id=client_id,
        client_secret=client_secret or None,
        access_token=access_token or None,
        open_id=open_id or None,
        parent_folder_id=parent_folder_id,
        timeout_seconds=timeout_seconds,
    )
    if (
        int(uploaded.get("progress") or 0) < 100
        or not uploaded.get("id")
        or not uploaded.get("url")
        or uploaded.get("permission_policy") != TENCENT_DOCS_PUBLIC_READ_POLICY
    ):
        raise RuntimeError(
            "腾讯文档未返回可确认的完成状态或公开只读权限，本地文档未删除。"
        )
    try:
        workbook_path.unlink()
    except OSError as exc:
        raise RuntimeError(
            f"腾讯文档上传成功，但删除本地文档失败：{exc}"
        ) from exc
    return uploaded


def selected_servers(server_option: str) -> list[ServerConfig]:
    if server_option == "all":
        return [SERVERS["west"], SERVERS["tokyo"]]
    return [SERVERS[server_option]]


def main() -> int:
    args = parse_args()
    if not args.skip_tencent_upload:
        try:
            loaded_env = load_tencent_docs_env_file(args.tencent_env_file)
        except (OSError, UnicodeError, RuntimeError) as exc:
            print(f"读取腾讯文档凭据文件失败：{exc}", file=sys.stderr)
            return 1
        if loaded_env:
            print(
                f"已读取腾讯文档本地凭据：{args.tencent_env_file.expanduser().resolve()}",
                file=sys.stderr,
            )
    try:
        mapping = load_group_mapping(args.mapping_file)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"业务组映射: {len(mapping)} 个 Key", file=sys.stderr)

    servers = selected_servers(args.server)
    sql = build_usage_sql(
        args.start_date,
        args.end_date,
        args.timezone,
        args.exclude_person,
    )

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
            except Exception as exc:
                errors[server.key] = str(exc)
                print(f"{server.display_name}: {exc}", file=sys.stderr)

    if errors and not args.continue_on_error:
        print(
            "有服务器查询失败；如需保留成功服务器结果请加 --continue-on-error。",
            file=sys.stderr,
        )
        return 1
    if not results:
        print("没有成功取得任何服务器的数据。", file=sys.stderr)
        return 1

    reports = build_reports(
        results,
        mapping,
        set(args.exclude_group),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        args.output_dir
        / f"AI网关Token用量{args.start_date}-{args.end_date}.xlsx"
    ).resolve()

    metadata = {
        "generated_at": datetime.now(ZoneInfo(args.timezone)).isoformat(),
        "from": args.start_date,
        "to": args.end_date,
        "timezone": args.timezone,
        "excluded_people": args.exclude_person,
        "excluded_groups": args.exclude_group,
        "group_aliases": BUSINESS_GROUP_ALIASES,
        "mapping_file": str(args.mapping_file.expanduser().resolve()),
        "mapping_key_count": len(mapping),
        "mapping_source": (
            "qiyuan-us / qiyuan-tokyo business-group mapping backup snapshot "
            "2026-08-20"
        ),
        "template_url": "https://docs.qq.com/sheet/DVndmU1dRZmNJdm1w?tab=000001",
        "person_definition": "按 API Key 显示名称识别人；同名 Key 合并",
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
                "key_daily_rows": (
                    len(results[server.key][1]) if server.key in results else 0
                ),
                **({"error": errors[server.key]} if server.key in errors else {}),
            }
            for server in servers
        ],
        "unmapped": reports["unmapped"],
        "name_mismatches": reports["name_mismatches"],
        "excluded_group_usage": reports["excluded_group_usage"],
    }
    payload = {
        "metadata": metadata,
        "summary": reports["summary"],
        "per_group": reports["per_group"],
        "per_person": reports["per_person"],
    }
    write_workbook(payload, output_path)
    print(f"已写入 {output_path}", file=sys.stderr)
    if reports["unmapped"]:
        print(
            f"注意：{len(reports['unmapped'])} 个有用量 Key 未映射，已归入‘未映射’。",
            file=sys.stderr,
        )
    if reports["name_mismatches"]:
        print(
            f"注意：{len(reports['name_mismatches'])} 个 Key 的当前名称与映射名称不同，"
            "报表使用当前名称。",
            file=sys.stderr,
        )
    if errors:
        print("注意：部分服务器失败，报表已保留成功节点并标明状态。", file=sys.stderr)
    if args.skip_tencent_upload:
        print("已跳过腾讯文档上传，本地 Excel 保留。", file=sys.stderr)
        return 0

    try:
        uploaded = publish_workbook_to_tencent_docs(
            output_path,
            timeout_seconds=args.tencent_upload_timeout_seconds,
        )
    except RuntimeError as exc:
        print(f"腾讯文档发布失败：{exc}", file=sys.stderr)
        print(f"本地文档已保留：{output_path}", file=sys.stderr)
        return 1

    print(
        f"腾讯文档上传成功且已设为任何人可查看：{uploaded['url']}",
        file=sys.stderr,
    )
    print(f"已删除本地文档：{output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
