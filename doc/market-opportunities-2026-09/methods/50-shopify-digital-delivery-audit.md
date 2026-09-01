# 方法 50｜Shopify 数字商品附件与交付审计

> **一页结论：**面向销售电子书、课程文件、音频或预售数字内容的小型 Shopify 商家，用「20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP」先收费验证。启动现金成本 ¥0–200，目标是 缺失/错误附件数、测试交付成功率、补发时间、相关客服工单数。这里的报价和收益是**本报告的测试模型，不是行业均价或收益保证**。

## 0. 执行卡

| 项目 | 内容 |
|---|---|
| 分类 | 电商增长 |
| 买方 | 销售电子书、课程文件、音频或预售数字内容的小型 Shopify 商家 |
| 当前痛点 | 商品与附件绑定不透明，版本更新、补发和测试订单容易漏文件或发错文件 |
| 可交付结果 | 建立商品—variant—附件映射表，逐项检查 20 个商品，跑测试订单并交付补发、版本和发布日 SOP |
| 最小试点 | 20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP |
| 工具栈 | Shopify Digital Products + Shopify Payments test mode + Google Sheets |
| 启动成本 | ¥0–200（不含自己的人工） |
| 时间 | 7–10 天付费验证；3–7 天样例 |
| 技能 | Shopify 商品/订单、数字文件版本、测试与操作 SOP |
| 参考测试报价 | Upwork 20 商品试点 US$215；后续审计 ¥1,500–5,000；月度复检 ¥500–1,500 |
| 最小验证 | 先审计 5 个商品并展示 1 条真实映射缺口；1 个客户购买并全额注资一个 US$215 Upwork Project Catalog 试点（按 US$1=¥7 为 ¥1,505） |
| 综合分 | 4.50/5；需求证据 4 / 验证速度 5 / 低成本 5 / 复购性 4 / 自动化杠杆 4 / 获客可达 5 / 风险可控 5 |

## 1. 为什么现在能赚钱

赚钱逻辑不是“AI/数据/模板很火”，而是把 **商品与附件绑定不透明，版本更新、补发和测试订单容易漏文件或发错文件** 变成一个买方能验收的固定范围结果：**建立商品—variant—附件映射表，逐项检查 20 个商品，跑测试订单并交付补发、版本和发布日 SOP**。先用人工和低成本工具交付，客户确认价值后才把重复步骤自动化；这样现金投入低，也避免先做没人买的软件。

### 当前市场证据

