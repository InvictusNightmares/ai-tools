# 方法 41｜Census 建筑许可热点报告

> **一页结论：**面向屋顶、HVAC、建材分销、加盟和本地广告代理，用「一个州、过去 24 个月、10 个地区的月报样板」先收费验证。启动现金成本 ¥0–300，目标是 目标地区被采用数、数据对账差异、客户行动数。这里的报价和收益是**本报告的测试模型，不是行业均价或收益保证**。

## 0. 执行卡

| 项目 | 内容 |
|---|---|
| 分类 | 公共数据情报 |
| 买方 | 屋顶、HVAC、建材分销、加盟和本地广告代理 |
| 当前痛点 | 不知道哪些城市住宅新建许可正在增长，市场投放靠感觉 |
| 可交付结果 | 按 metro/县/城市做许可量、同比、趋势和局限的一页纸，不提供个人地址线索 |
| 最小试点 | 一个州、过去 24 个月、10 个地区的月报样板 |
| 工具栈 | Census BPS 下载/API + Sheets + Looker Studio |
| 启动成本 | ¥0–300（不含自己的人工） |
| 时间 | 7–14 天 |
| 技能 | Census 数据、同比/季节性、地图/可视化 |
| 参考测试报价 | ¥999–4,000/报告；¥499–1,499/月 |
| 最小验证 | 给 5 个本地服务商一页免费样板；1 个以 ¥999 购买完整州报告 |
| 综合分 | 4.35/5；需求证据 4 / 验证速度 4 / 低成本 5 / 复购性 4 / 自动化杠杆 5 / 获客可达 4 / 风险可控 5 |

## 1. 为什么现在能赚钱

赚钱逻辑不是“AI/数据/模板很火”，而是把 **不知道哪些城市住宅新建许可正在增长，市场投放靠感觉** 变成一个买方能验收的固定范围结果：**按 metro/县/城市做许可量、同比、趋势和局限的一页纸，不提供个人地址线索**。先用人工和低成本工具交付，客户确认价值后才把重复步骤自动化；这样现金投入低，也避免先做没人买的软件。

### 当前市场证据

