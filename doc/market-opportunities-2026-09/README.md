# 2026 年 50 个低成本赚钱项目：完整执行包

> **研究快照：2026-09-01。** 适用对象是中国境内个人或 1–3 人团队，优先面向全球线上客户；默认现金预算不超过 ¥10,000，优先低于 ¥2,000，并要求 30 天内能验证真实付费。所有收益均为透明情景假设，不是保证；涉及 USD 的统一换算模型为 US$1=¥7，执行日必须以平台与银行实际汇率/费用替换。

## 先做哪三个最稳

1. **[Merchant Center Feed 诊断与免费列表修复](methods/20-merchant-feed-repair.md)**：Google Merchant Center 直接给出 issue code、Product status 和 destination visibility；现金成本近零，先修一个错误类别即可收费。技术尾款只在商品 Approved 且目标 visibility 通过后触发，不承诺展示、点击或销量。
2. **[HubSpot 入站线索分级与人工路由试点](methods/01-ai-lead-routing.md)**：企业 AI 落地仍低，而 Upwork 的 AI integration 需求增长；这个项目直接缩短首响和减少漏单，可按设置费+监控费销售。关键是规则优先、人工审批、不自动拒绝。
3. **[GA4 电商事件与 Looker 漏斗仪表盘](methods/22-ga4-ecommerce-funnel.md)**：GA4 电商事件必须显式实施，测试订单可以做金额、币种和去重验收；交付边界清楚，失败也能定位到具体事件，而不是争论“营销有没有变好”。

**建议顺序：**先只选其中一个，Day 1–7 做公开/脱敏样例，Day 8–20 手工触达 20 个高度相关买方；Day 20 结束时必须拿到真实付费信号（已注资里程碑、平台净订单或已入账合法账单），或明确拒绝原因。延迟结算平台的订单不写成银行到账，不要同时启动三个。

## 研究与筛选方法

- 第一轮独立扫描 105 个候选，覆盖 B2B 自动化、电商/网站、公共数据、数字产品和微型软件。
- 第二轮只补最终候选的官方 API、平台准入、费率、数据许可、竞品价格与付款边界。
- 统一评分：需求证据 20%、验证速度 15%、低成本 10%、复购性 15%、自动化杠杆 15%、获客可达 15%、风险可控 10%。
- 剔除：假评论、刷量、自动 LinkedIn/批量冷邮件、个人数据抓取、代收款/账户套利、AI 外呼/声音克隆、侵权资产、PLR/MRR、提示词包、无差异低内容书、投资/医疗/法律自动决策和任何绕过地区/平台限制的方案。
- 市场事实与本报告假设分开：带链接的数据是来源事实；价格、订单数、收益情景是用于验证的模型，必须以预售结果替换。

完整证据账本与候选收敛记录见 [研究底稿](research/report-source.md)。共享脚本均是低风险 MVP 辅助，不会替代许可核验或人工判断。

## 中国境内执行的四条硬边界

1. 中国大陆不在 OpenAI API 当前支持地区；默认使用合规的国内模型/区域，或由支持地区客户在其自有基础设施执行，绝不教绕过。
2. Stripe 不支持大陆主体直接开户；服务项目只配置客户自有受支持地区账户，不代收资金。
3. Etsy 大陆新店不可开，不能作为默认渠道。Creative Market/Patreon/Udemy/KDP/Upwork 都必须使用真实身份、税务和收款资料。Upwork Project Catalog Price、offer 与 milestone 都输入 USD，人民币只作内部折算；普通职位先 `Apply now`，收到客户 Offer 后走 `Messages > View offer > Accept offer`，再确认当前 fixed-price milestone 为 Active/Funded。只有已付款旧客户可从 `Messages > View contract > … > Propose new contract`，有效 Project Catalog 主动询盘才从 `Messages > Propose new contract`；Catalog 直接购买沿用现有已注资订单，卖方任何分支都不点击 Fund。`Account settings > Withdrawals > Add a method > Direct to Local Bank > Set up` 支持中国 CNY，新方式 3 天激活、US$0.99/次、提现后通常 4 天内到银行。固定价完成后必须走 `Deliver work > Your active contracts > Submit work` 才启动审核；状态在 `Manage finances > Financial overview/Transactions` 核对，客户批准后还有 5 天安全期。Creative Market 本币提现通常需等值 US$1,030 且随币种变化，不能只写 US$20。Udemy 的 30 天实验只记订单/应计讲师收入；KDP 发行前只记 Pre-Order Report 净预售单，发行后才计版税。均不把延迟结算写成银行到账。
4. 公开数据不等于可无限转售：只用官方 API/bulk，保留来源与链接，不镜像原始整库或第三方附件；许可不清时不收费、不处理真实数据、不交付，先用合成数据演示结构，并在报价前取得来源方书面许可分类。“只卖分析”本身不是免许可理由。

