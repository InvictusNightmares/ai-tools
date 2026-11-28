#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中国移动江苏 act2510 自动签到（会话自动续期 + 风控硬熔断）。

链路：
  1. autoLogin 现签 client.app.coc 会话（冷启动不带伪造 Cookie，x-sign 第 4 段用 "null"）
  2. appTokenLogin 换 QWHD 会话
  3. getYDRZToken(sourceId=039014) 换 JSYD jtToken
  4. jtWx10086AuthLogin 换江苏活动 Cookie
  5. initIndexPage 查状态，必要时 doSign

兼容全国版「中国移动」（cn.10086.app v12.5.8）与「中国移动江苏」（com.jsmcc.ZP7267A6ES v12.0.5），
支持 uamonekeylogin/autoLogin 与 uamrandcodelogin/autoLogin 等接口路径。

私有配置（0600）：/ql/data/config/cmcc_profile.json
状态文件（0600）：默认与 profile 同目录的 *.state.json（可通过 CMCC_STATE_FILE / --state-file 指定）

用法：
  python3 cmcc_auto.py --dry-run        # 纯离线校验配置、签名与风控状态（零网络请求）
  python3 cmcc_auto.py --check          # 只查登录/签到状态（跳过启动延迟，仍受熔断与冷却保护）
  python3 cmcc_auto.py --now            # 跳过启动延迟立即签到
  python3 cmcc_auto.py --clear-lockout  # 清除风控熔断状态（纯本地，不发网络请求）
  python3 cmcc_auto.py                  # 非整点随机延迟后签到，成功后发飞书通知

环境变量：
  CMCC_PROFILE       私有配置路径，默认 /ql/data/config/cmcc_profile.json
  CMCC_STATE_FILE    持久化状态文件路径（可选）
  CMCC_MIN_INTERVAL  跨进程最小 autoLogin 调用间隔秒数，默认 300
  CMCC_DELAY_MIN     非整点随机启动延迟下限秒数，默认 30
  CMCC_DELAY_MAX     非整点随机启动延迟上限秒数，默认 900
  QL_FEISHU_APP_ID / QL_FEISHU_APP_SECRET / QL_FEISHU_OPEN_ID  可选通知

退出码：
  0 = 成功 / --dry-run 通过 / --clear-lockout 完成
  1 = 配置错误或运行时异常
  2 = 风控硬熔断或跨进程冷却拦截（零网络请求）
