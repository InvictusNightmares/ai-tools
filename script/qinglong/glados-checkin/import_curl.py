#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从浏览器「Copy as cURL」文本中提取 GLaDOS Cookie 与 User-Agent。

用法：
  # 1. 在 glados.cloud 控制台 F12 -> Network，刷新后右键 challenge 请求
  #    Copy -> Copy as cURL (bash)，粘贴到 .curl.txt
  # 2. 运行：
  python3 import_curl.py .curl.txt

生成同目录 .env.local（权限 0600），内容形如：
  export GLADOS_COOKIE='gld:sess=...; gld:sess.sig=...'
  export GLADOS_USER_AGENT='Mozilla/5.0 ...'

之后运行：
  set -a; source .env.local; set +a
  python3 glados_checkin.py --check
"""

import os
import shlex
import sys

REQUIRED = ("gld:sess", "gld:sess.sig")
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.local")


def parse_curl(text):
    text = text.replace("\\\r\n", " ").replace("\\\n", " ")
    try:
        tokens = shlex.split(text)
    except ValueError as exc:
        raise SystemExit(f"cURL 文本解析失败：{exc}")

    headers = {}
    cookie = None
    url = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in ("-H", "--header") and i + 1 < len(tokens):
            name, sep, value = tokens[i + 1].partition(":")
            if sep:
                headers[name.strip().lower()] = value.strip()
            i += 2
        elif token in ("-b", "--cookie") and i + 1 < len(tokens):
            cookie = tokens[i + 1]
            i += 2
        elif token in ("--url",) and i + 1 < len(tokens):
            url = tokens[i + 1]
            i += 2
        elif token.startswith("http://") or token.startswith("https://"):
            url = token
            i += 1
        else:
            i += 1

    cookie = cookie or headers.get("cookie")
    ua = headers.get("user-agent")
    return url, cookie, ua


def cookie_names(cookie):
    names = []
    for item in cookie.split(";"):
        name, sep, _ = item.strip().partition("=")
        if sep and name:
            names.append(name)
    return names


def mask(cookie):
    return "; ".join(f"{name}=***" for name in cookie_names(cookie))


def shell_quote(value):
    return "'" + value.replace("'", "'\\''") + "'"


def main(argv):
    path = argv[0] if argv else ".curl.txt"
    if path == "-":
        text = sys.stdin.read()
    else:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            raise SystemExit(f"读取失败：{exc}")

    url, cookie, ua = parse_curl(text)
    if not cookie:
        raise SystemExit("未找到 Cookie：请确认复制的是已登录状态下的 challenge/status 请求")
    if url and "glados" not in url:
        print(f"⚠️ 请求域名不是 glados：{url}", file=sys.stderr)

    names = cookie_names(cookie)
    missing = [name for name in REQUIRED if name not in names]
    if missing:
        raise SystemExit(
            "Cookie 缺少 " + ", ".join(missing) +
            "；请重新登录 https://glados.cloud 后再复制，且必须是签到页的请求"
        )

    lines = [
        "# 由 import_curl.py 生成，含登录凭据，禁止提交或分享",
        f"export GLADOS_COOKIE={shell_quote(cookie)}",
    ]
    if ua:
        lines.append(f"export GLADOS_USER_AGENT={shell_quote(ua)}")
    lines.append("")
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    os.chmod(OUTPUT, 0o600)

    print(f"已写入 {OUTPUT}（权限 0600）")
    print(f"Cookie: {mask(cookie)}")
    print(f"User-Agent: {'已提取' if ua else '未找到，将使用脚本默认 UA'}")
    print("\n下一步：")
    print(f"  set -a; source {OUTPUT}; set +a")
    print("  python3 glados_checkin.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