## 50 个完整方法

01. [HubSpot 入站线索分级与人工路由试点](methods/01-ai-lead-routing.md) — 7 天固定试点：1 个 HubSpot 表单、1 个联系人对象、3 个负责人、20–100 条授权历史线索；只写测试字段和审批草稿
02. [会议转写到 CRM 与任务自动化](methods/02-meeting-to-crm.md) — 5 场会议影子试点：只生成草稿，不自动写入；确认后再启用 CRM 写入
03. [共享邮箱分类与回复草稿](methods/03-shared-inbox-triage.md) — 100 封脱敏历史邮件影子模式试点，不自动发送
04. [客服工单优先级与 SLA 升级](methods/04-support-sla-triage.md) — 200 条历史工单离线回测加 14 天影子监控
05. [网站 FAQ/RAG 客服机器人](methods/05-faq-rag-bot.md) — 20–50 份文档、50 个真实问题、一个网页组件的 14 天试点
06. [内部 SOP 知识助手](methods/06-internal-sop-assistant.md) — 20–50 份 SOP、30 个测试问题、一个团队空间的试点
07. [提案与报价草稿生成器](methods/07-proposal-generator.md) — 用 10 份已成交提案建立一个服务线模板和审批流程
08. [成交后客户 Onboarding 自动化](methods/08-client-onboarding-automation.md) — 一个产品、一个付款/deal 触发、一个项目模板的 10 天试点
09. [预约提醒与爽约降低工作流](methods/09-no-show-reduction.md) — 一个 event type、最多 50 个预约的 14 天试点
10. [发票提醒与失败付款恢复](methods/10-invoice-recovery.md) — 7 天 sandbox 试点：1 条订阅失败付款路径、1 条 send_invoice 提醒路径和 8 个测试用例；不连接真实客户、不触碰资金
11. [每日/每周 KPI 管理摘要](methods/11-kpi-digest.md) — 2 个数据源、5 个指标、1 份周报的 7 天试点
12. [PDF/邮件订单结构化入库](methods/12-document-extraction.md) — 100 份脱敏样本、最多 12 个字段、一个输出表的离线试点
13. [NPS/CSAT/评论主题洞察月报](methods/13-feedback-insights.md) — 200–1,000 条脱敏反馈的首月报告与 30 条人工双标
14. [CRM 清洗、去重与生命周期提醒](methods/14-crm-cleanup.md) — 1,000 条以内 CSV/CRM 只读审计加 100 条样本迁移
15. [合规的真实评论请求工作流](methods/15-review-request-workflow.md) — 一个服务完成触发、一个地点、50 位已有客户的 14 天试点
16. [Google Business Profile 月度运营](methods/16-gbp-operations.md) — 一个地点的资料审计、4 条帖子、20 条回复草稿和基线月报
17. [Webinar/Podcast 多渠道内容包](methods/17-content-repurposing.md) — 一场公开视频样稿：3 个短片、1 封邮件、3 条帖子和引用核对表
18. [YouTube 自动配音审核与本地化](methods/18-youtube-localization-qa.md) — 一个 10 分钟以内公开视频、一个语言的术语和 QA 试点
19. [电商目录、Variant 与属性清洗](methods/19-ecommerce-catalog-cleanup.md) — 100 个 SKU 的审计与 20 个 SKU 样本修复
20. [Merchant Center Feed 诊断与免费列表修复](methods/20-merchant-feed-repair.md) — 一个国家、最多 100 个商品、一个高影响错误类别的 10 天试点
21. [Product/Offer/ReturnPolicy 结构化数据实施](methods/21-product-structured-data.md) — 一个商品模板、5 个 SKU、一个市场的固定范围实施
22. [GA4 电商事件与 Looker 漏斗仪表盘](methods/22-ga4-ecommerce-funnel.md) — 一个店，view_item/add_to_cart/view_cart/begin_checkout/purchase 五个事件，3 条测试旅程、2 个不同 transaction_id 和一页 Looker 看板
23. [Core Web Vitals 快修 Sprint](methods/23-core-web-vitals-sprint.md) — 一个模板/五个 URL、最多三类高影响问题的 7 天 Sprint
24. [WordPress 备份、更新与健康检查 Care Plan](methods/24-wordpress-care-plan.md) — 一个站的首次健康审计、完整备份与一次 staging 恢复演练
25. [Shopify 弃单、购后与复购自动化配置](methods/25-shopify-lifecycle-flows.md) — 欢迎、弃单、购后三条流程，限一个市场与语言
26. [Shopify 多语店面本地化 QA](methods/26-shopify-localization-qa.md) — 一个 collection、最多 20 个 SKU、一个目标语言的 QA 试点
27. [电商客服宏、订单路由与 AI 辅助](methods/27-ecommerce-support-macros.md) — 100 条历史工单、10 个宏、5 个意图的影子试点
28. [SPF/DKIM/DMARC 邮件送达基础配置](methods/28-email-deliverability.md) — 一个域名、最多三个合法发件源的只读审计和 p=none 上线
29. [中小企业网络安全卫生基线](methods/29-smb-cyber-hygiene.md) — 一个 Google Workspace 或 Microsoft 365 租户、一个客户已有备份系统；10 项检查、红黄绿报告、最多 3 项批准的低风险修复和 1 次隔离恢复，不做渗透测试
30. [小型网站 WCAG 2.2 A/AA 重点项审计与修复 Sprint](methods/30-accessibility-audit-fix.md) — 5 个代表页面/状态、10 类 WCAG 2.2 A/AA 重点项范围测试、最多 10 个代码/内容修复；属于抽样评估，不是整站符合性声明
31. [SAM.gov 垂直投标提醒与 Bid/No-Bid 摘要](methods/31-sam-bid-alerts.md) — 一个 NAICS/关键词组合、7 天人工审核日报、最多 20 条机会
32. [USAspending 续约与 Incumbent 情报](methods/32-usaspending-renewal-intel.md) — 一个机构/NAICS、过去三年、20 个 incumbent 信号的一次性报告
33. [Grants.gov 资助匹配与截止日提醒](methods/33-grants-matching.md) — 一个项目画像、7 天监测、10 条人工核验机会
34. [TED 欧盟招标中文垂直简报](methods/34-ted-tender-brief.md) — 一个 CPV/国家组合、7 天日报、最多 15 条机会
35. [Federal Register/Regulations.gov 监管变化雷达](methods/35-regulatory-radar.md) — 一个机构加一个产品主题、14 天人工审核周报
36. [SEC 8-K/10-K 企业事件销售情报](methods/36-sec-filing-event-signals.md) — 一个行业/公司清单、7 天、最多 20 条 8-K/10-K 公司事件信号
37. [Companies House 新注册企业 SIC 垂直线索](methods/37-companies-house-leads.md) — 一个 SIC/地区、过去 14 天、50 家公司级清单，不含个人画像
38. [openFDA 食品召回关键词监控](methods/38-openfda-food-recall-monitor.md) — 20 个品牌/关键词、30 条历史分层金标、14 天每周人工检查
39. [EPA ECHO DC 活跃重大设施检查/行动/罚款信号](methods/39-epa-echo-leads.md) — DC 活跃重大设施、过去 30 天、最多 20 条经人工核验的检查/正式行动/罚款日期信号
40. [CFPB 投诉主题与异常看板](methods/40-cfpb-complaint-dashboard.md) — 一个产品线、过去 12 个月、一个 Looker 仪表盘和月度摘要
41. [Census 建筑许可热点报告](methods/41-building-permit-hotspots.md) — 一个州、过去 24 个月、10 个地区的月报样板
42. [Census 对美进口 HS6 机会简报](methods/42-census-us-import-brief.md) — 一个 HS6、美国从中国及 5 个替代供应国进口、过去 60 个月的一次性简报
43. [竞品价格与条款变化监控](methods/43-competitor-change-monitor.md) — 5 个公开页面、每天一次、14 天、周报一份
44. [垂直行业 B2B Sales Deck 模板套件](methods/44-vertical-sales-deck-kit.md) — 先完成可即时交付的 8 页 beta 和一个垂直示例；用 Upwork 定制服务分别卖给 2 个独立团队，再扩成 30 页
45. [创作者赞助 Media Kit 与收入 Tracker](methods/45-creator-sponsorship-kit.md) — 一个 12 页 media kit 加 Google Sheets tracker，先卖 5 个 founding copies
46. [Shopify 单行业商品图与 UGC 广告模板系统](methods/46-shopify-ad-template-system.md) — 先完成可即时交付的 10 个自制 beta 模板和 3 个虚构商品演示，用 Upwork 定制服务分别卖给 3 个独立商家
47. [Udemy 岗位化 AI Workflow 实战课](methods/47-udemy-role-ai-course.md) — 先通过 Upwork 固定范围服务卖一个 60 分钟企业小班和 5 个模板；验证后录制至少 30 分钟/5 节的 Udemy 课程
48. [KDP 30 天岗位化 AI 实验 Workbook](methods/48-kdp-ai-workbook.md) — 先免费招募 10 名 beta 读者验证 7 天样章，再完成 60–100 页终稿并创建 Kindle eBook 预售
49. [Patreon Shopify 本地化与无障碍周报](methods/49-patreon-shopify-digest.md) — 先做 2 期公开样报和 4 周 founding plan，预售 5 个会员
50. [Shopify 数字商品附件与交付审计](methods/50-shopify-digital-delivery-audit.md) — 20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP

