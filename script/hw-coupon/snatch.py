#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""华为云开发者成长中心 · 200 元代金券抢兑工具

接口（2026-10 实测）：
  基址  https://devdata.huaweicloud.com
  CSRF  GET  /api/get-ainfo                    -> 响应头 csrf
  积分  GET  /rest/developer/fwdu/rest/developer/user/hdcommunitysoservice/v1/growth/bonus-beans
  分类  GET  .../growth/prize-category
  列表  POST .../growth/prize                  body {page_no,page_size,prize_category}
  详情  POST .../growth/get-prize-detail       body {prize_id}   -> has_stock/remain_number/version
  兑换  POST .../growth/prize-exchange         body {prize_id,version,prize_count}
  记录  GET  .../growth/order?page_no=&page_size=&prize_category_ids=

成功判定：error_msg == "SUCCESS"
无库存：  HD.67510027 Prize Remain Number Not Enough
频繁：    99999999
登录/实名：HD.35020001 / HD.35020002

用法：
  python3 snatch.py check                     # 看积分 + 各券库存
  python3 snatch.py monitor                   # 常驻监听 200 券，记录补货时间
  python3 snatch.py run                       # 监听 + 有货立即兑换
  python3 snatch.py run --at 10:00:00         # 到点开始（服务器时间）
  python3 snatch.py run --value 200 --burst 3 --poll 0.8
