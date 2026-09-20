# 多语言分类诊断基线

日期：2026-09-15，Asia/Shanghai。范围：中文、英文、中英混合；原 stage12 Go 分类器，无词表补丁，无供应商调用。

## 方法与复现边界

[36 条输入](cases.json)按 12 个独立语义场景组成中/英/混合三联组。每条均从新会话、相同模型目录与空健康配置开始。6 类小源任务来自历史摘要重建，其余为合成反例；不是原始历史记录逐 token 重放。期望任务类型与复杂度是审核者标签，不能证明某个模型的真实解题能力。

GPU 诊断目录：`/tmp/multilingual-probe-20260915.upP8Tq`；复制原 stage12 Go 源码，在独立目录加入 [探针](probe_test.go.txt) 和 `multilingual-cases.json`，通过已有 `golang:1.27.1-bookworm` 运行 `go test -run TestMultilingualDiagnostic -v`。原始结果见 [baseline-go.log](baseline-go.log)，结构化结果见 [baseline.json](baseline.json)。日志中的 PASS 只表示诊断程序执行完成，**不是分类质量验收通过**。生产配置和分类逻辑未改。

## 观察

| 场景 | 中文 | 英文 | 中英混合 |
| --- | --- | --- | --- |
| 网络层排障 | flash / none / quick_qa | luna / none / debugging | luna / none / debugging |
| 跨端会话方案 | terra / low | terra / medium | terra / medium |
| 解释“架构”这个词 | terra / low | terra / low | terra / low |
| 简短并发状态正确性问题 | flash / none / quick_qa | flash / none / quick_qa | flash / none / quick_qa |
| 单词翻译，附带无关工具目录 | terra / medium / agent | terra / medium / agent | terra / medium / agent |
| 登录 UI、退出登录、发布审计、卡片宽度、环境切换（5 组） | 均 flash / none / quick_qa | 均 flash / none / quick_qa | 均 flash / none / quick_qa |

36 条分布：flash 22、luna 5、terra 9；none 24、low 7、medium 5；无 sol、astra、high、xhigh。12 组中 2 组出现跨语言 intent/model/effort 差异，一致率 10/12（83.3%）；一致本身不代表正确，很多组是三种语言一起误判。少量人工样本只用于复现缺陷，不代表总体误差率。

## 结论

现有代码把词出现等同于任务意图，把工具列表等同于复杂工具任务，并且无法识别多种语言中的简短复杂任务。缺口是语义理解、上下文分层和质量标定，追加中英文关键词不足以完成修复。临时词表补丁已撤回，语义分类器待按[总计划](../../智能网关与Guard分阶段实施总计划.md#621-分类器重设计中文英文与中英混合输入)实现和验收。

## Astra 上游记录核对

2026-09-15 17:55 东京只读统计：测试 Key ID 141 当日共 20 条业务用量，DeepSeek 16 条（none 10、low 5、未传 1），Luna 4 条（low 3、未传 1），没有 astra。GPU 17:05 的三个 astra 决策对应 `success=false`、输入/输出 0，是未带 Key 的 401，不能宣称成功。

17:55 使用授权 Key 在临时 8093 补测：第一轮 luna/low HTTP 200，东京业务记录 ID 954059，27 输入 token、12 输出 token；第二轮选中 astra/xhigh，但 Auto usage 为失败、0 token，测试客户端还出现非 JSON 响应解析失败。截至后续查询，东京没有相应 astra 业务用量或该 Key 的错误记录。未能定位到有证据的错误阶段前，不能断言具体是供应商、前置还是网络故障。仍未通过 astra 业务调用验收。

只读数据库观察已归档至 [tokyo-usage-check.json](tokyo-usage-check.json)。18:03 再次诊断时堡垒机连接关闭，未得到新的 HTTP 状态证据，不继续声称最高档调用通过。第一次补测已停止临时进程并删除服务器测试 Key 文件。