## 整体执行优先级与清晰对比表

排名 1–3 是综合当前买方可达性、技术验收确定性和中国执行边界后人工选出的首做顺序；第 4 名起按统一加权综合分排序。难度 1 最低、5 最高；杠杆 5 最高。服务/数据项目列为税前毛营收；数字平台项目按方法文中的分成/版税假设折算可计收入。均未扣人工、税、退款和支持，不是利润或收入保证。

| 排名 | 方法 | 类型 | 启动成本 | 难度 | 付费验证 | 保守/月 | 中性/月 | 乐观/月 | 杠杆 | 综合分 |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | [20 Merchant Center Feed 诊断与免费列表修复](methods/20-merchant-feed-repair.md) | 电商增长 | ¥0–150 | 1/5 | 10 天 | ¥3,500 | ¥15,000 | ¥41,000 | 4/5 | 4.70 |
| 2 | [01 HubSpot 入站线索分级与人工路由试点](methods/01-ai-lead-routing.md) | AI与业务自动化 | ¥0–300 | 1/5 | 7 天 | ¥2,500 | ¥13,800 | ¥39,000 | 5/5 | 4.60 |
| 3 | [22 GA4 电商事件与 Looker 漏斗仪表盘](methods/22-ga4-ecommerce-funnel.md) | 电商增长 | ¥0–150 | 1/5 | 10 天 | ¥5,000 | ¥18,000 | ¥49,000 | 5/5 | 4.70 |
| 4 | [43 竞品价格与条款变化监控](methods/43-competitor-change-monitor.md) | 市场情报 | ¥0–1,000 | 1/5 | 7 天 | ¥999 | ¥8,990 | ¥30,000 | 5/5 | 4.90 |
| 5 | [15 合规的真实评论请求工作流](methods/15-review-request-workflow.md) | 本地商业增长 | ¥0–150 | 1/5 | 7 天 | ¥1,500 | ¥7,500 | ¥21,000 | 4/5 | 4.85 |
| 6 | [28 SPF/DKIM/DMARC 邮件送达基础配置](methods/28-email-deliverability.md) | 网站技术服务 | ¥0–200 | 1/5 | 14 天 | ¥2,500 | ¥12,000 | ¥34,000 | 4/5 | 4.85 |
| 7 | [10 发票提醒与失败付款恢复](methods/10-invoice-recovery.md) | 财务运营自动化 | ¥0–300 | 1/5 | 7 天 | ¥3,500 | ¥14,000 | ¥38,000 | 5/5 | 4.75 |
| 8 | [11 每日/每周 KPI 管理摘要](methods/11-kpi-digest.md) | 数据与运营服务 | ¥0–300 | 1/5 | 7 天 | ¥3,000 | ¥17,500 | ¥48,000 | 5/5 | 4.75 |
| 9 | [24 WordPress 备份、更新与健康检查 Care Plan](methods/24-wordpress-care-plan.md) | 网站技术服务 | ¥0–200/站/月 | 1/5 | 7 天 | ¥900 | ¥9,000 | ¥30,000 | 4/5 | 4.75 |
| 10 | [27 电商客服宏、订单路由与 AI 辅助](methods/27-ecommerce-support-macros.md) | 电商增长 | ¥0–300 | 1/5 | 10 天 | ¥3,500 | ¥17,000 | ¥47,000 | 5/5 | 4.75 |
| 11 | [14 CRM 清洗、去重与生命周期提醒](methods/14-crm-cleanup.md) | 数据与运营服务 | ¥0–200 | 1/5 | 7 天 | ¥1,500 | ¥12,000 | ¥32,000 | 4/5 | 4.70 |
| 12 | [16 Google Business Profile 月度运营](methods/16-gbp-operations.md) | 本地商业增长 | ¥0–300 | 1/5 | 7 天 | ¥1,800 | ¥12,000 | ¥36,000 | 4/5 | 4.70 |
| 13 | [33 Grants.gov 资助匹配与截止日提醒](methods/33-grants-matching.md) | 公共数据情报 | ¥0–300 | 2/5 | 10 天 | ¥799 | ¥7,990 | ¥28,000 | 5/5 | 4.70 |
| 14 | [03 共享邮箱分类与回复草稿](methods/03-shared-inbox-triage.md) | AI与业务自动化 | ¥50–400 | 2/5 | 10 天 | ¥3,500 | ¥15,500 | ¥43,000 | 5/5 | 4.60 |
| 15 | [25 Shopify 弃单、购后与复购自动化配置](methods/25-shopify-lifecycle-flows.md) | 电商增长 | ¥0–200 | 1/5 | 10 天 | ¥3,500 | ¥17,000 | ¥48,000 | 4/5 | 4.60 |
| 16 | [04 客服工单优先级与 SLA 升级](methods/04-support-sla-triage.md) | AI与业务自动化 | ¥100–500 | 2/5 | 10 天 | ¥4,500 | ¥21,000 | ¥59,000 | 5/5 | 4.50 |
| 17 | [50 Shopify 数字商品附件与交付审计](methods/50-shopify-digital-delivery-audit.md) | 电商增长 | ¥0–200 | 1/5 | 10 天 | ¥1,505 | ¥8,500 | ¥24,000 | 4/5 | 4.50 |
| 18 | [08 成交后客户 Onboarding 自动化](methods/08-client-onboarding-automation.md) | AI与业务自动化 | ¥0–300 | 2/5 | 10 天 | ¥4,000 | ¥17,500 | ¥47,000 | 5/5 | 4.45 |
| 19 | [26 Shopify 多语店面本地化 QA](methods/26-shopify-localization-qa.md) | 内容与本地化 | ¥0–300 | 1/5 | 14 天 | ¥4,000 | ¥18,000 | ¥48,000 | 4/5 | 4.45 |
| 20 | [29 中小企业网络安全卫生基线](methods/29-smb-cyber-hygiene.md) | 网站技术服务 | ¥0–300 | 1/5 | 10 天 | ¥4,000 | ¥16,000 | ¥43,000 | 4/5 | 4.45 |
| 21 | [02 会议转写到 CRM 与任务自动化](methods/02-meeting-to-crm.md) | AI与业务自动化 | ¥0–300 | 1/5 | 7 天 | ¥2,000 | ¥11,000 | ¥30,000 | 5/5 | 4.40 |
| 22 | [17 Webinar/Podcast 多渠道内容包](methods/17-content-repurposing.md) | 内容与本地化 | ¥0–300 | 1/5 | 5 天 | ¥2,500 | ¥16,000 | ¥45,000 | 4/5 | 4.40 |
| 23 | [19 电商目录、Variant 与属性清洗](methods/19-ecommerce-catalog-cleanup.md) | 电商增长 | ¥0–200 | 1/5 | 14 天 | ¥3,000 | ¥15,000 | ¥42,000 | 4/5 | 4.40 |
| 24 | [21 Product/Offer/ReturnPolicy 结构化数据实施](methods/21-product-structured-data.md) | 电商增长 | ¥0–100 | 1/5 | 10 天 | ¥4,000 | ¥14,000 | ¥38,000 | 4/5 | 4.40 |
| 25 | [23 Core Web Vitals 快修 Sprint](methods/23-core-web-vitals-sprint.md) | 网站技术服务 | ¥0–150 | 1/5 | 10 天 | ¥4,000 | ¥19,000 | ¥52,000 | 4/5 | 4.40 |
| 26 | [41 Census 建筑许可热点报告](methods/41-building-permit-hotspots.md) | 公共数据情报 | ¥0–300 | 2/5 | 14 天 | ¥999 | ¥6,990 | ¥24,000 | 5/5 | 4.35 |
| 27 | [45 创作者赞助 Media Kit 与收入 Tracker](methods/45-creator-sponsorship-kit.md) | 数字产品 | ¥0–300 | 1/5 | 14 天 | ¥569 | ¥4,063 | ¥15,189 | 5/5 | 4.35 |
| 28 | [37 Companies House 新注册企业 SIC 垂直线索](methods/37-companies-house-leads.md) | 公共数据情报 | ¥0–300 | 2/5 | 10 天 | ¥699 | ¥6,990 | ¥24,000 | 5/5 | 4.30 |
| 29 | [05 网站 FAQ/RAG 客服机器人](methods/05-faq-rag-bot.md) | AI与业务自动化 | ¥100–800 | 2/5 | 14 天 | ¥5,000 | ¥26,000 | ¥72,000 | 5/5 | 4.25 |
| 30 | [07 提案与报价草稿生成器](methods/07-proposal-generator.md) | AI与业务自动化 | ¥0–300 | 1/5 | 7 天 | ¥3,000 | ¥13,500 | ¥36,000 | 5/5 | 4.25 |
| 31 | [09 预约提醒与爽约降低工作流](methods/09-no-show-reduction.md) | AI与业务自动化 | ¥0–200 | 1/5 | 7 天 | ¥1,800 | ¥8,500 | ¥22,000 | 4/5 | 4.25 |
| 32 | [12 PDF/邮件订单结构化入库](methods/12-document-extraction.md) | AI与业务自动化 | ¥100–600 | 2/5 | 14 天 | ¥5,000 | ¥26,000 | ¥70,000 | 5/5 | 4.25 |
| 33 | [13 NPS/CSAT/评论主题洞察月报](methods/13-feedback-insights.md) | 数据与运营服务 | ¥0–300 | 2/5 | 10 天 | ¥2,500 | ¥14,500 | ¥40,000 | 4/5 | 4.25 |
| 34 | [31 SAM.gov 垂直投标提醒与 Bid/No-Bid 摘要](methods/31-sam-bid-alerts.md) | 公共数据情报 | ¥0–500 | 2/5 | 10 天 | ¥699 | ¥6,990 | ¥24,900 | 5/5 | 4.25 |
| 35 | [38 openFDA 食品召回关键词监控](methods/38-openfda-food-recall-monitor.md) | 公共数据情报 | ¥100–700 | 2/5 | 14 天 | ¥1,500 | ¥9,500 | ¥32,000 | 5/5 | 4.25 |
| 36 | [49 Patreon Shopify 本地化与无障碍周报](methods/49-patreon-shopify-digest.md) | 数字产品 | ¥0–300 | 2/5 | 14 天 | ¥264 | ¥2,762 | ¥8,813 | 5/5 | 4.25 |
| 37 | [30 小型网站 WCAG 2.2 A/AA 重点项审计与修复 Sprint](methods/30-accessibility-audit-fix.md) | 网站技术服务 | ¥0–300 | 2/5 | 14 天 | ¥5,000 | ¥20,000 | ¥55,000 | 4/5 | 4.15 |
| 38 | [34 TED 欧盟招标中文垂直简报](methods/34-ted-tender-brief.md) | 公共数据情报 | ¥100–600 | 2/5 | 14 天 | ¥999 | ¥9,990 | ¥35,000 | 5/5 | 4.15 |
| 39 | [36 SEC 8-K/10-K 企业事件销售情报](methods/36-sec-filing-event-signals.md) | 公共数据情报 | ¥100–500 | 2/5 | 14 天 | ¥999 | ¥8,990 | ¥30,000 | 5/5 | 4.15 |
| 40 | [06 内部 SOP 知识助手](methods/06-internal-sop-assistant.md) | AI与业务自动化 | ¥100–800 | 2/5 | 14 天 | ¥6,000 | ¥32,000 | ¥85,000 | 5/5 | 4.05 |
| 41 | [42 Census 对美进口 HS6 机会简报](methods/42-census-us-import-brief.md) | 公共数据情报 | ¥0–500 | 2/5 | 14 天 | ¥1,505 | ¥10,000 | ¥35,000 | 5/5 | 4.05 |
| 42 | [47 Udemy 岗位化 AI Workflow 实战课](methods/47-udemy-role-ai-course.md) | 数字产品 | ¥300–1,800 | 2/5 | 14 天 | ¥1,001 | ¥5,980 | ¥20,000 | 5/5 | 4.05 |
| 43 | [35 Federal Register/Regulations.gov 监管变化雷达](methods/35-regulatory-radar.md) | 公共数据情报 | ¥100–500 | 2/5 | 14 天 | ¥1,200 | ¥12,000 | ¥42,000 | 5/5 | 4.00 |
| 44 | [39 EPA ECHO DC 活跃重大设施检查/行动/罚款信号](methods/39-epa-echo-leads.md) | 公共数据情报 | ¥100–500 | 2/5 | 21 天 | ¥1,200 | ¥10,000 | ¥34,000 | 5/5 | 4.00 |
| 45 | [18 YouTube 自动配音审核与本地化](methods/18-youtube-localization-qa.md) | 内容与本地化 | ¥0–250 | 2/5 | 7 天 | ¥1,500 | ¥12,000 | ¥36,000 | 4/5 | 3.95 |
| 46 | [32 USAspending 续约与 Incumbent 情报](methods/32-usaspending-renewal-intel.md) | 公共数据情报 | ¥100–600 | 2/5 | 14 天 | ¥1,500 | ¥8,500 | ¥28,000 | 5/5 | 3.95 |
| 47 | [44 垂直行业 B2B Sales Deck 模板套件](methods/44-vertical-sales-deck-kit.md) | 数字产品 | ¥0–700 | 2/5 | 14 天 | ¥1,008 | ¥5,990 | ¥16,975 | 5/5 | 3.95 |
| 48 | [46 Shopify 单行业商品图与 UGC 广告模板系统](methods/46-shopify-ad-template-system.md) | 数字产品 | ¥0–500 | 2/5 | 14 天 | ¥609 | ¥3,988 | ¥17,962 | 5/5 | 3.95 |
| 49 | [40 CFPB 投诉主题与异常看板](methods/40-cfpb-complaint-dashboard.md) | 公共数据情报 | ¥100–500 | 3/5 | 21 天 | ¥2,000 | ¥12,000 | ¥38,000 | 5/5 | 3.75 |
| 50 | [48 KDP 30 天岗位化 AI 实验 Workbook](methods/48-kdp-ai-workbook.md) | 数字产品 | ¥200–1,000 | 2/5 | 30 天 | ¥230 | ¥1,840 | ¥6,900 | 5/5 | 3.70 |

