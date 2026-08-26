#!/usr/bin/env python3
"""Generate the daily AI gateway report as inline PNGs and send it by SMTP.

This is intentionally separate from ``sub2api_daily_person_token_usage.py``.
The existing workbook/Tencent Docs workflow is left untouched; this entrypoint
only reuses its read-only query and grouping helpers.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import smtplib
import ssl
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - exercised on the deployment host.
    raise SystemExit(
        "缺少 Pillow；请在运行邮件日报的服务器安装 Pillow。"
    ) from exc

from sub2api_daily_person_token_usage import (
    ALWAYS_EXCLUDED_GROUPS,
    BUSINESS_GROUP_ALIASES,
    DEFAULT_MAPPING_FILE,
    SERVERS,
    build_reports,
    build_usage_sql,
    load_group_mapping,
    query_server,
)


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEFAULT_EMAIL_CONFIG_FILE = Path(__file__).resolve().parent / ".env.email"
DEFAULT_WORK_DIR = Path(__file__).resolve().parent / "email-runs"
DEFAULT_TEST_RECIPIENT = "fuxiaozhen@cpirhzl.com"
DEFAULT_SMTP_HOST = "smtp.qiye.aliyun.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_SMTP_TIMEOUT_SECONDS = 60
DEFAULT_FONT_REGULAR_CANDIDATES = (
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
DEFAULT_FONT_BOLD_CANDIDATES = (
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    sender: str
    recipients: tuple[str, ...]
    test_recipient: str
    use_ssl: bool
    starttls: bool
    timeout_seconds: int


@dataclass(frozen=True)
class FontSet:
    regular: ImageFont.FreeTypeFont
    bold: ImageFont.FreeTypeFont
    title: ImageFont.FreeTypeFont
    note: ImageFont.FreeTypeFont
    header: ImageFont.FreeTypeFont
    body: ImageFont.FreeTypeFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "生成前一天 AI 网关 Token 日报的三张 PNG，并通过 SMTP 发送邮件；"
            "不生成 Excel，也不上传腾讯文档。"
        )
    )
    parser.add_argument("--from", dest="start_date", metavar="YYYY-MM-DD")
    parser.add_argument("--to", dest="end_date", metavar="YYYY-MM-DD")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_MAPPING_FILE)
    parser.add_argument(
        "--config-file", type=Path, default=DEFAULT_EMAIL_CONFIG_FILE
    )
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--test", action="store_true", help="只发给测试收件人。")
    parser.add_argument(
        "--test-recipient",
        default=None,
        help=f"覆盖测试收件人；默认 {DEFAULT_TEST_RECIPIENT}。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="生成图片并构造邮件，但不连接 SMTP 发送。",
    )
    args = parser.parse_args()

    if (args.start_date is None) != (args.end_date is None):
        parser.error("--from 和 --to 必须同时提供。")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds 必须大于 0。")
    try:
        ZoneInfo(args.timezone)
    except Exception as exc:
        parser.error(f"无法识别时区 {args.timezone!r}：{exc}")

    if args.start_date is None:
        today = datetime.now(ZoneInfo(args.timezone)).date()
        yesterday = today - timedelta(days=1)
        args.start_date = args.end_date = yesterday.isoformat()
    for option, value in (("--from", args.start_date), ("--to", args.end_date)):
        if not DATE_RE.fullmatch(value):
            parser.error(f"{option} 必须是 YYYY-MM-DD。")
        try:
            date.fromisoformat(value)
        except ValueError:
            parser.error(f"{option} 不是有效日期：{value}。")
    if args.start_date > args.end_date:
        parser.error("--from 不能晚于 --to。")
    if args.test_recipient and not EMAIL_RE.fullmatch(args.test_recipient.strip()):
        parser.error("--test-recipient 不是有效邮箱地址。")
    return args


def _parse_bool(value: str, default: bool) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise RuntimeError(f"布尔配置值无效：{value!r}")


def load_env_file(path: Path) -> None:
    """Load email settings without printing or overriding process variables."""

    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return
    if not resolved.is_file():
        raise RuntimeError(f"邮件配置路径不是文件：{resolved}")
    if resolved.stat().st_mode & 0o077:
        raise RuntimeError(f"邮件配置文件权限过宽（需要仅所有者可读写）：{resolved}")
    allowed = {
        "EMAIL_SMTP_HOST",
        "EMAIL_SMTP_PORT",
        "EMAIL_SMTP_USERNAME",
        "EMAIL_SMTP_PASSWORD",
        "EMAIL_FROM",
        "EMAIL_TO",
        "EMAIL_TEST_TO",
        "EMAIL_SMTP_USE_SSL",
        "EMAIL_SMTP_STARTTLS",
        "EMAIL_SMTP_TIMEOUT_SECONDS",
    }
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
            raise RuntimeError(f"邮件配置第 {line_number} 行格式或变量名无效。")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif value.startswith(("'", '"')) or value.endswith(("'", '"')):
            raise RuntimeError(f"邮件配置第 {line_number} 行引号不匹配。")
        os.environ.setdefault(key, value)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少邮件配置：{name}")
    return value


def _parse_recipients(value: str, name: str, *, required: bool) -> tuple[str, ...]:
    recipients = tuple(
        item.strip() for item in re.split(r"[,;\n]", value) if item.strip()
    )
    invalid = [item for item in recipients if not EMAIL_RE.fullmatch(item)]
    if invalid:
        raise RuntimeError(f"{name} 包含无效邮箱地址。")
    if required and not recipients:
        raise RuntimeError(f"缺少邮件配置：{name}")
    return recipients


def load_email_config(
    path: Path,
    *,
    test_override: str | None,
    test_mode: bool,
) -> EmailConfig:
    load_env_file(path)
    smtp_host = os.environ.get("EMAIL_SMTP_HOST", DEFAULT_SMTP_HOST).strip()
    try:
        smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", str(DEFAULT_SMTP_PORT)))
        timeout_seconds = int(
            os.environ.get(
                "EMAIL_SMTP_TIMEOUT_SECONDS", str(DEFAULT_SMTP_TIMEOUT_SECONDS)
            )
        )
    except ValueError as exc:
        raise RuntimeError("邮件 SMTP 端口或超时配置必须是整数。") from exc
    if smtp_port <= 0 or timeout_seconds <= 0:
        raise RuntimeError("邮件 SMTP 端口和超时必须大于 0。")
    username = _required_env("EMAIL_SMTP_USERNAME")
    password = _required_env("EMAIL_SMTP_PASSWORD")
    sender = os.environ.get("EMAIL_FROM", username).strip()
    if not EMAIL_RE.fullmatch(sender):
        raise RuntimeError("EMAIL_FROM 不是有效邮箱地址。")
    recipients = _parse_recipients(
        os.environ.get("EMAIL_TO", ""), "EMAIL_TO", required=not test_mode
    )
    test_recipient = (test_override or os.environ.get("EMAIL_TEST_TO", "")).strip()
    if not test_recipient:
        test_recipient = DEFAULT_TEST_RECIPIENT
    if not EMAIL_RE.fullmatch(test_recipient):
        raise RuntimeError("测试收件人不是有效邮箱地址。")
    use_ssl = _parse_bool(os.environ.get("EMAIL_SMTP_USE_SSL", "1"), True)
    starttls = _parse_bool(
        os.environ.get("EMAIL_SMTP_STARTTLS", "0" if use_ssl else "1"),
        not use_ssl,
    )
    if use_ssl and starttls:
        raise RuntimeError("EMAIL_SMTP_USE_SSL 和 EMAIL_SMTP_STARTTLS 不能同时启用。")
    return EmailConfig(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_username=username,
        smtp_password=password,
        sender=sender,
        recipients=recipients,
        test_recipient=test_recipient,
        use_ssl=use_ssl,
        starttls=starttls,
        timeout_seconds=timeout_seconds,
    )


def _query_with_retry(server: Any, sql: str, timeout_seconds: int) -> tuple[Any, list[dict[str, str]]]:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            return query_server(server, sql, timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - preserve the original SSH error.
            last_error = exc
            if attempt == 0:
                time.sleep(2)
    assert last_error is not None
    raise last_error


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except InvalidOperation:
        return Decimal("0")


def _number(value: Any) -> float:
    return float(_decimal(value))


def format_token(value: Any) -> str:
    amount = _decimal(value)
    if amount >= Decimal("1000000000"):
        return f"{amount / Decimal('1000000000'):.2f}B（十亿）"
    if amount >= Decimal("1000000"):
        return f"{amount / Decimal('1000000'):.2f}M（百万）"
    if amount == amount.to_integral_value():
        return f"{int(amount):,}"
    return f"{amount:,.2f}"


def format_count(value: Any) -> str:
    amount = _decimal(value)
    if amount == amount.to_integral_value():
        return f"{int(amount):,}"
    return f"{amount:,.2f}"


def format_cost(value: Any) -> str:
    return f"${_decimal(value):,.4f}"


def _font(
    candidates: Iterable[str], size: int, *, env_name: str | None = None
) -> ImageFont.FreeTypeFont:
    configured = os.environ.get(env_name, "").strip() if env_name else ""
    paths = (configured, *candidates) if configured else tuple(candidates)
    for candidate in paths:
        path = Path(candidate)
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def load_fonts() -> FontSet:
    regular = _font(
        DEFAULT_FONT_REGULAR_CANDIDATES, 18, env_name="AI_GATEWAY_FONT"
    )
    bold = _font(
        DEFAULT_FONT_BOLD_CANDIDATES, 18, env_name="AI_GATEWAY_FONT_BOLD"
    )
    return FontSet(
        regular=regular,
        bold=bold,
        title=_font(
            DEFAULT_FONT_BOLD_CANDIDATES, 32, env_name="AI_GATEWAY_FONT_BOLD"
        ),
        note=_font(
            DEFAULT_FONT_REGULAR_CANDIDATES, 16, env_name="AI_GATEWAY_FONT"
        ),
        header=_font(
            DEFAULT_FONT_BOLD_CANDIDATES, 17, env_name="AI_GATEWAY_FONT_BOLD"
        ),
        body=regular,
    )


COLORS = {
    "navy": "#0F172A",
    "header": "#1E293B",
    "slate": "#334155",
    "muted": "#64748B",
    "white": "#FFFFFF",
    "note": "#F8FAFC",
    "stripe": "#EFF6FF",
    "border": "#CBD5E1",
    "total_fill": "#DCFCE7",
    "total_text": "#14532D",
}


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    chunks = text.split(" / ")
    lines: list[str] = []
    for chunk in chunks:
        if _text_width(draw, chunk, font) <= max_width:
            lines.append(chunk)
            continue
        current = ""
        for character in chunk:
            candidate = current + character
            if current and _text_width(draw, candidate, font) > max_width:
                lines.append(current)
                current = character
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines or [""]


def _draw_cell_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font: ImageFont.FreeTypeFont,
    *,
    align: str,
    fill: str,
    wrap: bool = False,
) -> None:
    left, top, right, bottom = box
    max_width = right - left - 18
    lines = _wrap_text(draw, text, font, max_width) if wrap else [text]
    line_height = max(20, getattr(font, "size", 16) + 4)
    total_height = line_height * len(lines)
    y = top + max(0, (bottom - top - total_height) // 2)
    for line in lines:
        line_width = _text_width(draw, line, font)
        if align == "right":
            x = right - 9 - int(line_width)
        elif align == "center":
            x = left + (right - left - int(line_width)) // 2
        else:
            x = left + 9
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height


def _draw_table(
    *,
    title: str,
    note: str,
    headers: list[str],
    rows: list[list[str]],
    widths: list[int],
    numeric_columns: set[int],
    total_row: int,
    output_path: Path,
) -> None:
    fonts = load_fonts()
    margin = 24
    title_height = 66
    note_height = 58
    gap_height = 18
    header_height = 72
    row_height = 48
    total_height = row_height + 4
    width = margin * 2 + sum(widths)
    height = margin + title_height + note_height + gap_height + header_height
    height += row_height * len(rows) + (4 if rows else 0) + margin
    image = Image.new("RGB", (width, height), COLORS["white"])
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, width, title_height), fill=COLORS["navy"])
    _draw_cell_text(
        draw,
        title,
        (margin, 0, width - margin, title_height),
        fonts.title,
        align="left",
        fill=COLORS["white"],
    )
    note_top = title_height
    draw.rectangle((0, note_top, width, note_top + note_height), fill=COLORS["note"])
    _draw_cell_text(
        draw,
        note,
        (margin, note_top, width - margin, note_top + note_height),
        fonts.note,
        align="left",
        fill=COLORS["slate"],
        wrap=True,
    )

    table_left = margin
    header_top = title_height + note_height + gap_height
    x_positions = [table_left]
    for column_width in widths:
        x_positions.append(x_positions[-1] + column_width)
    for index, header in enumerate(headers):
        left = x_positions[index]
        right = x_positions[index + 1]
        draw.rectangle(
            (left, header_top, right, header_top + header_height),
            fill=COLORS["header"],
            outline=COLORS["border"],
            width=1,
        )
        _draw_cell_text(
            draw,
            header,
            (left, header_top, right, header_top + header_height),
            fonts.header,
            align="center",
            fill=COLORS["white"],
            wrap=True,
        )

    body_top = header_top + header_height
    for row_index, row in enumerate(rows):
        top = body_top + row_index * row_height
        bottom = top + (total_height if row_index == total_row else row_height)
        fill = COLORS["total_fill"] if row_index == total_row else (
            COLORS["stripe"] if row_index % 2 == 1 else COLORS["white"]
        )
        text_fill = COLORS["total_text"] if row_index == total_row else COLORS["slate"]
        for column_index, value in enumerate(row):
            left = x_positions[column_index]
            right = x_positions[column_index + 1]
            draw.rectangle((left, top, right, bottom), fill=fill, outline=COLORS["border"], width=1)
            _draw_cell_text(
                draw,
                value,
                (left, top, right, bottom),
                fonts.bold if row_index == total_row else fonts.body,
                align="right" if column_index in numeric_columns else "left",
                fill=text_fill,
            )
    image.save(output_path, format="PNG", optimize=True)


def _sum_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total: dict[str, Any] = {"request_count": 0, "actual_cost": Decimal("0")}
    for field in (
        "input_tokens",
        "output_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
        "image_input_tokens",
        "image_output_tokens",
        "total_tokens",
        "total_tokens_with_image",
    ):
        total[field] = 0
    for row in rows:
        total["request_count"] += int(row.get("request_count") or 0)
        total["actual_cost"] += _decimal(row.get("actual_cost"))
        for field in total:
            if field in {"request_count", "actual_cost"}:
                continue
            total[field] += int(row.get(field) or 0)
    return total


def _report_note(metadata: dict[str, Any], suffix: str = "") -> str:
    servers = "；".join(
        f"{server.get('name')}: {'正常' if server.get('status') == 'ok' else '失败'}"
        for server in metadata.get("servers", [])
    )
    return (
        f"统计范围: {metadata.get('from')} 至 {metadata.get('to')}；"
        f"时区: {metadata.get('timezone')}；节点: {servers}；"
        "Token 单位: ≥1,000,000 显示 M（百万），≥1,000,000,000 显示 B（十亿）"
        + suffix
    )


def render_report_images(payload: dict[str, Any], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = payload.get("metadata", {})
    summary = list(payload.get("summary", []))
    per_group = list(payload.get("per_group", []))
    per_person = list(payload.get("per_person", []))

    summary_total = _sum_rows(summary)
    summary_total.update({
        "server": "合计 / Total",
        "group_count": sum(int(row.get("group_count") or 0) for row in summary),
    })
    summary_rows = [
        [
            str(row.get("server", "")),
            format_count(row.get("group_count")),
            format_count(row.get("request_count")),
            format_token(row.get("input_tokens")),
            format_token(row.get("output_tokens")),
            format_token(row.get("cache_creation_tokens")),
            format_token(row.get("cache_read_tokens")),
            format_token(row.get("image_input_tokens")),
            format_token(row.get("image_output_tokens")),
            format_token(row.get("total_tokens")),
            format_token(row.get("total_tokens_with_image")),
            format_cost(row.get("actual_cost")),
        ]
        for row in summary
    ]
    summary_rows.append([
        summary_total["server"],
        format_count(summary_total["group_count"]),
        format_count(summary_total["request_count"]),
        format_token(summary_total["input_tokens"]),
        format_token(summary_total["output_tokens"]),
        format_token(summary_total["cache_creation_tokens"]),
        format_token(summary_total["cache_read_tokens"]),
        format_token(summary_total["image_input_tokens"]),
        format_token(summary_total["image_output_tokens"]),
        format_token(summary_total["total_tokens"]),
        format_token(summary_total["total_tokens_with_image"]),
        format_cost(summary_total["actual_cost"]),
    ])
    summary_path = output_dir / "01-summary.png"
    _draw_table(
        title="AI网关 Token 使用汇总",
        note=_report_note(metadata),
        headers=[
            "服务器 / Server", "分组数 / Groups", "请求数 / Requests",
            "输入 Token / Input", "输出 Token / Output", "缓存创建 Token / Cache Creation",
            "缓存读取 Token / Cache Read", "图片输入 Token / Image Input",
            "图片输出 Token / Image Output", "总 Token / Total",
            "含图片总 Token / Total+Image", "Actual Cost",
        ],
        rows=summary_rows,
        widths=[150, 140, 140, 180, 180, 220, 220, 200, 200, 180, 220, 155],
        numeric_columns=set(range(1, 12)),
        total_row=len(summary_rows) - 1,
        output_path=summary_path,
    )

    group_total = _sum_rows(per_group)
    group_total.update({
        "business_group": "合计 / Total",
        "key_count": sum(int(row.get("key_count") or 0) for row in per_group),
    })
    group_rows = []
    for row in per_group:
        key_count = int(row.get("key_count") or 0)
        group_rows.append([
            str(row.get("server", "")),
            str(row.get("business_group", "")),
            format_count(key_count),
            format_count(row.get("request_count")),
            format_count(_number(row.get("request_count")) / key_count if key_count else 0),
            format_token(row.get("input_tokens")),
            format_token(row.get("output_tokens")),
            format_token(row.get("cache_creation_tokens")),
            format_token(row.get("cache_read_tokens")),
            format_token(row.get("image_input_tokens")),
            format_token(row.get("image_output_tokens")),
            format_token(row.get("total_tokens")),
            format_token(_number(row.get("total_tokens")) / key_count if key_count else 0),
            format_token(row.get("total_tokens_with_image")),
            format_cost(row.get("actual_cost")),
        ])
    group_key_count = int(group_total["key_count"] or 0)
    group_rows.append([
        group_total["business_group"], "", format_count(group_key_count),
        format_count(group_total["request_count"]),
        format_count(_number(group_total["request_count"]) / group_key_count if group_key_count else 0),
        format_token(group_total["input_tokens"]), format_token(group_total["output_tokens"]),
        format_token(group_total["cache_creation_tokens"]), format_token(group_total["cache_read_tokens"]),
        format_token(group_total["image_input_tokens"]), format_token(group_total["image_output_tokens"]),
        format_token(group_total["total_tokens"]),
        format_token(_number(group_total["total_tokens"]) / group_key_count if group_key_count else 0),
        format_token(group_total["total_tokens_with_image"]), format_cost(group_total["actual_cost"]),
    ])
    group_path = output_dir / "02-groups.png"
    _draw_table(
        title="AI网关 每个业务组 Token 使用量",
        note=_report_note(metadata, "；按总 Token 降序。"),
        headers=[
            "服务器 / Server", "分组 / Group", "Key数 / Keys", "请求数 / Requests",
            "平均请求数 / Avg Requests", "输入 Token / Input", "输出 Token / Output",
            "缓存创建 Token / Cache Creation", "缓存读取 Token / Cache Read",
            "图片输入 Token / Image Input", "图片输出 Token / Image Output",
            "总 Token / Total", "平均 Token / Avg Token",
            "含图片总 Token / Total+Image", "Actual Cost",
        ],
        rows=group_rows,
        widths=[140, 150, 105, 135, 170, 180, 180, 220, 220, 200, 200, 180, 180, 220, 155],
        numeric_columns=set(range(2, 15)),
        total_row=len(group_rows) - 1,
        output_path=group_path,
    )

    person_total = _sum_rows(per_person)
    person_total["key_count"] = sum(int(row.get("key_count") or 0) for row in per_person)
    person_rows = []
    for row in per_person:
        key_count = int(row.get("key_count") or 0)
        person_rows.append([
            format_count(row.get("rank")), str(row.get("servers", "")),
            str(row.get("business_group", "")), str(row.get("person_name", "")),
            format_count(key_count), format_count(row.get("request_count")),
            format_count(_number(row.get("request_count")) / key_count if key_count else 0),
            format_token(row.get("input_tokens")), format_token(row.get("output_tokens")),
            format_token(row.get("cache_creation_tokens")), format_token(row.get("cache_read_tokens")),
            format_token(row.get("image_input_tokens")), format_token(row.get("image_output_tokens")),
            format_token(row.get("total_tokens")),
            format_token(_number(row.get("total_tokens")) / key_count if key_count else 0),
            format_token(row.get("total_tokens_with_image")), format_cost(row.get("actual_cost")),
        ])
    person_key_count = int(person_total["key_count"] or 0)
    person_rows.append([
        "", "", "", "合计 / Total", format_count(person_key_count),
        format_count(person_total["request_count"]),
        format_count(_number(person_total["request_count"]) / person_key_count if person_key_count else 0),
        format_token(person_total["input_tokens"]), format_token(person_total["output_tokens"]),
        format_token(person_total["cache_creation_tokens"]), format_token(person_total["cache_read_tokens"]),
        format_token(person_total["image_input_tokens"]), format_token(person_total["image_output_tokens"]),
        format_token(person_total["total_tokens"]),
        format_token(_number(person_total["total_tokens"]) / person_key_count if person_key_count else 0),
        format_token(person_total["total_tokens_with_image"]), format_cost(person_total["actual_cost"]),
    ])
    person_path = output_dir / "03-persons.png"
    _draw_table(
        title="AI网关 人员 Token 使用排行榜",
        note=_report_note(metadata, "；按总 Token 从大到小排列。"),
        headers=[
            "排名 / Rank", "服务器 / Server", "分组 / Group", "人员 / Person",
            "Key数 / Keys", "请求数 / Requests", "平均请求数 / Avg Requests",
            "输入 Token / Input", "输出 Token / Output", "缓存创建 Token / Cache Creation",
            "缓存读取 Token / Cache Read", "图片输入 Token / Image Input",
            "图片输出 Token / Image Output", "总 Token / Total", "平均 Token / Avg Token",
            "含图片总 Token / Total+Image", "Actual Cost",
        ],
        rows=person_rows,
        widths=[95, 135, 145, 145, 105, 135, 170, 180, 180, 220, 220, 200, 200, 180, 180, 220, 155],
        numeric_columns=set(range(0, 1)) | set(range(4, 17)),
        total_row=len(person_rows) - 1,
        output_path=person_path,
    )
    return [summary_path, group_path, person_path]


def build_email_message(
    *,
    subject: str,
    recipients: tuple[str, ...],
    sender: str,
    plain_text: str,
    image_paths: list[Path],
) -> MIMEMultipart:
    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = formataddr(("张成", sender))
    message["To"] = ", ".join(recipients)

    related = MIMEMultipart("related")
    alternative = MIMEMultipart("alternative")
    image_tags = []
    for index, _ in enumerate(image_paths, start=1):
        image_tags.append(
            f'<p style="margin:0 0 12px 0"><img src="cid:report-{index}" '
            'style="display:block;max-width:100%;height:auto" /></p>'
        )
    html_body = (
        "<html><body style=\"font-family:Tahoma,Arial,'Microsoft YaHei',sans-serif;\">"
        f"<p>{html.escape(plain_text)}</p>"
        + "".join(image_tags)
        + "</body></html>"
    )
    alternative.attach(MIMEText(plain_text, "plain", "utf-8"))
    alternative.attach(MIMEText(html_body, "html", "utf-8"))
    related.attach(alternative)
    message.attach(related)

    for index, image_path in enumerate(image_paths, start=1):
        image = MIMEImage(image_path.read_bytes(), _subtype="png")
        image.add_header("Content-ID", f"<report-{index}>")
        # Keep the images inline in the related body; omitting a filename avoids
        # mail clients presenting them as ordinary downloadable attachments.
        image.add_header("Content-Disposition", "inline")
        related.attach(image)
    return message


def send_email(message: MIMEMultipart, config: EmailConfig) -> None:
    if config.use_ssl:
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(
            config.smtp_host,
            config.smtp_port,
            timeout=config.timeout_seconds,
            context=ssl.create_default_context(),
        )
    else:
        smtp = smtplib.SMTP(
            config.smtp_host, config.smtp_port, timeout=config.timeout_seconds
        )
    try:
        smtp.ehlo()
        if config.starttls:
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        try:
            smtp.login(config.smtp_username, config.smtp_password)
        except smtplib.SMTPAuthenticationError as exc:
            raise RuntimeError(
                "SMTP 认证失败，请检查邮箱账号和授权码；邮件未发送。"
            ) from exc
        smtp.send_message(message)
    finally:
        try:
            smtp.quit()
        except smtplib.SMTPServerDisconnected:
            pass


def _metadata_payload(
    start_date: str,
    end_date: str,
    timezone: str,
    mapping: dict[tuple[str, str], dict[str, str]],
    reports: dict[str, Any],
    results: dict[str, tuple[Any, list[dict[str, str]]]],
) -> dict[str, Any]:
    return {
        "from": start_date,
        "to": end_date,
        "timezone": timezone,
        "excluded_people": ["张成"],
        "excluded_groups": list(ALWAYS_EXCLUDED_GROUPS),
        "group_aliases": BUSINESS_GROUP_ALIASES,
        "mapping_key_count": len(mapping),
        "mapping_source": (
            "2026-08-20 business-group mapping backup snapshot; "
            "maintained west/86 闫志豪→研发Codex"
        ),
        "servers": [
            {
                "key": server.key,
                "name": server.display_name,
                "status": "ok" if server.key in results else "error",
                "key_daily_rows": len(results[server.key][1]) if server.key in results else 0,
            }
            for server in SERVERS.values()
        ],
        "unmapped": reports["unmapped"],
        "name_mismatches": reports["name_mismatches"],
    }


def main() -> int:
    args = parse_args()
    print(
        f"日报日期：{args.start_date} 至 {args.end_date}；"
        f"时区：{args.timezone}；数据节点：美西、东京"
    )
    try:
        config = load_email_config(
            args.config_file,
            test_override=args.test_recipient,
            test_mode=args.test,
        )
    except (OSError, UnicodeError, RuntimeError) as exc:
        print(f"读取邮件配置失败：{exc}", file=sys.stderr)
        return 1

    mapping = load_group_mapping(args.mapping_file)
    servers = list(SERVERS.values())
    sql = build_usage_sql(args.start_date, args.end_date, args.timezone, ["张成"])
    results: dict[str, tuple[Any, list[dict[str, str]]]] = {}
    errors: dict[str, str] = {}
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=len(servers)) as executor:
        futures = {
            executor.submit(_query_with_retry, server, sql, args.timeout_seconds): server
            for server in servers
        }
        for future in as_completed(futures):
            server = futures[future]
            try:
                completed_server, rows = future.result()
                results[completed_server.key] = (completed_server, rows)
                print(f"{completed_server.display_name}: {len(rows)} 条 Key-日期汇总记录")
            except Exception as exc:  # noqa: BLE001 - report the node and continue gathering.
                errors[server.key] = str(exc)
                print(f"{server.display_name}: 查询失败：{exc}", file=sys.stderr)

    if errors:
        print("有服务器查询失败，不生成或发送邮件。", file=sys.stderr)
        return 1

    reports = build_reports(results, mapping, set(ALWAYS_EXCLUDED_GROUPS))
    metadata = _metadata_payload(
        args.start_date, args.end_date, args.timezone, mapping, reports, results
    )
    payload = {
        "metadata": metadata,
        "summary": reports["summary"],
        "per_group": reports["per_group"],
        "per_person": reports["per_person"],
    }
    print(
        f"业务映射：{len(mapping)} 条；未映射有用量 Key：{len(reports['unmapped'])}；"
        f"名称差异：{len(reports['name_mismatches'])}"
    )

    args.work_dir.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=f"{args.start_date}-", dir=args.work_dir))
    succeeded = False
    try:
        image_paths = render_report_images(payload, run_dir)
        suffix = (
            args.start_date
            if args.start_date == args.end_date
            else f"{args.start_date}-{args.end_date}"
        )
        subject = f"AI网关用量{suffix}"
        recipients = (config.test_recipient,) if args.test else config.recipients
        plain_text = f"您好，{suffix}部门Token用量："
        print(f"发送收件人：{', '.join(recipients)}；主题：{subject}")
        message = build_email_message(
            subject=subject,
            recipients=recipients,
            sender=config.sender,
            plain_text=plain_text,
            image_paths=image_paths,
        )
        if args.dry_run:
            print(
                f"Dry-run: 已生成 {len(image_paths)} 张图片，邮件包含 "
                f"{len([part for part in message.walk() if part.get_content_type() == 'image/png'])} 个行内 PNG。"
            )
            return 0
        send_email(message, config)
        print(f"邮件发送成功：{len(recipients)} 个收件人，主题 {subject}")
        succeeded = True
        return 0
    except Exception as exc:  # noqa: BLE001 - preserve artifacts for diagnosis.
        print(f"邮件日报失败：{exc}", file=sys.stderr)
        print(f"失败运行目录已保留：{run_dir}", file=sys.stderr)
        return 1
    finally:
        if succeeded:
            shutil.rmtree(run_dir, ignore_errors=True)
        elif not args.dry_run and not any(run_dir.iterdir()):
            shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
