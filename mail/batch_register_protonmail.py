#!/usr/bin/env python3
"""批量注册 ProtonMail 邮箱脚本

使用 Playwright 模拟浏览器自动化注册 ProtonMail 邮箱。

Proton 注册流程:
    1. 单一页面: username + 域名选择 + password  (都在同一页)
    2. 提交后 → 人机验证 → 邮箱首页

用法:
    python batch_register_protonmail.py                 # 单次注册
    python batch_register_protonmail.py --count 5       # 批量注册 5 个
    python batch_register_protonmail.py --headless=false --debug  # 调试模式
"""

import argparse
import asyncio
import csv
import random
import string
import sys
from datetime import datetime
from pathlib import Path

from faker import Faker
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

BASE_DIR = Path(__file__).parent
ACCOUNTS_FILE = BASE_DIR / "protonmail_accounts.csv"
DEBUG_DIR = BASE_DIR / "debug_protonmail"
SIGNUP_URL = "https://account.proton.me/mail/signup?plan=free&billing=12&currency=USD"

fake = Faker()
DEBUG_MODE = False

PROTON_DOMAINS = ["proton.me", "protonmail.com", "pm.me"]


def generate_password(length: int = 14) -> str:
    upper = random.choice(string.ascii_uppercase)
    lower = "".join(random.choices(string.ascii_lowercase, k=length - 4))
    digits = "".join(random.choices(string.digits, k=2))
    special = random.choice("!@#$%^&*")
    chars = list(upper + lower + digits + special)
    random.shuffle(chars)
    return "".join(chars)


def generate_username() -> str:
    patterns = [
        lambda: f"{fake.first_name().lower()}.{fake.last_name().lower()}{random.randint(10, 99)}",
        lambda: f"{fake.word().lower()}.{fake.word().lower()}{random.randint(100, 999)}",
        lambda: f"{fake.first_name().lower()}{random.randint(1000, 99999)}",
        lambda: f"{fake.user_name()}.{random.randint(100, 999)}",
    ]
    return random.choice(patterns)()


def generate_profile(domain: str = None) -> dict:
    first = fake.first_name()
    last = fake.last_name()
    username = generate_username()
    dom = domain or PROTON_DOMAINS[0]
    display_name = f"{first} {last}"
    password = generate_password()
    return {
        "username": username,
        "email": f"{username}@{dom}",
        "password": password,
        "first_name": first,
        "last_name": last,
        "display_name": display_name,
        "domain": dom,
        "created_at": "",
        "status": "pending",
    }


