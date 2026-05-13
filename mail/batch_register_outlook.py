#!/usr/bin/env python3
"""批量注册 Outlook 邮箱脚本 (Batch Outlook Registration)

使用 Playwright 模拟浏览器自动化注册 Outlook 邮箱。
需要先安装依赖和浏览器:
    pip install -r requirements.txt
    playwright install chromium

用法:
    python batch_register_outlook.py                 # 单次注册
    python batch_register_outlook.py --count 5       # 批量注册 5 个
    python batch_register_outlook.py --headless=false --debug  # 调试模式
    python batch_register_outlook.py --count 2 --proxy http://127.0.0.1:7890
"""

import argparse
import asyncio
import csv
import random
import re
import string
import sys
from datetime import datetime
from pathlib import Path

from faker import Faker
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

BASE_DIR = Path(__file__).parent
ACCOUNTS_FILE = BASE_DIR / "outlook_accounts.csv"
DEBUG_DIR = BASE_DIR / "debug_screenshots"
SIGNUP_URL = "https://signup.live.com/"

fake = Faker()

DEBUG_MODE = False


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
        lambda: f"{fake.first_name().lower()}{fake.last_name().lower()}{random.randint(100, 9999)}",
        lambda: f"{fake.user_name()}{random.randint(10, 999)}",
        lambda: f"{fake.word().lower()}{random.randint(1000, 99999)}",
        lambda: f"{fake.first_name().lower()}_{fake.last_name().lower()}{random.randint(10, 99)}",
    ]
    return random.choice(patterns)()


