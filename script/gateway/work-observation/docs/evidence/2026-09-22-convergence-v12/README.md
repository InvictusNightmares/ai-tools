# 2026-09-22 v12 收敛版与正式采集复核

本证据只记录无正文的部署和运行元数据，不保存员工请求、回复、认证头或模型输入。

## 代码与部署

- 本地分支：`main`（保留原有未提交修改）。
- GPU 分析 release：`/opt/work-observation/releases/observation-review-20260922-v12.1-convergence`（从 v12 基础 release 复制后更新 `semantic.py`）。
- systemd 执行路径已切到该 release；`WorkingDirectory`、`TimeoutStartSec=240s`、只读路径和分析目录保持原值。
- GPU 脚本 SHA256：
  - `tools/rolling.py` `cf1422f2cab8991b394c3d7623a9df10dd62900091bd16cb435cfb27edfb0e22`
  - `tools/semantic.py` `e0cf754d6740f8207549aeca753c76860f527b31aaa8743f2fe8f828f40acdb3`
- `/etc/work-observation/rolling.json` 当前语义配置为 `max_jobs=20`、`max_workers=1`、`max_attempts=3`、`timeout_seconds=8`；权限为 `root:work-observation 0640`。
- 配置和 service 修改前已保留 GPU 回退副本：
  - `/etc/work-observation/rolling.json.bak-20260922-v12-convergence`
  - `/etc/systemd/system/work-observation-analysis.service.bak-20260922-v12-convergence`

## 采集复核

复核时间约为 2026-09-22 13:37（Asia/Shanghai）。

| 区域 | capture_enabled | 15 秒 captured 增量 | 15 秒 written 增量 | dropped | write_errors | loss_persist_errors | truncated | projection_errors 总数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tokyo | true | 3 | 3 | 0 | 0 | 0 | 0 | 52 |
| US West | true | 17 | 120 | 0 | 0 | 0 | 0 | 0 |

- 4000→18400、4001→18401 的 Nginx 命名空间探针均 HTTP 200；4000、4001 外部入口探针均 HTTP 200。
- collector 与 live watchdog 两地均 `active`；US 曾因 watchdog 回退而关闭采集，本次已只重启 US watchdog 恢复旁路。4004/4005 未改动。
- `/data/work-observation` 总容量约 195.86 GiB，复核时剩余约 139.13 GiB。

## 分析队列

中止一次语义 worker 后，20 个未提交 claim 已恢复为 `pending`，达到 3 次上限的 8 个 pending 已转为 `deferred`。当前 `review_jobs` 状态为：

```text
complete  8014
deferred  5510
pending   4490
skipped   507
running   0
```

当前 `work-observation-analysis.timer` 和 service 均为 `inactive/dead`。这一步是为了遵守当前“不把员工正文继续发送到 Guard/Auto”的采集边界；v12 代码和配置已部署，但没有把一次未完成的 live batch 当作训练或质量验收证据。恢复 timer 前，应先明确允许哪一批离线正文进入 GPU 私有 8013/8014、8095/8096，并继续观察 `classifier_unavailable` 与 Guard/Auto 结果分层。

## 本地验证

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s script/gateway/work-observation/tests -p 'test_*.py'
83 tests passed, 1 skipped
node --check script/gateway/work-observation/review/app.js
python3 -m py_compile tools/rolling.py tools/semantic.py tools/review_dashboard.py
git diff --check
```

这些检查证明代码和状态机边界可运行，不代表真实样本已经完成离线复核、标注或训练。