def save_account(account: dict) -> None:
    file_exists = ACCOUNTS_FILE.exists()
    with open(ACCOUNTS_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=account.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(account)


async def debug_screenshot(page: Page, name: str) -> None:
    if not DEBUG_MODE:
        return
    DEBUG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%H%M%S_%f")
    await page.screenshot(path=str(DEBUG_DIR / f"{name}_{ts}.png"))
    (DEBUG_DIR / f"{name}_{ts}.html").write_text(await page.content())
    print(f"  [DEBUG] {name}_{ts}")


async def fill_input_js(page: Page, selector: str, value: str,
                        timeout: int = 10000) -> bool:
    """直接用 JS 设置 input 值并触发 React 事件。绕过可见性检查。"""
    try:
        result = await page.evaluate('''([sel, v]) => {
            const el = document.querySelector(sel);
            if (!el) return "NOT_FOUND";
            const nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, "value").set;
            nativeSetter.call(el, v);
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            el.dispatchEvent(new FocusEvent("focus"));
            el.dispatchEvent(new FocusEvent("blur"));
            return "OK";
        }''', [selector, value])
        print(f"  [OK] {selector} = '{value}' (JS: {result})")
        return result == "OK"
    except Exception as e:
        print(f"  [WARN] {selector}: {e}")
        return False


async def try_click(page: Page, selectors: list[str], timeout: int = 5000) -> bool:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            await el.wait_for(state="visible", timeout=timeout)
            if await el.is_enabled():
                await el.click()
                print(f"  [OK] 点击 {sel}")
                await page.wait_for_timeout(2500)
                return True
        except Exception:
            continue
    return False


def read_line_nonblock(timeout: float = 1.0) -> str:
    import select as sel_mod
    fd = sys.stdin.fileno()
    try:
        r, _, _ = sel_mod.select([fd], [], [], timeout)
        if not r:
            return ""
        return sys.stdin.readline().rstrip("\n")
    except (OSError, TypeError):
        return ""


# ── 填充表单 (DOM 驱动) ──────────────────────────────────────────

async def fill_signup_form(page: Page, profile: dict) -> bool:
    await debug_screenshot(page, "01_form")
    print("  [→] 填写注册表单 …")

    # 1) username — JS 直接操作 DOM
    await fill_input_js(page, "#username", profile["username"])
    await asyncio.sleep(0.8)

    # 确认填进去了
    try:
        val = await page.locator("#username").input_value(timeout=3000)
        print(f"  [→] username value = '{val}'")
        if not val:
            print("  [!] 重试 username …")
            await page.keyboard.press("Tab")
            await page.keyboard.type(profile["username"], delay=80)
            await page.wait_for_timeout(500)
    except Exception:
        print("  [!] 无法读取 username，尝试 keyboard type …")
        try:
            await page.locator("#username").click(force=True, timeout=5000)
            await page.keyboard.type(profile["username"], delay=80)
        except Exception:
            pass

    # 2) domain
    if profile["domain"] != "proton.me":
        try:
            await page.evaluate(
                f'document.querySelector(\'#select-domain\').click()')
            await page.wait_for_timeout(600)
            await page.evaluate('''(domain) => {
                const opts = document.querySelectorAll('button[title]');
                for (const o of opts) {
                    if (o.title.includes(domain)) { o.click(); return; }
                }
            }''', profile["domain"])
            print(f"  [OK] 域名 @{profile['domain']}")
            await page.wait_for_timeout(500)
        except Exception as e:
            print(f"  [WARN] 域名: {e}")

    # 3) 所有密码框
    pw_count = await page.evaluate(
        'document.querySelectorAll(\'input[type="password"]\').length')
    print(f"  [→] {pw_count} 个密码框")
    for i in range(pw_count):
        await page.evaluate('''(pw) => {
            const el = document.querySelectorAll('input[type="password"]')[pw.i];
            if (!el) return;
            const s = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, "value").set;
            s.call(el, pw.v);
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
        }''', {"i": i, "v": profile["password"]})
        print(f"  [OK] 密码框 {i + 1}/{pw_count}")

    await asyncio.sleep(1.5)

    # 4) 提交
    await click_submit(page)
    return True


async def click_submit(page: Page) -> bool:
    # 先等按钮变为可用
    try:
        for i in range(20):
            enabled = await page.evaluate(
                '!document.querySelector(\'button[type="submit"]\').disabled')
            if enabled:
                await page.evaluate(
                    'document.querySelector(\'button[type="submit"]\').click()')
                print("  [OK] 表单提交")
                await page.wait_for_timeout(4000)
                return True
            await asyncio.sleep(1)
        print("  [WARN] 按钮超时未启用，强制 JS click")
        await page.evaluate(
            'document.querySelector(\'button[type="submit"]\').click()')
        await page.wait_for_timeout(4000)
        return True
    except Exception as e:
        print(f"  [ERROR] 提交: {e}")
        return False


async def handle_set_password(page: Page, profile: dict) -> bool:
    await debug_screenshot(page, "xx_set_password")
    print("  [→] 补填密码 …")
    pw_count = await page.evaluate(
        'document.querySelectorAll(\'input[type="password"]\').length')
    for i in range(pw_count):
        await page.evaluate('''(pw) => {
            const el = document.querySelectorAll('input[type="password"]')[pw.i];
            if (!el) return;
            const s = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, "value").set;
            s.call(el, pw.v);
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
        }''', {"i": i, "v": profile["password"]})
        print(f"  [OK] 密码 {i + 1}/{pw_count}")
    await asyncio.sleep(0.5)
    await click_submit(page)
    return True


async def handle_recovery(page: Page) -> bool:
    await debug_screenshot(page, "02_recovery")
    print("  [→] 跳过恢复方式 …")
    for sel in [
        'button:has-text("Skip")',
        'button:has-text("Maybe later")',
        'button:has-text("Not now")',
        'a:has-text("Skip")',
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=5000):
                await btn.click()
                print(f"  [OK] 跳过 ({sel})")
                await page.wait_for_timeout(3000)
                return True
        except Exception:
            continue
    await try_click(page, ['button:has-text("Next")', 'button[type="submit"]'])
    return True


async def handle_verification(page: Page) -> str:
    """人机验证 — 用户手动操作。返回 'continue' | 'abort'"""
    await debug_screenshot(page, "03_verify")
    await page.bring_to_front()

    print(f"\n  ⚠️  请手动完成人机验证，然后按 Enter 继续 (输入 a 放弃)")
    start_url = page.url
    for _ in range(180):
        line = await asyncio.get_event_loop().run_in_executor(
            None, lambda: read_line_nonblock(1.0)
        )
        if line:
            if line.strip().lower() == "a":
                return "abort"
            return "continue"

        try:
            if page.url != start_url:
                print(f"  [OK] 页面跳转: {page.url}")
                await page.wait_for_timeout(3000)
                return "continue"
        except Exception:
            pass

    print("  [WARN] 180s 超时")
    return "continue"


async def handle_complete(page: Page, profile: dict) -> bool:
    await debug_screenshot(page, "04_complete")
    for sel in ['#displayName', 'input[id*="display"]', 'input[name*="name"]']:
        try:
            if await page.locator(sel).first.is_visible(timeout=2000):
                await fill_input_js(page, sel, profile["display_name"])
                await page.wait_for_timeout(500)
                break
        except Exception:
            continue
    await click_submit(page)
    return True


# ── 主流程 ────────────────────────────────────────────────────

async def register_protonmail(page: Page, profile: dict) -> dict | None:
    try:
        print(f"\n  → 打开 {SIGNUP_URL}")
        await page.goto(SIGNUP_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)
        await debug_screenshot(page, "00_landing")

        # cookie
        for sel in ['button:has-text("Accept all")', 'button:has-text("Accept")']:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    print("  [OK] Cookie 关闭")
                    await page.wait_for_timeout(1000)
            except Exception:
                continue

        # ——— Step 1: 填注册表单 ———
        success = await fill_signup_form(page, profile)
        if not success:
            profile["status"] = "form_error"
            save_account(profile)
            return None

        # ——— Step 2: 循环处理后续页面 (DOM 驱动) ———
        step = 1
        verify_attempts = 0
        while step < 15:
            step += 1
            url = page.url
            await asyncio.sleep(0.5)

            print(f"\n  [步 {step}] {url[:90]}")

            # 成功
            if any(s in url for s in ("mail.proton.me", "beta.proton.me")):
                profile["status"] = "success"
                profile["created_at"] = datetime.now().isoformat()
                save_account(profile)
                print(f"  [✓] 成功: {profile['email']}")
                return profile

            # DOM 检查: 当前页面有哪些关键元素
            has_username = await page.locator("#username").count() > 0
            has_password = await page.locator('input[type="password"]').count() > 0
            has_submit = await page.locator('button[type="submit"]').count() > 0
            on_signup = "signup" in url and "plan=free" in url

            # 还在注册表单页 (username + password 都存在)
            if has_username and has_password:
                try:
                    val = await page.evaluate(
                        'document.querySelector("#username").value')
                except Exception:
                    val = ""
                if not val:
                    print("  [→] username 仍为空，重填 …")
                    await fill_input_js(page, "#username", profile["username"])
                # 检查密码是否为空
                pw_empty = False
                for i in range(await page.locator('input[type="password"]').count()):
                    try:
                        pw_val = await page.locator('input[type="password"]').nth(i).input_value(timeout=1000)
                        if not pw_val:
                            pw_empty = True
                            break
                    except Exception:
                        pw_empty = True
                        break
                if pw_empty:
                    print("  [→] 密码为空，重填 …")
                    await handle_set_password(page, profile)
                else:
                    await click_submit(page)
                await page.wait_for_timeout(4000)
                continue

            # 验证页: 无表单元素
            if not has_username and not has_password:
                verify_attempts += 1
                if verify_attempts > 3:
                    profile["status"] = "verify_limit"
                    save_account(profile)
                    return None
                print(f"  [→] 疑似验证页 ({verify_attempts}/3)")
                r = await handle_verification(page)
                if r == "abort":
                    profile["status"] = "aborted"
                    save_account(profile)
                    return None
                await page.wait_for_timeout(2000)
                continue

            # 完成页: 有 name/display 字段
            has_display = await page.locator('#displayName, input[id*="display"], '
                                              'input[name*="name"]').count() > 0
            if has_display:
                print("  [→] 完成设置 …")
                await handle_complete(page, profile)
                await page.wait_for_timeout(3000)
                continue

            # Skip 按钮 (recovery 跳过)
            has_skip = await page.locator(
                'button:has-text("Skip"), button:has-text("Maybe later"), '
                'button:has-text("Not now"), a:has-text("Skip")'
            ).count() > 0
            if has_skip:
                print("  [→] 跳过步骤 …")
                await handle_recovery(page)
                await page.wait_for_timeout(3000)
                continue

            # 仍在 signup url 但没关键元素 → 结束
            if on_signup:
                print("  [?] 仍在注册 URL 但无关键元素")
                await debug_screenshot(page, f"step{step}_end")
                break

            # 未知
            await debug_screenshot(page, f"step{step}_unknown")
            print(f"  [?] 未知页面 (60s, Enter继续 / a放弃)")
            for _ in range(60):
                line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: read_line_nonblock(1.0)
                )
                if line:
                    if line.strip().lower() == "a":
                        profile["status"] = "aborted"
                        save_account(profile)
                        return None
                    break
            await page.wait_for_timeout(2000)

        profile["status"] = "unknown"
        save_account(profile)
        return profile

    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()
        profile["status"] = "error"
        save_account(profile)
        return None