def generate_profile() -> dict:
    first = fake.first_name()
    last = fake.last_name()
    username = generate_username()
    password = generate_password()
    return {
        "username": username,
        "email": f"{username}@outlook.com",
        "password": password,
        "first_name": first,
        "last_name": last,
        "birth_year": random.randint(1985, 2002),
        "birth_month": random.randint(1, 12),
        "birth_day": random.randint(1, 28),
        "country": "US",
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
    path = DEBUG_DIR / f"{name}_{datetime.now().strftime('%H%M%S')}.png"
    await page.screenshot(path=path)
    page_html = await page.content()
    html_path = DEBUG_DIR / f"{name}_{datetime.now().strftime('%H%M%S')}.html"
    html_path.write_text(page_html)
    print(f"  [DEBUG] 截图已保存: {path}")


async def try_fill_first_field(page: Page, selectors: list[str], value: str, timeout: int = 8000) -> bool:
    """尝试使用多个选择器找到并填写第一个匹配的输入框。"""
    for sel in selectors:
        try:
            elem = page.locator(sel).first
            await elem.wait_for(state="visible", timeout=timeout)
            await elem.click()
            await elem.fill(value)
            print(f"  [OK] 已填写 ({sel}): {value}")
            return True
        except Exception:
            continue
    return False


async def try_select_option(page: Page, selectors: list[str], value: str, timeout: int = 8000) -> bool:
    """尝试使用多个选择器找到下拉框并选择值。"""
    for sel in selectors:
        try:
            elem = page.locator(sel).first
            await elem.wait_for(state="visible", timeout=timeout)
            await elem.select_option(value)
            print(f"  [OK] 已选择 ({sel}): {value}")
            return True
        except Exception:
            continue
    return False


async def try_click_next(page: Page) -> bool:
    """尝试点击 Next/继续 按钮。"""
    selectors = [
        'input[type="submit"]',
        'button[type="submit"]',
        "#nextButton",
        "#iSignupAction",
        'button:has-text("Next")',
        'button:has-text("下一步")',
        'button:has-text("Continue")',
        'button:has-text("Create")',
        'button:has-text("I agree")',
        'button:has-text("同意")',
        "button#idSIButton9",
        "#idSIButton9",
        '[data-testid="liveCoreButton-primary"]',
        "button.primary",
        'input[value="Next"]',
        'input[value="下一步"]',
    ]
    for sel in selectors:
        try:
            elem = page.locator(sel).first
            await elem.wait_for(timeout=5000)
            if await elem.is_enabled():
                await elem.click()
                print(f"  [OK] 点击成功 ({sel})")
                await page.wait_for_timeout(2500)
                return True
        except Exception:
            continue
    return False


async def _element_visible(page: Page, selector: str) -> bool:
    """检查是否有可见的元素匹配选择器。"""
    try:
        elem = page.locator(selector).first
        return await elem.is_visible(timeout=1000)
    except Exception:
        return False


async def detect_page_type(page: Page, quiet: bool = False) -> str:
    """检测当前页面类型（优先 DOM 检查）。quiet=True 时不打印调试信息。"""
    html = (await page.content()).lower()

    # —— DOM 检查 ——
    has_email_input = await _element_visible(page, 'input[type="email"]')
    has_password_input = await _element_visible(page, 'input[type="password"]')

    # 姓名页: firstNameInput / lastNameInput (Fluent UI React 组件真实 ID)
    has_name_fields = any([
        await _element_visible(page, "#firstNameInput"),
        await _element_visible(page, "#lastNameInput"),
    ])

    # 生日/国家页: BirthMonthDropdown / BirthDayDropdown 是按钮下拉, BirthYear 是 input[type="number"]
    has_birth_dropdown = any([
        await _element_visible(page, "#BirthMonthDropdown"),
        await _element_visible(page, "#BirthDayDropdown"),
    ])
    has_country_dropdown = any([
        await _element_visible(page, "#countryDropdownId"),
        await _element_visible(page, '[data-testid="countryDropdown"]'),
    ])
    has_birth_year = await _element_visible(page, 'input[name="BirthYear"]')

    has_name_and_birth = has_name_fields and (has_birth_dropdown or has_birth_year or has_country_dropdown)
    has_details_fields = (has_birth_dropdown or has_country_dropdown) and not has_name_fields

    def _log(msg: str) -> None:
        if not quiet:
            print(msg)

    if has_email_input:
        _log("  [检测] 当前页面类型: email_input")
        return "email_input"

    if has_password_input:
        _log("  [检测] 当前页面类型: password_input")
        return "password_input"

    if has_name_and_birth:
        _log("  [检测] 当前页面类型: name_and_birth")
        return "name_and_birth"

    if has_details_fields:
        _log("  [检测] 当前页面类型: birth_country")
        return "birth_country"

    if has_name_fields:
        _log("  [检测] 当前页面类型: name_input")
        return "name_input"

    # —— 文本回退 ——
    if any(kw in html for kw in ["captcha", "robot", "are you a human", "验证码", "人机验证",
                                  "enter the characters", "puzzle", "challenge"]):
        _log("  [检测] 当前页面类型: captcha (text)")
        return "captcha"

    if any(kw in html for kw in ["verify your identity", "phone number", "手机号码",
                                  "enter your phone", "send code"]):
        _log("  [检测] 当前页面类型: phone_verify (text)")
        return "phone_verify"

    if any(kw in html for kw in ["stay signed in", "keep me signed in",
                                  "保持登录", "保持我的登录"]):
        _log("  [检测] 当前页面类型: stay_signed_in (text)")
        return "stay_signed_in"

    _log("  [检测] 未知页面类型")
    return "unknown"


async def _try_solve_press_and_hold(page: Page) -> bool:
    """尝试自动解决 'press and hold' 按钮 CAPTCHA：在页面中寻找可见按钮，
    mousedown 按住 15 秒后 mouseup。返回 True 表示尝试过。"""
    print("  [*] 尝试自动解决 'Press and hold' CAPTCHA …")
    # 目标选择器：Arkose enforcement 的可点击元素
    target_selectors = [
        'button:has-text("Press and Hold")',
        'button:has-text("press and hold")',
        'button:has-text("hold")',
        'div[role="button"]:has-text("Press")',
        '[role="button"]:has-text("hold")',
        '.fc-verify-button',
        'button.fc-verify-button',
        'iframe[title*="verify" i]',
    ]
    el = None
    for sel in target_selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=2000):
                break
            el = None
        except Exception:
            el = None

    if not el:
        print("  [*] 未找到目标元素，尝试全页面区域点击按住 …")
        center = page.locator("body")
    else:
        print(f"  [*] 找到目标元素，准备按住 …")
        center = el

    try:
        box = await center.bounding_box()
        if not box:
            raise RuntimeError("no bounding box")
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        await page.mouse.move(x, y)
        await page.mouse.down()
        print("  [*] 正在按住 … (15s)")
        await asyncio.sleep(15)
        await page.mouse.up()
        print("  [*] 已松开，等待验证结果 …")
        await page.wait_for_timeout(5000)
        return True
    except Exception as e:
        print(f"  [WARN] 自动按住失败: {e}")
        return False


