# 方法 42｜Census 对美进口 HS6 机会简报

> **一页结论：**面向想验证中国商品对美需求并比较替代供应国的外贸工厂、商会和营销代理，用「一个 HS6、美国从中国及 5 个替代供应国进口、过去 60 个月的一次性简报」先收费验证。启动现金成本 ¥0–500，目标是 逐月值/年累计对账通过率、shortlist 采用数、后续访谈/报价数。这里的报价和收益是**本报告的测试模型，不是行业均价或收益保证**。

## 0. 执行卡

| 项目 | 内容 |
|---|---|
| 分类 | 公共数据情报 |
| 买方 | 想验证中国商品对美需求并比较替代供应国的外贸工厂、商会和营销代理 |
| 当前痛点 | 美国进口数据免费但 HS 层级、月值/年累计、来源国代码、修订和异常很难转成选市场动作 |
| 可交付结果 | 一个 HS6 的中国对美进口趋势、五个替代供应国对比、异常月份、下一步客户访谈清单和数据局限 |
| 最小试点 | 一个 HS6、美国从中国及 5 个替代供应国进口、过去 60 个月的一次性简报 |
| 工具栈 | U.S. Census International Trade API + Postman + Python/Sheets + Looker Studio |
| 启动成本 | ¥0–500（不含自己的人工） |
| 时间 | 7–14 天 |
| 技能 | HS/贸易数据、统计、商业写作、局限说明 |
| 参考测试报价 | Upwork 试点 US$215；后续 ¥1,500–8,000/份；月度 ¥999–2,999 |
| 最小验证 | 用官方 API 做 1 页中国+2 个替代国样报并访谈 5 家工厂；1 家购买并注资 Upwork US$215 固定价试点（报告按 US$1=¥7 约 ¥1,505）才扩到 6 国/60 月 |
| 综合分 | 4.05/5；需求证据 4 / 验证速度 3 / 低成本 5 / 复购性 3 / 自动化杠杆 5 / 获客可达 4 / 风险可控 5 |

## 1. 为什么现在能赚钱

赚钱逻辑不是“AI/数据/模板很火”，而是把 **美国进口数据免费但 HS 层级、月值/年累计、来源国代码、修订和异常很难转成选市场动作** 变成一个买方能验收的固定范围结果：**一个 HS6 的中国对美进口趋势、五个替代供应国对比、异常月份、下一步客户访谈清单和数据局限**。先用人工和低成本工具交付，客户确认价值后才把重复步骤自动化；这样现金投入低，也避免先做没人买的软件。

### 当前市场证据