- **M13｜[Shopify About](https://www.shopify.com/news/about-us)：**Shopify 服务 175 多个国家的数百万商家，2025 年 GMV 为 3,780 亿美元，生态中有 21,000 多个应用。 **使用边界：**平台规模不自动证明某个细分需求。
- **P12｜[Shopify Digital Products app listing](https://apps.shopify.com/digital-downloads)：**Shopify 官方应用当前显示为 Digital Products；应用页约有 1,000 条以上评论，近期评论直接提到发布日需求和附件绑定可见性问题。 **使用边界：**应用评论是具体问题线索而非独立市场规模；功能、评分和评论数会变化，执行前应重查。
- **P22｜[Upwork Direct to Local Bank](https://support.upwork.com/hc/en-us/articles/211063888-How-to-withdraw-earnings-with-Direct-to-Local-Bank)：**Upwork Direct to Local Bank 支持中国 CNY，每次提现费 0.99 美元；新收款方式为安全需 3 天激活，提现后通常 4 天内到银行。 **使用边界：**姓名必须与 Upwork 验证身份一致，银行限制/费用可另行适用。Day 1 只验证 Account settings > Withdrawals > Add a method > Set up 的真实可用状态，不伪造地区或到账。
- **P23｜[Upwork fixed-price and Project Catalog payments](https://support.upwork.com/hc/en-us/articles/211063718-How-payments-for-milestones-and-fixed-price-contracts-work)：**Upwork fixed-price 里程碑/项目需客户先注资；提交后客户最长可审核 14 天，批准或自动释放后再有 5 天安全期才可提现。 **使用边界：**已注资只证明付费意愿，不等于技术验收、可提现余额或银行到账。核心工作不用 bonus 代替；每个里程碑的交付和金额必须先写清。
- **P25｜[Shopify Digital Products help](https://help.shopify.com/en/manual/products/digital-service-product/digital-downloads)：**Shopify 官方应用当前名为 Digital Products，主区为 Dashboard、Orders 和 Settings；Dashboard 点击商品后在 Digital Products block 管理数字文件，Orders 内打开订单可 Resend download email。 **使用边界：**文件替换/删除可影响既有买家链接。审计必须逐 variant 核对资产、版本、attachment status、fulfillment 和 download limit，并保留客户批准。
- **P26｜[Shopify placing a test order](https://help.shopify.com/en/manual/checkout-settings/test-orders)：**Shopify 明确提醒：Shopify Payments 的 Test mode 路径是 Settings > Payments > Shopify Payments > Manage > Test mode；启用时真实客户不能下单，测试单不进入 payout 或正常报表。 **使用边界：**只能在客户书面批准的低流量连续维护窗口启用 test mode，一次完成全部测试后立即关闭并确认恢复真实结账。
- **M30｜[Upwork How to create a project in Project Catalog](https://support.upwork.com/hc/en-us/articles/360057397533-How-to-create-a-project-in-Project-Catalog)：**当前自由职业者创建 Project Catalog 的路径为 Find Work > Your services > Create Project；项目价格范围明确列为 US$5–US$500,000。 **使用边界：**人民币只可作内部折算模型，不能填进 Upwork Price/offer 金额；实际 CNY 到账由支付伙伴换汇且可能含加价。菜单、资格、费率和审核会变化。
- **P27｜[Upwork submit work and milestones](https://support.upwork.com/hc/en-us/articles/211068368-How-to-submit-work-and-milestones-to-your-client)：**固定价工作完成后，自由职业者必须从 Deliver work > Your active contracts 打开合同并点击 Submit work，写明交付并附文件，才会启动客户审核流程。 **使用边界：**只交 Drive/邮件不等于向 Upwork 提交；多里程碑合同每段都要提交当前已注资里程碑、等客户批准并注资下一段后再继续。
- **P28｜[Upwork track earnings status](https://support.upwork.com/hc/en-us/articles/211068418-How-to-track-the-status-of-your-earnings-on-Upwork)：**当前收益状态入口为 Manage finances > Financial overview，也可在 Manage finances > Transactions 查看明细；状态区分 work in progress、in review、pending 和 available。 **使用边界：**Funded、submitted、approved、pending、available、withdrawn 和 bank-arrived 必须分开记录；只有 bank-arrived 才是银行到账。
- **P29｜[Upwork local currency and USD listing](https://support.upwork.com/hc/en-us/articles/211068028-How-to-pay-in-your-local-currency)：**Upwork 官方说明所有成本以 USD 列示；部分客户付款时可看到本币换算，但显示汇率只是估计，最终扣款以交易记录为准。 **使用边界：**自由职业者必须在 Project Catalog Price、offer 和 milestone 输入 USD；人民币只作报告换算假设，实际 CNY 到账由支付伙伴汇率和费用决定。
- **P31｜[Upwork eligibility to propose a new contract](https://support.upwork.com/hc/en-us/articles/115006647007-How-to-propose-a-new-contract)：**自由职业者只能向已至少付过一次款的当前/既往客户，或主动从有效 Project Catalog 项目发消息的潜在客户提出新合同。 **使用边界：**普通职位申请不能由卖方直接 Propose new contract；应 Apply 后等待客户发送 Offer，并先核验 fixed-price 当前里程碑已 Active/Funded。
- **P32｜[Upwork fixed-price milestone requirements](https://support.upwork.com/hc/en-us/articles/211068218-How-to-use-milestones-in-fixed-price-jobs)：**固定价里程碑开始前应写清金额、交付物与截止日；每次只能注资一个里程碑，当前段释放后才能激活并注资下一段。 **使用边界：**卖方不能替客户点击 Fund；每段只在 Active/Funded 后开工，完成后从 Deliver work 提交，等批准并看到下一段 Active/Funded 才继续。
- **P35｜[Upwork direct offers from clients](https://support.upwork.com/hc/en-us/articles/30113729524499-How-direct-offers-from-clients-work-on-Upwork)：**自由职业者收到客户 Offer 后，可从 Messages 打开对应会话，依次选择 View offer，再选择 Accept offer、Request changes 或 Decline offer；接受前可以协商范围、价格和期限。 **使用边界：**普通职位仍需先 Apply 并等待客户发 Offer；接受后还要核验 fixed-price 当前里程碑/订单为 Active/Funded，卖方不能替客户点击 Fund。

### 竞品与切入

Shopify 官方 Digital Products 已覆盖基本交付，但用户评论暴露附件绑定、发布日和审计可见性缺口；先卖人工 QA，不开发泛下载 App。因此不要卖“我会某个工具”，要卖一条窄结果、真实回放、人工审批、可回滚交付和后续维护。

**证据依赖提醒：**本方法使用来源 M13、P12、P22、P23、P25、P26、M30、P27、P28、P29、P31、P32、P35。它们支持市场/渠道/工具事实，但不直接证明你的细分客户会购买；付费意愿必须由本方案的预售试点验证。

## 2. 产品、价格与单位经济

### 固定范围产品

- **名称：**Shopify 数字商品附件与交付审计 30 天验证包
- **交付：**20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP；另附基线、测试记录、异常清单、SOP、回滚/删除说明。
- **客户输入：**20 个商品/variant、应交付文件与版本、发布时间、下载限制、Shopify Payments 当前状态、测试邮箱、退款/补发规则
- **验收指标：**缺失/错误附件数、测试交付成功率、补发时间、相关客服工单数
- **参考报价：**Upwork 20 商品试点 US$215；后续审计 ¥1,500–5,000；月度复检 ¥500–1,500

### 月收益情景（税前可计收入；数字平台按文中分成/版税模型）

| 情景 | 本报告假设 | 预估月营收 |
|---|---|---:|
| 保守 | 保守 1×US$215×¥7=¥1,505（平台费前已注资订单值）；模型合计=¥1,505 | ¥1,505 |
| 中性 | 中性 4×¥1,750 审计+3×¥500 复检=¥8,500；模型合计=¥8,500 | ¥8,500 |
| 乐观 | 乐观 10×¥2,000 审计+8×¥500 复检=¥24,000；模型合计=¥24,000 | ¥24,000 |

- **回本周期：**现金口径：按保守月营收匀速折算约 4 天；含工时口径：按首月 24 小时、目标时薪 ¥200/小时，需覆盖约 ¥5,000，按保守情景折算约 100 天。这是容量模型；真实回本以实际收款日、平台结算期、退款、税和工时为准。
- **毛利闸门：**试点结束统计实际工时、工具费、平台费、退款与支持。税前贡献毛利低于 60% 时，不扩量，先提价或缩范围。
- **停止条件：**30 天无付费、关键验收失败、平台/KYC 不可用、数据许可不清或必须靠违规抓取/群发才能获客，立即停止或换细分。

## 3. 最小验证方案

1. 不先做完整产品；只做「20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP」。
2. 使用公开信息或客户主动提供的脱敏样本，不先索要管理员、支付或生产写权限。
3. **商业验证门槛：**先审计 5 个商品并展示 1 条真实映射缺口；1 个客户购买并全额注资一个 US$215 Upwork Project Catalog 试点（按 US$1=¥7 为 ¥1,505）
4. **技术验收门槛：**20 个商品的每个 variant 都有附件/链接、版本、attachment status、fulfillment type、download limit 和 owner；3 个测试订单 100% 收到正确资产，补发成功，test mode 已关闭且真实结账恢复
5. 只做 10–30 个强相关潜在买方的人工触达；不买名单、不抓 LinkedIn、不做自动群发。
6. 失败也要留数据：拒绝原因、价格、真实工时、误报/漏报和客户不用的功能，作为是否换细分的依据。

## 4. Day 1–30 落地日历

| 天 | 今天具体做什么 | 工具/点击路径 | 输入、输出与通过条件 |
|---:|---|---|---|
| Day 1 | 收款与范围双闸门 | Upwork > Account settings > Withdrawals > Add a method > Direct to Local Bank > Set up；Shopify 只读范围表 | 中国 CNY 收款方式真实姓名一致；新方式 3 天激活、US$0.99/次，客户批准后还有 5 天安全期。范围只含 20 商品/variant、3 测试单和一次连续维护窗口 |
| Day 2 | 核证据 | 打开本文件“市场证据”中的全部官方链接；浏览器 > Bookmark folder | 逐条记录发布日期、事实与局限；如果关键链接失效，暂停宣传该事实 |
| Day 3 | 建 30 个 ICP | Upwork > Find Work > Search jobs > 输入 Shopify digital downloads audit；公司官网只看 Contact/Team 通用入口 | Sheets targets 列 company/source_url/why_fit/jurisdiction/entity_type/status；只录与“商品与附件绑定不透明，版本更新、补发和测试订单容易漏文件或发错文件”直接相关的 30 个主体，不抓个人数据 |
| Day 4 | 量基线 | Google Sheets > baseline tab | 输入最近 30 天 缺失/错误附件数、测试交付成功率、补发时间、相关客服工单数；没有数字就记录样本量、当前耗时和错误例子 |
| Day 5 | 做 5 商品只读样例 | Shopify Admin > Apps > Digital Products > Dashboard > Has digital file/No digital file > 点击商品 > Digital Products block；Sheets > sample | 逐 variant 记录 expected/actual asset、version、attachment status、fulfillment、download limit 和证据；只展示至少 1 条真实缺口，不替换或删除文件 |
| Day 6 | 收脱敏样本 | Google Drive > New > Folder > Share > Restricted | 向测试客户索取：20 个商品/variant、应交付文件与版本、发布时间、下载限制、Shopify Payments 当前状态、测试邮箱、退款/补发规则；密码/API key 不放文档 |
| Day 7 | 发布 US$215 固定价服务 | Upwork > Find Work > Your services > Create Project | 价格字段输入 US$215（按 US$1=¥7 折算约 ¥1,505）；粘贴标题、20 商品/3 测试单/一个连续窗口的范围和不包含项，不把人民币金额填进 USD 价格字段 |
| Day 8 | 首批手工触达 | Upwork > Find Work > Search jobs > 打开 10 个强相关职位 > Apply now；或通过司法辖区闸门后 Gmail > Compose | 每条引用 1 个真实公开观察，发送本文件文案；CTA 只要求脱敏样本，范围为“20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP” |
| Day 9 | 发现访谈 | Calendly > Event types > New event type > 20 min；Google Meet > New meeting | 访谈 3 人，记录当前流程、缺失/错误附件数、测试交付成功率、补发时间、相关客服工单数 基线、禁止自动动作、预算和采购人 |
| Day 10 | 客户购买唯一完整试点 | Upwork > Find Work > Your services > 已发布 US$215 Project > 客户 Buy project > Fund | 一个 US$215 Project Catalog 订单一次全额注资；范围固定为映射表、20 商品、3 测试单、一次连续窗口、恢复结账、SOP 和技术验收，不另收第二个试点、不走替代账单 |
| Day 11 | 完成 20 商品审计 | Shopify Admin > Apps > Digital Products > Dashboard > 点击商品 > Digital Products block；Sheets > mapping/QA | 20 商品每个 variant 都写 expected_asset/actual_asset/version/status/result/evidence；缺失、错版、链接和权限问题单列 |
| Day 12 | 只做客户批准的修复 | Digital Products > Dashboard > 目标商品 > Digital Products block；Sheets > approval | 客户逐项勾选 approved 后才改附件、链接或限制；每项先记录既有买家影响、before 值和回滚值 |
| Day 13 | 冻结测试计划 | Google Calendar > Create event；Shopify > Settings > Payments 只读截图 | 书面确认 Day 14 低流量连续窗口、owner、三种订单、测试邮箱、入口前后截图和立即关闭步骤；明确 test mode 期间真实客户不能下单 |
| Day 14 | 只开一次连续测试窗口 | Settings > Payments > Shopify Payments > Manage > Test mode > Enable test mode；完成单 variant/多 variant/版本补发 3 单；Apps > Digital Products > Orders > 订单 > Resend download email；Manage > Disable test mode | Day 14 一次完成全部 3 单和补发，每单核对文件/链接/版本/邮件；立即关闭 test mode，用设置和真实结账页截图确认恢复，此后原试点不再重开 |
| Day 15 | 整理唯一验收包 | Sheets > QA filter；Digital Products > Dashboard/Orders；Drive > Restricted folder | 执行技术验收：20 个商品的每个 variant 都有附件/链接、版本、attachment status、fulfillment type、download limit 和 owner；3 个测试订单 100% 收到正确资产，补发成功，test mode 已关闭且真实结账恢复；整理映射、三单、补发、test mode 已关闭、真实结账恢复、已知例外与 SOP；付款信号单列 |
| Day 16 | 只提交一次 | Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Sheets > approval | Day 16 写明完整交付、附验收包并只点一次 Submit work，确认进入 in review；之后只回应已交内容的问题，不追加测试窗口、不重复提交或重新议价 |
| Day 17 | 处理一次验收反馈 | Upwork > Messages；Sheets > exceptions | 只澄清已交证据或修正文档；若必须重开 test mode 或扩大商品范围，只记录为 Day 30 后的独立合同候选；本轮不重开 test mode、不新增订单、不再次使用平台提交按钮 |
| Day 18 | 隐私与回滚 | Google Docs > Blank > Data handling & rollback；Share > Restricted | 写数据区、最小权限、保留期、删除、撤权、备份、回滚负责人和恢复时间；客户书面确认 |
| Day 19 | 录 90 秒证据演示 | QuickTime Player > File > New Screen Recording；或 OBS > Start Recording | 按问题20秒→20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP30秒→测试30秒→边界10秒；遮住账号、密钥和客户数据 |
| Day 20 | 第二批 10 个触达 | Upwork > Saved searches/Jobs；或已过闸门的 Gmail drafts | 只复用已验证的一页样例；每个对象写不同的公开观察，不自动化、不买名单 |
| Day 21 | 一次跟进 | Upwork > Messages；或 Gmail > Sent > 对应线程 > Reply | 只跟进已联系对象一次，新增一条真实证据；退订立即写 suppression，之后停止 |
| Day 22 | 确认执行范围未变 | Google Docs > Proposal > Version history；Upwork > Contract > Milestones | 对照 Day 10 已注资合同，确认“20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP”、技术验收、权限、日期和停止条件未变；不重新谈或重复收试点 |
| Day 23 | 只查付款状态 | Upwork > Manage finances > Financial overview；Manage finances > Transactions；Shopify > Settings > Payments | Day 23 只记录 submitted/in review/approved、5 天安全期、pending/available 与真实结账仍恢复；不把注资/pending 写成银行到账，不重跑测试 |
| Day 24 | 每日 QA | Sheets > logs/QA tab > Create a filter | 每天抽查至少 10 条或全部小样本；只计算 缺失/错误附件数、测试交付成功率、补发时间、相关客服工单数，保留分母、失败和不能归因部分 |
| Day 25 | 读结果 | Sheets > baseline vs pilot；Looker Studio 可选 | 只对比 缺失/错误附件数、测试交付成功率、补发时间、相关客服工单数；写样本量和不能归因的部分 |
| Day 26 | 只修离线文档 | Sheets > mapping/exceptions > Duplicate v1 to v2；Docs > SOP > Version history | 只修映射表、例外说明或 SOP 的一类错误并保留 v1/v2；不进入 Shopify Payments、不重开 test mode、不改附件。需要再次实测或生产修改时另签后续独立窗口 |
| Day 27 | 归档唯一提交后的最终证据 | Google Docs > SOP > Version history；Drive > Restricted；Upwork > Messages | 把最终映射表、SOP、录屏和删除/撤权记录归档到 Day 16 已提交的受限交付目录；只在 Messages 回答客户对已交内容的问题，不再使用平台提交按钮，不重置审核期 |
| Day 28 | 提续费 | Gmail > Compose/Reply；粘贴验收与复购话术 | 只把已证明稳定的步骤做月费；列每月上限、响应时间和不包含项 |
| Day 29 | 做案例 | Notion/官网 > New page/draft | 得到书面许可后才发布匿名案例；写基线、样本、结果、局限，不写客户机密 |
| Day 30 | 按唯一订单门槛关闭试点 | Upwork > Manage finances > Transactions > Available balance > Withdraw earnings > Withdraw now；Shopify > Settings > Users and permissions；Sheets > closeout | Day 30 逐字核验商业门槛：先审计 5 个商品并展示 1 条真实映射缺口；1 个客户购买并全额注资一个 US$215 Upwork Project Catalog 试点（按 US$1=¥7 为 ¥1,505）。同时记录 funded/approved/pending/available/withdrawn/bank-arrived，只有 bank-arrived 写到账；撤销多余权限并确认 test mode 关闭。本轮不重开测试、不新增订单；后续需求只能在本轮关闭后成为独立合同 |

## 5. 可复制注册、发布、销售与交付文案

### A. 平台服务页/落地页文案

**标题（直接粘贴）**

> Shopify 数字商品附件与交付审计｜先做固定范围试点，用真实数据验收，不承诺虚假增长

**副标题（直接粘贴）**

> 面向销售电子书、课程文件、音频或预售数字内容的小型 Shopify 商家。我会在不改变生产关键动作的前提下，完成「20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP」，并用 缺失/错误附件数、测试交付成功率、补发时间、相关客服工单数 做前后验收。涉及发送、付款、退款、删除、公开发布或高风险判断的步骤默认保留人工批准。

**服务说明（直接粘贴）**

> 你现在可能遇到的问题是：商品与附件绑定不透明，版本更新、补发和测试订单容易漏文件或发错文件。本项目不会先卖一套昂贵系统，而是先交付一个可回滚试点：建立商品—variant—附件映射表，逐项检查 20 个商品，跑测试订单并交付补发、版本和发布日 SOP。你会收到现状基线、配置/数据文件、测试记录、异常清单、操作 SOP、回滚办法和 14/30 天结果复盘。固定范围外的工作会在开始前单独报价。参考价：Upwork 20 商品试点 US$215；后续审计 ¥1,500–5,000；月度复检 ¥500–1,500。

**CTA（直接粘贴）**

> 请发送 1 份脱敏样本、当前工具、每月处理量和最想改善的一个指标。我会先回复“能做/不该做/还缺什么”，不会要求你先开放管理员权限。

### B. 有条件适用的手工冷邮件（发送前先过司法辖区闸门）

**发送闸门（每个联系人都要记录）**

> 先记录发送者国家/地区、收件人国家/地区、收件主体是 corporate subscriber 还是个人/sole trader/partnership、合法基础、隐私告知 URL 和 suppression 状态。英国公司/LLP 等 corporate body 的 PECR 规则与个人不同，但姓名和个人化工作邮箱仍可能受 UK GDPR 约束；sole trader、非 LLP 等部分 partnership 通常按个人处理。类型不明时按个人处理。禁止追踪像素、个人数据拼接、购买名单和自动群发；无法确定规则时，改用 Upwork 平台响应、用户主动订阅、转介绍或公开内容获客。发送前复核收件地最新规则。

**主题：**关于贵司「Shopify 数字商品附件与交付审计」的一页试点建议

> 你好，{姓名/团队}：  
> 我查看了贵司公开的 {页面/流程/职位信息}，发现一个可以用固定范围验证的问题：商品与附件绑定不透明，版本更新、补发和测试订单容易漏文件或发错文件。我不是来承诺排名或收入的；我可以先用公开信息或你提供的脱敏样本，做「20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP」，验收只看 缺失/错误附件数、测试交付成功率、补发时间、相关客服工单数。  
> 如果方向不相关，回复“不需要”即可，我不会再联系。若相关，我可以先发一页样例和完整边界，确认后再开任何权限。  
> {你的真实姓名}｜{公司/个人主体}｜{实体邮寄地址}｜{官网/作品集}  
> 退订：回复“不需要”。

**第一次跟进（3 个工作日后）**

> 补充一个具体点：本试点的最小通过条件是「先审计 5 个商品并展示 1 条真实映射缺口；1 个客户购买并全额注资一个 US$215 Upwork Project Catalog 试点（按 US$1=¥7 为 ¥1,505）」。如果你已有团队在做，我也可以只交只读审计和测试清单；若不相关，回复“不需要”，我会停止联系。

**最后一次跟进（再过 5 个工作日）**

> 这是最后一次跟进。我可以免费发一张脱敏样例，不需要管理员权限。若本季度没有优先级，无需回复；我会关闭这条联系记录。

### C. 发现电话脚本

> 这次 20 分钟只确认四件事：一，当前流程从哪里开始、在哪里结束；二，过去 30 天处理量和基线；三，哪些动作绝不能自动执行；四，什么数字达到才值得继续。若拿不到基线，我们就把试点目标改成“正确性和节省时间”，不编造收入归因。

### D. 固定范围提案

> **项目：**Shopify 数字商品附件与交付审计 30 天验证  
> **客户：**{客户名}  
> **范围：**20 个数字商品、3 个 Shopify Payments 测试订单、一个交付映射表和补发/版本 SOP  
> **客户提供：**20 个商品/variant、应交付文件与版本、发布时间、下载限制、Shopify Payments 当前状态、测试邮箱、退款/补发规则  
> **交付：**基线表、实施/配置、测试证据、异常队列、SOP、回滚说明、结果复盘  
> **技术验收：**20 个商品的每个 variant 都有附件/链接、版本、attachment status、fulfillment type、download limit 和 owner；3 个测试订单 100% 收到正确资产，补发成功，test mode 已关闭且真实结账恢复  
> **商业验证：**先审计 5 个商品并展示 1 条真实映射缺口；1 个客户购买并全额注资一个 US$215 Upwork Project Catalog 试点（按 US$1=¥7 为 ¥1,505）  
> **不包含：**未授权数据、法律/医疗/金融意见、批量群发、平台条款规避、资金代收、自动退款/删除/公开发布  
> **付款路径：**Upwork 使用一个 US$215 Project Catalog fixed-price order，客户购买时全额注资；完成映射、一次连续测试窗口与恢复结账后只提交一次验收。客户批准后仍有 5 天安全期，不把注资或 Pending 写成已到账。 参考扩展价：Upwork 20 商品试点 US$215；后续审计 ¥1,500–5,000；月度复检 ¥500–1,500。技术验收与注资、批准、Pending 和银行到账分开记录。  
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

### Shopify 数字交付确定性审计表

```text
product_handle | product_id | variant_title | variant_id | fulfillment_type | expected_asset | expected_version | attachment_status | actual_asset | download_limit | release_date | test_order | delivery_received | resend_test | owner | result | evidence
```

1. `Apps > Digital Products > Dashboard`：用 `Has digital file` / `No digital file` / attachment status 筛选，点击商品后在 `Digital Products block` 逐 variant 核对附件，禁止只按 product 级假设。  
2. 文件命名：`product-slug_vYYYY-MM-DD.ext`；旧版保留/替换由客户书面决定。  
3. 核对 `attachment_status`、数字/混合履约类型、下载限制、发布日及现有订单更新影响。  
4. 客户批准后启用 test mode，完成 3 个测试订单：单 variant、多 variant、更新/补发。  
5. 正确补发路径：`Apps > Digital Products > Orders > 订单 > Resend download email`。  
6. 三单必须收到正确文件/版本；退出 test mode，撤销多余权限，临时文件按约定删除。

> **不可拆分的试点约束：**全程只有一个 US$215 Project Catalog 订单、一个 Day 14 连续 test-mode 窗口、一次 Day 16 Submit work。Day 23 只查付款状态；任何新增范围或再次开启 test mode 只记录为 Day 30 关闭本轮后的独立合同候选，本轮不新增订单、不再次提交。




本方法不依赖通用抓取脚本；优先使用客户自有平台的测试/副本/导出能力。

## 7. 主要风险与预设应对

- **风险：test mode 阻断真实客户下单**　应对：只在客户书面批准的低流量连续维护窗口启用一次；三单和补发结束后立即关闭并用测试页确认结账恢复
- **风险：文件版权或敏感链接泄露**　应对：只处理客户拥有的文件，最小权限，不复制到个人云盘，交付后删除临时文件
- **渠道风险：**平台 KYC、收款、费率和功能会变。Day 1 只验证真实账户、税务与收款方式状态；首个真实余额后再验证到账，失败则换合法渠道，不伪造地区。
- **归因风险：**外部销量、转化或中标受多因素影响。只报告试点可测指标、样本量和局限。
- **外联风险：**只做人工、相关、低量外联，使用真实身份/地址/退订；不得抓取、自动私信或骚扰。

## 8. 30 天结束时的 Go / Iterate / Stop

- **Go：**达到本方法的商业验证门槛：“先审计 5 个商品并展示 1 条真实映射缺口；1 个客户购买并全额注资一个 US$215 Upwork Project Catalog 试点（按 US$1=¥7 为 ¥1,505）”；关键验收达标；贡献毛利可接受；交付不依赖违规或单点人工英雄主义。
- **Iterate：**有人愿付但范围或价格错；只改最大障碍，再跑一个 7–14 天试点。
- **Stop：**Day 30 未达到上述商业验证门槛、存在重大合规/许可问题、收款不可用或价值只能靠不可验证承诺成立。

> **方法50已完成，开始最终对比表与执行优先级排序。**