async def fill_email(page: Page, profile: dict) -> bool:
    await debug_screenshot(page, "step1_email")
    if not await try_fill_first_field(page, [
        'input[type="email"]',
        'input[name="MemberName"]',
        "#MemberName",
        'input[aria-label*="email" i]',
        'input[aria-label*="Email" i]',
        'input[placeholder*="email" i]',
        'input[placeholder*="outlook" i]',
        "input:text('')",
    ], profile["email"]):
        print("  [ERROR] 未找到邮箱输入框")
        return False
    await page.wait_for_timeout(800)
    await try_click_next(page)
    return True


async def fill_password(page: Page, profile: dict) -> bool:
    await debug_screenshot(page, "step2_password")
    if not await try_fill_first_field(page, [
        'input[type="password"]',
        'input[name="Password"]',
        "#PasswordInput",
        "#i0118",
        'input[aria-label*="password" i]',
        'input[aria-label*="Password" i]',
    ], profile["password"]):
        print("  [WARN] 未找到密码输入框")
    await page.wait_for_timeout(800)
    await try_click_next(page)
    return True


async def fill_name(page: Page, profile: dict) -> bool:
    """填写姓名，可能与出生日期/国家在同一页面。"""
    await debug_screenshot(page, "step3_name")

    found_first = await try_fill_first_field(page, [
        "#firstNameInput",
        'input[name="firstNameInput"]',
        'input[name="FirstName"]',
        "#FirstName",
        "#i0116",
        'input[aria-label*="First" i]',
        'input[placeholder*="First" i]',
    ], profile["first_name"])

    found_last = await try_fill_first_field(page, [
        "#lastNameInput",
        'input[name="lastNameInput"]',
        'input[name="LastName"]',
        "#LastName",
        "#i0120",
        'input[aria-label*="Last" i]',
        'input[placeholder*="Last" i]',
    ], profile["last_name"])

    return found_first or found_last


async def click_dropdown_option(page: Page, dropdown_selector: str, option_text: str) -> bool:
    """点击一个 custom button 下拉，然后从弹出列表中选择选项。"""
    try:
        btn = page.locator(dropdown_selector).first
        await btn.wait_for(state="visible", timeout=5000)
        await btn.click(force=True)
        await page.wait_for_timeout(800)

        option_selectors = [
            f'[role="option"]:has-text("{option_text}")',
            f'[role="menuitem"]:has-text("{option_text}")',
            f'li:has-text("{option_text}")',
            f'div[role="listbox"] >> text="{option_text}"',
            f'[role="listbox"] >> :text-is("{option_text}")',
        ]
        for sel in option_selectors:
            try:
                opt = page.locator(sel).first
                await opt.wait_for(timeout=3000)
                await opt.click()
                print(f"  [OK] 已选择 ({dropdown_selector}): {option_text}")
                await page.wait_for_timeout(500)
                return True
            except Exception:
                continue

        # 如果角色选择器失败，按 ESC 关闭下拉
        await page.keyboard.press("Escape")
        return False
    except Exception as e:
        print(f"  [WARN] 下拉选择失败 ({dropdown_selector}): {e}")
        return False


async def fill_birth_and_country(page: Page, profile: dict) -> bool:
    """填写出生日期和国家/地区。"""
    await debug_screenshot(page, "step4_birth_country")

    country_settings = {
        "US": "United States",
        "CN": "China",
        "HK": "Hong Kong SAR",
        "JP": "Japan",
        "KR": "Korea",
    }
    country_text = country_settings.get(profile["country"], profile["country"])

    # 1) Country/Region — 按钮下拉
    await click_dropdown_option(
        page,
        '#countryDropdownId, [data-testid="countryDropdown"]',
        country_text,
    )

    # 2) Birth Month — 按钮下拉
    birth_month_map = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December",
    }
    month_name = birth_month_map[profile["birth_month"]]
    await click_dropdown_option(
        page,
        '#BirthMonthDropdown, [aria-label="Birth month"]',
        month_name,
    )

    # 3) Birth Day — 按钮下拉
    day_str = str(profile["birth_day"])
    await click_dropdown_option(
        page,
        '#BirthDayDropdown, [aria-label="Birth day"]',
        day_str,
    )

    # 4) Birth Year — 输入框 (type="number")
    try:
        year_input = page.locator('input[name="BirthYear"], #floatingLabelInput24').first
        await year_input.wait_for(state="visible", timeout=5000)
        await year_input.click()
        await year_input.fill(str(profile["birth_year"]))
        print(f"  [OK] 已填写年份: {profile['birth_year']}")
    except Exception as e:
        print(f"  [WARN] 填写年份失败: {e}")

    return True