- **D14｜[Census Building Permits Survey](https://www.census.gov/construction/bps/index.html)：**Building Permits Survey 覆盖约 8,400 个许可地区，提供州、县、城市月度与年度住宅新建许可数据。 **使用边界：**仅覆盖住宅新建并存在修订和月度滞后。
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

商业许可线索库更细但昂贵；你的产品是聚合选址信号而非地址级线索。因此不要卖“我会某个工具”，要卖一条窄结果、真实回放、人工审批、可回滚交付和后续维护。

**证据依赖提醒：**本方法使用来源 D14、M30、P22、P23、P27、P28、P29、P31、P32、P35。它们支持市场/渠道/工具事实，但不直接证明你的细分客户会购买；付费意愿必须由本方案的预售试点验证。

## 2. 产品、价格与单位经济

### 固定范围产品

- **名称：**Census 建筑许可热点报告 30 天验证包
- **交付：**一个州、过去 24 个月、10 个地区的月报样板；另附基线、测试记录、异常清单、SOP、回滚/删除说明。
- **客户输入：**州/metro、服务半径、最小许可量、同比阈值、客户服务类型
- **验收指标：**目标地区被采用数、数据对账差异、客户行动数
- **参考报价：**¥999–4,000/报告；¥499–1,499/月

### 月收益情景（税前可计收入；数字平台按文中分成/版税模型）

| 情景 | 本报告假设 | 预估月营收 |
|---|---|---:|
| 保守 | 保守 1 份州报告；归一化校验：1 个该情景订单组合×¥999=¥999；模型合计=¥999 | ¥999 |
| 中性 | 中性 5 份报告加 4 个订阅；归一化校验：1 个该情景订单组合×¥6,990=¥6,990；模型合计=¥6,990 | ¥6,990 |
| 乐观 | 乐观 12 份报告加 10 个订阅；归一化校验：1 个该情景订单组合×¥24,000=¥24,000；模型合计=¥24,000 | ¥24,000 |

- **回本周期：**现金口径：按保守月营收匀速折算约 10 天；含工时口径：按首月 18 小时、目标时薪 ¥200/小时，需覆盖约 ¥3,900，按保守情景折算约 118 天。这是容量模型；真实回本以实际收款日、平台结算期、退款、税和工时为准。
- **毛利闸门：**试点结束统计实际工时、工具费、平台费、退款与支持。税前贡献毛利低于 60% 时，不扩量，先提价或缩范围。
- **停止条件：**30 天无付费、关键验收失败、平台/KYC 不可用、数据许可不清或必须靠违规抓取/群发才能获客，立即停止或换细分。

## 3. 最小验证方案

1. 不先做完整产品；只做「一个州、过去 24 个月、10 个地区的月报样板」。
2. 使用公开信息或客户主动提供的脱敏样本，不先索要管理员、支付或生产写权限。
3. **商业验证门槛：**给 5 个本地服务商一页免费样板；1 个以 ¥999 购买完整州报告
4. **技术验收门槛：**在约定样本/页面上复测“目标地区被采用数、数据对账差异、客户行动数”，每项都有输入、预期、实际、证据链接与人工签字；付款只验证购买意愿，不作为技术通过条件。
5. 只做 10–30 个强相关潜在买方的人工触达；不买名单、不抓 LinkedIn、不做自动群发。
6. 失败也要留数据：拒绝原因、价格、真实工时、误报/漏报和客户不用的功能，作为是否换细分的依据。

## 4. Day 1–30 落地日历

| 天 | 今天具体做什么 | 工具/点击路径 | 输入、输出与通过条件 |
|---:|---|---|---|
| Day 1 | 定一条窄线 | Google Sheets > Blank > scope tab | 写唯一买方“屋顶、HVAC、建材分销、加盟和本地广告代理”、唯一数据主题和试点“一个州、过去 24 个月、10 个地区的月报样板”；不先建泛平台 |
| Day 2 | 查许可 | 打开本文件全部官方来源 > Terms/API docs | 记录允许用途、署名/声明、限流、第三方权利和更新时间；许可不清时不收费、不处理真实数据、不交付，先取得书面分类 |
| Day 3 | 取 10–20 条官方样本 | Census BPS > Data > Monthly data；Sheets > File > Import；Looker > Create | 优先用官方 UI、Saved Search、CSV 或 Postman；保存筛选条件、日期、状态码/导出名和 official ID，不假设通用脚本支持该来源 |
| Day 4 | 定义 schema | Google Sheets > schema tab | 字段至少含 source_id、source_url、published_at、fetched_at、status、matched_reason、human_verified |
| Day 5 | 做人工样本 | 与 Census 发布表随机对账 10 个地区；记录 vintage 和修订日期 | 人工筛 20 条并逐条回链；把“真有用/无关/不确定”作为黄金标签 |
| Day 6 | 写匹配规则 | Sheets > rules tab | 输入：州/metro、服务半径、最小许可量、同比阈值、客户服务类型；把必须条件、加分项、排除词和人工核验写成可见规则 |
| Day 7 | 保存官方筛选/请求 | Census BPS > Data > Monthly data；Sheets > File > Import；Looker > Create | 保存官方 Saved Search、导出参数或 Postman collection；POST body、分页、认证和限流按该来源官方文档逐项记录，不用一个通用命令冒充全覆盖 |
| Day 8 | 做增量与去重 | Google Sheets > Data > Data cleanup > Remove duplicates；以 official ID+status 建复合键 | 只保留字段白名单；状态变化作为新事件，标题微调不重复推送；个人字段默认排除 |
| Day 9 | 保留证据 | Sheets > output tab | 每条结果包含原链接、日期、抓取时间、匹配理由、原文短摘和人工核验状态 |
| Day 10 | 出首份样报 | Google Docs > New from blank | 只放 5–15 条最相关结果；页首写用途、来源和局限；结果目标：按 metro/县/城市做许可量、同比、趋势和局限的一页纸，不提供个人地址线索 |
| Day 11 | 双人/二遍 QA | Sheets > QA tab | 隔 24 小时重新核对 10 条或请同伴复核；记录误报和遗漏原因 |
| Day 12 | 补人工增值 | Docs > sample report > Insert > Building blocks/Checklist | 加入资格/影响/材料缺口/行动问题、no-fit 原因、截止提醒和源链接；不只转发官方免费提醒 |
| Day 13 | 发布固定价服务 | Upwork > Find Work > Your services > Create Project | Upwork Price 字段输入 US$145（报告统一按 US$1=¥7 折算约 ¥1,015；执行日以平台/银行实际换汇为准）；粘贴标题、样报、来源许可和免责声明，先卖人工报告，不卖未完成订阅软件 |
| Day 14 | 列 20 个买方 | Upwork > Find Work > Search jobs > 输入 building permit market report；Sheets > targets | 记录 company/source_url/why_fit/jurisdiction/entity_type；只用公司级通用入口，不抓个人邮箱或社媒数据 |
| Day 15 | 首批 10 个触达 | Upwork > 打开匹配职位 > Apply now；或通过司法辖区闸门后 Gmail > Compose | 逐封附 3 条公开样报；真实身份、实体地址、隐私告知和退订齐全，不用追踪像素 |
| Day 16 | 访谈并进入合法合同路径 | Calendly > Event types > 20 min；普通职位 > Apply now 后等待客户 Offer；仅已付款旧客户或主动从 Project Catalog 发消息的客户 > Propose new contract | 访谈 3 人：上次错过什么、哪些字段最值钱、谁批准；Upwork 总价输入 US$145（报告统一按 US$1=¥7 折算约 ¥1,015；执行日以平台/银行实际换汇为准）。普通职位客户必须由客户发送 Offer，卖方不能把 Propose new contract 当通用按钮；技术验收与付款分开 |
| Day 17 | 核验首个付费阶段已注资 | Upwork > Offers/Your active contracts > Fixed-price > 当前 milestone/Project Catalog order > status | 客户侧完成购买或注资；卖方只在当前段显示 Active/Funded 后接受/开工，绝不代客户点击 Fund。商业验证：给 5 个本地服务商一页免费样板；1 个以 ¥999 购买完整州报告；未注资只保留样报，不继续做软件或批量采集 |
| Day 18 | 重做筛选 | Sheets > rules tab > Duplicate v1 to v2 | 只改最大误报来源；用原 20 条黄金集重新算精确率/召回率并保留 v1 |
| Day 19 | 启动付费实时周 | 与 Census 发布表随机对账 10 个地区；记录 vintage 和修订日期 | 按官方更新频率手工/官方导出运行；每次记录筛选、响应/导出、条数、失败、版本和抓取日 |
| Day 20 | 每日人审 | Sheets > human_verified filter | 发布前逐条打开原链接；状态不确定、权利不清或高风险一律不推送 |
| Day 21 | 交付首段并开下一段 | Google Docs > File > Download > PDF；Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Contract > Milestones | 交付源链接、抓取日、匹配理由、局限和行动清单，不镜像第三方附件；自定义合同提交当前里程碑后，等客户批准并注资下一里程碑才继续；一次注资 Project Catalog 订单只发中期预览，不提前提交整单 |
| Day 22 | 确认下一段已注资再看使用 | Upwork > Contract > Milestones；Sheets > customer feedback tab | 自定义合同只在下一里程碑为 Active/Funded 后继续；询问哪些结果被打开/采取行动，只看 目标地区被采用数、数据对账差异、客户行动数，不把外部成交全部归因给报告 |
| Day 23 | 修噪声 | Sheets > false-positive pivot | 按原因汇总误报；加入排除词或最小样本阈值，保留变更日志 |
| Day 24 | 有条件半自动化 | 仅兼容单一 JSON 响应时：终端 > python3 tools/feed_alert.py --help；否则继续官方 Saved Search/导出 | 只有客户已付款、许可明确、字段白名单和 source-specific 请求/分页已写清时才自动抓取；通用脚本不替代 schema/权限判断，人审不取消 |
| Day 25 | 验证字段最小化 | Sheets > schema > 保留 source_id/source_url/date/status/matched_reason；删除无关列 | 检查输出、缓存和日志无 API key、含 key URL、评论者/联系人等无关个人数据；写删除日期 |
| Day 26 | 一次跟进 | Upwork > Messages；或 Gmail > Sent > 对应线程 > Reply | 对未回复者只跟进一次并新增真实信号；收到退订立即写 suppression tab，之后停止 |
| Day 27 | 设续费 | Google Calendar > Create recurring reminder；Upwork milestone/合法账单 | 提前 7 天发真实使用摘要、下月范围和取消方式，不暗扣 |
| Day 28 | 提交最终交付 | Google Docs > final report；Upwork > Deliver work > Your active contracts > 目标合同 > Submit work | 附最终 PDF/SOP/受限证据链接，在 Upwork 写明当前已注资里程碑的交付并点 Submit work；确认进入 in review。只发 Drive/邮件不启动审核期 |
| Day 29 | 检查许可/成本与款项 | 来源条款 + Sheets unit economics；Upwork > Manage finances > Financial overview/Transactions | 重查 API/许可/限流/人工分钟；逐项记录 funded/submitted/approved/pending/available，任何漂移立即调整或停更，不把 pending 写成到账 |
| Day 30 | 查款并规模/停止 | Upwork > Manage finances > Financial overview；Manage finances > Transactions；Sheets > decision/cash-ledger | 记录 funded/submitted/approved/pending/available/withdrawn/bank-arrived；只有 bank-arrived 写到账。继续条件：至少 1 个真实付费信号、样报被实际使用、数据许可清楚、毛利可达；否则换垂直而非堆功能 |

## 5. 可复制注册、发布、销售与交付文案

### A. 平台服务页/落地页文案

**标题（直接粘贴）**

> Census 建筑许可热点报告｜先做固定范围试点，用真实数据验收，不承诺虚假增长

**副标题（直接粘贴）**

> 面向屋顶、HVAC、建材分销、加盟和本地广告代理。我会在不改变生产关键动作的前提下，完成「一个州、过去 24 个月、10 个地区的月报样板」，并用 目标地区被采用数、数据对账差异、客户行动数 做前后验收。涉及发送、付款、退款、删除、公开发布或高风险判断的步骤默认保留人工批准。

**服务说明（直接粘贴）**

> 你现在可能遇到的问题是：不知道哪些城市住宅新建许可正在增长，市场投放靠感觉。本项目不会先卖一套昂贵系统，而是先交付一个可回滚试点：按 metro/县/城市做许可量、同比、趋势和局限的一页纸，不提供个人地址线索。你会收到现状基线、配置/数据文件、测试记录、异常清单、操作 SOP、回滚办法和 14/30 天结果复盘。固定范围外的工作会在开始前单独报价。参考价：¥999–4,000/报告；¥499–1,499/月。

**CTA（直接粘贴）**

> 请发送 1 份脱敏样本、当前工具、每月处理量和最想改善的一个指标。我会先回复“能做/不该做/还缺什么”，不会要求你先开放管理员权限。

### B. 有条件适用的手工冷邮件（发送前先过司法辖区闸门）

**发送闸门（每个联系人都要记录）**

> 先记录发送者国家/地区、收件人国家/地区、收件主体是 corporate subscriber 还是个人/sole trader/partnership、合法基础、隐私告知 URL 和 suppression 状态。英国公司/LLP 等 corporate body 的 PECR 规则与个人不同，但姓名和个人化工作邮箱仍可能受 UK GDPR 约束；sole trader、非 LLP 等部分 partnership 通常按个人处理。类型不明时按个人处理。禁止追踪像素、个人数据拼接、购买名单和自动群发；无法确定规则时，改用 Upwork 平台响应、用户主动订阅、转介绍或公开内容获客。发送前复核收件地最新规则。

**主题：**关于贵司「Census 建筑许可热点报告」的一页试点建议

> 你好，{姓名/团队}：  
> 我查看了贵司公开的 {页面/流程/职位信息}，发现一个可以用固定范围验证的问题：不知道哪些城市住宅新建许可正在增长，市场投放靠感觉。我不是来承诺排名或收入的；我可以先用公开信息或你提供的脱敏样本，做「一个州、过去 24 个月、10 个地区的月报样板」，验收只看 目标地区被采用数、数据对账差异、客户行动数。  
> 如果方向不相关，回复“不需要”即可，我不会再联系。若相关，我可以先发一页样例和完整边界，确认后再开任何权限。  
> {你的真实姓名}｜{公司/个人主体}｜{实体邮寄地址}｜{官网/作品集}  
> 退订：回复“不需要”。

**第一次跟进（3 个工作日后）**

> 补充一个具体点：本试点的最小通过条件是「给 5 个本地服务商一页免费样板；1 个以 ¥999 购买完整州报告」。如果你已有团队在做，我也可以只交只读审计和测试清单；若不相关，回复“不需要”，我会停止联系。

**最后一次跟进（再过 5 个工作日）**

> 这是最后一次跟进。我可以免费发一张脱敏样例，不需要管理员权限。若本季度没有优先级，无需回复；我会关闭这条联系记录。

### C. 发现电话脚本

> 这次 20 分钟只确认四件事：一，当前流程从哪里开始、在哪里结束；二，过去 30 天处理量和基线；三，哪些动作绝不能自动执行；四，什么数字达到才值得继续。若拿不到基线，我们就把试点目标改成“正确性和节省时间”，不编造收入归因。

### D. 固定范围提案

> **项目：**Census 建筑许可热点报告 30 天验证  
> **客户：**{客户名}  
> **范围：**一个州、过去 24 个月、10 个地区的月报样板  
> **客户提供：**州/metro、服务半径、最小许可量、同比阈值、客户服务类型  
> **交付：**基线表、实施/配置、测试证据、异常队列、SOP、回滚说明、结果复盘  
> **技术验收：**在约定样本/页面上复测“目标地区被采用数、数据对账差异、客户行动数”，每项都有输入、预期、实际、证据链接与人工签字；付款只验证购买意愿，不作为技术通过条件。  
> **商业验证：**给 5 个本地服务商一页免费样板；1 个以 ¥999 购买完整州报告  
> **不包含：**未授权数据、法律/医疗/金融意见、批量群发、平台条款规避、资金代收、自动退款/删除/公开发布  
> **付款路径：**Upwork 所有金额以 USD 列示：Project Catalog 输入 US$145（报告统一按 US$1=¥7 折算约 ¥1,015；执行日以平台/银行实际换汇为准） 并由客户一次注资；若走自定义 fixed-price 合同，则两个里程碑为 US$73/US$72，合计 US$145，里程碑1交付基线、范围、规则和验收计划，截止 Day 17；里程碑2交付最终结果、QA、SOP和删除/回滚记录，截止 Day 28。每次只在当前里程碑 Active/Funded 后开工，提交并获批当前段后，等下一段 Active/Funded 才继续。独立获客且从未在 Upwork 建立关系的客户，可另用合规账单按 ¥999 报价；不得把 Upwork 客户移到站外付款。客户批准后仍有 5 天安全期。 参考扩展价：¥999–4,000/报告；¥499–1,499/月。技术验收与注资、批准、Pending 和银行到账分开记录。  
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

### 确定性实施与证据模板

```text
case_id | source/input | expected | actual | evidence_url | owner | approval | rollback | status
```

先按 `Census BPS > Data > Monthly data；Sheets > File > Import；Looker > Create` 建最小副本/测试环境，再按 `与 Census 发布表随机对账 10 个地区；记录 vintage 和修订日期` 跑 5 条正常样本、1 条空值、1 条重复、1 条权限拒绝和 1 条回滚。技术通过条件：在约定样本/页面上复测“目标地区被采用数、数据对账差异、客户行动数”，每项都有输入、预期、实际、证据链接与人工签字；付款只验证购买意愿，不作为技术通过条件。 任何涉及发送、付款、退款、删除、公开发布、法律/医疗/金融判断的动作保持人工批准。




本方法的 MVP 以官方 UI、Saved Search、CSV/导出、Postman 与人工核验为准。只有单一 JSON 响应与许可、schema、分页都已确认时，才可选用 [字段白名单 Feed 增量脚本](../tools/feed_alert.py)；它不提供来源专用分页、权限判断或多源实体匹配。

## 7. 主要风险与预设应对

- **风险：许可数据被当作实时需求**　应对：注明住宅新建、月度滞后、修订和代理指标属性
- **风险：错误同比受季节影响**　应对：同时给同比和滚动 12 月，不只展示单月环比
- **渠道风险：**平台 KYC、收款、费率和功能会变。Day 1 只验证真实账户、税务与收款方式状态；首个真实余额后再验证到账，失败则换合法渠道，不伪造地区。
- **归因风险：**外部销量、转化或中标受多因素影响。只报告试点可测指标、样本量和局限。
- **外联风险：**只做人工、相关、低量外联，使用真实身份/地址/退订；不得抓取、自动私信或骚扰。

## 8. 30 天结束时的 Go / Iterate / Stop

- **Go：**达到本方法的商业验证门槛：“给 5 个本地服务商一页免费样板；1 个以 ¥999 购买完整州报告”；关键验收达标；贡献毛利可接受；交付不依赖违规或单点人工英雄主义。
- **Iterate：**有人愿付但范围或价格错；只改最大障碍，再跑一个 7–14 天试点。
- **Stop：**Day 30 未达到上述商业验证门槛、存在重大合规/许可问题、收款不可用或价值只能靠不可验证承诺成立。

> **方法41已完成，开始方法42调研。**
