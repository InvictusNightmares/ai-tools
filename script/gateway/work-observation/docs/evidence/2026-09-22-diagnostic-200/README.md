# 首批 200 条诊断集证据

## 范围

- 时间：2026-09-22（Asia/Shanghai）
- 数据集：`diagnostic-200-20260922`
- GPU 清单：`/data/work-observation/analysis/diagnostic-200.json`
- 页面：`http://192.168.64.16:8765/` 的“诊断集 200”视图
- 组成：Tokyo 100 条、US 100 条；分页每页 100 条，共 2 页

## 选择结果

| 选择桶 | 条数 |
| --- | ---: |
| Guard 拦截 | 58 |
| 技术失败 | 40 |
| 客户端/协议差异 | 36 |
| 业务结果失败或取消 | 30 |
| 长上下文/工具/附件 | 20 |
| 正常基线 | 16 |
| **合计** | **200** |

这些是候选样本的实际分布；分桶配额是选择上限，若某桶可用样本不足，会用固定 seed 的其它候选补足区域配额。

## 数据边界

- 清单只含事件标识、时间、入口、客户端/协议、模型、Guard/Auto 状态、选择桶和大小/工具特征。
- 清单不含 `source_path`、请求正文、回复正文或凭据。
- 生成过程只校验源记录，不调用 Guard、Auto，不启动 semantic worker。
- 页面打开单条结果时才在区域存储根目录内校验 SHA 并读取源记录。

## 校验

```text
e98e2987183691a9102dced873eac4ca94d5032a39591218963c5fe96544af80  /data/work-observation/analysis/diagnostic-200.json
f8263663cb60975428a2d524d4eb150a5ee85b15376b1eae2c68a944db3bd5c6  tools/review_dashboard.py
86140585d25821f07a0cfff610eb261f79c0bdbbe7470c5c2533c3ae71b6df5c  review/app.js
f711b8cd3d4752c5ca7e2f58197a4d16942fa078e667a47f59e440c8be50448e  review/index.html
54fbd3b6390ce64c576b81876b5ef1a0f21ffffbe53ef6455749f43d1071ee71  review/styles.css
e88632bad88946497959f866013f9d316a3fe5414697b5f33118f253169370c9  tools/diagnostic_set.py
```

GPU dashboard release：`/opt/work-observation/releases/observation-review-20260922-v12-diagnostic`。部署后 health、summary、诊断集第 1/2 页和单条 SHA 校验均返回成功；采集器、4000/4001、4004/4005 未改动，semantic timer 保持 inactive。
