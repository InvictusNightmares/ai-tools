# 方法 21｜Product/Offer/ReturnPolicy 结构化数据实施

> **一页结论：**面向商品页缺价格、库存和退货标记的 Shopify 商家，用「一个商品模板、5 个 SKU、一个市场的固定范围实施」先收费验证。启动现金成本 ¥0–100，目标是 有效页面占比、错误/警告数、与页面数据一致率。这里的报价和收益是**本报告的测试模型，不是行业均价或收益保证**。

## 0. 执行卡

| 项目 | 内容 |
|---|---|
| 分类 | 电商增长 |
| 买方 | 商品页缺价格、库存和退货标记的 Shopify 商家 |
| 当前痛点 | 页面信息机器不可读或 JSON-LD 与页面不一致，失去丰富结果资格 |
| 可交付结果 | 检查并去除重复 Product JSON-LD；缺失时使用 Shopify structured_data 输出 Product/Offer，可选加入与公开页一致的全局退货政策链接 |
| 最小试点 | 一个商品模板、5 个 SKU、一个市场的固定范围实施 |
| 工具栈 | 主题代码 + Rich Results Test + Search Console |
| 启动成本 | ¥0–100（不含自己的人工） |
| 时间 | 5–10 天 |
| 技能 | JSON-LD、主题代码、测试与回滚 |
| 参考测试报价 | ¥4,000–12,000/模板；维护 ¥500–1,500/月 |
| 最小验证 | 1 个客户为 5 URL 固定范围试点注资/支付 ¥4,000 |
| 综合分 | 4.40/5；需求证据 5 / 验证速度 4 / 低成本 5 / 复购性 3 / 自动化杠杆 4 / 获客可达 5 / 风险可控 5 |

## 1. 为什么现在能赚钱

赚钱逻辑不是“AI/数据/模板很火”，而是把 **页面信息机器不可读或 JSON-LD 与页面不一致，失去丰富结果资格** 变成一个买方能验收的固定范围结果：**检查并去除重复 Product JSON-LD；缺失时使用 Shopify structured_data 输出 Product/Offer，可选加入与公开页一致的全局退货政策链接**。先用人工和低成本工具交付，客户确认价值后才把重复步骤自动化；这样现金投入低，也避免先做没人买的软件。

### 当前市场证据

