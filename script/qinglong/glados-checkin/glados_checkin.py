#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GLaDOS 每日签到（青龙 / 本地通用，2026-11 接口）。

抓包结论（详见同目录 README.md）：
  1. GET  /api/user/checkin/challenge  -> {code:0, nonce, ttl, turnstile?}
  2. 等待至少 2.5 秒（页面实现为 2.5s，服务端会校验时间差）
  3. proof = SHA-256(nonce + ".glados-observe-v1")
  4. POST /api/user/checkin            -> {token: 域名, nonce, proof, [turnstile]}
     页面还会附带 tsState；纯 API 模式不提供 Turnstile 令牌时省略。

环境变量：
  GLADOS_COOKIE       单账号 Cookie（必须包含 gld:sess 与 gld:sess.sig）
  GLADOS_COOKIES      多账号，每行一个 Cookie（# 开头为注释）
  GLADOS_USER_AGENT   与登录时一致的单行 User-Agent（设备校验依赖它）
  GLADOS_USER_AGENTS  多账号 UA，每行一个，按顺序与 GLADOS_COOKIES 对应
  GLADOS_MODE         auto（默认）| api | browser
  GLADOS_BROWSER_HEADLESS  1（默认，服务器）| 0（本机有桌面时通过率更高）
  GLADOS_BROWSER_TIMEOUT   浏览器等待秒数，默认 150
  GLADOS_DOMAINS      逗号分隔，默认 https://glados.cloud,https://glados.rocks
  GLADOS_DELAY        账号间隔秒数，默认 3

推送（可选，均为青龙常用变量）：
  PUSHPLUS_TOKEN | SERVERCHAN_SENDKEY | TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID

用法：
  python3 glados_checkin.py --check     # 只读：校验 Cookie / 查询积分，不签到
  python3 glados_checkin.py             # 正常签到
  python3 glados_checkin.py --self-test # 校验 proof 算法
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlsplit

try:
    import requests
except ImportError:  # pragma: no cover
    sys.stderr.write("缺少 requests：pip3 install requests\n")
    raise

PROOF_SALT = ".glados-observe-v1"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_DOMAINS = "https://glados.cloud,https://glados.rocks"
MIN_CHALLENGE_WAIT = 2.7
HTTP_TIMEOUT = 15
PROOF_TEST_VECTOR = "abc.glados-observe-v1"
PROOF_TEST_DIGEST = "2ee3c3966bb1071c8a0888be3c4613013b7ae4f7a035f683321c8e82e85081f8"
REPEAT_MARKERS = ("checkin repeats", "today's observation logged", "已签到")
SUCCESS_MARKERS = ("checkin! got",)


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def mask_cookie(cookie):
    parts = []
    for item in cookie.split(";"):
        name, sep, _ = item.strip().partition("=")
        if sep and name:
            parts.append(f"{name}=***")
    return "; ".join(parts) or "<empty>"


def proof_for(nonce):
    return hashlib.sha256((nonce + PROOF_SALT).encode("utf-8")).hexdigest()


def fmt_number(raw, signed=False):
    """服务端返回 40.0000000000000000 这类浮点，输出前收敛成 40 / +2。"""
    try:
        num = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    if abs(num - round(num)) < 1e-9:
        value = int(round(num))
        return (f"+{value}" if value >= 0 else str(value)) if signed else str(value)
    text = f"{num:.4f}".rstrip("0").rstrip(".")
    if signed and num >= 0:
        text = "+" + text
    return text


def today_gain(points_res):
    """从积分流水汇总今日正变动（排除兑换/退款），无法判断时返回 None。"""
    history = points_res.get("history")
    if not isinstance(history, list):
        return None
    today = datetime.now().strftime("%Y-%m-%d")
    total = 0.0
    found = False
    for item in history:
        if not isinstance(item, dict):
            continue
        ts = item.get("time")
        if not isinstance(ts, (int, float)):
            continue
        try:
            day = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            change = float(item.get("change") or 0)
        except (ValueError, OSError):
            continue
        business = str(item.get("business", "")).lower()
        if day == today and change > 0 and "exchange" not in business and "refund" not in business:
            total += change
            found = True
    return total if found else None


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