"""
import argparse
import csv
import json
import os
import random
import sys
import threading
import time
from email.utils import parsedate_to_datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hw_cookies import cookie_header  # noqa: E402

BASE = "https://devdata.huaweicloud.com"
API = "/rest/developer/fwdu/rest/developer/user/hdcommunitysoservice/v1/growth"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36")
HERE = os.path.dirname(os.path.abspath(__file__))
LOG_CSV = os.path.join(HERE, "stock_log.csv")
EX_LOG = os.path.join(HERE, "exchange_log.txt")


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def notify(title, msg):
    print(f"\n>>> {title}: {msg}\n")
    try:
        os.system(
            "osascript -e 'display notification %s with title %s sound name \"Glass\"'"
            % (json.dumps(msg), json.dumps(title))
        )
        os.system("afplay /System/Library/Sounds/Glass.aiff >/dev/null 2>&1 &")
    except Exception:
        pass


class Api:
    def __init__(self, cookie=None, cookie_file=None):
        self.cookie_file = cookie_file
        self.s = requests.Session()
        self.s.trust_env = False
        self.s.headers.update({
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://developer.huaweicloud.com",
            "Referer": "https://developer.huaweicloud.com/grow",
        })
        self.cookie = cookie or self._load_cookie()
        self.s.headers["Cookie"] = self.cookie
        self.csrf = self._csrf()
        self.offset = 0.0
        self._bean_cache = (0, 0)
        self._last_refresh_msg = 0.0

    def _load_cookie(self):
        if self.cookie_file:
            with open(self.cookie_file, encoding="utf-8") as f:
                c = f.read().strip()
            if not c:
                raise RuntimeError(f"{self.cookie_file} 是空的")
            return c
        return cookie_header()

    def _csrf(self):
        r = self.s.get(BASE + "/api/get-ainfo", timeout=10)
        return r.headers.get("csrf") or ""

    def refresh(self):
        """重新读取登录态（本地 Chrome 或 cookie 文件）并刷新 CSRF。"""
        if time.time() - self._last_refresh_msg > 60:
            print(f"[{now()}] 刷新登录态 ...")
            self._last_refresh_msg = time.time()
        self.cookie = self._load_cookie()
        self.s.headers["Cookie"] = self.cookie
        self.csrf = self._csrf()

    def _req(self, method, path, payload=None, timeout=6, auth_retry=True):
        url = BASE + path
        headers = {"csrf": self.csrf} if self.csrf else {}
        try:
            if method == "GET":
                r = self.s.get(url, headers=headers, timeout=timeout)
            else:
                r = self.s.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
        except requests.RequestException as e:
            raise RuntimeError(f"网络错误: {e}")

        if r.status_code in (301, 302, 401, 403) or "text/html" in r.headers.get("content-type", ""):
            if auth_retry:
                self.refresh()
                return self._req(method, path, payload, timeout, auth_retry=False)
            raise RuntimeError(f"登录态失效 (HTTP {r.status_code})")

        try:
            j = r.json()
        except ValueError:
            raise RuntimeError(f"非 JSON 响应 HTTP {r.status_code}: {r.text[:120]}")
        j["_http"] = r.status_code
        return j

    # ---- 业务 ----
    def beans(self, ttl=20):
        ts, v = self._bean_cache
        if time.time() - ts < ttl:
            return v
        j = self._req("GET", f"{API}/bonus-beans")
        v = int(j.get("beans") or 0)
        self._bean_cache = (time.time(), v)
        return v

    def categories(self):
        return self._req("GET", f"{API}/prize-category").get("category_list") or []

    def prizes(self, category_id=None, page_size=100):
        body = {"page_no": 1, "page_size": page_size}
        if category_id:
            body["prize_category"] = category_id
        return self._req("POST", f"{API}/prize", body).get("prize_list") or []

    def detail(self, prize_id):
        return self._req("POST", f"{API}/get-prize-detail", {"prize_id": prize_id})

    def exchange(self, prize_id, version, count=1):
        return self._req("POST", f"{API}/prize-exchange",
                         {"prize_id": prize_id, "version": version, "prize_count": count},
                         timeout=10)

    def orders(self, category_id, page_size=10):
        return self._req("GET", f"{API}/order?page_no=1&page_size={page_size}"
                                f"&prize_category_ids={category_id}")

    def server_offset(self):
        """服务器时间 - 本机时间（秒）"""
        try:
            r = self.s.get(BASE + "/api/get-ainfo", timeout=5)
            d = r.headers.get("Date")
            if d:
                self.offset = parsedate_to_datetime(d).timestamp() - time.time()
        except Exception:
            pass
        return self.offset


def find_target(api, value, name_kw):
    cats = api.categories()
    cid = cats[0]["id"] if cats else None
    items = api.prizes(cid)
    for p in items:
        try:
            pv = float(p.get("prize_value") or 0)
        except (TypeError, ValueError):
            pv = 0
        if (value and pv == value) or (name_kw and name_kw in p.get("name", "")):
            return p, cid, items
    raise SystemExit(f"没找到目标券 value={value} name~={name_kw}，当前列表: "
                     + ", ".join(p.get("name", "?") for p in items))


def is_stock(p):
    return str(p.get("has_stock")) == "1" and int(p.get("remain_number") or 0) > 0


def log_stock(p, beans, state_key):
    new = not os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "prize", "has_stock", "remain", "version", "beans"])
        w.writerow([now(), p.get("name"), p.get("has_stock"), p.get("remain_number"),
                    p.get("version"), beans])


def make_api(args):
    return Api(cookie_file=getattr(args, "cookie_file", None))


def resolve_target(api, args):
    """登录态失效/网络抖动时等待重试，避免 systemd 崩溃循环。"""
    while True:
        try:
            return find_target(api, args.value, args.name)
        except SystemExit:
            raise
        except Exception as e:
            print(f"[{now()}] 初始化失败: {e}")
            print(f"[{now()}] 可能是登录态过期或网络问题，30s 后重试；"
                  f"若持续出现请重新 export-cookie")
            time.sleep(30)
            try:
                api.refresh()
            except Exception as e2:
                print(f"[{now()}] 刷新登录态失败: {e2}")


def cmd_check(args):
    api = make_api(args)
    api.server_offset()
    beans = api.beans(ttl=0)
    print(f"[{now()}] 服务器时差 {api.offset:+.2f}s | 积分 {beans}")
    cats = api.categories()
    cid = cats[0]["id"] if cats else None
    print(f"{'商品':<16}{'积分':>6}{'面值':>6}{'库存':>8}{'剩余':>7}{'版本':>6}  id")
    for p in api.prizes(cid):
        print(f"{p.get('name',''):<16}{p.get('bonus',''):>6}{str(p.get('prize_value','')):>6}"
              f"{p.get('has_stock'):>8}{str(p.get('remain_number','')):>7}{str(p.get('version','')):>6}  {p.get('id')}")
    print("\n提示：只有 has_stock=1 且 remain_number>0 才能兑。")


def _wait_until(api, at, prefire):
    hh, mm, ss = [int(x) for x in (at.split(":") + ["0", "0"])[:3]]
    t = time.localtime()
    target = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hh, mm, ss, 0, 0, -1))
    if target < time.time():
        target += 86400
    print(f"[{now()}] 等待到 {at}（提前 {prefire}s 起跑），服务器时差 {api.offset:+.2f}s")
    while True:
        remain = target - time.time() - api.offset - prefire
        if remain <= 0:
            break
        if remain > 60:
            time.sleep(min(30, remain - 30))
        else:
            time.sleep(0.05)


def try_exchange(api, pid, bonus, attempts=8):
    for i in range(attempts):
        try:
            d = api.detail(pid)
        except Exception as e:
            print(f"[{now()}] 详情失败: {e}")
            time.sleep(0.2)
            continue
        if not is_stock(d):
            print(f"[{now()}] 库存刚被抢光（第 {i+1} 次）")
            return False
        beans = api.beans(ttl=5)
        if beans < bonus:
            notify("积分不足", f"需要 {bonus}，当前 {beans}")
            return False
        ver = d.get("version")
        print(f"[{now()}] 有货 remain={d.get('remain_number')} version={ver} -> 提交兑换")
        try:
            r = api.exchange(pid, ver)
        except Exception as e:
            print(f"[{now()}] 兑换请求异常: {e}")
            time.sleep(0.2)
            continue

        msg, code = r.get("error_msg"), r.get("error_code")
        with open(EX_LOG, "a", encoding="utf-8") as f:
            f.write(f"{now()} version={ver} http={r.get('_http')} code={code} msg={msg}\n")
        print(f"[{now()}] 返回: {code} {msg}")

        if msg == "SUCCESS":
            notify("抢到了", f"200元代金券兑换成功")
            print("订单号/券请在 费用中心 > 优惠券 查看。")
            return True
        if code == "HD.67510027":       # 又没了
            return False
        if code == "99999999":          # 操作频繁
            time.sleep(3)
        elif code in ("HD.35020001", "HD.35020002"):
            notify("需要处理", f"{code} {msg}（登录态/实名认证）")
            return False
        else:
            time.sleep(0.15)
    return False


def cmd_monitor(args):
    api = make_api(args)
    api.server_offset()
    prize, cid, items = resolve_target(api, args)
    pid = prize["id"]
    bonus = int(prize.get("bonus") or 0)
    print(f"目标: {prize['name']} id={pid} 积分={bonus} 当前库存={prize.get('remain_number')} "
          f"version={prize.get('version')} | 服务端时差 {api.offset:+.2f}s")
    last_state = None
    last_beat = 0
    while True:
        try:
            d = api.detail(pid)
        except Exception as e:
            print(f"[{now()}] 轮询失败: {e}")
            time.sleep(2)
            continue
        beans = api.beans(ttl=30)
        state = (str(d.get("has_stock")), d.get("remain_number"), d.get("version"))
        if state != last_state:
            print(f"[{now()}] has_stock={d.get('has_stock')} remain={d.get('remain_number')} "
                  f"version={d.get('version')} beans={beans}")
            log_stock(d, beans, state)
            last_state = state
            last_beat = time.time()
        elif args.verbose:
            print(f"[{now()}] poll remain={d.get('remain_number')} version={d.get('version')} beans={beans}")
        elif time.time() - last_beat > args.heartbeat:
            print(f"[{now()}] 心跳 remain={d.get('remain_number')} version={d.get('version')} "
                  f"beans={beans}（无变化）")
            last_beat = time.time()
        if is_stock(d) and not args.no_alert:
            notify("有货了", f"{prize['name']} 剩余 {d.get('remain_number')}")
            last_state = None          # 冷却 60s 后继续监听，避免反复响铃
            time.sleep(60)
            continue
        time.sleep(random.uniform(args.poll_min, args.poll_max))


def cmd_run(args):
    api = make_api(args)
    api.server_offset()
    prize, cid, items = resolve_target(api, args)
    pid = prize["id"]
    bonus = int(prize.get("bonus") or 0)
    beans = api.beans(ttl=0)
    print(f"[{now()}] 目标 {prize['name']} (id={pid}) 需要 {bonus} 积分，当前 {beans} 积分")
    if beans < bonus:
        print("!! 积分不足，脚本会继续等（积分到账后自动可用）")
    print(f"当前: has_stock={prize.get('has_stock')} remain={prize.get('remain_number')} "
          f"version={prize.get('version')} | 服务端时差 {api.offset:+.2f}s")

    if args.at:
        _wait_until(api, args.at, args.prefire)

    last_state = None
    last_beat = 0
    auth_fails = 0
    while True:
        try:
            d = api.detail(pid)
            auth_fails = 0
        except Exception as e:
            if "登录态失效" in str(e):
                auth_fails += 1
                if auth_fails == 1 or auth_fails % 30 == 0:
                    print(f"[{now()}] 登录态失效（第 {auth_fails} 次）：Cookie 已过期，"
                          f"请重新 export-cookie 并同步到服务器")
                if auth_fails >= 5:
                    print(f"[{now()}] 连续失效，暂停 5 分钟后再试")
                    time.sleep(300)
                    auth_fails = 0
                else:
                    time.sleep(3)
            else:
                print(f"[{now()}] 轮询失败: {e}")
                time.sleep(2)
            continue
        beans = api.beans(ttl=30)
        state = (str(d.get("has_stock")), d.get("remain_number"), d.get("version"))
        if state != last_state:
            print(f"[{now()}] has_stock={d.get('has_stock')} remain={d.get('remain_number')} "
                  f"version={d.get('version')} beans={beans}")
            log_stock(d, beans, state)
            last_state = state
            last_beat = time.time()
        elif args.verbose:
            print(f"[{now()}] poll remain={d.get('remain_number')} version={d.get('version')} beans={beans}")
        elif time.time() - last_beat > args.heartbeat:
            print(f"[{now()}] 心跳 remain={d.get('remain_number')} version={d.get('version')} "
                  f"beans={beans}（无变化）")
            last_beat = time.time()

        if is_stock(d):
            notify("检测到有货", f"{prize['name']} 剩余 {d.get('remain_number')}，开始抢")
            got = [False] * args.burst
            lock = threading.Lock()

            def worker(idx):
                if got[0] or got[-1]:
                    return
                ok = try_exchange(api, pid, bonus)
                if ok:
                    with lock:
                        got[0] = True

            threads = [threading.Thread(target=worker, args=(i,), daemon=True)
                       for i in range(args.burst)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=15)
            if any(got):
                return
            print(f"[{now()}] 本轮没抢到，继续监听")
        time.sleep(random.uniform(args.poll_min, args.poll_max))


def cmd_export(args):
    path = args.cookie_file or os.path.join(HERE, "cookie.txt")
    h = cookie_header()
    with open(path, "w", encoding="utf-8") as f:
        f.write(h)
    os.chmod(path, 0o600)
    print(f"已导出 Cookie 到 {path}（{len(h)} 字节，权限 600）")
    print("传到服务器后：python3 snatch.py check --cookie-file " + path)


def main():
    ap = argparse.ArgumentParser(description="华为云成长中心代金券抢兑")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--cookie-file", default=None,
                        help="使用导出的 cookie.txt（服务器上跑时用），不传则从本机 Chrome 解密")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", parents=[common], help="查看积分与库存")
    c.set_defaults(func=cmd_check)

    m = sub.add_parser("monitor", parents=[common], help="监听库存/补货时间")
    m.add_argument("--value", type=float, default=200)
    m.add_argument("--name", default=None)
    m.add_argument("--poll-min", type=float, default=0.8)
    m.add_argument("--poll-max", type=float, default=1.3)
    m.add_argument("--no-alert", action="store_true")
    m.add_argument("--heartbeat", type=float, default=60, help="无变化时每隔多少秒打一行心跳")
    m.add_argument("--verbose", action="store_true", help="每轮都打印")
    m.set_defaults(func=cmd_monitor)

    r = sub.add_parser("run", parents=[common], help="监听并自动兑换")
    r.add_argument("--value", type=float, default=200)
    r.add_argument("--name", default=None)
    r.add_argument("--poll-min", type=float, default=0.7)
    r.add_argument("--poll-max", type=float, default=1.2)
    r.add_argument("--burst", type=int, default=2)
    r.add_argument("--at", default=None, help="HH:MM[:SS] 服务器时间起跑")
    r.add_argument("--prefire", type=float, default=0.4)
    r.add_argument("--heartbeat", type=float, default=60, help="无变化时每隔多少秒打一行心跳")
    r.add_argument("--verbose", action="store_true", help="每轮都打印")
    r.set_defaults(func=cmd_run)

    e = sub.add_parser("export-cookie", help="导出 Cookie 文件给服务器用")
    e.add_argument("--cookie-file", default=None, help="输出路径，默认 ./cookie.txt")
    e.set_defaults(func=cmd_export)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