- **D15｜[U.S. Census International Trade API](https://www.census.gov/data/developers/data-sets/international-trade.html)：**Census International Trade 月度数据覆盖 2010 年至今，按月更新，提供美国进口/出口的 HS、国家、金额、数量、运输方式等字段；历史数据随每年 4 月统计发布修订。 **使用边界：**2026 年官方页面要求所有查询使用 API key；报告必须区分月值 GEN_VAL_MO 与年累计 GEN_VAL_YR，保存 LAST_UPDATE，并把美国进口额标为需求代理而非订单。
- **D27｜[Census Data API Terms of Service](https://www.census.gov/data/developers/about/terms-of-service.html)：**官方条款明确允许用 Census API 开发搜索、展示、分析、检索和查看 Census 数据的服务，并要求使用 API 的服务显著显示不获 Census 背书的声明。 **使用边界：**不得暗示 Census 背书、歪曲数据或绕过访问限制；应用/报告应展示规定声明并遵守隐私和适用法律。
- **D29｜[Census API time predicates](https://www.census.gov/data/developers/guidance/api-user-guide.Core_Concepts.html)：**官方 User Guide 支持 `time=from+YYYY-MM+to+YYYY-MM` 时间范围语法。 **使用边界：**该页只证明时间谓词语法；imports/hs 字段定义见 D30，Schedule C 国家代码见 D31。
- **D30｜[Census International Trade imports/hs variables](https://api.census.gov/data/timeseries/intltrade/imports/hs/variables.html)：**官方变量表定义 I_COMMODITY 为 2/4/6/10 位进口 Harmonized Code、GEN_VAL_MO 为月度一般进口总额、GEN_VAL_YR 为年累计一般进口总额、LAST_UPDATE 为最后更新日期。 **使用边界：**月度趋势只用 GEN_VAL_MO；年累计对账须按同一国家、HS 和 LAST_UPDATE 并在跨年时重置。
- **D31｜[Census Schedule C country codes](https://www.census.gov/foreign-trade/schedules/c/countrycodes.html)：**官方 Schedule C 国家代码表列出 China 的 Country Code 为 5700、ISO Code 为 CN。 **使用边界：**每个替代供应国都必须从当前官方表逐一核验代码；不得凭 ISO 代码猜测 Schedule C 数值。
- **P30｜[Postman Vault secrets](https://learning.postman.com/docs/use/postman-vault/use-vault-secrets)：**Postman v12 可在 Local Vault 保存 API key，并用 `{{vault:secret-name}}` 在 Params 等请求字段直接引用；Vault 值运行时解析，不暴露在 collection 或 request 中。 **使用边界：**为 secret 设置 allowed domain；Census key 仅允许 api.census.gov。不要 Share、截图、导出已解析值或把含 key 的完整 URL 写入报告/日志。
- **M30｜[Upwork How to create a project in Project Catalog](https://support.upwork.com/hc/en-us/articles/360057397533-How-to-create-a-project-in-Project-Catalog)：**当前自由职业者创建 Project Catalog 的路径为 Find Work > Your services > Create Project；项目价格范围明确列为 US$5–US$500,000。 **使用边界：**人民币只可作内部折算模型，不能填进 Upwork Price/offer 金额；实际 CNY 到账由支付伙伴换汇且可能含加价。菜单、资格、费率和审核会变化。
- **P22｜[Upwork Direct to Local Bank](https://support.upwork.com/hc/en-us/articles/211063888-How-to-withdraw-earnings-with-Direct-to-Local-Bank)：**Upwork Direct to Local Bank 支持中国 CNY，每次提现费 0.99 美元；新收款方式为安全需 3 天激活，提现后通常 4 天内到银行。 **使用边界：**姓名必须与 Upwork 验证身份一致，银行限制/费用可另行适用。Day 1 只验证 Account settings > Withdrawals > Add a method > Set up 的真实可用状态，不伪造地区或到账。
- **P23｜[Upwork fixed-price and Project Catalog payments](https://support.upwork.com/hc/en-us/articles/211063718-How-payments-for-milestones-and-fixed-price-contracts-work)：**Upwork fixed-price 里程碑/项目需客户先注资；提交后客户最长可审核 14 天，批准或自动释放后再有 5 天安全期才可提现。 **使用边界：**已注资只证明付费意愿，不等于技术验收、可提现余额或银行到账。核心工作不用 bonus 代替；每个里程碑的交付和金额必须先写清。
- **P27｜[Upwork submit work and milestones](https://support.upwork.com/hc/en-us/articles/211068368-How-to-submit-work-and-milestones-to-your-client)：**固定价工作完成后，自由职业者必须从 Deliver work > Your active contracts 打开合同并点击 Submit work，写明交付并附文件，才会启动客户审核流程。 **使用边界：**只交 Drive/邮件不等于向 Upwork 提交；多里程碑合同每段都要提交当前已注资里程碑、等客户批准并注资下一段后再继续。
- **P28｜[Upwork track earnings status](https://support.upwork.com/hc/en-us/articles/211068418-How-to-track-the-status-of-your-earnings-on-Upwork)：**当前收益状态入口为 Manage finances > Financial overview，也可在 Manage finances > Transactions 查看明细；状态区分 work in progress、in review、pending 和 available。 **使用边界：**Funded、submitted、approved、pending、available、withdrawn 和 bank-arrived 必须分开记录；只有 bank-arrived 才是银行到账。
- **P29｜[Upwork local currency and USD listing](https://support.upwork.com/hc/en-us/articles/211068028-How-to-pay-in-your-local-currency)：**Upwork 官方说明所有成本以 USD 列示；部分客户付款时可看到本币换算，但显示汇率只是估计，最终扣款以交易记录为准。 **使用边界：**自由职业者必须在 Project Catalog Price、offer 和 milestone 输入 USD；人民币只作报告换算假设，实际 CNY 到账由支付伙伴汇率和费用决定。
- **P31｜[Upwork eligibility to propose a new contract](https://support.upwork.com/hc/en-us/articles/115006647007-How-to-propose-a-new-contract)：**自由职业者只能向已至少付过一次款的当前/既往客户，或主动从有效 Project Catalog 项目发消息的潜在客户提出新合同。 **使用边界：**普通职位申请不能由卖方直接 Propose new contract；应 Apply 后等待客户发送 Offer，并先核验 fixed-price 当前里程碑已 Active/Funded。
- **P32｜[Upwork fixed-price milestone requirements](https://support.upwork.com/hc/en-us/articles/211068218-How-to-use-milestones-in-fixed-price-jobs)：**固定价里程碑开始前应写清金额、交付物与截止日；每次只能注资一个里程碑，当前段释放后才能激活并注资下一段。 **使用边界：**卖方不能替客户点击 Fund；每段只在 Active/Funded 后开工，完成后从 Deliver work 提交，等批准并看到下一段 Active/Funded 才继续。
- **P35｜[Upwork direct offers from clients](https://support.upwork.com/hc/en-us/articles/30113729524499-How-direct-offers-from-clients-work-on-Upwork)：**自由职业者收到客户 Offer 后，可从 Messages 打开对应会话，依次选择 View offer，再选择 Accept offer、Request changes 或 Decline offer；接受前可以协商范围、价格和期限。 **使用边界：**普通职位仍需先 Apply 并等待客户发 Offer；接受后还要核验 fixed-price 当前里程碑/订单为 Active/Funded，卖方不能替客户点击 Fund。

### 竞品与切入

商业贸易数据库卖全球检索；你的切口是免费的美国官方数据、客户产能约束、异常解释和可执行 shortlist。因此不要卖“我会某个工具”，要卖一条窄结果、真实回放、人工审批、可回滚交付和后续维护。

**证据依赖提醒：**本方法使用来源 D15、D27、D29、D30、D31、P30、M30、P22、P23、P27、P28、P29、P31、P32、P35。它们支持市场/渠道/工具事实，但不直接证明你的细分客户会购买；付费意愿必须由本方案的预售试点验证。

## 2. 产品、价格与单位经济

### 固定范围产品

- **名称：**Census 对美进口 HS6 机会简报 30 天验证包
- **交付：**一个 HS6、美国从中国及 5 个替代供应国进口、过去 60 个月的一次性简报；另附基线、测试记录、异常清单、SOP、回滚/删除说明。
- **客户输入：**HS6、5 个对比供应国、60 个月窗口、金额下限、客户产能/认证和目标买方
- **验收指标：**逐月值/年累计对账通过率、shortlist 采用数、后续访谈/报价数
- **参考报价：**Upwork 试点 US$215；后续 ¥1,500–8,000/份；月度 ¥999–2,999

### 月收益情景（税前可计收入；数字平台按文中分成/版税模型）

| 情景 | 本报告假设 | 预估月营收 |
|---|---|---:|
| 保守 | 保守 1×US$215×¥7=¥1,505；模型合计=¥1,505 | ¥1,505 |
| 中性 | 中性 5 份简报加 2 个订阅；归一化校验：1 个该情景订单组合×¥10,000=¥10,000；模型合计=¥10,000 | ¥10,000 |
| 乐观 | 乐观 10 份简报加 8 个订阅；归一化校验：1 个该情景订单组合×¥35,000=¥35,000；模型合计=¥35,000 | ¥35,000 |

- **回本周期：**现金口径：按保守月营收匀速折算约 10 天；含工时口径：按首月 18 小时、目标时薪 ¥200/小时，需覆盖约 ¥4,100，按保守情景折算约 82 天。这是容量模型；真实回本以实际收款日、平台结算期、退款、税和工时为准。
- **毛利闸门：**试点结束统计实际工时、工具费、平台费、退款与支持。税前贡献毛利低于 60% 时，不扩量，先提价或缩范围。
- **停止条件：**30 天无付费、关键验收失败、平台/KYC 不可用、数据许可不清或必须靠违规抓取/群发才能获客，立即停止或换细分。

## 3. 最小验证方案

1. 不先做完整产品；只做「一个 HS6、美国从中国及 5 个替代供应国进口、过去 60 个月的一次性简报」。
2. 使用公开信息或客户主动提供的脱敏样本，不先索要管理员、支付或生产写权限。
3. **商业验证门槛：**用官方 API 做 1 页中国+2 个替代国样报并访谈 5 家工厂；1 家购买并注资 Upwork US$215 固定价试点（报告按 US$1=¥7 约 ¥1,505）才扩到 6 国/60 月
4. **技术验收门槛：**同一国家、HS6、LAST_UPDATE 下，1 月 GEN_VAL_YR=GEN_VAL_MO；2–12 月 GEN_VAL_YR(t)-GEN_VAL_YR(t-1)=GEN_VAL_MO(t)，跨年重置。容差 0 美元；对所有已取月份计算 passed_equations/checked_equations，100% 才通过。另记录 shortlist 采用数和后续访谈/报价数，付款不代替技术验收
5. 只做 10–30 个强相关潜在买方的人工触达；不买名单、不抓 LinkedIn、不做自动群发。
6. 失败也要留数据：拒绝原因、价格、真实工时、误报/漏报和客户不用的功能，作为是否换细分的依据。

## 4. Day 1–30 落地日历

| 天 | 今天具体做什么 | 工具/点击路径 | 输入、输出与通过条件 |
|---:|---|---|---|
| Day 1 | 定一个美国进口问题 | Google Sheets > Blank > scope tab | 唯一买方、一个 HS6、中国+5 个替代供应国、过去 60 个月；写明进口额只是需求代理，不承诺订单 |
| Day 2 | 核条款、Vault 与归因声明 | 打开 D15/D27/D29/D30/D31/P30；Docs > source-policy | 抄录允许 search/display/analyze/retrieve 的用途、访问限制、时间语法、字段定义、Schedule C 代码、Vault secret 路径和声明；报告显著写 This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau |
| Day 3 | 跑官方精确请求 | Census Developers > Request a Key；Postman > Vault > Local Vault > Add new secret > CENSUS_API_KEY；Allowed domains=api.census.gov；New > GET | 原样填 get/time=from+2025-01+to+2026-06/CTY_CODE=5700/I_COMMODITY=850440/key={{vault:CENSUS_API_KEY}}，点 Send；付款前只取样报所需 18 个月，保存 LAST_UPDATE、fetched_at 和不含 key 的官方回链 |
| Day 4 | 定义 schema | Google Sheets > schema tab | 字段至少含 source_id、source_url、published_at、fetched_at、status、matched_reason、human_verified |
| Day 5 | 完成逐月/年累计等式 QA | Sheets > QA > 按 CTY_CODE/I_COMMODITY/LAST_UPDATE/month 排序；Census 官方单月结果抽查 | 1 月核 GEN_VAL_YR=GEN_VAL_MO；2–12 月核 YR(t)-YR(t-1)=MO(t)，跨年重置、容差 0；写 checked_equations、passed_equations、pass_rate，所有已取月份 100% 才通过 |
| Day 6 | 写匹配规则 | Sheets > rules tab | 输入：HS6、5 个对比供应国、60 个月窗口、金额下限、客户产能/认证和目标买方；把必须条件、加分项、排除词和人工核验写成可见规则 |
| Day 7 | 保存分页/增量契约 | Postman > Duplicate request > Params > CTY_CODE；Sheets > provenance | 付款前只为中国+2 个替代国各跑一个 18 个月请求，用前 6 个月对账、样报仅展示后 12 个月；其余三国和完整 60 月保持待办。月趋势只用 GEN_VAL_MO；key 不进截图/collection/report/log |
| Day 8 | 做增量与去重 | Google Sheets > Data > Data cleanup > Remove duplicates；以 official ID+status 建复合键 | 只保留字段白名单；状态变化作为新事件，标题微调不重复推送；个人字段默认排除 |
| Day 9 | 保留证据 | Sheets > output tab | 每条结果包含原链接、日期、抓取时间、匹配理由、原文短摘和人工核验状态 |
| Day 10 | 出一页真实样报 | Google Docs > New；Sheets > pivot/chart | 只展示中国+2 国、最近 12 个月的真实官方数据、来源声明、修订日和局限；不把进口额写成销售或订单 |
| Day 11 | 双人/二遍 QA | Sheets > QA tab | 隔 24 小时重新核对 10 条或请同伴复核；记录误报和遗漏原因 |
| Day 12 | 补人工增值 | Docs > sample report > Insert > Building blocks/Checklist | 加入资格/影响/材料缺口/行动问题、no-fit 原因、截止提醒和源链接；不只转发官方免费提醒 |
| Day 13 | 发布固定价服务 | Upwork > Find Work > Your services > Create Project | Upwork Price 字段输入 US$215（报告统一按 US$1=¥7 折算约 ¥1,505；执行日以平台/银行实际换汇为准）；粘贴标题、样报、来源许可和免责声明，先卖人工报告，不卖未完成订阅软件 |
| Day 14 | 列 20 个买方 | Upwork > Find Work > Search jobs > 输入 Census US import HS market research；Sheets > targets | 记录 company/source_url/why_fit/jurisdiction/entity_type；只用公司级通用入口，不抓个人邮箱或社媒数据 |
| Day 15 | 首批 10 个触达 | Upwork > 打开匹配职位 > Apply now；或通过司法辖区闸门后 Gmail > Compose | 逐封附 3 条公开样报；真实身份、实体地址、隐私告知和退订齐全，不用追踪像素 |
| Day 16 | 访谈并只给合法购买路径 | Calendly > Event types > 20 min；Upwork 普通职位 > Apply now；Project Catalog 主动询盘 > Messages | 访谈 3 人；普通职位等待客户 Offer，不使用 Propose new contract。需要试点者从已发布 US$215 Project Catalog 页面购买；卖方不点击 Fund、不走站外账单 |
| Day 17 | 确认唯一订单已 Active/Funded | Upwork > Deliver work > Your active contracts > 目标 US$215 Project Catalog order > status | 客户完成 Buy project 和一次全额注资；只有订单显示 Active/Funded 才开完整范围。未注资只保留中国+2 国/12 月样报，不取其余国家或 60 月数据 |
| Day 18 | 重做筛选 | Sheets > rules tab > Duplicate v1 to v2 | 只改最大误报来源；用原 20 条黄金集重新算精确率/召回率并保留 v1 |
| Day 19 | 启动已注资的完整取数 | Postman > Duplicate request > Params；time=from+2021-01+to+2026-06；Sheets > paid-run | 订单 Active/Funded 后，对中国+5 个替代国各跑一个 66 个月范围请求，用前 6 个月做累计值对账，最终只展示 2021-07 至 2026-06 的 60 个月；记录 LAST_UPDATE/fetched_at |
| Day 20 | 每日人审 | Sheets > human_verified filter | 发布前逐条打开原链接；状态不确定、权利不清或高风险一律不推送 |
| Day 21 | 发送中期预览但不提交整单 | Upwork > Messages；Drive > Restricted preview；Sheets > QA | 只发 6 国 QA 结果、异常清单和报告目录；Project Catalog 是一次注资整单，Day 28 完成前不使用平台提交按钮，不把预览写成最终交付 |
| Day 22 | 看客户如何使用 shortlist | Upwork > Messages；Sheets > customer feedback | 询问哪些信号进入访谈/报价清单；只记录逐月值/年累计对账通过率、shortlist 采用数、后续访谈/报价数，不把外部成交全部归因给报告 |
| Day 23 | 修噪声 | Sheets > false-positive pivot | 按原因汇总误报；加入排除词或最小样本阈值，保留变更日志 |
| Day 24 | 只做来源专用半自动化 | Postman Collection Runner 或客户批准的来源专用脚本；Sheets > runbook | 每国一个 time range 请求、低频缓存；Census key 必须在 query，所以禁止交给 feed_alert.py，分享请求前删已解析 key |
| Day 25 | 验证字段最小化 | Sheets > schema > 保留 source_id/source_url/date/status/matched_reason；删除无关列 | 检查输出、缓存和日志无 API key、含 key URL、评论者/联系人等无关个人数据；写删除日期 |
| Day 26 | 一次跟进 | Upwork > Messages；或 Gmail > Sent > 对应线程 > Reply | 对未回复者只跟进一次并新增真实信号；收到退订立即写 suppression tab，之后停止 |
| Day 27 | 只起草后续范围，不提前收费 | Google Docs > follow-on draft；Upwork > Messages 保持草稿 | 只写下月 HS6、国家、更新频率、价格与取消方式；当前 Project Catalog 订单尚未最终提交，不建新订单、不发站外账单、不暗扣 |
| Day 28 | 提交唯一 Project Catalog 最终交付 | Google Docs > final report；Upwork > Deliver work > Your active contracts > 目标 US$215 Project Catalog order > Submit work | 附最终 PDF、QA、方法说明和受限证据链接，只点一次 Submit work 并确认进入 in review；不拆单、不重复提交、不把 Messages 预览算最终交付 |
| Day 29 | 重查更新与单位经济 | Census API Terms/variables/LAST_UPDATE；Sheets > unit economics | 重查 key、字段、条款、4 月修订和人工分钟；记录本期 LAST_UPDATE，任何漂移先停更再修 |
| Day 30 | 按商业门槛查款并决定 | Upwork > Manage finances > Financial overview；Manage finances > Transactions；Sheets > decision/cash-ledger | 记录 funded/submitted/approved/pending/available/withdrawn/bank-arrived，只有 bank-arrived 写到账；仅当 1 个 US$215 独立 Project Catalog 订单已 Active/Funded 且逐月/年累计等式 QA 100% 通过才 Go，否则 Stop 或缩窄范围 |

## 5. 可复制注册、发布、销售与交付文案

### A. 平台服务页/落地页文案

**标题（直接粘贴）**

> Census 对美进口 HS6 机会简报｜先做固定范围试点，用真实数据验收，不承诺虚假增长

**副标题（直接粘贴）**

> 面向想验证中国商品对美需求并比较替代供应国的外贸工厂、商会和营销代理。我会在不改变生产关键动作的前提下，完成「一个 HS6、美国从中国及 5 个替代供应国进口、过去 60 个月的一次性简报」，并用 逐月值/年累计对账通过率、shortlist 采用数、后续访谈/报价数 做前后验收。涉及发送、付款、退款、删除、公开发布或高风险判断的步骤默认保留人工批准。

**服务说明（直接粘贴）**

> 你现在可能遇到的问题是：美国进口数据免费但 HS 层级、月值/年累计、来源国代码、修订和异常很难转成选市场动作。本项目不会先卖一套昂贵系统，而是先交付一个可回滚试点：一个 HS6 的中国对美进口趋势、五个替代供应国对比、异常月份、下一步客户访谈清单和数据局限。你会收到现状基线、配置/数据文件、测试记录、异常清单、操作 SOP、回滚办法和 14/30 天结果复盘。固定范围外的工作会在开始前单独报价。参考价：Upwork 试点 US$215；后续 ¥1,500–8,000/份；月度 ¥999–2,999。

**CTA（直接粘贴）**

> 请发送 1 份脱敏样本、当前工具、每月处理量和最想改善的一个指标。我会先回复“能做/不该做/还缺什么”，不会要求你先开放管理员权限。

### B. 有条件适用的手工冷邮件（发送前先过司法辖区闸门）

**发送闸门（每个联系人都要记录）**

> 先记录发送者国家/地区、收件人国家/地区、收件主体是 corporate subscriber 还是个人/sole trader/partnership、合法基础、隐私告知 URL 和 suppression 状态。英国公司/LLP 等 corporate body 的 PECR 规则与个人不同，但姓名和个人化工作邮箱仍可能受 UK GDPR 约束；sole trader、非 LLP 等部分 partnership 通常按个人处理。类型不明时按个人处理。禁止追踪像素、个人数据拼接、购买名单和自动群发；无法确定规则时，改用 Upwork 平台响应、用户主动订阅、转介绍或公开内容获客。发送前复核收件地最新规则。

**主题：**关于贵司「Census 对美进口 HS6 机会简报」的一页试点建议

> 你好，{姓名/团队}：  
> 我查看了贵司公开的 {页面/流程/职位信息}，发现一个可以用固定范围验证的问题：美国进口数据免费但 HS 层级、月值/年累计、来源国代码、修订和异常很难转成选市场动作。我不是来承诺排名或收入的；我可以先用公开信息或你提供的脱敏样本，做「一个 HS6、美国从中国及 5 个替代供应国进口、过去 60 个月的一次性简报」，验收只看 逐月值/年累计对账通过率、shortlist 采用数、后续访谈/报价数。  
> 如果方向不相关，回复“不需要”即可，我不会再联系。若相关，我可以先发一页样例和完整边界，确认后再开任何权限。  
> {你的真实姓名}｜{公司/个人主体}｜{实体邮寄地址}｜{官网/作品集}  
> 退订：回复“不需要”。

**第一次跟进（3 个工作日后）**

> 补充一个具体点：本试点的最小通过条件是「用官方 API 做 1 页中国+2 个替代国样报并访谈 5 家工厂；1 家购买并注资 Upwork US$215 固定价试点（报告按 US$1=¥7 约 ¥1,505）才扩到 6 国/60 月」。如果你已有团队在做，我也可以只交只读审计和测试清单；若不相关，回复“不需要”，我会停止联系。

**最后一次跟进（再过 5 个工作日）**

> 这是最后一次跟进。我可以免费发一张脱敏样例，不需要管理员权限。若本季度没有优先级，无需回复；我会关闭这条联系记录。

### C. 发现电话脚本

> 这次 20 分钟只确认四件事：一，当前流程从哪里开始、在哪里结束；二，过去 30 天处理量和基线；三，哪些动作绝不能自动执行；四，什么数字达到才值得继续。若拿不到基线，我们就把试点目标改成“正确性和节省时间”，不编造收入归因。

### D. 固定范围提案

> **项目：**Census 对美进口 HS6 机会简报 30 天验证  
> **客户：**{客户名}  
> **范围：**一个 HS6、美国从中国及 5 个替代供应国进口、过去 60 个月的一次性简报  
> **客户提供：**HS6、5 个对比供应国、60 个月窗口、金额下限、客户产能/认证和目标买方  
> **交付：**基线表、实施/配置、测试证据、异常队列、SOP、回滚说明、结果复盘  
> **技术验收：**同一国家、HS6、LAST_UPDATE 下，1 月 GEN_VAL_YR=GEN_VAL_MO；2–12 月 GEN_VAL_YR(t)-GEN_VAL_YR(t-1)=GEN_VAL_MO(t)，跨年重置。容差 0 美元；对所有已取月份计算 passed_equations/checked_equations，100% 才通过。另记录 shortlist 采用数和后续访谈/报价数，付款不代替技术验收  
> **商业验证：**用官方 API 做 1 页中国+2 个替代国样报并访谈 5 家工厂；1 家购买并注资 Upwork US$215 固定价试点（报告按 US$1=¥7 约 ¥1,505）才扩到 6 国/60 月  
> **不包含：**未授权数据、法律/医疗/金融意见、批量群发、平台条款规避、资金代收、自动退款/删除/公开发布  
> **付款路径：**只走一个 US$215 Upwork Project Catalog fixed-price order：客户从已发布项目购买并一次全额注资；卖方只在订单显示 Active/Funded 后，才从免费中国+2 国/12 月样报扩到中国+5 个替代国/60 月。Day 28 完整交付后只提交一次；不使用 Propose new contract、自定义里程碑或站外替代账单。 参考扩展价：Upwork 试点 US$215；后续 ¥1,500–8,000/份；月度 ¥999–2,999。技术验收与注资、批准、Pending 和银行到账分开记录。  
> **变更：**新增数据源、国家、语言、页面、SKU 或自动动作另行书面确认。

### E. Onboarding 表单

1. 当前最痛的一个问题是什么？请给最近 30 天的例子。  
2. 当前工具、账号 owner、数据所在国家/地区是什么？  
3. 基线：处理量、时间、错误/漏损、当前负责人。  
4. 哪些字段属于个人信息、商业机密或受监管数据？  
5. 哪些动作必须人工批准？  
6. 谁批准上线、谁接异常、谁能执行回滚？  
7. 数据保留期限和删除要求是什么？  
8. 请上传脱敏样本；不要发送密码、API key 或支付凭据。

### F. 验收与复购话术

> 本轮范围已完成。基线为 {数值}，试点结果为 {数值}，样本量 {N}；已知局限是 {局限}。附件含配置、测试记录、异常、SOP 和回滚。若继续，建议只把「{已证明稳定的低风险步骤}」转为月度维护；其余仍人工批准。你若愿意评价，请只描述真实交付和结果，不需要给五星，也没有任何奖励。


## 6. 可直接使用的实施包、提示词与自动化边界

### Census 对美进口 HS6 可运行请求

先在 `https://api.census.gov/data/key_signup.html` 用真实邮箱申请免费 key。打开 `Postman > Vault > Local Vault > Add new secret`：Key 填 `CENSUS_API_KEY`、Value 粘贴 key、Allowed domains 只填 `api.census.gov`。不要 Share；不要把已解析 key 写入环境、collection、文档、截图、日志或命令历史。

`Postman > New > HTTP Request > GET`，`Authorization > No Auth`；在 Params 逐项输入：

```text
get=CTY_CODE,CTY_NAME,I_COMMODITY,I_COMMODITY_LDESC,GEN_VAL_MO,GEN_VAL_YR,LAST_UPDATE
time=from+2025-01+to+2026-06
CTY_CODE=5700
I_COMMODITY=850440
key={{vault:CENSUS_API_KEY}}
```

请求基础 URL：

```text
https://api.census.gov/data/timeseries/intltrade/imports/hs
```

中国的 Schedule C code 为 `5700`。**付款前**只对中国和 2 个替代供应国各跑一次上述 18 个月请求，用前 6 个月完成累计值对账，只在样报展示 2025-07 至 2026-06 的 12 个月。**只有 US$215 Project Catalog 订单显示 Active/Funded 后**，才把 time 改为 `from+2021-01+to+2026-06`，对中国和 5 个替代供应国各跑一次 66 个月请求，用前 6 个月完成对账，最终只展示 2021-07 至 2026-06 的 60 个月；不做 360 个单月请求。

在 Sheets 建 `country,hs6,last_update,month,gen_val_mo,gen_val_yr,prev_gen_val_yr,equation_pass`。同一国家、HS6、`LAST_UPDATE` 内按月排序：1 月检查 `GEN_VAL_YR = GEN_VAL_MO`；2–12 月检查 `GEN_VAL_YR(t) - GEN_VAL_YR(t-1) = GEN_VAL_MO(t)`；跨年重置。容差为 0 美元，`通过率 = passed_equations / checked_equations`，所有已取月份 100% 通过才交付；`LAST_UPDATE` 不一致则重新抓取并分版本。月趋势只用 `GEN_VAL_MO`，`GEN_VAL_YR` 只用于对账。保存请求参数、fetched_at 和不含 key 的官方 examples/variables 回链。

报告页首必须显示官方要求的声明：

> This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.

不得暗示 Census 背书或修改后仍冒充官方数据。Census key 必须放 URL query，因此本来源**不使用**会拒绝 secret query 的 `feed_alert.py`；只用 Postman Local Vault 或客户批准的来源专用脚本，分享/截图/日志前删掉已解析 key。




本方法明确不使用通用 `feed_alert.py`：Census key 位于 query。只使用 Postman Local Vault/Collection Runner 或客户批准的来源专用脚本，并在分享、截图和日志前移除已解析 key。

## 7. 主要风险与预设应对

- **风险：进口额被误解为可获得订单**　应对：明确它只是美国市场筛选信号，另列认证、渠道、关税和买方访谈待核验
- **风险：把年累计当月值或忽略修订**　应对：月趋势只用 GEN_VAL_MO，保存 LAST_UPDATE；每年 4 月修订后重跑并标版本
- **渠道风险：**平台 KYC、收款、费率和功能会变。Day 1 只验证真实账户、税务与收款方式状态；首个真实余额后再验证到账，失败则换合法渠道，不伪造地区。
- **归因风险：**外部销量、转化或中标受多因素影响。只报告试点可测指标、样本量和局限。
- **外联风险：**只做人工、相关、低量外联，使用真实身份/地址/退订；不得抓取、自动私信或骚扰。

## 8. 30 天结束时的 Go / Iterate / Stop

- **Go：**达到本方法的商业验证门槛：“用官方 API 做 1 页中国+2 个替代国样报并访谈 5 家工厂；1 家购买并注资 Upwork US$215 固定价试点（报告按 US$1=¥7 约 ¥1,505）才扩到 6 国/60 月”；关键验收达标；贡献毛利可接受；交付不依赖违规或单点人工英雄主义。
- **Iterate：**有人愿付但范围或价格错；只改最大障碍，再跑一个 7–14 天试点。
- **Stop：**Day 30 未达到上述商业验证门槛、存在重大合规/许可问题、收款不可用或价值只能靠不可验证承诺成立。

> **方法42已完成，开始方法43调研。**
