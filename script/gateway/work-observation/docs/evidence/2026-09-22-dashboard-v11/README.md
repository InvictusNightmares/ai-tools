# 独立复核页 v11 部署证据

## 范围

- 时间：2026-09-22（Asia/Shanghai）
- 目标主机：GPU，受控内网地址 `192.168.64.16:8765`
- 发布目录：`/opt/work-observation/releases/observation-review-20260922-v11-dashboard`
- 变更对象：独立 `review_dashboard.py` 和 `review/` 静态页
- 未变更：采集器、`semantic.py`、滚动分析 worker、4000/4001、4004/4005、正式 Guard/Auto 路由
- 回退副本：`/etc/systemd/system/work-observation-review-dashboard.service.bak-20260922-v11-dashboard`

## 本地制品 SHA-256

```text
cbbfe507fb403334efb5e408afdae69d8b4cd34c9e95ad0eb83bcbcaad49f2c2  tools/review_dashboard.py
b74662a28264ed751d5d9aef57b7426ce076f46f3d86f9edf0b7358276783625  review/app.js
8148ed7f9e0d8121ec207335f776cd8c55cdae5c41df49bcf8f57060f78b9a9a  review/index.html
e475a15f6014a0accae6ebdd16ff7f2e29e637fc8857c6df6ebe851866f1ba73  review/styles.css
```

远端 release 的 `manifest.sha256` 与上述四个文件逐项一致。

## 验证结果

- `/healthz` 返回 `status=ok`。
- `/api/summary` 可区分 Guard 明确拦截、Guard 待人工处理、Auto 已返回和技术失败。
- `view=review` 默认仅返回尚未人工处理的明确 Guard block；`view=auto` 保留离线 Auto 结果，并明确线上是否实际执行。
- 页面验证了固定高度详情、分页当前范围、人工状态筛选、每页 50/100 条、上一条/下一条和保存并下一条。
- 本地 Python 回归：81 项通过、1 项因沙箱禁止监听跳过；`node --check review/app.js`、Python 编译和 `git diff --check` 通过。
- 部署后 socket 复核：`192.168.64.16:8765`、4000、4001、4004、4005 仍分别监听原端口；dashboard 只使用 8765。

## 运行数据边界

本次只发布页面和读取接口。GPU 上的离线分析 worker 保持原 release 和 timer；页面显示的技术失败仍不进入安全标签或 Auto 模型统计，也不代表训练或正式路由已完成。