def _read_line_nonblock(timeout: float = 5.0) -> str:
    """从 stdin 读取一行，支持非阻塞、返回空串表示超时。"""
    import select as sel_mod
    import os
    fd = sys.stdin.fileno()
    try:
        r, _, _ = sel_mod.select([fd], [], [], timeout)
        if not r:
            return ""
        return sys.stdin.readline().rstrip("\n")
    except (OSError, TypeError):
        return ""


async def _wait_for_page_change(page: Page, timeout: int = 120) -> bool:
    """等待页面 URL 改变或 CAPTCHA 消失（用户手动操作导致跳转）。"""
    start_url = page.url
    print(f"  等待页面跳转或 CAPTCHA 消失（最多 {timeout}s）…")
    for elapsed in range(timeout):
        await asyncio.sleep(1)
        try:
            current_url = page.url
            if current_url != start_url:
                print(f"  [OK] 页面已跳转: {current_url}")
                await page.wait_for_timeout(2000)
                return True

            # 检查 CAPTCHA 是否已消失 (Press and hold 按钮 / iframe 不见了)
            page_type = await detect_page_type(page)
            if page_type != "captcha":
                print(f"  [OK] CAPTCHA 已消失，当前页面: {page_type}")
                await page.wait_for_timeout(1000)
                return True
        except Exception:
            pass
    print(f"  [WARN] {timeout}s 后页面未跳转")
    return False


async def handle_captcha_interactive(page: Page, profile: dict) -> str:
    """处理 CAPTCHA 页面，返回 'continue'/ 'back' / 'abort'。

    先尝试自动解决 press-and-hold CAPTCHA，失败则提示用户手动操作，
    然后轮询等待 DOM 变化（页面跳转或 CAPTCHA 消失）。
    """
    await debug_screenshot(page, "step_captcha")
    await page.bring_to_front()
    html = (await page.content()).lower()

    if "press and hold" in html or "按住按钮" in html:
        hint = "⚠️  'Press and hold' — 请在浏览器中按住按钮完成验证"
    elif "enter the characters" in html or "输入字符" in html:
        hint = "⚠️  字符验证码 — 请在浏览器中手动输入完成"
    else:
        hint = "⚠️  人机验证 — 请在浏览器中手动完成操作"

    print(f"\n  {hint}")
    print("  等待页面自动跳转（最多 120s）…")
    print("  终端: 'a'=放弃 | 'b'=回退 | Enter=跳过等待继续")

    await _try_solve_press_and_hold(page)

    start_url = page.url
    for elapsed in range(120):
        line = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _read_line_nonblock(1.0)
        )
        if line:
            r = line.strip().lower()
            if r == "a":
                return "abort"
            if r == "b":
                return "back"
            return "continue"

        try:
            if page.url != start_url:
                print(f"  [OK] 页面已跳转: {page.url}")
                await page.wait_for_timeout(2000)
                return "continue"

            page_type = await detect_page_type(page)
            if page_type != "captcha":
                print(f"  [OK] CAPTCHA 已消失，当前页面: {page_type}")
                await page.wait_for_timeout(1000)
                return "continue"
        except Exception:
            pass

    print("  [超时] 120s 无变化，尝试继续 …")
    return "continue"


