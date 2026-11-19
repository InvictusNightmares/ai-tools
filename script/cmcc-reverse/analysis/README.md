# 分析脚本

- `jsyd_probe.py`：江苏 act2510 公开 H5 接口探测。默认只做匿名请求，不保存凭证：

  ```bash
  python3 jsyd_probe.py --probe
  ```

  有有效 `jtToken` 时可验证登录：

  ```bash
  python3 jsyd_probe.py --jt-token '<token>' --cookie '<可选 Cookie>'
  ```

- `import_auto_login.py`：从 HAR 或 mitmproxy flow JSON 提取 `autoLogin` 模板，生成
  权限 `0600` 的青龙 profile：

  ```bash
  python3 import_auto_login.py \
    --input cmcc.har \
    --phone 188xxxxxxxx \
    --myway <江苏活动 mywaytoopen> \
    --out cmcc_profile.json
  ```

  输入支持 Proxyman/Charles/mitmproxy HAR，以及
  `capture/qwhd_capture.py` 保存的单条 `flows/<id>.json`。

- `sanitize_flows.py`：把原始 flow 脱敏成 `samples/*.sanitized.json`；保留 URL、方法、
  头名称、参数名和字段结构，替换 Cookie/token/手机号/设备标识。
- `samples/`：可提交的脱敏抓包样本和 `profile.example.json`。
- `test_import_auto_login.py`：离线测试模板解密、双层 base64 和 flow 解析：

  ```bash
  python3 -m unittest discover -s . -p 'test_*.py' -v
  ```

依赖：

```bash
pip3 install -r requirements.txt
```

profile、Cookie、token、手机号和 `xk`/`cellNum` 都是敏感数据，只放本地或青龙
`data/config/`，不得提交。