"""

import argparse
import base64
import contextlib
import hashlib
import json
import math
import os
import random
import re
import ssl
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

try:
    import fcntl
except ImportError:  # pragma: no cover - 非 POSIX 环境降级
    fcntl = None

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

SALT = "Leadeon/SecurityOrganization"
REQ_KEY, REQ_IV = b"tVkdaRWRY0ZkV1Vr", b"VjFSQ1ZtVkQxRTlQ"
RESP_KEY = b"RYV0hCV1lV25KYVJ"
TOK_KEY, TOK_IV = b"bAIgvwAuA4tbDr9d", b"9791027341711819"

QWHD_BASE = "https://wx.10086.cn"
SSO_LOGIN = QWHD_BASE + "/qwhdsso/login"
DEFAULT_ACT_URL = QWHD_BASE + "/qwhdhub/qwhdmark/1021122301?channelId=P00000109876"
JSYD_LOGIN = "https://wap.js.10086.cn/vw/gateway/auth/auth/jtWx10086AuthLogin"
JSYD_ACTION = "https://wap.js.10086.cn/nact/action.do"
JSYD_REFERER = "https://wap.js.10086.cn/nact/resource/2510/html/index.html"
DEFAULT_PROFILE = "/ql/data/config/cmcc_profile.json"
DEFAULT_APP_VERSION = "12.5.6"
DEFAULT_ACCEPT_LANGUAGE = "zh-CN,zh-Hans;q=0.9"
DEFAULT_MIN_INTERVAL = 300
DEFAULT_DELAY_MIN = 30
DEFAULT_DELAY_MAX = 900
TZ_SHANGHAI = timezone(timedelta(hours=8))
LEGACY_SERVER_CONNECT = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
PHONE_RE = re.compile(r"(?<!\d)(1\d{2})\d{4}(\d{4})(?!\d)")

DEFAULT_SSO_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/wkwebview "
    "leadeon/12.5.2/CMCCIT"
)
DEFAULT_JSYD_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/wkwebview "
    "leadeon/12.0.5/CMCCIT"
)

# 命中以下任一风控/频控码立即持久化硬熔断，后续定时零请求退出
RISK_LOCKOUT_CODES = {
    "214100": "登录风控拦截",
    "214101": "登录风控拦截",
    "214102": "登录风控拦截",
    "214103": "触发实人/人脸校验风控",
    "214104": "登录风控拦截",
    "214105": "登录风控拦截",
    "214200": "账号安全校验拦截",
    "214300": "账号安全校验拦截",
    "213245": "设备/环境安全校验拦截",
    "420000": "账号已在其他设备登录互斥",
    "233031": "登录请求过于频繁触发频控",
}


class AutoLoginError(RuntimeError):
    """autoLogin 返回非 000000 或无法解密响应。"""

    def __init__(self, ret_code="", ret_desc="", http_status=None):
        self.ret_code = str(ret_code or "").strip()
        self.ret_desc = str(ret_desc or "").strip()
        self.http_status = http_status
        code_part = f"retCode={self.ret_code}" if self.ret_code else f"HTTP {http_status}"
        desc_part = f" {self.ret_desc[:80]}" if self.ret_desc else ""
        super().__init__(f"autoLogin 失败: {code_part}{desc_part}")

    @property
    def is_risk_lockout(self):
        return self.ret_code in RISK_LOCKOUT_CODES


class GuardrailBlocked(RuntimeError):
    """被持久化风控硬熔断或跨进程冷却拦下（零网络请求）。"""

    def __init__(self, reason, message):
        self.reason = reason
        super().__init__(message)


class LegacyAdapter(HTTPAdapter):
    """wx.10086.cn / client.app.coc 需要 legacy renegotiation。"""

    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.set_ciphers("DEFAULT@SECLEVEL=1")
        context.options |= LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)


def new_session():
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", LegacyAdapter())
    return session


def _cbc(key, iv, data, encrypt):
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    if encrypt:
        pad = 16 - len(data) % 16
        enc = cipher.encryptor()
        return enc.update(data + bytes([pad]) * pad) + enc.finalize()
    dec = cipher.decryptor()
    out = dec.update(data) + dec.finalize()
    pad = out[-1]
    if not 1 <= pad <= 16 or out[-pad:] != bytes([pad]) * pad:
        raise ValueError("invalid PKCS7 padding")
    return out[:-pad]


def encrypt_body(plain):
    return base64.b64encode(_cbc(REQ_KEY, REQ_IV, plain.encode(), True)).decode()


def decrypt_response(raw):
    text = raw.decode("utf-8", "replace").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except ValueError:
            return None
    for _ in range(2):
        try:
            plain = _cbc(RESP_KEY, REQ_IV, base64.b64decode(text), False).decode("utf-8", "strict").strip()
        except Exception:
            return None
        if plain.startswith("{"):
            try:
                parsed = json.loads(plain)
                return parsed if isinstance(parsed, dict) else None
            except ValueError:
                return None
        text = plain
    return None


def _extract_jsessionid(cookie):
    cookie_str = (cookie or "").strip()
    if not cookie_str:
        return "", "null"
    match = re.search(r"(?:^|;\s*)JSESSIONID=([^;]+)", cookie_str)
    if match and match.group(1).strip():
        return cookie_str, match.group(1).strip()
    return cookie_str, "null"


def build_headers(
    url,
    plain,
    cookie,
    xk,
    user_agent,
    *,
    ts=None,
    nonce=None,
    accept_language=DEFAULT_ACCEPT_LANGUAGE,
):
    """构造 client.app.coc 签名请求头。

    冷启动（cookie 为空或 None）时不发送 Cookie 头，并以字面量 "null" 计算 x-sign 第 4 段；
    有真实 Cookie（含 JSESSIONID）传入时正常带 Cookie 并用 JSESSIONID 值签名。
    """
    cookie_str, jsid = _extract_jsessionid(cookie)
    ts_str = str(int(time.time() * 1000)) if ts is None else str(ts)
    nonce_str = str(random.randint(10_000_000, 99_999_999)) if nonce is None else str(nonce)
    path = urlsplit(url).path or "/"
    token = base64.b64encode(
        _cbc(TOK_KEY, TOK_IV, f"{xk}_{path}_{ts_str}_{nonce_str}".encode(), True)
    ).decode()
    headers = {
        "x-qen": "14",
        "Accept": "*/*",
        "xs": hashlib.md5(f"{url}_{plain}_{SALT}".encode()).hexdigest(),
        "x-sign": hashlib.md5(f"{token}_{ts_str}_{nonce_str}_{jsid}".encode()).hexdigest(),
        "x-nonce": nonce_str,
        "x-token": token,
        "Accept-Encoding": "deflate",
        "Accept-Language": accept_language,
        "Content-Type": "application/Json",
        "x-time": ts_str,
        "User-Agent": user_agent,
    }
    if cookie_str:
        headers["Cookie"] = cookie_str
    return headers


def api_headers(referer):
    return {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json;charset=UTF-8",
        "origin": QWHD_BASE,
        "referer": referer,
        "login-check": "1",
        "x-requested-with": "XMLHttpRequest",
    }


def resolve_app_version(profile):
    template = profile.get("auto_login_template")
    cv = str(template.get("cv") or "").strip() if isinstance(template, dict) else ""
    explicit = str(profile.get("app_version_code") or "").strip()
    return explicit or cv or DEFAULT_APP_VERSION


def resolve_auto_login_ua(profile):
    explicit = str(profile.get("auto_login_user_agent") or "").strip()
    if explicit:
        return explicit
    template = profile.get("auto_login_template")
    cv = str(template.get("cv") or "").strip() if isinstance(template, dict) else ""
    sv = str(template.get("sv") or "").strip() if isinstance(template, dict) else ""
    ver = cv or resolve_app_version(profile)
    ios_ver = sv or "18.7"
    return f"ChinaMobile/{ver} (iPhone; iOS {ios_ver}; Scale/3.00)"


def resolve_webview_ua(profile, key, fallback_ua):
    explicit = str(profile.get(key) or "").strip()
    if explicit:
        return explicit
    ver = resolve_app_version(profile)
    if re.fullmatch(r"\d+(?:\.\d+)+", ver):
        return re.sub(r"leadeon/[^/\s]+/CMCCIT", f"leadeon/{ver}/CMCCIT", fallback_ua)
    return fallback_ua


def safe_url_for_log(url):
    parts = urlsplit(str(url or ""))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def sanitize_text(text, profile=None):
    cleaned = str(text or "")
    if isinstance(profile, dict):
        phone_str = str(profile.get("phone") or "").strip()
        secrets = [
            phone_str,
            profile.get("xk"),
            profile.get("mywaytoopen"),
        ]
        if re.fullmatch(r"1\d{10}", phone_str):
            secrets.append(format(int(phone_str), "x"))
        template = profile.get("auto_login_template")
        if isinstance(template, dict):
            secrets.extend([
                template.get("tel"),
                template.get("xk"),
                template.get("imei"),
                template.get("ctid"),
                template.get("cid"),
                template.get("ak"),
            ])
            req_body = template.get("reqBody")
            if isinstance(req_body, dict):
                secrets.extend([
                    req_body.get("cellNum"),
                    req_body.get("loginNum"),
                    req_body.get("token"),
                    req_body.get("devToken"),
                    req_body.get("imei"),
                    req_body.get("caid"),
                ])
        for secret in secrets:
            if isinstance(secret, str) and len(secret) >= 6:
                cleaned = cleaned.replace(secret, "[已脱敏]")
    return PHONE_RE.sub(r"\1****\2", cleaned)


def validate_profile(data):
    if not isinstance(data, dict):
        raise RuntimeError("配置格式错误：顶层必须是 JSON 对象")
    required = (
        "auto_login_url", "auto_login_template", "xk", "phone",
        "province_code", "city_code", "source_id", "mywaytoopen",
    )
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise RuntimeError("配置缺少字段：" + ", ".join(missing))

    raw_url = str(data["auto_login_url"])
    if CONTROL_RE.search(raw_url):
        raise RuntimeError("auto_login_url 包含非法控制字符")
    url = raw_url.strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc or not parts.path.rstrip("/").endswith("/autoLogin"):
        raise RuntimeError("auto_login_url 必须是有效的 https .../autoLogin 地址")

    template = data["auto_login_template"]
    if not isinstance(template, dict):
        raise RuntimeError("auto_login_template 必须是 JSON 对象")
    raw_xk = str(data.get("xk") or "")
    if CONTROL_RE.search(raw_xk):
        raise RuntimeError("xk 包含非法控制字符")
    tpl_xk = str(template.get("xk") or "").strip()
    prof_xk = raw_xk.strip()
    if not tpl_xk or tpl_xk != prof_xk:
        raise RuntimeError("配置中的 xk 与 auto_login_template.xk 不一致")
    req_body = template.get("reqBody")
    if not isinstance(req_body, dict) or not req_body:
        raise RuntimeError("auto_login_template.reqBody 必须是非空对象")
    if "cellNum" in req_body and not str(req_body.get("cellNum") or "").strip():
        raise RuntimeError("auto_login_template.reqBody.cellNum 不能为空")

    phone = str(data["phone"]).strip()
    if not re.fullmatch(r"1\d{10}", phone):
        raise RuntimeError("phone 必须是 11 位手机号")
    raw_myway = str(data["mywaytoopen"])
    if CONTROL_RE.search(raw_myway) or not raw_myway.strip():
        raise RuntimeError("mywaytoopen 格式非法")
    myway = raw_myway.strip()

    normalized = dict(data)
    normalized["auto_login_url"] = url
    normalized["xk"] = prof_xk
    normalized["phone"] = phone
    normalized["mywaytoopen"] = myway
    for key in (
        "province_code",
        "city_code",
        "carrier_operator",
        "source_id",
        "app_version_code",
        "auto_login_user_agent",
        "sso_user_agent",
        "jsyd_user_agent",
    ):
        if key in normalized and normalized[key] is not None:
            normalized[key] = str(normalized[key]).strip()
    return normalized


def load_profile(path):
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"无法读取配置文件 {path}: {exc.strerror or exc}") from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError(f"配置文件不是合法 JSON: {path}") from exc
    return validate_profile(data)


def profile_hash(profile):
    canonical = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def default_state_path(profile_path):
    path = Path(profile_path)
    if path.suffix.lower() == ".json":
        return path.with_suffix(".state.json")
    return path.with_name(path.name + ".state.json")


def _format_iso(ts):
    return datetime.fromtimestamp(ts, tz=TZ_SHANGHAI).isoformat(timespec="seconds")


def _empty_state():
    return {
        "version": 1,
        "profile_hash": "",
        "locked": False,
        "lockout": None,
        "last_auto_login_at": None,
        "last_auto_login_at_iso": None,
        "last_result": None,
    }


@contextlib.contextmanager
def _state_lock(state_path):
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    if fcntl is None:  # pragma: no cover
        yield
        return
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock_path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _is_valid_timestamp(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_state(state_path):
    path = Path(state_path)
    if not path.exists():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"状态文件损坏或不可读（为避免绕过风控熔断已中止，请检查或执行 --clear-lockout）：{path}"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(
            f"状态文件格式异常（为避免绕过风控熔断已中止，请检查或执行 --clear-lockout）：{path}"
        )
    if "locked" in data and data["locked"] is not None and not isinstance(data["locked"], bool):
        raise RuntimeError(
            f"状态文件格式异常（locked 字段类型非法，已中止，请检查或执行 --clear-lockout）：{path}"
        )
    if "lockout" in data and data["lockout"] is not None and not isinstance(data["lockout"], dict):
        raise RuntimeError(
            f"状态文件格式异常（lockout 字段类型非法，已中止，请检查或执行 --clear-lockout）：{path}"
        )
    if "last_auto_login_at" in data and data["last_auto_login_at"] is not None:
        if not _is_valid_timestamp(data["last_auto_login_at"]):
            raise RuntimeError(
                f"状态文件格式异常（last_auto_login_at 字段类型非法，已中止，请检查或执行 --clear-lockout）：{path}"
            )
    if "profile_hash" in data and data["profile_hash"] is not None and not isinstance(data["profile_hash"], str):
        raise RuntimeError(
            f"状态文件格式异常（profile_hash 字段类型非法，已中止，请检查或执行 --clear-lockout）：{path}"
        )
    merged = _empty_state()
    merged.update(data)
    return merged


def save_state(state_path, state):
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state, ensure_ascii=False, indent=2)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".cmcc-state-", delete=False
        ) as fh:
            tmp_path = Path(fh.name)
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
        os.chmod(path, 0o600)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def inspect_guard_state(state, current_hash, now, min_interval):
    lockout = state.get("lockout") if isinstance(state.get("lockout"), dict) else None
    is_locked_flag = bool(state.get("locked"))
    lockout_hash = ""
    if lockout and lockout.get("profile_hash"):
        lockout_hash = str(lockout["profile_hash"])
    elif state.get("profile_hash"):
        lockout_hash = str(state["profile_hash"])

    locked = False
    auto_unlock = False
    if is_locked_flag:
        if lockout_hash and lockout_hash != current_hash:
            auto_unlock = True
        else:
            locked = True

    cooldown_remaining = 0.0
    last_ts = state.get("last_auto_login_at")
    if min_interval > 0 and last_ts is not None:
        if not _is_valid_timestamp(last_ts):
            cooldown_remaining = float(min_interval)
        else:
            elapsed = now - float(last_ts)
            if elapsed < min_interval:
                cooldown_remaining = min(float(min_interval), float(min_interval) - elapsed)

    return {
        "locked": locked,
        "auto_unlock": auto_unlock,
        "lockout": lockout,
        "cooldown_remaining": cooldown_remaining,
    }


def _format_lockout_block_msg(lockout):
    code = (lockout or {}).get("code") or "未知"
    hint = (lockout or {}).get("hint") or RISK_LOCKOUT_CODES.get(str(code), "风控/频控拦截")
    when = (lockout or {}).get("triggered_at_iso") or "未知时间"
    return (
        f"处于风控硬熔断状态（retCode={code}，{hint}，触发于 {when}），"
        "本次零请求退出。更换新 profile 后将自动解锁，或运行 --clear-lockout 手动解除。"
    )


def _format_cooldown_block_msg(remaining, min_interval):
    wait_sec = max(1, int(round(remaining)))
    return (
        f"跨进程冷却保护：距离上次 autoLogin 不足 {int(min_interval)} 秒，"
        f"仍需等待约 {wait_sec} 秒；本次零请求退出。"
    )


def check_and_reserve_auto_login(state_path, current_hash, min_interval, now_fn=None):
    """原子检查熔断与冷却并在发送 autoLogin 前占坑，防止并发/连发。"""
    clock = now_fn or time.time
    with _state_lock(state_path):
        state = load_state(state_path)
        now = float(clock())
        info = inspect_guard_state(state, current_hash, now, min_interval)
        if info["locked"]:
            raise GuardrailBlocked("lockout", _format_lockout_block_msg(info["lockout"]))

        if info["cooldown_remaining"] > 0:
            raise GuardrailBlocked(
                "cooldown",
                _format_cooldown_block_msg(info["cooldown_remaining"], min_interval),
            )

        unlocked_msg = None
        if info["auto_unlock"]:
            old_code = (info["lockout"] or {}).get("code") or "未知"
            unlocked_msg = f"检测到新 profile 哈希变更，已自动解除历史风控熔断（原 retCode={old_code}）。"
            state["locked"] = False
            state["lockout"] = None
            state["unlocked_reason"] = "profile_changed"
            state["unlocked_at"] = now
            state["unlocked_at_iso"] = _format_iso(now)

        state["profile_hash"] = current_hash
        state["last_auto_login_at"] = now
        state["last_auto_login_at_iso"] = _format_iso(now)
        state["last_result"] = "in_progress"
        save_state(state_path, state)
        return unlocked_msg


def record_lockout(state_path, current_hash, ret_code, ret_desc, profile=None, now_fn=None):
    clock = now_fn or time.time
    with _state_lock(state_path):
        try:
            state = load_state(state_path)
        except RuntimeError:
            state = _empty_state()
        now = float(clock())
        code = str(ret_code or "").strip()
        hint = RISK_LOCKOUT_CODES.get(code, "风控/频控拦截")
        clean_desc = sanitize_text(ret_desc, profile)[:120]
        state["profile_hash"] = current_hash
        state["locked"] = True
        state["lockout"] = {
            "code": code,
            "hint": hint,
            "desc": clean_desc,
            "triggered_at": now,
            "triggered_at_iso": _format_iso(now),
            "profile_hash": current_hash,
        }
        state["last_result"] = f"lockout:{code}"
        state["last_finished_at"] = now
        save_state(state_path, state)
        return state["lockout"]


def record_outcome(state_path, current_hash, result_label, now_fn=None):
    clock = now_fn or time.time
    with _state_lock(state_path):
        try:
            state = load_state(state_path)
        except RuntimeError:
            return
        now = float(clock())
        state["profile_hash"] = current_hash
        state["last_result"] = result_label
        state["last_finished_at"] = now
        save_state(state_path, state)


def clear_lockout(state_path, now_fn=None):
    path = Path(state_path)
    lock_path = path.with_name(path.name + ".lock")
    if not path.exists() and not path.is_symlink() and not lock_path.exists():
        return False
    clock = now_fn or time.time
    with _state_lock(state_path):
        if not path.exists() and not path.is_symlink():
            return False
        corrupted = False
        try:
            state = load_state(state_path)
        except RuntimeError:
            state = _empty_state()
            corrupted = True
        was_locked = bool(state.get("locked")) or corrupted
        now = float(clock())
        state["locked"] = False
        state["lockout"] = None
        state["unlocked_reason"] = "manual"
        state["unlocked_at"] = now
        state["unlocked_at_iso"] = _format_iso(now)
        save_state(state_path, state)
        return was_locked


def mint_session(profile, cookie=None, session=None):
    url = profile["auto_login_url"]
    template = profile["auto_login_template"]
    plain = json.dumps(template, separators=(",", ":"), ensure_ascii=False)
    headers = build_headers(
        url,
        plain,
        cookie,
        profile["xk"],
        resolve_auto_login_ua(profile),
    )
    client = session or new_session()
    response = client.post(url, data=encrypt_body(plain), headers=headers, timeout=25)
    payload = decrypt_response(response.content)
    if not isinstance(payload, dict) or payload.get("retCode") is None:
        raise AutoLoginError(
            ret_code="",
            ret_desc=f"响应无法解密（HTTP {response.status_code}）",
            http_status=response.status_code,
        )
    code = str(payload.get("retCode")).strip()
    desc = str(payload.get("retDesc") or "").strip()
    if code != "000000":
        raise AutoLoginError(ret_code=code, ret_desc=desc, http_status=response.status_code)
    set_cookie = response.headers.get("Set-Cookie")
    if not set_cookie:
        raise RuntimeError("autoLogin 未返回 Set-Cookie")
    return set_cookie


def exchange_qwhd(profile, app_cookie):
    session = new_session()
    session.headers.update({
        "user-agent": resolve_webview_ua(profile, "sso_user_agent", DEFAULT_SSO_UA),
        "accept-language": DEFAULT_ACCEPT_LANGUAGE,
    })
    act_url = profile.get("act_url", DEFAULT_ACT_URL)
    response = session.get(SSO_LOGIN, params={"dlwmh": "true", "actUrl": act_url}, timeout=30)
    match = re.search(r"loginPath\s*=\s*'([^']+)'", response.text)
    if not match:
        raise RuntimeError("SSO 登录页未返回 loginPath")
    login_url = QWHD_BASE + "/qwhdsso" + match.group(1)
    body = {
        "provinceCode": profile["province_code"],
        "cityCode": profile["city_code"],
        "userCheckId": format(int(profile["phone"]), "x"),
        "carrierOperator": profile.get("carrier_operator", "002"),
        "appVersionCode": resolve_app_version(profile),
        "took": random.randint(120, 900),
        "jwtToken": None,
        "token": app_cookie,
    }
    response = session.post(login_url, json=body, timeout=30)
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("appTokenLogin 返回非 JSON")
    if data.get("code") != "SUCCESS":
        raise RuntimeError(f"appTokenLogin 失败: {data.get('code')} {str(data.get('msg'))[:80]}")
    url = (data.get("data") or {}).get("url") or ""
    if not url.startswith(QWHD_BASE + "/"):
        raise RuntimeError("appTokenLogin 返回了非预期地址")
    session.get(url, timeout=30, allow_redirects=False)
    if not any(name.endswith("SESSION_TOKEN") for name in session.cookies.keys()):
        raise RuntimeError("appTokenLogin 未下发活动会话")
    return session, url


def get_jt_token(session, referer, source_id):
    response = session.get(
        QWHD_BASE + "/qwhdhub/user/getYDRZToken",
        params={"targetSourceId": source_id},
        headers=api_headers(referer),
        timeout=30,
    )
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("getYDRZToken 返回非 JSON")
    token = data.get("data")
    if data.get("code") != "SUCCESS" or not token:
        raise RuntimeError(f"getYDRZToken 失败: {data.get('code')}")
    return token


def jsyd_login(profile, jt_token):
    session = new_session()
    user_agent = resolve_webview_ua(profile, "jsyd_user_agent", DEFAULT_JSYD_UA)
    body = {
        "wapContext": {"bizCode": "JTWX10086LOGIN", "subBizCode": "login_KT", "optType": "1"},
        "jtToken": jt_token,
        "pageCode": "logintest",
        "tokenType": 3,
        "packageType": 2,
    }
    headers = {
        "accept": "*/*",
        "accept-language": DEFAULT_ACCEPT_LANGUAGE,
        "content-type": "application/json",
        "origin": "https://wap.js.10086.cn",
        "referer": "https://wap.js.10086.cn/hyl/content/super-market/market-index?channelId=10000000",
        "user-agent": user_agent,
    }
    response = session.post(JSYD_LOGIN, json=body, headers=headers, timeout=30)
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("jtWx10086AuthLogin 返回非 JSON")
    if str(data.get("code")) != "200" or str(data.get("success")) != "0":
        raise RuntimeError(f"jtWx10086AuthLogin 失败: {data.get('code')} {str(data.get('message'))[:80]}")
    return session


def act(session, profile, method, extra=""):
    myway = profile["mywaytoopen"]
    session.cookies.set("mywaytoopen", myway, domain=".js.10086.cn", path="/")
    data = (
        f"reqUrl=act2510&method={method}&operType=1&actCode=2510&isJtAPP=true"
        f"&env=jt_app&extendParams=&ywcheckcode=&mywaytoopen={myway}{extra}"
    )
    response = session.post(
        JSYD_ACTION,
        data=data,
        headers={
            "accept-language": DEFAULT_ACCEPT_LANGUAGE,
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://wap.js.10086.cn",
            "referer": JSYD_REFERER,
            "user-agent": resolve_webview_ua(profile, "jsyd_user_agent", DEFAULT_JSYD_UA),
        },
        timeout=30,
    )
    try:
        return response.json()
    except ValueError:
        raise RuntimeError(f"{method} 返回非 JSON（HTTP {response.status_code}）")


def streak_days(result):
    """从 toolSignList 计算截至今天的连续签到天数。"""
    signed = set()
    for item in result.get("toolSignList") or []:
        if not isinstance(item, dict):
            continue
        day = str(item.get("signDate") or "")
        state = str(item.get("signState") or item.get("state") or "")
        if day and state == "1":
            signed.add(day)
    if result.get("isSignToday") and result.get("today"):
        signed.add(str(result["today"]))
    if not signed:
        return 0
    today = str(result.get("today") or max(signed))
    try:
        cursor = datetime.strptime(today, "%Y%m%d").date()
    except ValueError:
        return 0
    if today not in signed:
        prior = [day for day in signed if day <= today]
        if not prior:
            return 0
        cursor = datetime.strptime(max(prior), "%Y%m%d").date()
    count = 0
    while cursor.strftime("%Y%m%d") in signed:
        count += 1
        cursor -= timedelta(days=1)
    return count


def connect(profile):
    app_cookie = mint_session(profile)
    qwhd, referer = exchange_qwhd(profile, app_cookie)
    jt_token = get_jt_token(qwhd, referer, profile["source_id"])
    return jsyd_login(profile, jt_token)


def send_feishu(title, body):
    app_id = os.environ.get("QL_FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("QL_FEISHU_APP_SECRET", "").strip()
    open_id = os.environ.get("QL_FEISHU_OPEN_ID", "").strip()
    if not (app_id and app_secret and open_id):
        return False
    try:
        auth = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret}, timeout=15,
        )
        auth_data = auth.json() if auth.ok else None
        token = auth_data.get("tenant_access_token") if isinstance(auth_data, dict) else None
        if not token:
            return False
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": open_id,
                "msg_type": "text",
                "content": json.dumps({"text": f"{title}\n\n{body}"}, ensure_ascii=False),
                "uuid": str(uuid.uuid4()),
            },
            timeout=15,
        )
        resp_data = resp.json()
        return isinstance(resp_data, dict) and resp_data.get("code") == 0
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return False


def run_dry_run(profile, state_path, current_hash, min_interval, now_fn=None):
    """纯离线校验：检查模板加密、冷启动签名头与当前熔断/冷却状态，零网络请求、不写状态。"""
    clock = now_fn or time.time
    url = profile["auto_login_url"]
    template = profile["auto_login_template"]
    plain = json.dumps(template, separators=(",", ":"), ensure_ascii=False)
    cipher = encrypt_body(plain)
    restored = _cbc(REQ_KEY, REQ_IV, base64.b64decode(cipher), False).decode("utf-8")
    if restored != plain:
        raise RuntimeError("离线自检失败：请求体 AES 往返不一致")

    ua = resolve_auto_login_ua(profile)
    headers = build_headers(url, plain, None, profile["xk"], ua)
    if "Cookie" in headers:
        raise RuntimeError("离线自检失败：冷启动不应发送 Cookie 头")
    expected_sign = hashlib.md5(
        f"{headers['x-token']}_{headers['x-time']}_{headers['x-nonce']}_null".encode()
    ).hexdigest()
    if headers["x-sign"] != expected_sign:
        raise RuntimeError("离线自检失败：冷启动 x-sign 校验不匹配")
    if headers.get("Accept-Language") != DEFAULT_ACCEPT_LANGUAGE:
        raise RuntimeError("离线自检失败：缺少 Accept-Language 头")

    state = load_state(state_path)
    info = inspect_guard_state(state, current_hash, float(clock()), min_interval)
    pkg = template.get("packageName") or "-"
    cv = template.get("cv") or "-"
    app_ver = resolve_app_version(profile)
    phone_tail = str(profile["phone"])[-4:]

    print("[dry-run] 离线配置与冷启动签名校验通过（未发起任何网络请求，未修改状态文件）")
    print(f"[dry-run] auto_login_url={safe_url_for_log(url)}")
    print(f"[dry-run] app: packageName={pkg} template_cv={cv} app_version_code={app_ver}")
    print(f"[dry-run] auto_login_ua={ua}")
    print(f"[dry-run] phone=尾号{phone_tail} profile_hash={current_hash[:12]}")
    if info["locked"]:
        print("[dry-run] 风控状态：" + _format_lockout_block_msg(info["lockout"]))
    elif info["auto_unlock"]:
        old_code = (info["lockout"] or {}).get("code") or "未知"
        print(f"[dry-run] 风控状态：检测到新 profile 哈希变更，正式运行时将自动解除原熔断（retCode={old_code}）")
    else:
        print("[dry-run] 风控状态：正常（未熔断）")
    if info["cooldown_remaining"] > 0:
        print(f"[dry-run] 冷却状态：剩余约 {max(1, int(round(info['cooldown_remaining'])))} 秒（最小间隔 {int(min_interval)} 秒）")
    else:
        print(f"[dry-run] 冷却状态：可立即调用（最小间隔 {int(min_interval)} 秒）")
    return 0


def _env_int(name, default):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"环境变量 {name} 必须是整数: {raw!r}") from exc


def maybe_startup_delay(args, sleep_fn=None, randint_fn=None, now_fn=None):
    if args.now or args.check or args.dry_run:
        return 0
    if args.delay_max <= 0:
        return 0
    sleeper = sleep_fn or time.sleep
    rand = randint_fn or random.randint
    clock = now_fn or time.time
    wait = rand(args.delay_min, args.delay_max)
    if wait <= 0:
        return 0
    planned = datetime.fromtimestamp(float(clock()) + wait, tz=TZ_SHANGHAI).strftime("%H:%M:%S")
    print(f"非整点随机等待 {wait // 60} 分 {wait % 60} 秒，预计北京时间 {planned} 开始。", flush=True)
    sleeper(wait)
    return wait


def main(argv):
    parser = argparse.ArgumentParser(description="中国移动江苏 act2510 自动签到")
    parser.add_argument("--check", action="store_true", help="只查状态，不签到（跳过随机延迟）")
    parser.add_argument("--dry-run", action="store_true", help="纯离线校验配置、签名与风控状态，不发任何请求")
    parser.add_argument("--now", action="store_true", help="跳过非整点随机启动延迟立即执行")
    parser.add_argument("--clear-lockout", action="store_true", help="清除持久化风控熔断状态并退出（不发网络请求）")
    parser.add_argument("--profile", default="")
    parser.add_argument("--state-file", default="")
    parser.add_argument(
        "--min-interval",
        type=int,
        default=None,
        help="跨进程最小 autoLogin 调用间隔秒数（默认 300）",
    )
    parser.add_argument(
        "--delay-min",
        type=int,
        default=None,
        help="非整点随机启动延迟下限秒数（默认 30）",
    )
    parser.add_argument(
        "--delay-max",
        type=int,
        default=None,
        help="非整点随机启动延迟上限秒数（默认 900）",
    )
    args = parser.parse_args(argv)

    try:
        if args.min_interval is None:
            args.min_interval = _env_int("CMCC_MIN_INTERVAL", DEFAULT_MIN_INTERVAL)
        if args.delay_min is None:
            args.delay_min = _env_int("CMCC_DELAY_MIN", DEFAULT_DELAY_MIN)
        if args.delay_max is None:
            args.delay_max = _env_int("CMCC_DELAY_MAX", DEFAULT_DELAY_MAX)
    except ValueError as exc:
        print("参数错误：" + str(exc))
        return 1

    if args.min_interval < 0:
        print("参数错误：--min-interval 不能为负数")
        return 1
    if args.delay_min < 0 or args.delay_max < 0 or args.delay_min > args.delay_max:
        print("参数错误：--delay-min / --delay-max 范围无效")
        return 1

    args.profile = (args.profile or "").strip() or os.environ.get("CMCC_PROFILE", "").strip() or DEFAULT_PROFILE
    state_arg = (args.state_file or "").strip() or os.environ.get("CMCC_STATE_FILE", "").strip()
    state_path = Path(state_arg) if state_arg else default_state_path(args.profile)

    if args.clear_lockout:
        try:
            was_locked = clear_lockout(state_path)
        except Exception as exc:  # noqa: BLE001
            print("清除风控熔断状态失败：" + sanitize_text(str(exc)))
            return 1
        if was_locked:
            print(f"已清除风控熔断状态：{state_path}（纯本地操作，未发起网络请求）")
        else:
            print(f"当前未处于风控熔断状态：{state_path}（纯本地操作，未发起网络请求）")
        if not args.dry_run:
            return 0

    try:
        profile = load_profile(args.profile)
        current_hash = profile_hash(profile)
    except Exception as exc:  # noqa: BLE001
        print("配置校验失败：" + sanitize_text(str(exc)))
        return 1

    if args.dry_run:
        try:
            return run_dry_run(profile, state_path, current_hash, args.min_interval)
        except Exception as exc:  # noqa: BLE001
            print("[dry-run] 失败：" + sanitize_text(str(exc), profile))
            return 1

    try:
        # 延迟前先做只读快速拦截：已熔断或仍在冷却期内直接零请求退出
        pre_state = load_state(state_path)
        pre_info = inspect_guard_state(pre_state, current_hash, time.time(), args.min_interval)
        if pre_info["locked"]:
            raise GuardrailBlocked("lockout", _format_lockout_block_msg(pre_info["lockout"]))
        if pre_info["cooldown_remaining"] > 0:
            raise GuardrailBlocked(
                "cooldown",
                _format_cooldown_block_msg(pre_info["cooldown_remaining"], args.min_interval),
            )

        maybe_startup_delay(args)

        unlocked_msg = check_and_reserve_auto_login(state_path, current_hash, args.min_interval)
        if unlocked_msg:
            print(unlocked_msg)
    except GuardrailBlocked as exc:
        print(str(exc))
        return 2
    except Exception as exc:  # noqa: BLE001
        print("风控状态检查失败：" + sanitize_text(str(exc), profile))
        return 1

    try:
        session = connect(profile)
        init = act(session, profile, "initIndexPage")
        result = init.get("resultObj") or {}
        if str(init.get("resultCode")) != "1" or not result.get("isLogin"):
            raise RuntimeError("活动会话未登录")
        already = bool(result.get("isSignToday"))
        month = result.get("monthSignCnt")
        streak = streak_days(result)
        print(f"登录=成功 今日已签到={already} 连续签到={streak}天 本月已签={month}天")

        if args.check:
            record_outcome(state_path, current_hash, "check_ok")
            return 0

        if already:
            body = f"今日已签到，已连续签到 {streak} 天，本月已签到 {month} 天。"
            title = "中国移动签到 · 已签到"
            record_outcome(state_path, current_hash, "already_signed")
        else:
            sign = act(session, profile, "doSign", "&fxmobile=")
            if str(sign.get("resultCode")) != "1":
                raise RuntimeError(f"doSign 失败: resultCode={sign.get('resultCode')}")
            after = act(session, profile, "initIndexPage")
            after_obj = after.get("resultObj") or {}
            if not after_obj.get("isSignToday"):
                raise RuntimeError("doSign 后仍未确认今日签到")
            month = after_obj.get("monthSignCnt", month)
            streak = streak_days(after_obj)
            body = f"签到成功，已连续签到 {streak} 天，本月已签到 {month} 天。"
            title = "中国移动签到 · 成功"
            record_outcome(state_path, current_hash, "signed")
        print(body)
        print("飞书通知已发送" if send_feishu(title, body) else "未配置或发送失败飞书通知")
        return 0
    except AutoLoginError as exc:
        if exc.is_risk_lockout:
            persist_err = None
            try:
                lockout = record_lockout(state_path, current_hash, exc.ret_code, exc.ret_desc, profile=profile)
            except OSError as io_exc:
                persist_err = str(io_exc)
                code = str(exc.ret_code or "").strip()
                lockout = {
                    "code": code,
                    "hint": RISK_LOCKOUT_CODES.get(code, "风控/频控拦截"),
                    "desc": sanitize_text(exc.ret_desc, profile)[:120],
                }
            alert = (
                f"命中风控/频控码 retCode={lockout['code']}（{lockout['hint']}），"
                f"已触发持久化硬熔断（profile={current_hash[:12]}）。\n"
                f"后续定时任务将自动零请求退出，避免升级人脸校验。\n"
                f"处置：请在真机 App 确认正常后重新抓包更新 profile（哈希变更后自动解锁），"
                f"或人工确认后执行 --clear-lockout。"
            )
            if persist_err:
                alert = f"{alert}\n警告：熔断状态落盘失败（{sanitize_text(persist_err, profile)}），请立即手工停用定时任务！"
            if lockout.get("desc"):
                alert = f"{alert}\n服务端描述：{lockout['desc']}"
            print("风控熔断：" + alert)
            print("飞书风控告警已发送" if send_feishu("中国移动签到 · 风控熔断", alert) else "未配置或发送失败飞书风控告警")
            return 2
        record_outcome(state_path, current_hash, f"autologin_error:{exc.ret_code or exc.http_status}")
        message = sanitize_text(f"{type(exc).__name__}: {exc}", profile)
        print("任务失败：" + message)
        send_feishu("中国移动签到 · 失败", message)
        return 1
    except Exception as exc:  # noqa: BLE001 - 单次任务失败要通知
        record_outcome(state_path, current_hash, f"error:{type(exc).__name__}")
        message = sanitize_text(f"{type(exc).__name__}: {exc}", profile)
        print("任务失败：" + message)
        send_feishu("中国移动签到 · 失败", message)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