async def _register_outlook_page(page: Page, profile: dict) -> dict | None:
    try:
        await page.goto(SIGNUP_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        await debug_screenshot(page, "00_initial")

        # 处理可能出现的 cookie/隐私 弹窗
        try:
            dismiss_selectors = [
                'button:has-text("Accept")',
                'button:has-text("I accept")',
                'button:has-text("同意")',
                'button:has-text("Continue")',
                'button[aria-label*="Accept" i]',
                "#acceptButton",
            ]
            for sel in dismiss_selectors:
                try:
                    btn = page.locator(sel).first
                    await btn.wait_for(timeout=3000)
                    await btn.click()
                    print("  [OK] 关闭了 cookie 弹窗")
                    await page.wait_for_timeout(1000)
                    break
                except Exception:
                    continue
        except Exception:
            pass

        # Step 1: Email
        page_type = await detect_page_type(page)
        if page_type == "email_input":
            print("  [1] 输入邮箱地址...")
            if not await fill_email(page, profile):
                return None
            await page.wait_for_timeout(3000)
        else:
            print(f"  [WARN] 期望邮箱输入页，但检测到: {page_type}")

        # 循环处理后续页面，直到离开 signup 流程
        max_steps = 10
        step_count = 0
        captcha_attempts = 0
        MAX_CAPTCHA_ATTEMPTS = 2

        while step_count < max_steps:
            step_count += 1
            current_url = page.url
            if "signup.live.com" not in current_url and "account" in current_url.lower():
                print(f"  [OK] 已跳转到: {current_url}")
                profile["status"] = "success"
                profile["created_at"] = datetime.now().isoformat()
                save_account(profile)
                print(f"  [OK] 注册成功: {profile['email']}")
                return profile

            page_type = await detect_page_type(page)

            if page_type == "password_input":
                print(f"  [{step_count + 1}] 输入密码...")
                await fill_password(page, profile)
                await page.wait_for_timeout(3000)

            elif page_type == "name_input":
                print(f"  [{step_count + 1}] 填写姓名...")
                await fill_name(page, profile)

                has_birth_on_page = await _element_visible(page, "#BirthMonthDropdown") or \
                    await _element_visible(page, "input[name='BirthYear']") or \
                    await _element_visible(page, "#countryDropdownId")
                if has_birth_on_page:
                    print(f"  [{step_count + 1}] 同时填写出生日期和国家...")
                    await fill_birth_and_country(page, profile)

                await page.wait_for_timeout(800)
                if not await try_click_next(page):
                    print("  [WARN] 未找到 Next 按钮")
                await page.wait_for_timeout(3000)

            elif page_type == "name_and_birth":
                print(f"  [{step_count + 1}] 填写姓名、出生日期和国家...")
                await fill_name(page, profile)
                await fill_birth_and_country(page, profile)
                await page.wait_for_timeout(800)
                await try_click_next(page)
                await page.wait_for_timeout(3000)

            elif page_type == "birth_country":
                print(f"  [{step_count + 1}] 填写出生日期和国家...")
                await fill_birth_and_country(page, profile)
                await page.wait_for_timeout(800)
                await try_click_next(page)
                await page.wait_for_timeout(3000)

            elif page_type == "captcha":
                captcha_attempts += 1
                if captcha_attempts > MAX_CAPTCHA_ATTEMPTS:
                    print(f"  [ABORT] 已达到最大 CAPTCHA 尝试次数 ({MAX_CAPTCHA_ATTEMPTS})，放弃此注册")
                    profile["status"] = "captcha_limit"
                    save_account(profile)
                    return None
                print(f"  [{step_count + 1}] 处理验证码... (第 {captcha_attempts}/{MAX_CAPTCHA_ATTEMPTS} 次)")
                con = await handle_captcha_interactive(page, profile)
                if con == "abort":
                    profile["status"] = "aborted"
                    save_account(profile)
                    return None
                if con == "back":
                    print("  [?] 回退到上一步...")
                    back_btn = page.locator('#back-button, [data-testid="leftArrowIcon"]').first
                    try:
                        await back_btn.click(timeout=3000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(3000)
                    continue
                await page.wait_for_timeout(2000)

            elif page_type == "phone_verify":
                print(f"  [{step_count + 1}] 需要手机验证...")
                con = await handle_captcha_interactive(page, profile)
                if con == "abort":
                    profile["status"] = "aborted"
                    save_account(profile)
                    return None
                if con == "back":
                    back_btn = page.locator('#back-button, [data-testid="leftArrowIcon"]').first
                    try:
                        await back_btn.click(timeout=3000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(3000)
                    continue
                await page.wait_for_timeout(2000)

            elif page_type == "stay_signed_in":
                print(f"  [{step_count + 1}] 处理保持登录...")
                decline_selectors = [
                    'button:has-text("No")',
                    'button:has-text("否")',
                    'input[value="否"]',
                ]
                clicked = False
                for sel in decline_selectors:
                    try:
                        btn = page.locator(sel).first
                        await btn.wait_for(timeout=3000)
                        await btn.click()
                        clicked = True
                        break
                    except Exception:
                        continue
                if not clicked:
                    await try_click_next(page)
                await page.wait_for_timeout(3000)

            else:
                print(f"  [{step_count + 1}] 未知页面，尝试截图并等待手动处理...")
                await debug_screenshot(page, f"step{step_count}_unknown")
                print("  请在浏览器中手动完成当前页面，等待 60s …")
                print("  终端输入: Enter=继续 | b=回退 | a=放弃")
                action = "continue"
                for _ in range(60):
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: _read_line_nonblock(1.0)
                    )
                    if line:
                        r = line.strip().lower()
                        if r == "a":
                            profile["status"] = "aborted"
                            save_account(profile)
                            return None
                        if r == "b":
                            action = "back"
                        break
                    await asyncio.sleep(0)
                if action == "back":
                    back_btn = page.locator('#back-button, [data-testid="leftArrowIcon"]').first
                    try:
                        await back_btn.click(timeout=3000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(3000)
                    continue
                await page.wait_for_timeout(2000)

            current_url = page.url
            success_indicators = [
                "account.microsoft.com",
                "login.live.com/login.srf",
                "outlook.live.com",
                "signup-complete",
                "welcome",
            ]
            if any(indicator in current_url.lower() for indicator in success_indicators):
                profile["status"] = "success"
                profile["created_at"] = datetime.now().isoformat()
                save_account(profile)
                print(f"  [OK] 注册成功: {profile['email']}")
                return profile

        print(f"  [?] 达到最大步骤数 ({max_steps})，状态不确定")
        profile["status"] = "unknown"
        save_account(profile)
        return profile

    except Exception as e:
        print(f"  [ERROR] 注册异常: {e}")
        import traceback
        traceback.print_exc()
        profile["status"] = "error"
        save_account(profile)
        return None


async def run_batch(count: int, headless: bool = True, proxy: str | None = None):
    global DEBUG_MODE

    print(f"\n批量注册 Outlook，数量: {count}, 无头模式: {headless}, 代理: {proxy or '无'}")
    print(f"账号保存到: {ACCOUNTS_FILE}")
    if DEBUG_MODE:
        print(f"调试截图保存到: {DEBUG_DIR}")
    print()

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
                profile = generate_profile()
                print(f"\n{'='*50}")
                print(f"开始注册: {profile['email']}")
                print(f"{'='*50}")

                result = await _register_outlook_page(page, profile)
                if result and result.get("status") == "success":
                    success_count += 1

                if i < count - 1:
                    delay = random.uniform(3, 8)
                    print(f"\n等待 {delay:.0f}s 后继续下一个...")
                    await asyncio.sleep(delay)
            finally:
                await page.close()
                await context.close()

        await browser.close()

    print(f"\n{'='*50}")
    print(f"注册完成: 成功 {success_count}/{count}")
    print(f"账号已保存到: {ACCOUNTS_FILE}")
    print(f"{'='*50}")


def show_accounts():
    if not ACCOUNTS_FILE.exists():
        print("暂无已保存的账号。")
        return

    with open(ACCOUNTS_FILE) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\n共 {len(rows)} 个账号:\n")
    for row in rows:
        status_icon = "✓" if row.get("status") == "success" else "⚠"
        print(f"  {status_icon} {row.get('email', 'N/A')} "
              f"| {row.get('first_name', '')} {row.get('last_name', '')} "
              f"| {row.get('status', 'N/A')}")


def main():
    global DEBUG_MODE

    parser = argparse.ArgumentParser(description="批量注册 Outlook 邮箱")
    parser.add_argument("--count", type=int, default=1, help="注册数量 (默认: 1)")
    parser.add_argument("--headless", type=str, default="true",
                        choices=["true", "false"], help="是否无头模式 (默认: true)")
    parser.add_argument("--debug", action="store_true",
                        help="开启调试模式，每步保存截图和 HTML")
    parser.add_argument("--proxy", type=str, default=None,
                        help="代理地址, 如 http://127.0.0.1:7890")
    parser.add_argument("--show", action="store_true", help="显示已注册的账号列表")
    args = parser.parse_args()

    if args.show:
        show_accounts()
        return

    DEBUG_MODE = args.debug

    asyncio.run(run_batch(
        count=args.count,
        headless=args.headless == "true",
        proxy=args.proxy,
    ))


if __name__ == "__main__":
    main()