可筛选与修改的表格版本见 [comparison.xlsx](outputs/01a05a86-2db0-74f3-b045-21a42b91bcb1/comparison.xlsx)，CSV 原始版见 [comparison.csv](assets/comparison.csv)。

## 共享可执行资产

- [单位经济命令行计算器](tools/unit_economics.py)：计算营收、平台费、工具费、人工与贡献毛利。
- [官方 JSON Feed 增量提醒](tools/feed_alert.py)：只适合一个已确认 schema 的 JSON 响应，强制字段白名单、状态去重和 JSON/CSV 输出；不负责来源专用分页、多源匹配或许可判断。
- [包完整性检查](tools/validate_package.py)：验证 50 个文件、Day 1–30、必需章节、来源键和过渡句。
- [手工获客跟踪表](assets/lead-tracker.csv)：不发送邮件，只记录人工、相关、低量联系和退订。
- [单位经济模板](assets/unit-economics.csv) 与 [实验日志](assets/experiment-log.csv)。

## 使用方式

1. 只打开一个方法文件，复制 Day 1–7 到自己的日历。
2. 用共享 `unit_economics.py` 把目标时薪计入，不要把营收当利润。
3. 首次发布、报价或签约前，先过账户、权限、数据许可和收款方式 Active 闸门；首个真实订单后再验证到账，任何失败不靠伪造地区解决。
4. 除方法 48 的 KDP 发行实验外，Day 20 前没有已注资里程碑、平台净订单或已入账合法账单，就按文件的 Stop 条件缩窄或换方向；延迟结算只记订单，不写到账。方法 48 在 Day 20 上传终稿并开预售、Day 27 发行，唯一商业 Go/Stop 是 Day 30 的至少 5 个不重复净付费购买。
5. 页面菜单和价格会变化；每次真正执行前打开原始官方链接复核。
