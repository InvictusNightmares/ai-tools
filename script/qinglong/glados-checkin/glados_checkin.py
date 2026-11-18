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
import uuid
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


TURNSTILE_HOST = "challenges.cloudflare.com"


def _turnstile_widget_box(page):
    """返回可见 Turnstile 组件的坐标；隐藏的 1x1 挑战帧会被跳过。"""
    for frame in page.frames:
        if TURNSTILE_HOST not in (frame.url or ""):
            continue
        try:
            box = frame.frame_element().bounding_box()
        except Exception:  # noqa: BLE001 - 跨域帧偶尔不可读
            continue
        if box and box.get("width", 0) > 10 and box.get("height", 0) > 10:
            return box
    return None


def _click_turnstile(page):
    """点击 Turnstile 复选框。页面把组件渲染在跨域 iframe 里，
    内部 DOM 不可读，但按组件坐标点击左侧复选框区域即可。"""
    box = _turnstile_widget_box(page)
    if not box:
        return False
    page.mouse.click(box["x"] + 30, box["y"] + box["height"] / 2)
    return True


def _add_glados_cookies(context, cookie, domain):
    for item in cookie.split(";"):
        name, sep, value = item.strip().partition("=")
        if not sep or not name:
            continue
        spec = {"name": name, "value": value, "url": domain + "/"}
        if name.startswith("gld:") or name.startswith("koa:"):
            spec.update({"secure": True, "httpOnly": True, "sameSite": "Lax"})
        context.add_cookies([spec])


def _apply_mac_ua_metadata(page, ua):
    """远程 Linux Chrome 需要同时伪装 UA-CH，否则 Turnstile 易判环境不一致。"""
    match = re.search(r"Chrome/(\d+)", ua or "")
    if "Macintosh" not in (ua or "") or not match:
        return
    major = match.group(1)
    try:
        cdp = page.context.new_cdp_session(page)
        cdp.send("Emulation.setUserAgentOverride", {
            "userAgent": ua,
            "acceptLanguage": "zh-CN,zh;q=0.9,en;q=0.8",
            "platform": "MacIntel",
            "userAgentMetadata": {
                "brands": [
                    {"brand": "Chromium", "version": major},
                    {"brand": "Google Chrome", "version": major},
                    {"brand": "Not_A Brand", "version": "99"},
                ],
                "fullVersionList": [
                    {"brand": "Chromium", "version": f"{major}.0.0.0"},
                    {"brand": "Google Chrome", "version": f"{major}.0.0.0"},
                    {"brand": "Not_A Brand", "version": "99.0.0.0"},
                ],
                "fullVersion": f"{major}.0.0.0",
                "platform": "macOS",
                "platformVersion": "10.15.7",
                "architecture": "x86",
                "model": "",
                "mobile": False,
                "bitness": "64",
                "wow64": False,
            },
        })
    except Exception:  # noqa: BLE001 - 元数据伪装失败不阻断主流程
        pass


def _remote_browser(pw):
    """连接 Browserless/远程 Chrome；未配置时返回 None。"""
    ws = os.environ.get("GLADOS_BROWSER_WS", "").strip()
    if not ws:
        return None
    token = os.environ.get("GLADOS_BROWSER_TOKEN", "").strip()
    if token:
        ws += ("&" if "?" in ws else "?") + "token=" + token
    params = "headless=false&stealth=true&--disable-blink-features=AutomationControlled"
    ws += ("&" if "?" in ws else "?") + params
    return pw.chromium.connect(ws, timeout=60000)


def _browser_flow(page, cookie, ua, domain, wait_seconds, remote):
    """打开签到页 -> 点击签到 -> 点 Turnstile 复选框 -> 等 POST 响应。"""
    if remote:
        _apply_mac_ua_metadata(page, ua)
    page.bring_to_front()
    page.goto(domain + "/console/checkin", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)  # 页面挂载时先取 challenge，给它一点时间渲染组件

    button_re = re.compile(r"签到|check\s*in", re.IGNORECASE)
    btn = None
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            candidate = page.get_by_role("button", name=button_re).first
            if candidate.count() and not candidate.is_disabled():
                btn = candidate
                break
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(500)
    if btn is None:
        return None

    captured = {}
    page.on(
        "response",
        lambda resp: captured.update({"json": _safe_json(resp)}) if (
            resp.url.startswith(domain)
            and "/api/user/checkin" in resp.url
            and resp.request.method == "POST"
        ) else None,
    )

    log("    点击签到，等待页面完成验证……")
    btn.click()
    clicked_ts = False
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if captured.get("json"):
            break
        if not clicked_ts:
            clicked_ts = _click_turnstile(page)
            if clicked_ts:
                log("    已点击 Turnstile 人机验证复选框")
        page.wait_for_timeout(500)
    return captured.get("json")