# ── 批量运行 ──────────────────────────────────────────────────

async def run_batch(count: int, headless: bool = True, proxy: str | None = None,
                    domain: str = None):
    global DEBUG_MODE

    dom = domain or PROTON_DOMAINS[0]
    print(f"\n批量注册 ProtonMail")
    print(f"  数量: {count}, 无头: {headless}, 代理: {proxy or '无'}, 域名: @{dom}")
    print(f"  保存: {ACCOUNTS_FILE}\n")

    async with async_playwright() as pw:
        launch_options = {
            "channel": "chrome",
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--disable-default-apps",
                "--disable-popup-blocking",
                "--disable-sync",
                "--disable-translate",
            ],
        }
        if proxy:
            launch_options["proxy"] = {"server": proxy}

        browser: Browser = await pw.chromium.launch(**launch_options)
        success_count = 0

        anti_detect_js = """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        delete navigator.__proto__.webdriver;
        window.chrome = { runtime: {} };
        """

        for i in range(count):
            context = await browser.new_context(
                locale="en-US",
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()
            await page.add_init_script(anti_detect_js)

            try:
                profile = generate_profile(domain=dom)
                print(f"{'=' * 50}")
                print(f"[{i + 1}/{count}] {profile['email']}")
                print(f"{'=' * 50}")

                result = await register_protonmail(page, profile)
                if result and result.get("status") == "success":
                    success_count += 1

                if i < count - 1:
                    delay = random.uniform(5, 15)
                    print(f"\n  等待 {delay:.0f}s …")
                    await asyncio.sleep(delay)
            finally:
                await page.close()
                await context.close()

        await browser.close()

    print(f"\n{'=' * 50}")
    print(f"完成: {success_count}/{count} 成功")
    print(f"账号: {ACCOUNTS_FILE}")
    print(f"{'=' * 50}")


def show_accounts():
    if not ACCOUNTS_FILE.exists():
        print("暂无账号。")
        return
    with open(ACCOUNTS_FILE) as f:
        rows = list(csv.DictReader(f))
    print(f"\n共 {len(rows)} 个账号:\n")
    for row in rows:
        icon = "✓" if row.get("status") == "success" else "⚠"
        print(f"  {icon} {row.get('email', 'N/A')} | {row.get('status', 'N/A')}")


def main():
    global DEBUG_MODE
    parser = argparse.ArgumentParser(description="批量注册 ProtonMail 邮箱")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--headless", type=str, default="true",
                        choices=["true", "false"])
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--proxy", type=str, default=None)
    parser.add_argument("--domain", type=str, default=None, choices=PROTON_DOMAINS)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    if args.show:
        show_accounts()
        return

    DEBUG_MODE = args.debug
    asyncio.run(run_batch(
        count=args.count,
        headless=args.headless == "true",
        proxy=args.proxy,
        domain=args.domain,
    ))


if __name__ == "__main__":
    main()