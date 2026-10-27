# 华为云成长中心 · 200 元代金券抢兑

实测时间：2026-10-27。目标页 `https://developer.huaweicloud.com/grow`，
真实 API 域名 `https://devdata.huaweicloud.com`，Cookie 鉴权 + CSRF。

## 文件

| 文件 | 作用 |
|---|---|
| `hw_cookies.py` | 从本机 Chrome 解密华为云登录 Cookie（macOS 钥匙串） |
| `snatch.py` | 查库存 / 监听补货 / 自动兑换 |
| `stock_log.csv` | 监听时自动写入的库存变化记录（用于摸清补货时间） |
| `exchange_log.txt` | 每次兑换请求的原始返回 |

## 已确认的接口

```
基址  https://devdata.huaweicloud.com
CSRF  GET  /api/get-ainfo                          -> 响应头 csrf
积分  GET  /rest/developer/fwdu/rest/developer/user/hdcommunitysoservice/v1/growth/bonus-beans
分类  GET  .../growth/prize-category
列表  POST .../growth/prize                        {"page_no","page_size","prize_category"}
详情  POST .../growth/get-prize-detail             {"prize_id"}
兑换  POST .../growth/prize-exchange               {"prize_id","version","prize_count"}
记录  GET  .../growth/order?page_no=&page_size=&prize_category_ids=
```

- 有货判断：`has_stock == "1"` 且 `remain_number > 0`
- 兑换必须带**当前** `version`（库存变动会自增），所以脚本每次兑换前先拉一次详情
- 成功：`error_msg == "SUCCESS"`
- 无库存：`HD.67510027 Prize Remain Number Not Enough`
- 请求过频：`99999999`
- 登录/实名问题：`HD.35020001` / `HD.35020002`

## 用法

```bash
cd script/hw-coupon

python3 snatch.py check        # 看积分 + 所有券库存/版本
python3 snatch.py monitor      # 常驻监听 200 券，有货响铃 + 写 stock_log.csv
python3 snatch.py run          # 监听 + 有货自动兑换（成功响铃并退出）
python3 snatch.py run --at 10:00:00 --burst 3 --poll 0.7
```

可选参数：

- `--value 200`：按面值找券
- `--name 200元`：按名称找券
- `--at HH:MM:SS`：按**服务器时间**到点开抢（自动校时，提前 `--prefire` 秒起跑）
- `--burst N`：有货时并发兑换线程数，默认 2，别超过 5
- `--poll 0.7~1.2`：轮询间隔，低于 0.3s 容易被 WAF 掐

## 明天（积分到 2000 后）

1. 先 `check` 确认 `积分 >= 2000`。
2. 白天挂 `monitor`，把 `stock_log.csv` 里 `has_stock` 从 0 变 1 的时间点记下来——这就是补货时刻。
3. 已知补货时段前后，跑 `run --at <时刻>`，脚本会提前 0.4s 起跑。
4. 抢到后去 **费用中心 → 优惠折扣 → 代金券** 确认到账，30 天有效。

## 不想一直开电脑？三种跑法

### 方案 A：Mac 不关（最快，今晚就能用）

```bash
cd script/hw-coupon

# 前台常驻（自动阻止睡眠、崩溃自动重启、抢到自动退出）
./run-forever.sh run --value 200

# 或装成登录自启的 LaunchAgent
cp com.invictus.hwcoupon.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.invictus.hwcoupon.plist
```

注意：`caffeinate` 挡不住**合盖睡眠**。笔记本要么开盖插电，要么执行
`sudo pmset -a disablesleep 1`（会发热耗电，用完改回 `pmset -a disablesleep 0`）；
Mac mini / iMac 直接挂着就行。

### 方案 B：挪到服务器（推荐长期用，电脑随便关）

华为云 ECS / Flexus 上都行：

```bash
# 1. 本机导出登录态
python3 snatch.py export-cookie            # 生成 cookie.txt (600 权限)

# 2. 传到服务器
scp cookie.txt snatch.py hw_cookies.py user@HOST:~/hw-coupon/

# 3. 服务器上先验证登录态（关键：换 IP 可能触发风控）
ssh user@HOST
cd ~/hw-coupon
python3 snatch.py check --cookie-file cookie.txt

# 4. 验证通过后常驻
nohup bash run-forever.sh run --cookie-file cookie.txt --value 200 > run.log 2>&1 &
```

- 第 3 步若返回“登录态失效”，说明华为云对这个 IP 不认，换同城/同省节点再试；
  还不行就退回方案 A。
- 服务器没有 `afplay`，响铃会静默失败，但日志和兑换不受影响。
- Cookie 会过期，过期后本机重新 `export-cookie` 再传一次即可。
- 想把 `run-forever.sh` 做成开机自启，systemd 里 `ExecStart=/bin/bash /home/user/hw-coupon/run-forever.sh run --cookie-file /home/user/hw-coupon/cookie.txt`。

### 方案 C：只在补货窗口开机（最省事）

先让 `monitor` 跑一天，看 `stock_log.csv` 里 `has_stock` 从 0 变 1 的时间点；
补货时间通常固定，之后每天只在那个时间前后 10 分钟开机跑：

```bash
python3 snatch.py run --at 10:00:00 --burst 3
```

今天这批已经放过了，正好从明天开始把窗口摸出来。

## 注意

- 券规则写死：单用户每天限兑 1 张，200 元券全年最多 2 张；兑换前需完成实名认证。
- 规则明确禁止多账号刷分，用单账号 + 单 IP，别开小号一起抢。
- 浏览器登录态过期后脚本会自动重新解密 Chrome Cookie；只要 Chrome 里是登录状态即可。
- Chrome 正在运行时也能读 Cookie（复制数据库读取），不需要退出浏览器。