def browser_checkin(cookie, ua, domains, account_idx, user_agent_override=None):
    """浏览器签到：优先连接远程 Browserless，否则本机启动 Chrome/Edge。

    远程模式需要 GLADOS_BROWSER_WS（如 ws://host:3000/chrome/playwright）
    和 GLADOS_BROWSER_TOKEN；本机模式使用持久化 profile + 系统 Chrome。
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

    with sync_playwright() as pw:
        remote = False
        browser = None
        context = None
        try:
            browser = _remote_browser(pw)
        except Exception as exc:  # noqa: BLE001
            log(f"    远程浏览器连接失败：{type(exc).__name__}，回退本机")

        if browser is not None:
            remote = True
            context = browser.new_context(
                user_agent=ua or None, locale="zh-CN", timezone_id="Asia/Shanghai",
            )
            log("    浏览器通道：远程 Browserless（headed）")
        else:
            channel = None
            errors = []
            for candidate in ("chrome", "msedge", None):
                kwargs = {
                    "user_data_dir": profile,
                    "headless": headless,
                    "ignore_default_args": ["--enable-automation"],
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
                    _add_glados_cookies(context, cookie, domain)
                    page = context.new_page()
                    result = _browser_flow(page, cookie, ua, domain, wait_seconds, remote)
                    if result:
                        return result
                    log(f"    {domain} 未拿到签到响应，尝试下一个域名")
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
            if browser is not None:
                try:
                    browser.close()
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
    streak = points_res.get("streak")
    streak = int(streak) if isinstance(streak, (int, float)) and streak >= 0 else None
    return email, left_days, points, fmt_number(gain, signed=True) if gain is not None else None, streak


def send_feishu(title, content):
    """通过青龙现有的飞书私聊应用发送文本消息。未配置时返回 None。"""
    app_id = os.environ.get("QL_FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("QL_FEISHU_APP_SECRET", "").strip()
    open_id = os.environ.get("QL_FEISHU_OPEN_ID", "").strip()
    if not (app_id and app_secret and open_id):
        return None
    if not re.match(r"^ou_[A-Za-z0-9]+$", open_id):
        log("⚠️ 飞书通知跳过：QL_FEISHU_OPEN_ID 格式不正确")
        return False
    try:
        auth = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret}, timeout=15,
        )
        token = auth.json().get("tenant_access_token") if auth.ok else None
        if not token:
            log(f"⚠️ 飞书通知失败：未获取访问凭据（HTTP {auth.status_code}）")
            return False
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": open_id,
                "msg_type": "text",
                "content": json.dumps({"text": f"{title}\n\n{content}"}, ensure_ascii=False),
                "uuid": str(uuid.uuid4()),
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("code") == 0 and (data.get("data") or {}).get("message_id"):
            return True
        log(f"⚠️ 飞书通知失败：业务错误 {data.get('code')}")
    except (requests.RequestException, ValueError) as exc:
        log(f"⚠️ 飞书通知失败：{type(exc).__name__}")
    return False


def send_push(title, content):
    """按已配置的渠道发送通知；任一成功即返回 True。"""
    ok = False
    feishu = send_feishu(title, content)
    if feishu is not None:
        log("飞书通知已发送" if feishu else "飞书通知未送达")
        ok = bool(feishu) or ok

    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if token:
        try:
            r = requests.post("https://www.pushplus.plus/send", json={
                "token": token, "title": title, "content": content, "template": "html",
            }, timeout=10)
            ok = r.status_code == 200 or ok
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

    email, left_days, points, gain, streak = account_overview(session, cookie, ua, domains)
    overview_ok = not (email == "?" and points == "?")
    if not overview_ok:
        log(f"{tag} 只读查询失败：Cookie 可能已过期，或 UA 与登录设备不一致")
    else:
        gain_text = f"，今日 {gain}" if gain else ""
        streak_text = f"，已连续签到 {streak} 天" if streak is not None else ""
        log(f"{tag} {email} 剩余 {left_days} 天，当前积分 {points}{gain_text}{streak_text}")

    if check_only:
        return {"tag": tag, "status": "check-only" if overview_ok else "auth",
                "email": email, "days": left_days, "points": points,
                "gain": gain, "streak": streak}

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
        email, left_days, points, gain, streak = account_overview(session, cookie, ua, domains)
        gain_text = f"，今日 {gain}" if gain else ""
        streak_text = f"，已连续签到 {streak} 天" if streak is not None else ""
        log(f"{tag} 签到成功（{status}），积分 {points}{gain_text}{streak_text}，剩余 {left_days} 天")
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
            "streak": streak, "detail": describe(result)}


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
        labels = {
            "success": "签到成功",
            "repeat": "今日已签到",
            "turnstile": "人机验证未通过",
            "device-mismatch": "设备校验失败",
            "auth": "Cookie 失效",
            "failed": "签到失败",
            "error": "运行异常",
        }
        lines = []
        for r in results:
            line = (
                f"{r['tag']}：{labels.get(r['status'], r['status'])} | "
                f"积分 {r.get('points', '?')} | 今日 {r.get('gain') or '0'} | "
                f"剩余 {r.get('days', '?')} 天"
            )
            if r.get("streak") is not None:
                line += f" | 已连续签到 {r['streak']} 天"
            if r.get("email") and r.get("email") != "?":
                line += f" | {r['email']}"
            if r["status"] not in ("success", "repeat") and r.get("detail"):
                line += f"\n  原因：{str(r['detail'])[:200]}"
            lines.append(line)
        body = "\n".join(lines)

        statuses = {r["status"] for r in results}
        if statuses <= {"success"}:
            title = "GLaDOS 签到 · 成功"
        elif statuses <= {"success", "repeat"}:
            title = "GLaDOS 签到 · 已签到"
        elif statuses & {"success", "repeat"}:
            title = "GLaDOS 签到 · 部分成功"
        else:
            title = "GLaDOS 签到 · 失败"
        body = time.strftime("%Y-%m-%d %H:%M") + "（北京时间）\n" + body

        log("----- 汇总 -----\n" + body)
        if not send_push(title, body):
            log("未配置可用的通知渠道（飞书 / PushPlus / ServerChan / Telegram）")

    ok_status = {"success", "repeat", "check-only"}
    return 0 if all(r["status"] in ok_status for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
