#!/usr/bin/env python3
"""Host-side watchdog for agentbox-ctyun keepalive health with Feishu alerting."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import socket
import subprocess
import sys
import urllib.request
import uuid
from typing import Any, Callable


def parse_iso_utc(raw: str) -> dt.datetime:
    value = raw.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def inspect_container(container: str) -> tuple[bool, str, str]:
    try:
        proc = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
                container,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        code = f"docker_inspect_error:{type(exc).__name__}"
        return False, code, code
    if proc.returncode != 0:
        return False, "container_missing_or_inspect_failed", "container_missing_or_inspect_failed"
    parts = proc.stdout.strip().split()
    if len(parts) != 2:
        return False, f"unexpected_inspect_output:{proc.stdout.strip()}", "unexpected_inspect_output"
    running, health = parts
    if running != "true":
        code = f"container_not_running:{running}"
        return False, code, code
    if health != "healthy":
        code = f"container_unhealthy:{health}"
        return False, code, code
    return True, "running:healthy", "ok"


def inspect_health_file(
    health_file: pathlib.Path,
    now: dt.datetime,
    max_age_seconds: int,
    max_future_skew_seconds: int = 120,
) -> tuple[bool, str, str, dict[str, Any]]:
    meta: dict[str, Any] = {}
    if not health_file.is_file():
        return False, "health_file_missing", "health_file_missing", meta
    try:
        data = json.loads(health_file.read_text(encoding="utf-8"))
    except Exception as exc:
        code = f"health_file_invalid_json:{type(exc).__name__}"
        return False, code, code, meta
    if not isinstance(data, dict):
        return False, "health_file_schema_invalid", "health_file_schema_invalid", meta
    state = data.get("State")
    raw_time = data.get("Time")
    meta["state"] = state
    meta["time"] = raw_time
    if not isinstance(state, str) or not isinstance(raw_time, str):
        return False, "health_file_schema_invalid", "health_file_schema_invalid", meta
    try:
        ts = parse_iso_utc(raw_time)
    except Exception:
        return False, "health_file_timestamp_invalid", "health_file_timestamp_invalid", meta
    age = (now - ts).total_seconds()
    meta["age_seconds"] = round(age, 1)
    if state != "connected":
        code = f"keepalive_state_{state}"
        return False, code, code, meta
    if age > max_age_seconds:
        return False, f"health_stale:{int(age)}s>{max_age_seconds}s", "health_stale", meta
    if age < -max_future_skew_seconds:
        return False, f"health_future_timestamp:{int(-age)}s", "health_future_timestamp", meta
    return True, "connected", "ok", meta


def _call_container_checker(
    container_checker: Callable[[str], tuple[Any, ...]],
    container: str,
) -> tuple[bool, str, str]:
    result = container_checker(container)
    if len(result) == 3:
        return result[0], result[1], result[2]
    ok, detail = result
    return ok, detail, "ok" if ok else detail


def evaluate(
    container: str,
    health_file: pathlib.Path,
    now: dt.datetime,
    max_age_seconds: int,
    container_checker: Callable[[str], tuple[Any, ...]] = inspect_container,
) -> dict[str, Any]:
    c_ok, c_detail, c_key = _call_container_checker(container_checker, container)
    h_ok, h_detail, h_key, h_meta = inspect_health_file(health_file, now, max_age_seconds)
    reasons: list[str] = []
    reason_keys: list[str] = []
    if not c_ok:
        reasons.append(f"container={c_detail}")
        reason_keys.append(f"container={c_key}")
    if not h_ok:
        reasons.append(f"health={h_detail}")
        reason_keys.append(f"health={h_key}")
    return {
        "ok": c_ok and h_ok,
        "container_ok": c_ok,
        "container_detail": c_detail,
        "health_ok": h_ok,
        "health_detail": h_detail,
        "health_meta": h_meta,
        "reason": "; ".join(reasons) if reasons else "ok",
        "reason_key": "; ".join(reason_keys) if reason_keys else "ok",
    }


def load_state(state_file: pathlib.Path) -> dict[str, Any]:
    if not state_file.is_file():
        return {"status": "healthy", "reason": None, "reason_key": None, "last_alert_ts": 0}
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"status": "healthy", "reason": None, "reason_key": None, "last_alert_ts": 0}


def save_state(state_file: pathlib.Path, state: dict[str, Any]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = state_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(state_file)


def _feishu_post_json(url: str, body: dict[str, Any], access_token: str | None = None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError(f"Feishu API error code={data.get('code')} msg={data.get('msg')}")
    return data


def send_feishu_direct(title: str, message: str, env: dict[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    app_id = (source.get("FEISHU_APP_ID") or source.get("QL_FEISHU_APP_ID") or "").strip()
    app_secret = (source.get("FEISHU_APP_SECRET") or source.get("QL_FEISHU_APP_SECRET") or "").strip()
    open_id = (source.get("FEISHU_OPEN_ID") or source.get("QL_FEISHU_OPEN_ID") or "").strip()
    if not (app_id and app_secret and open_id):
        raise RuntimeError("Missing Feishu credentials (FEISHU_APP_ID/FEISHU_APP_SECRET/FEISHU_OPEN_ID)")
    auth = _feishu_post_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    token = auth.get("tenant_access_token")
    if not token:
        raise RuntimeError("Feishu auth did not return tenant_access_token")
    result = _feishu_post_json(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        {
            "receive_id": open_id,
            "msg_type": "text",
            "content": json.dumps({"text": f"{title}\n\n{message}"}, ensure_ascii=False),
            "uuid": str(uuid.uuid4()),
        },
        access_token=token,
    )
    msg_id = (result.get("data") or {}).get("message_id")
    if not msg_id:
        raise RuntimeError("Feishu send returned no message_id")
    return str(msg_id)


def decide_and_act(
    verdict: dict[str, Any],
    state: dict[str, Any],
    now: dt.datetime,
    cooldown_seconds: int,
    hostname: str,
    sender: Callable[[str, str], str],
    dry_run: bool = False,
) -> tuple[str, dict[str, Any]]:
    now_ts = int(now.timestamp())
    bjt = now.astimezone(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

    if verdict["ok"]:
        if state.get("status") == "alerting":
            title = f"CTYun 保活恢复 · {hostname}"
            body = (
                f"时间：{bjt}（北京时间）\n"
                f"容器状态：{verdict['container_detail']}\n"
                f"会话状态：{verdict['health_detail']}（更新于 {verdict['health_meta'].get('age_seconds')}s 前）\n"
                f"此前异常：{state.get('reason')}"
            )
            if not dry_run:
                sender(title, body)
            return "recovered_notified", {"status": "healthy", "reason": None, "reason_key": None, "last_alert_ts": 0}
        return "healthy_quiet", {"status": "healthy", "reason": None, "reason_key": None, "last_alert_ts": 0}

    reason = verdict["reason"]
    reason_key = verdict.get("reason_key") or reason
    prev_reason_key = state.get("reason_key") or state.get("reason")
    last_ts = int(state.get("last_alert_ts") or 0)
    if (
        state.get("status") == "alerting"
        and prev_reason_key == reason_key
        and (now_ts - last_ts) < cooldown_seconds
    ):
        return "suppressed_cooldown", state

    title = f"CTYun 保活异常 · {hostname}"
    body = (
        f"时间：{bjt}（北京时间）\n"
        f"异常详情：{reason}\n"
        f"容器状态：{verdict['container_detail']}\n"
        f"健康文件：{verdict['health_detail']}（State={verdict['health_meta'].get('state')}, age={verdict['health_meta'].get('age_seconds')}s）\n"
        f"建议排查：ssh 登录主机执行 agentbox-ctyun status，若会话过期需交互执行 agentbox-ctyun login。"
    )
    if not dry_run:
        sender(title, body)
    return "alert_sent", {"status": "alerting", "reason": reason, "reason_key": reason_key, "last_alert_ts": now_ts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor agentbox-ctyun keepalive health.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect only; do not send alerts or write state.")
    parser.add_argument("--test-alert", action="store_true", help="Send a one-time Feishu connectivity test message.")
    parser.add_argument(
        "--fail-on-unhealthy",
        action="store_true",
        help="Return exit code 1 when keepalive is unhealthy (default exits 0 once check/alert completes cleanly).",
    )
    args = parser.parse_args(argv)

    hostname = socket.gethostname()
    if args.test_alert:
        msg_id = send_feishu_direct(
            f"CTYun 保活监控 · 连接测试 ({hostname})",
            "宿主机 5 分钟保活监控已启用；仅在保活容器或 health.json 异常及恢复时发送通知。",
        )
        print(json.dumps({"test_alert": "ok", "message_id": msg_id}))
        return 0

    health_file = pathlib.Path(os.environ.get("CTYUN_HEALTH_FILE", "/srv/agentbox/ctyun/data/health.json"))
    container = os.environ.get("CTYUN_CONTAINER_NAME", "agentbox-ctyun")
    max_age = int(os.environ.get("CTYUN_MAX_AGE_SECONDS", "240"))
    state_file = pathlib.Path(os.environ.get("CTYUN_ALERT_STATE_FILE", "/var/lib/agentbox-ctyun-monitor/state.json"))
    cooldown = int(os.environ.get("CTYUN_ALERT_COOLDOWN_SECONDS", "3600"))

    now = dt.datetime.now(dt.timezone.utc)
    verdict = evaluate(container, health_file, now, max_age)
    prev_state = load_state(state_file)
    action, new_state = decide_and_act(
        verdict,
        prev_state,
        now,
        cooldown,
        hostname,
        sender=lambda t, m: send_feishu_direct(t, m),
        dry_run=args.dry_run,
    )
    if not args.dry_run and new_state != prev_state:
        save_state(state_file, new_state)

    print(json.dumps({"action": action, "verdict": verdict}, ensure_ascii=False))
    if args.fail_on_unhealthy and not verdict["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