def load_accounts():
    """返回 [(cookie, user_agent), ...]，保持输入顺序。"""
    cookies = []
    for line in os.environ.get("GLADOS_COOKIES", "").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            cookies.append(line)
    single = os.environ.get("GLADOS_COOKIE", "").strip()
    if single:
        cookies.insert(0, single)
    # 去重但保留顺序
    cookies = list(dict.fromkeys(cookies))

    uas = [x.strip() for x in os.environ.get("GLADOS_USER_AGENTS", "").splitlines() if x.strip()]
    default_ua = os.environ.get("GLADOS_USER_AGENT", "").strip() or DEFAULT_USER_AGENT

    accounts = []
    for idx, cookie in enumerate(cookies):
        ua = uas[idx] if idx < len(uas) else default_ua
        accounts.append((cookie, ua))
    return accounts


def load_domains():
    raw = os.environ.get("GLADOS_DOMAINS", DEFAULT_DOMAINS)
    domains = [d.strip().rstrip("/") for d in raw.split(",") if d.strip()]
    return domains or [d.strip() for d in DEFAULT_DOMAINS.split(",")]


def browser_headers(ua):
    """构造与登录浏览器一致的请求头；设备校验通常与 UA 绑定。"""
    headers = {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json;charset=UTF-8",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    m = re.search(r"(?:Chrome|Chromium)/(\d+)", ua)
    if m:
        major = m.group(1)
        if "Macintosh" in ua:
            platform = "macOS"
        elif "Windows" in ua:
            platform = "Windows"
        elif "Android" in ua:
            platform = "Android"
        elif "Linux" in ua:
            platform = "Linux"
        else:
            platform = "Unknown"
        headers.update({
            "Sec-CH-UA": f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not_A Brand";v="99"',
            "Sec-CH-UA-Mobile": "?1" if "Mobile" in ua else "?0",
            "Sec-CH-UA-Platform": f'"{platform}"',
        })
    return headers


# ---------------------------------------------------------------------------
# 单次 API 调用
# ---------------------------------------------------------------------------

def api_call(session, method, path, cookie, ua, domain, payload=None, timeout=HTTP_TIMEOUT):
    url = f"{domain}{path}"
    headers = browser_headers(ua)
    headers["Cookie"] = cookie
    headers["Origin"] = domain
    headers["Referer"] = f"{domain}/console/checkin"
    try:
        if method == "GET":
            resp = session.get(url, headers=headers, timeout=timeout)
        else:
            resp = session.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        # 异常文本可能包含请求头，只记录类型
        return {"request_failed": True, "error": type(exc).__name__}

    data = None
    try:
        data = resp.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        data = {}
    data["http_status"] = resp.status_code
    if resp.status_code in (401, 403):
        data.setdefault("reason", "http-auth-rejected")
    return data


def call_with_domains(session, method, path, cookie, ua, domains, payload=None):
    last = {"request_failed": True, "reason": "request-failed"}
    for domain in domains:
        result = api_call(session, method, path, cookie, ua, domain, payload)
        if result.get("http_status") == 200 and "code" in result:
            return result, domain
        if result.get("http_status") in (401, 403):
            # 认证被拒时不要换域重放
            return result, domain
        last = result
    return last, domains[0]


# ---------------------------------------------------------------------------
# 签到
# ---------------------------------------------------------------------------

def classify(result):
    """返回 success / repeat / turnstile / device-mismatch / auth / failed。"""
    if not isinstance(result, dict) or result.get("request_failed"):
        return "failed"
    reason = str(result.get("reason", "")).lower()
    message = str(result.get("message", "")).lower()
    code = result.get("code")

    if reason == "turnstile" or "cloudflare verification failed" in message:
        return "turnstile"
    if reason == "device-mismatch":
        return "device-mismatch"
    if code == -2 or result.get("http_status") in (401, 403) or "没有权限" in message:
        return "auth"
    if code == 1 or result.get("repeated") is True or any(m in message for m in REPEAT_MARKERS):
        return "repeat"
    if code == 0 or any(m in message for m in SUCCESS_MARKERS):
        return "success"
    return "failed"


def describe(result):
    code = result.get("code")
    reason = result.get("reason")
    message = str(result.get("message", ""))[:160]
    parts = []
    if code is not None:
        parts.append(f"code={code}")
    if reason:
        parts.append(f"reason={reason}")
    if message:
        parts.append(f"message={message}")
    return ", ".join(parts) or "no-json-body"


def api_checkin(session, cookie, ua, domains):
    """纯 API 流程：challenge -> 等待 -> proof -> POST。"""
    challenge, domain = call_with_domains(
        session, "GET", "/api/user/checkin/challenge", cookie, ua, domains
    )
    status = classify(challenge)
    if status in ("auth", "device-mismatch"):
        return challenge
    nonce = challenge.get("nonce")
    ttl = challenge.get("ttl", 300000)
    if challenge.get("code") != 0 or not isinstance(nonce, str) or not nonce:
        challenge["reason"] = challenge.get("reason") or "challenge-unavailable"
        return challenge
    if not isinstance(ttl, (int, float)) or ttl <= MIN_CHALLENGE_WAIT * 1000:
        return {"request_failed": True, "reason": "challenge-ttl-invalid"}

    if challenge.get("turnstile"):
        log(f"    服务端已下发 Turnstile 站点密钥，纯 API 可能被拒（reason=turnstile）")

    received = time.monotonic()
    time.sleep(MIN_CHALLENGE_WAIT)
    if (time.monotonic() - received) * 1000 >= ttl:
        return {"request_failed": True, "reason": "challenge-expired"}

    payload = {
        "token": urlsplit(domain).hostname,
        "nonce": nonce,
        "proof": proof_for(nonce),
    }
    # nonce 绑定签发域，POST 不换域重放
    result = api_call(session, "POST", "/api/user/checkin", cookie, ua, domain, payload)
    return result


def browser_checkin(cookie, ua, domains, account_idx, user_agent_override=None):
    """真浏览器兜底：注入 Cookie -> 打开签到页 -> 点击签到按钮。

    复用真实 Chrome/Edge 与持久化 profile，让页面自己完成 Turnstile。
    青龙等无桌面环境默认无头；Turnstile 通过率取决于出口 IP 与浏览器环境。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"request_failed": True, "reason": "playwright-not-installed"}

    headless = os.environ.get("GLADOS_BROWSER_HEADLESS", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )
    wait_seconds = int(os.environ.get("GLADOS_BROWSER_TIMEOUT", "150") or "150")
    profile = os.path.join(
        os.path.expanduser("~"), ".cache", "glados-checkin",
        "profile-" + hashlib.sha1(cookie.encode()).hexdigest()[:10] + f"-{account_idx}",
    )
    os.makedirs(profile, exist_ok=True)
    button_re = re.compile(r"签到|check\s*in", re.IGNORECASE)
    captured = {"json": None, "domain": None}

    with sync_playwright() as pw:
        context, channel = None, None
        errors = []
        for candidate in ("chrome", "msedge", None):
            kwargs = {
                "user_data_dir": profile,
                "headless": headless,
                "args": ["--disable-blink-features=AutomationControlled",
                         "--no-first-run", "--no-default-browser-check"],
            }
            if candidate:
                kwargs["channel"] = candidate
            if user_agent_override:
                kwargs["user_agent"] = user_agent_override
            try:
                context, channel = pw.chromium.launch_persistent_context(**kwargs), candidate
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{candidate or 'chromium'}:{type(exc).__name__}")
        if context is None:
            return {"request_failed": True, "reason": "browser-unavailable",
                    "detail": ";".join(errors)}

        log(f"    浏览器通道：{channel or 'chromium'}（headless={headless}）")
        try:
            for domain in domains:
                page = None
                try:
                    for item in cookie.split(";"):
                        name, sep, value = item.strip().partition("=")
                        if not sep or not name:
                            continue
                        spec = {"name": name, "value": value, "url": domain + "/"}
                        if name in ("gld:sess", "gld:sess.sig", "koa:sess", "koa:sess.sig"):
                            spec.update({"secure": True, "httpOnly": True, "sameSite": "Lax"})
                        context.add_cookies([spec])

                    page = context.new_page()
                    page.on(
                        "response",
                        lambda resp: captured.update({
                            "json": _safe_json(resp),
                            "domain": domain,
                        }) if (
                            resp.url.startswith(domain)
                            and "/api/user/checkin" in resp.url
                            and resp.request.method == "POST"
                        ) else None,
                    )
                    page.goto(domain + "/console/checkin",
                              wait_until="domcontentloaded", timeout=45000)

                    btn = None
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline and not captured["json"]:
                        try:
                            candidate = page.get_by_role("button", name=button_re).first
                            if candidate.count() and not candidate.is_disabled():
                                btn = candidate
                                break
                        except Exception:  # noqa: BLE001
                            pass
                        page.wait_for_timeout(500)

                    if captured["json"]:
                        return captured["json"]
                    if btn is None:
                        log(f"    {domain} 未找到可点击的签到按钮，尝试下一个域名")
                        continue

                    log("    点击签到，等待页面完成验证……")
                    with page.expect_response(
                        lambda r: r.url.startswith(domain)
                        and "/api/user/checkin" in r.url
                        and r.request.method == "POST",
                        timeout=wait_seconds * 1000,
                    ) as info:
                        btn.click()
                    result = _safe_json(info.value)
                    return result or {"request_failed": True, "reason": "empty-response"}
                finally:
                    if page:
                        try:
                            page.close()
                        except Exception:  # noqa: BLE001
                            pass
            return {"request_failed": True, "reason": "browser-checkin-failed"}
        finally:
            try:
                context.close()
            except Exception:  # noqa: BLE001
                pass


def _safe_json(resp):
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# 状态查询与推送
# ---------------------------------------------------------------------------

def account_overview(session, cookie, ua, domains):
    status, domain = call_with_domains(session, "GET", "/api/user/status", cookie, ua, domains)
    email = "?"
    left_days = "?"
    if isinstance(status.get("data"), dict):
        email = str(status["data"].get("email", "?"))
        left_days = str(status["data"].get("leftDays", "?")).split(".")[0]
    points_res, domain = call_with_domains(session, "GET", "/api/user/points", cookie, ua, domains)
    points = fmt_number(points_res.get("points", "?"))
    gain = today_gain(points_res)
    return email, left_days, points, fmt_number(gain, signed=True) if gain is not None else None


def send_push(title, content):
    ok = False
    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if token:
        try:
            r = requests.post("https://www.pushplus.plus/send", json={
                "token": token, "title": title, "content": content, "template": "html",
            }, timeout=10)
            ok = r.status_code == 200
        except requests.RequestException:
            pass
    sendkey = os.environ.get("SERVERCHAN_SENDKEY", "").strip()
    if sendkey:
        try:
            r = requests.post(
                f"https://sctapi.ftqq.com/{sendkey}.send",
                data={"title": title, "desp": content}, timeout=10,
            )
            ok = r.status_code == 200 or ok
        except requests.RequestException:
            pass
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if tg_token and tg_chat:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={"chat_id": tg_chat, "text": f"{title}\n{content}"}, timeout=10,
            )
            ok = r.status_code == 200 or ok
        except requests.RequestException:
            pass
    return ok


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run_account(idx, cookie, ua, domains, mode, check_only):
    tag = f"账号{idx + 1}"
    session = requests.Session()
    log(f"===== {tag} 开始 =====")
    log(f"Cookie: {mask_cookie(cookie)}")

    email, left_days, points, gain = account_overview(session, cookie, ua, domains)
    overview_ok = not (email == "?" and points == "?")
    if not overview_ok:
        log(f"{tag} 只读查询失败：Cookie 可能已过期，或 UA 与登录设备不一致")
    else:
        gain_text = f"，今日 {gain}" if gain else ""
        log(f"{tag} {email} 剩余 {left_days} 天，当前积分 {points}{gain_text}")

    if check_only:
        return {"tag": tag, "status": "check-only" if overview_ok else "auth",
                "email": email, "days": left_days, "points": points, "gain": gain}

    if mode == "browser":
        result = browser_checkin(cookie, ua, domains, idx)
    else:
        result = api_checkin(session, cookie, ua, domains)
    status = classify(result)
    if status == "turnstile" and mode == "auto":
        log(f"{tag} API 被 Turnstile 拒绝，切换到浏览器兜底")
        result = browser_checkin(cookie, ua, domains, idx)
        status = classify(result)
    if status == "device-mismatch" and mode in ("auto", "browser"):
        # 浏览器默认 UA 与登录 UA 不同会导致设备校验失败，用配置的 UA 再试一次
        log(f"{tag} 设备不一致，使用 GLADOS_USER_AGENT 重试浏览器通道")
        result = browser_checkin(cookie, ua, domains, idx, user_agent_override=ua)
        status = classify(result)

    if status in ("success", "repeat"):
        email, left_days, points, gain = account_overview(session, cookie, ua, domains)
        gain_text = f"，今日 {gain}" if gain else ""
        log(f"{tag} 签到成功（{status}），积分 {points}{gain_text}，剩余 {left_days} 天")
    elif status == "turnstile":
        log(f"{tag} 被 Cloudflare Turnstile 拦截：{describe(result)}")
        log("    处理：换用住宅/家宽出口，或在本机有桌面环境用 GLADOS_MODE=browser")
    elif status == "device-mismatch":
        log(f"{tag} 设备校验失败（device-mismatch）：{describe(result)}")
        log("    处理：把 GLADOS_USER_AGENT 设为登录该账号时的浏览器 UA，再重新登录官网刷新 Cookie")
    elif status == "auth":
        log(f"{tag} 认证失败：{describe(result)}")
    else:
        log(f"{tag} 签到失败：{describe(result)}")

    return {"tag": tag, "status": status, "email": email,
            "days": left_days, "points": points, "gain": gain,
            "detail": describe(result)}


def main(argv):
    if "--self-test" in argv:
        got = hashlib.sha256(PROOF_TEST_VECTOR.encode()).hexdigest()
        assert got == PROOF_TEST_DIGEST, f"proof 算法不匹配: {got}"
        log("self-test OK: SHA-256(nonce + '.glados-observe-v1')")
        return 0

    check_only = "--check" in argv or "--dry-run" in argv
    mode = os.environ.get("GLADOS_MODE", "auto").strip().lower()
    if mode not in ("auto", "api", "browser"):
        mode = "auto"
    domains = load_domains()
    accounts = load_accounts()
    if not accounts:
        log("未配置 GLADOS_COOKIE / GLADOS_COOKIES，退出")
        return 2

    results = []
    for idx, (cookie, ua) in enumerate(accounts):
        try:
            results.append(run_account(idx, cookie, ua, domains, mode, check_only))
        except Exception as exc:  # noqa: BLE001 - 单账号异常不阻断其他账号
            log(f"账号{idx + 1} 运行异常：{type(exc).__name__}: {exc}")
            results.append({"tag": f"账号{idx + 1}", "status": "error",
                            "detail": type(exc).__name__})
        if idx + 1 < len(accounts):
            time.sleep(float(os.environ.get("GLADOS_DELAY", "3") or "3"))

    if not check_only:
        lines = []
        for r in results:
            lines.append(
                f"{r['tag']}: {r['status']} | 积分 {r.get('points', '?')} | "
                f"今日 {r.get('gain') or '0'} | 剩余 {r.get('days', '?')} 天"
            )
        body = "\n".join(lines)
        log("----- 汇总 -----\n" + body)
        send_push("GLaDOS 签到结果", body)

    ok_status = {"success", "repeat", "check-only"}
    return 0 if all(r["status"] in ok_status for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