- **M14｜[Google Merchant Center free listings](https://support.google.com/merchants/answer/13889434?hl=en-A)：**合格商品可免费出现在 Search、Maps、Gemini、YouTube、Shopping、Images 与 Lens。 **使用边界：**合格不等于一定展示，也不保证流量或销量。
- **M15｜[Google Product structured data](https://developers.google.com/search/docs/appearance/structured-data/product)：**Product 数据与 Merchant Center feed 可提供价格、库存、评分、配送和退货信息；两者并用可提高丰富结果资格。 **使用边界：**结构化数据不保证 rich result，页面与标记必须一致。
- **M13｜[Shopify About](https://www.shopify.com/news/about-us)：**Shopify 服务 175 多个国家的数百万商家，2025 年 GMV 为 3,780 亿美元，生态中有 21,000 多个应用。 **使用边界：**平台规模不自动证明某个细分需求。
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

SEO 插件可生成基础标记；你的价值是动态一致性、政策字段和主题兼容。因此不要卖“我会某个工具”，要卖一条窄结果、真实回放、人工审批、可回滚交付和后续维护。

**证据依赖提醒：**本方法使用来源 M14、M15、M13、M30、P22、P23、P27、P28、P29、P31、P32、P35。它们支持市场/渠道/工具事实，但不直接证明你的细分客户会购买；付费意愿必须由本方案的预售试点验证。

## 2. 产品、价格与单位经济

### 固定范围产品

- **名称：**Product/Offer/ReturnPolicy 结构化数据实施 30 天验证包
- **交付：**一个商品模板、5 个 SKU、一个市场的固定范围实施；另附基线、测试记录、异常清单、SOP、回滚/删除说明。
- **客户输入：**商品模板、价格/库存/SKU 字段、公开退货政策 URL、测试 URL、备份主题
- **验收指标：**有效页面占比、错误/警告数、与页面数据一致率
- **参考报价：**¥4,000–12,000/模板；维护 ¥500–1,500/月

### 月收益情景（税前可计收入；数字平台按文中分成/版税模型）

| 情景 | 本报告假设 | 预估月营收 |
|---|---|---:|
| 保守 | 保守 1×¥4,000 模板试点=¥4,000；模型合计=¥4,000 | ¥4,000 |
| 中性 | 中性 3×¥4,000 模板+2×¥1,000 维护=¥14,000；模型合计=¥14,000 | ¥14,000 |
| 乐观 | 乐观 7×¥5,000 模板+3×¥1,000 维护=¥38,000；模型合计=¥38,000 | ¥38,000 |

- **回本周期：**现金口径：按保守月营收匀速折算约 1 天；含工时口径：按首月 24 小时、目标时薪 ¥200/小时，需覆盖约 ¥4,900，按保守情景折算约 37 天。这是容量模型；真实回本以实际收款日、平台结算期、退款、税和工时为准。
- **毛利闸门：**试点结束统计实际工时、工具费、平台费、退款与支持。税前贡献毛利低于 60% 时，不扩量，先提价或缩范围。
- **停止条件：**30 天无付费、关键验收失败、平台/KYC 不可用、数据许可不清或必须靠违规抓取/群发才能获客，立即停止或换细分。

## 3. 最小验证方案

1. 不先做完整产品；只做「一个商品模板、5 个 SKU、一个市场的固定范围实施」。
2. 使用公开信息或客户主动提供的脱敏样本，不先索要管理员、支付或生产写权限。
3. **商业验证门槛：**1 个客户为 5 URL 固定范围试点注资/支付 ¥4,000
4. **技术验收门槛：**5 个 URL 无 Product/Merchant listing critical error，每页只有一套目标 Product 或合理 ProductGroup 实体，价格、币种、库存、SKU、URL 与可见页/后台一致，副本主题购买路径无回归
5. 只做 10–30 个强相关潜在买方的人工触达；不买名单、不抓 LinkedIn、不做自动群发。
6. 失败也要留数据：拒绝原因、价格、真实工时、误报/漏报和客户不用的功能，作为是否换细分的依据。

## 4. Day 1–30 落地日历

| 天 | 今天具体做什么 | 工具/点击路径 | 输入、输出与通过条件 |
|---:|---|---|---|
| Day 1 | 定边界 | Google Sheets > Blank spreadsheet；建 scope、baseline、risk 三个 tab | 写入买方“商品页缺价格、库存和退货标记的 Shopify 商家”、固定范围“一个商品模板、5 个 SKU、一个市场的固定范围实施”；产出一页范围，禁止扩到高风险动作 |
| Day 2 | 核证据 | 打开本文件“市场证据”中的全部官方链接；浏览器 > Bookmark folder | 逐条记录发布日期、事实与局限；如果关键链接失效，暂停宣传该事实 |
| Day 3 | 建 30 个 ICP | Upwork > Find Work > Search jobs > 输入 Shopify structured data JSON-LD；公司官网只看 Contact/Team 通用入口 | Sheets targets 列 company/source_url/why_fit/jurisdiction/entity_type/status；只录与“页面信息机器不可读或 JSON-LD 与页面不一致，失去丰富结果资格”直接相关的 30 个主体，不抓个人数据 |
| Day 4 | 量基线 | Google Sheets > baseline tab | 输入最近 30 天 有效页面占比、错误/警告数、与页面数据一致率；没有数字就记录样本量、当前耗时和错误例子 |
| Day 5 | 开最小工具 | Shopify admin > Online Store > Themes > 目标主题 > … > Duplicate；副本主题 > … > Edit code；搜索 application/ld+json 和 structured_data | 只开试点所需功能；栈：主题代码 + Rich Results Test + Search Console；保存账号 owner、权限、关闭/回滚路径截图 |
| Day 6 | 收脱敏样本 | Google Drive > New > Folder > Share > Restricted | 向测试客户索取：商品模板、价格/库存/SKU 字段、公开退货政策 URL、测试 URL、备份主题；密码/API key 不放文档 |
| Day 7 | 发布固定价服务 | Upwork > Find Work > Your services > Create Project | Upwork Price 字段输入 US$575（报告统一按 US$1=¥7 折算约 ¥4,025；执行日以平台/银行实际换汇为准）；粘贴标题/范围/不包含项，技术验收与付款分开；账号或收款方式未 Active 就用另一合法平台，不伪造地区 |
| Day 8 | 首批手工触达 | Upwork > Find Work > Search jobs > 打开 10 个强相关职位 > Apply now；或通过司法辖区闸门后 Gmail > Compose | 每条引用 1 个真实公开观察，发送本文件文案；CTA 只要求脱敏样本，范围为“一个商品模板、5 个 SKU、一个市场的固定范围实施” |
| Day 9 | 发现访谈 | Calendly > Event types > New event type > 20 min；Google Meet > New meeting | 访谈 3 人，记录当前流程、有效页面占比、错误/警告数、与页面数据一致率 基线、禁止自动动作、预算和采购人 |
| Day 10 | 接受合法 Offer 并核验注资 | 普通职位 > Apply now > 等客户 Offer > Messages > 对应会话 > View offer > Accept offer > Deliver work > Your active contracts；已至少付款一次的当前/旧客户 > Messages > 对应会话 > View contract > … > Propose new contract；有效 Project Catalog 主动询盘 > Messages > Propose new contract | 直接购买 Catalog 的客户沿用现有已注资订单，不另发合同。所有分支都先核对范围、金额、截止日并确认当前 fixed-price milestone/order 为 Active/Funded；卖方不点击 Fund。付款路径：Upwork 所有金额以 USD 列示：Project Catalog 输入 US$575（报告统一按 US$1=¥7 折算约 ¥4,025；执行日以平台/银行实际换汇为准） 并由客户一次注资；若走自定义 fixed-price 合同，则两个里程碑为 US$288/US$287，合计 US$575，里程碑1交付基线、范围、规则和验收计划，截止 Day 17；里程碑2交付最终结果、QA、SOP和删除/回滚记录，截止 Day 28。每次只在当前里程碑 Active/Funded 后开工，提交并获批当前段后，等下一段 Active/Funded 才继续。独立获客且从未在 Upwork 建立关系的客户，可另用合规账单按 ¥4,000 报价；不得把 Upwork 客户移到站外付款。客户批准后仍有 5 天安全期。 商业验证是注资/付款；技术通过只看“5 个 URL 无 Product/Merchant listing critical error，每页只有一套目标 Product 或合理 ProductGroup 实体，价格、币种、库存、SKU、URL 与可见页/后台一致，副本主题购买路径无回归” |
| Day 11 | 画实施流程 | diagrams.net > Create New Diagram；或 Sheets > flow tab | 画 source→deterministic checks→human approval→destination→error queue→rollback；客户确认后再构建 |
| Day 12 | 做第一版规则 | 副本主题 > … > Preview；Google Rich Results Test > URL/Code > Test；Search Console > URL inspection > Test live URL；逐项与可见商品页/后台对账 | 先只处理 5 条/1 页/1 个对象；字段来自“商品模板、价格/库存/SKU 字段、公开退货政策 URL、测试 URL、备份主题”；保存 expected/actual/evidence，不做未经批准的生产写入 |
| Day 13 | 建立确定性实施表 | Shopify admin > Online Store > Themes > 目标主题 > … > Duplicate；副本主题 > … > Edit code；搜索 application/ld+json 和 structured_data | 把 商品模板、价格/库存/SKU 字段、公开退货政策 URL、测试 URL、备份主题 拆成字段、确定性规则、owner、证据和回滚列；只实现合同明确要求的步骤 |
| Day 14 | 做反例与回滚测试 | 副本主题 > … > Preview；Google Rich Results Test > URL/Code > Test；Search Console > URL inspection > Test live URL；逐项与可见商品页/后台对账 | 测试空值、重复、冲突、权限不足、断网和回滚；每例写预期/实际/证据，任何生产写入须客户逐项批准 |
| Day 15 | 加审计日志 | Google Sheets > logs tab；目标工具 > 活动/错误/运行历史 | 记录 event_id、时间、输入 hash、规则/配置版本、动作、审批人、错误和回滚；不记录无关 PII 或密钥 |
| Day 16 | 回放约定样本 | 副本主题 > … > Preview；Google Rich Results Test > URL/Code > Test；Search Console > URL inspection > Test live URL；逐项与可见商品页/后台对账 | 执行技术验收：5 个 URL 无 Product/Merchant listing critical error，每页只有一套目标 Product 或合理 ProductGroup 实体，价格、币种、库存、SKU、URL 与可见页/后台一致，副本主题购买路径无回归；另记录商业验证阈值：1 个客户为 5 URL 固定范围试点注资/支付 ¥4,000 |
| Day 17 | 提交首段并开下一段闸门 | Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Contract > Milestones | 先完成本阶段技术验收与边界记录：至少加入空值、重复、冲突、超长、权限拒绝、网络失败和回滚各 1 例。自定义多里程碑合同点击 Submit work 后，等客户批准且下一里程碑已注资才继续；若是一次注资的 Project Catalog 订单，只保留阶段证据，不提前提交整单 |
| Day 18 | 隐私与回滚 | Google Docs > Blank > Data handling & rollback；Share > Restricted | 写数据区、最小权限、保留期、删除、撤权、备份、回滚负责人和恢复时间；客户书面确认 |
| Day 19 | 录 90 秒证据演示 | QuickTime Player > File > New Screen Recording；或 OBS > Start Recording | 按问题20秒→一个商品模板、5 个 SKU、一个市场的固定范围实施30秒→测试30秒→边界10秒；遮住账号、密钥和客户数据 |
| Day 20 | 第二批 10 个触达 | Upwork > Saved searches/Jobs；或已过闸门的 Gmail drafts | 只复用已验证的一页样例；每个对象写不同的公开观察，不自动化、不买名单 |
| Day 21 | 一次跟进 | Upwork > Messages；或 Gmail > Sent > 对应线程 > Reply | 只跟进已联系对象一次，新增一条真实证据；退订立即写 suppression，之后停止 |
| Day 22 | 确认执行范围未变 | Google Docs > Proposal > Version history；Upwork > Contract > Milestones | 对照 Day 10 已注资合同，确认“一个商品模板、5 个 SKU、一个市场的固定范围实施”、技术验收、权限、日期和停止条件未变；不重新谈或重复收试点 |
| Day 23 | 运行已注资阶段 | 副本主题 > … > Preview；Google Rich Results Test > URL/Code > Test；Search Console > URL inspection > Test live URL；逐项与可见商品页/后台对账 | 自定义合同只在下一里程碑已注资后运行；Project Catalog 只在整单已注资后运行。按客户批准的最小权限先 5、再 20、再到约定上限；高风险错误、真实扣款或不可回滚变更立即停 |
| Day 24 | 每日 QA | Sheets > logs/QA tab > Create a filter | 每天抽查至少 10 条或全部小样本；只计算 有效页面占比、错误/警告数、与页面数据一致率，保留分母、失败和不能归因部分 |
| Day 25 | 读结果 | Sheets > baseline vs pilot；Looker Studio 可选 | 只对比 有效页面占比、错误/警告数、与页面数据一致率；写样本量和不能归因的部分 |
| Day 26 | 修一次 | 主题代码 + Rich Results Test + Search Console > Duplicate/Clone/Version；仅在测试或副本中改 | 只修最大的一类错误；保留 v1/v2、变更说明、回放结果和恢复点，不同时改多个变量 |
| Day 27 | 交付并提交当前里程碑 | Google Docs > New > SOP；Drive > Restricted folder；Upwork > Deliver work > Your active contracts > 目标合同 > Submit work | 交付配置清单、账号 owner、日常检查、异常、回滚、数据删除和录屏并撤销多余权限；在 Upwork 写明本次交付、附文件/受限链接并点 Submit work，确认状态进入 in review；只发 Drive/邮件不算平台提交 |
| Day 28 | 提续费 | Gmail > Compose/Reply；粘贴验收与复购话术 | 只把已证明稳定的步骤做月费；列每月上限、响应时间和不包含项 |
| Day 29 | 做案例 | Notion/官网 > New page/draft | 得到书面许可后才发布匿名案例；写基线、样本、结果、局限，不写客户机密 |
| Day 30 | 查款并规模/停止 | Upwork > Manage finances > Financial overview；Manage finances > Transactions；Sheets > decision/cash-ledger | 逐项记录 funded/submitted/approved/pending/available/withdrawn/bank-arrived；只有 bank-arrived 写到账。通过条件：至少 1 个真实付费信号、验收达标、毛利可接受、无重大合规缺口；否则缩窄、换细分或停止 |

## 5. 可复制注册、发布、销售与交付文案

### A. 平台服务页/落地页文案

**标题（直接粘贴）**

> Product/Offer/ReturnPolicy 结构化数据实施｜先做固定范围试点，用真实数据验收，不承诺虚假增长

**副标题（直接粘贴）**

> 面向商品页缺价格、库存和退货标记的 Shopify 商家。我会在不改变生产关键动作的前提下，完成「一个商品模板、5 个 SKU、一个市场的固定范围实施」，并用 有效页面占比、错误/警告数、与页面数据一致率 做前后验收。涉及发送、付款、退款、删除、公开发布或高风险判断的步骤默认保留人工批准。

**服务说明（直接粘贴）**

> 你现在可能遇到的问题是：页面信息机器不可读或 JSON-LD 与页面不一致，失去丰富结果资格。本项目不会先卖一套昂贵系统，而是先交付一个可回滚试点：检查并去除重复 Product JSON-LD；缺失时使用 Shopify structured_data 输出 Product/Offer，可选加入与公开页一致的全局退货政策链接。你会收到现状基线、配置/数据文件、测试记录、异常清单、操作 SOP、回滚办法和 14/30 天结果复盘。固定范围外的工作会在开始前单独报价。参考价：¥4,000–12,000/模板；维护 ¥500–1,500/月。

**CTA（直接粘贴）**

> 请发送 1 份脱敏样本、当前工具、每月处理量和最想改善的一个指标。我会先回复“能做/不该做/还缺什么”，不会要求你先开放管理员权限。

### B. 有条件适用的手工冷邮件（发送前先过司法辖区闸门）

**发送闸门（每个联系人都要记录）**

> 先记录发送者国家/地区、收件人国家/地区、收件主体是 corporate subscriber 还是个人/sole trader/partnership、合法基础、隐私告知 URL 和 suppression 状态。英国公司/LLP 等 corporate body 的 PECR 规则与个人不同，但姓名和个人化工作邮箱仍可能受 UK GDPR 约束；sole trader、非 LLP 等部分 partnership 通常按个人处理。类型不明时按个人处理。禁止追踪像素、个人数据拼接、购买名单和自动群发；无法确定规则时，改用 Upwork 平台响应、用户主动订阅、转介绍或公开内容获客。发送前复核收件地最新规则。

**主题：**关于贵司「Product/Offer/ReturnPolicy 结构化数据实施」的一页试点建议

> 你好，{姓名/团队}：  
> 我查看了贵司公开的 {页面/流程/职位信息}，发现一个可以用固定范围验证的问题：页面信息机器不可读或 JSON-LD 与页面不一致，失去丰富结果资格。我不是来承诺排名或收入的；我可以先用公开信息或你提供的脱敏样本，做「一个商品模板、5 个 SKU、一个市场的固定范围实施」，验收只看 有效页面占比、错误/警告数、与页面数据一致率。  
> 如果方向不相关，回复“不需要”即可，我不会再联系。若相关，我可以先发一页样例和完整边界，确认后再开任何权限。  
> {你的真实姓名}｜{公司/个人主体}｜{实体邮寄地址}｜{官网/作品集}  
> 退订：回复“不需要”。

**第一次跟进（3 个工作日后）**

> 补充一个具体点：本试点的最小通过条件是「1 个客户为 5 URL 固定范围试点注资/支付 ¥4,000」。如果你已有团队在做，我也可以只交只读审计和测试清单；若不相关，回复“不需要”，我会停止联系。

**最后一次跟进（再过 5 个工作日）**

> 这是最后一次跟进。我可以免费发一张脱敏样例，不需要管理员权限。若本季度没有优先级，无需回复；我会关闭这条联系记录。

### C. 发现电话脚本

> 这次 20 分钟只确认四件事：一，当前流程从哪里开始、在哪里结束；二，过去 30 天处理量和基线；三，哪些动作绝不能自动执行；四，什么数字达到才值得继续。若拿不到基线，我们就把试点目标改成“正确性和节省时间”，不编造收入归因。

### D. 固定范围提案

> **项目：**Product/Offer/ReturnPolicy 结构化数据实施 30 天验证  
> **客户：**{客户名}  
> **范围：**一个商品模板、5 个 SKU、一个市场的固定范围实施  
> **客户提供：**商品模板、价格/库存/SKU 字段、公开退货政策 URL、测试 URL、备份主题  
> **交付：**基线表、实施/配置、测试证据、异常队列、SOP、回滚说明、结果复盘  
> **技术验收：**5 个 URL 无 Product/Merchant listing critical error，每页只有一套目标 Product 或合理 ProductGroup 实体，价格、币种、库存、SKU、URL 与可见页/后台一致，副本主题购买路径无回归  
> **商业验证：**1 个客户为 5 URL 固定范围试点注资/支付 ¥4,000  
> **不包含：**未授权数据、法律/医疗/金融意见、批量群发、平台条款规避、资金代收、自动退款/删除/公开发布  
> **付款路径：**Upwork 所有金额以 USD 列示：Project Catalog 输入 US$575（报告统一按 US$1=¥7 折算约 ¥4,025；执行日以平台/银行实际换汇为准） 并由客户一次注资；若走自定义 fixed-price 合同，则两个里程碑为 US$288/US$287，合计 US$575，里程碑1交付基线、范围、规则和验收计划，截止 Day 17；里程碑2交付最终结果、QA、SOP和删除/回滚记录，截止 Day 28。每次只在当前里程碑 Active/Funded 后开工，提交并获批当前段后，等下一段 Active/Funded 才继续。独立获客且从未在 Upwork 建立关系的客户，可另用合规账单按 ¥4,000 报价；不得把 Upwork 客户移到站外付款。客户批准后仍有 5 天安全期。 参考扩展价：¥4,000–12,000/模板；维护 ¥500–1,500/月。技术验收与注资、批准、Pending 和银行到账分开记录。  
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

### Shopify Liquid / JSON-LD 可复制实现

先在主题代码搜索 `application/ld+json` 和 `structured_data`；已有 Product 输出时只修现有实现，禁止叠加第二套。确实缺失时，在商品模板中只放一次：

```liquid
<script type="application/ld+json">
  {{ product | structured_data }}
</script>
```

可选全局退货政策只引用客户公开政策页：

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "OnlineStore",
  "name": "REPLACE_STORE_NAME",
  "url": "https://REPLACE_DOMAIN",
  "hasMerchantReturnPolicy": {
    "@type": "MerchantReturnPolicy",
    "merchantReturnLink": "https://REPLACE_DOMAIN/policies/refund-policy"
  }
}
</script>
```

验收表：`URL | Product实体数 | name | sku | price | priceCurrency | availability | 页面一致 | Critical errors | 回归`。先 Duplicate 主题并 Preview；5 个 SKU 用 [Rich Results Test](https://search.google.com/test/rich-results) 对账，客户批准后才发布。




本方法不依赖通用抓取脚本；优先使用客户自有平台的测试/副本/导出能力。

## 7. 主要风险与预设应对

- **风险：标记与页面不一致**　应对：全部数据从同一商品字段读取并做 5 SKU 抽查
- **风险：改主题导致站点故障**　应对：复制主题、预览、版本 diff，客户批准后发布
- **渠道风险：**平台 KYC、收款、费率和功能会变。Day 1 只验证真实账户、税务与收款方式状态；首个真实余额后再验证到账，失败则换合法渠道，不伪造地区。
- **归因风险：**外部销量、转化或中标受多因素影响。只报告试点可测指标、样本量和局限。
- **外联风险：**只做人工、相关、低量外联，使用真实身份/地址/退订；不得抓取、自动私信或骚扰。

## 8. 30 天结束时的 Go / Iterate / Stop

- **Go：**达到本方法的商业验证门槛：“1 个客户为 5 URL 固定范围试点注资/支付 ¥4,000”；关键验收达标；贡献毛利可接受；交付不依赖违规或单点人工英雄主义。
- **Iterate：**有人愿付但范围或价格错；只改最大障碍，再跑一个 7–14 天试点。
- **Stop：**Day 30 未达到上述商业验证门槛、存在重大合规/许可问题、收款不可用或价值只能靠不可验证承诺成立。

> **方法21已完成，开始方法22调研。**
