# 方法 28｜SPF/DKIM/DMARC 邮件送达基础配置

> **一页结论：**面向使用 Google Workspace、Microsoft 365 或邮件营销工具但缺认证的小企业，用「一个域名、最多三个合法发件源的只读审计和 p=none 上线」先收费验证。启动现金成本 ¥0–200，目标是 认证通过率、DMARC 对齐、退信/垃圾率、未知发件源数。这里的报价和收益是**本报告的测试模型，不是行业均价或收益保证**。

## 0. 执行卡

| 项目 | 内容 |
|---|---|
| 分类 | 网站技术服务 |
| 买方 | 使用 Google Workspace、Microsoft 365 或邮件营销工具但缺认证的小企业 |
| 当前痛点 | 邮件进垃圾箱、域名被冒用、批量发件不满足 Gmail 要求 |
| 可交付结果 | 只读审计 DNS，建立 SPF、DKIM、DMARC 监控模式、对齐和退订检查，再分阶段收紧 |
| 最小试点 | 一个域名、最多三个合法发件源的只读审计和 p=none 上线 |
| 工具栈 | DNS 提供商 + Google Postmaster/Workspace + DMARC 报告工具 |
| 启动成本 | ¥0–200（不含自己的人工） |
| 时间 | 7–14 天付费与上线；p=none 后至少观察 7 天 |
| 技能 | DNS、邮件认证、日志、谨慎变更 |
| 参考测试报价 | 审计 ¥1,500–3,000；实施 ¥2,500–8,000；监控 ¥500–1,500/月 |
| 最小验证 | 1 个客户为单域名固定范围实施注资/支付 ¥2,500；付款不代替 7 天技术复核 |
| 综合分 | 4.85/5；需求证据 5 / 验证速度 5 / 低成本 5 / 复购性 5 / 自动化杠杆 4 / 获客可达 5 / 风险可控 5 |

## 1. 为什么现在能赚钱

赚钱逻辑不是“AI/数据/模板很火”，而是把 **邮件进垃圾箱、域名被冒用、批量发件不满足 Gmail 要求** 变成一个买方能验收的固定范围结果：**只读审计 DNS，建立 SPF、DKIM、DMARC 监控模式、对齐和退订检查，再分阶段收紧**。先用人工和低成本工具交付，客户确认价值后才把重复步骤自动化；这样现金投入低，也避免先做没人买的软件。

### 当前市场证据

- **M23｜[Gmail sender guidelines](https://support.google.com/mail/answer/81126?hl=en)：**所有发件人应使用 SPF 或 DKIM；大量发件人还需 SPF、DKIM、DMARC、对齐和一键退订，并把垃圾邮件率保持在 0.3% 以下。 **使用边界：**技术配置不豁免 CAN-SPAM、PECR、GDPR 或收件人所在地法律。
- **C01｜[FTC CAN-SPAM compliance guide](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business)：**商业邮件包括 B2B 邮件，应使用真实头部和主题、标明广告、提供实体地址和退订并在 10 个工作日内执行。 **使用边界：**还需遵守收件人所在地的 PECR、GDPR、PIPL 等规则。
- **P22｜[Upwork Direct to Local Bank](https://support.upwork.com/hc/en-us/articles/211063888-How-to-withdraw-earnings-with-Direct-to-Local-Bank)：**Upwork Direct to Local Bank 支持中国 CNY，每次提现费 0.99 美元；新收款方式为安全需 3 天激活，提现后通常 4 天内到银行。 **使用边界：**姓名必须与 Upwork 验证身份一致，银行限制/费用可另行适用。Day 1 只验证 Account settings > Withdrawals > Add a method > Set up 的真实可用状态，不伪造地区或到账。
- **P23｜[Upwork fixed-price and Project Catalog payments](https://support.upwork.com/hc/en-us/articles/211063718-How-payments-for-milestones-and-fixed-price-contracts-work)：**Upwork fixed-price 里程碑/项目需客户先注资；提交后客户最长可审核 14 天，批准或自动释放后再有 5 天安全期才可提现。 **使用边界：**已注资只证明付费意愿，不等于技术验收、可提现余额或银行到账。核心工作不用 bonus 代替；每个里程碑的交付和金额必须先写清。
- **P27｜[Upwork submit work and milestones](https://support.upwork.com/hc/en-us/articles/211068368-How-to-submit-work-and-milestones-to-your-client)：**固定价工作完成后，自由职业者必须从 Deliver work > Your active contracts 打开合同并点击 Submit work，写明交付并附文件，才会启动客户审核流程。 **使用边界：**只交 Drive/邮件不等于向 Upwork 提交；多里程碑合同每段都要提交当前已注资里程碑、等客户批准并注资下一段后再继续。
- **P28｜[Upwork track earnings status](https://support.upwork.com/hc/en-us/articles/211068418-How-to-track-the-status-of-your-earnings-on-Upwork)：**当前收益状态入口为 Manage finances > Financial overview，也可在 Manage finances > Transactions 查看明细；状态区分 work in progress、in review、pending 和 available。 **使用边界：**Funded、submitted、approved、pending、available、withdrawn 和 bank-arrived 必须分开记录；只有 bank-arrived 才是银行到账。
- **P29｜[Upwork local currency and USD listing](https://support.upwork.com/hc/en-us/articles/211068028-How-to-pay-in-your-local-currency)：**Upwork 官方说明所有成本以 USD 列示；部分客户付款时可看到本币换算，但显示汇率只是估计，最终扣款以交易记录为准。 **使用边界：**自由职业者必须在 Project Catalog Price、offer 和 milestone 输入 USD；人民币只作报告换算假设，实际 CNY 到账由支付伙伴汇率和费用决定。
- **P31｜[Upwork eligibility to propose a new contract](https://support.upwork.com/hc/en-us/articles/115006647007-How-to-propose-a-new-contract)：**自由职业者只能向已至少付过一次款的当前/既往客户，或主动从有效 Project Catalog 项目发消息的潜在客户提出新合同。 **使用边界：**普通职位申请不能由卖方直接 Propose new contract；应 Apply 后等待客户发送 Offer，并先核验 fixed-price 当前里程碑已 Active/Funded。
- **P32｜[Upwork fixed-price milestone requirements](https://support.upwork.com/hc/en-us/articles/211068218-How-to-use-milestones-in-fixed-price-jobs)：**固定价里程碑开始前应写清金额、交付物与截止日；每次只能注资一个里程碑，当前段释放后才能激活并注资下一段。 **使用边界：**卖方不能替客户点击 Fund；每段只在 Active/Funded 后开工，完成后从 Deliver work 提交，等批准并看到下一段 Active/Funded 才继续。
- **P35｜[Upwork direct offers from clients](https://support.upwork.com/hc/en-us/articles/30113729524499-How-direct-offers-from-clients-work-on-Upwork)：**自由职业者收到客户 Offer 后，可从 Messages 打开对应会话，依次选择 View offer，再选择 Accept offer、Request changes 或 Decline offer；接受前可以协商范围、价格和期限。 **使用边界：**普通职位仍需先 Apply 并等待客户发 Offer；接受后还要核验 fixed-price 当前里程碑/订单为 Active/Funded，卖方不能替客户点击 Fund。

### 竞品与切入

dmarcian/MXToolbox 提供工具；你的价值是发件源盘点、受控 DNS 变更和解释报告。因此不要卖“我会某个工具”，要卖一条窄结果、真实回放、人工审批、可回滚交付和后续维护。

**证据依赖提醒：**本方法使用来源 M23、C01、P22、P23、P27、P28、P29、P31、P32、P35。它们支持市场/渠道/工具事实，但不直接证明你的细分客户会购买；付费意愿必须由本方案的预售试点验证。

## 2. 产品、价格与单位经济

### 固定范围产品

- **名称：**SPF/DKIM/DMARC 邮件送达基础配置 30 天验证包
- **交付：**一个域名、最多三个合法发件源的只读审计和 p=none 上线；另附基线、测试记录、异常清单、SOP、回滚/删除说明。
- **客户输入：**域名、全部发件平台清单、DNS 只读/受控权限、过去退信、联系人
- **验收指标：**认证通过率、DMARC 对齐、退信/垃圾率、未知发件源数
- **参考报价：**审计 ¥1,500–3,000；实施 ¥2,500–8,000；监控 ¥500–1,500/月

### 月收益情景（税前可计收入；数字平台按文中分成/版税模型）

| 情景 | 本报告假设 | 预估月营收 |
|---|---|---:|
| 保守 | 保守 1 个域名；归一化校验：1 个该情景订单组合×¥2,500=¥2,500；模型合计=¥2,500 | ¥2,500 |
| 中性 | 中性 4 个实施加 3 个监控；归一化校验：1 个该情景订单组合×¥12,000=¥12,000；模型合计=¥12,000 | ¥12,000 |
| 乐观 | 乐观 10 个实施加 8 个监控；归一化校验：1 个该情景订单组合×¥34,000=¥34,000；模型合计=¥34,000 | ¥34,000 |

- **回本周期：**现金口径：按保守月营收匀速折算约 3 天；含工时口径：按首月 24 小时、目标时薪 ¥200/小时，需覆盖约 ¥5,000，按保守情景折算约 60 天。这是容量模型；真实回本以实际收款日、平台结算期、退款、税和工时为准。
- **毛利闸门：**试点结束统计实际工时、工具费、平台费、退款与支持。税前贡献毛利低于 60% 时，不扩量，先提价或缩范围。
- **停止条件：**30 天无付费、关键验收失败、平台/KYC 不可用、数据许可不清或必须靠违规抓取/群发才能获客，立即停止或换细分。

## 3. 最小验证方案

1. 不先做完整产品；只做「一个域名、最多三个合法发件源的只读审计和 p=none 上线」。
2. 使用公开信息或客户主动提供的脱敏样本，不先索要管理员、支付或生产写权限。
3. **商业验证门槛：**1 个客户为单域名固定范围实施注资/支付 ¥2,500；付款不代替 7 天技术复核
4. **技术验收门槛：**域名只有一条 SPF TXT 且无 PermError；每个授权来源至少 1 封测试邮件通过 DKIM 或 aligned SPF 并显示 DMARC pass；DMARC 为 p=none；7 天报告无未解释的合法失败源
5. 只做 10–30 个强相关潜在买方的人工触达；不买名单、不抓 LinkedIn、不做自动群发。
6. 失败也要留数据：拒绝原因、价格、真实工时、误报/漏报和客户不用的功能，作为是否换细分的依据。

## 4. Day 1–30 落地日历

| 天 | 今天具体做什么 | 工具/点击路径 | 输入、输出与通过条件 |
|---:|---|---|---|
| Day 1 | 定边界 | Google Sheets > Blank spreadsheet；建 scope、baseline、risk 三个 tab | 写入买方“使用 Google Workspace、Microsoft 365 或邮件营销工具但缺认证的小企业”、固定范围“一个域名、最多三个合法发件源的只读审计和 p=none 上线”；产出一页范围，禁止扩到高风险动作 |
| Day 2 | 核证据 | 打开本文件“市场证据”中的全部官方链接；浏览器 > Bookmark folder | 逐条记录发布日期、事实与局限；如果关键链接失效，暂停宣传该事实 |
| Day 3 | 建 30 个 ICP | Upwork > Find Work > Search jobs > 输入 SPF DKIM DMARC setup；公司官网只看 Contact/Team 通用入口 | Sheets targets 列 company/source_url/why_fit/jurisdiction/entity_type/status；只录与“邮件进垃圾箱、域名被冒用、批量发件不满足 Gmail 要求”直接相关的 30 个主体，不抓个人数据 |
| Day 4 | 量基线 | Google Sheets > baseline tab | 输入最近 30 天 认证通过率、DMARC 对齐、退信/垃圾率、未知发件源数；没有数字就记录样本量、当前耗时和错误例子 |
| Day 5 | 开最小工具 | Google Workspace：Admin console > Apps > Google Workspace > Gmail > Authenticate email；Microsoft 365：Defender portal > Email & collaboration > Policies & rules > Threat policies > Email authentication settings > DKIM；DNS 主机 > Records | 只开试点所需功能；栈：DNS 提供商 + Google Postmaster/Workspace + DMARC 报告工具；保存账号 owner、权限、关闭/回滚路径截图 |
| Day 6 | 收脱敏样本 | Google Drive > New > Folder > Share > Restricted | 向测试客户索取：域名、全部发件平台清单、DNS 只读/受控权限、过去退信、联系人；密码/API key 不放文档 |
| Day 7 | 投递双里程碑固定价方案 | Upwork > Find Work > Search jobs > SPF DKIM DMARC > 打开匹配职位 > Apply now；Profile > Portfolio > Add project | proposal 的 Fixed-price 总价填 US$360，并在附信写 US$180 审计/变更计划、US$180 p=none 上线后 7 天验收；这里只申请并附脱敏案例，不创建 Project Catalog、不替客户发 Offer 或 Fund |
| Day 8 | 首批手工触达 | Upwork > Find Work > Search jobs > 打开 10 个强相关职位 > Apply now；或通过司法辖区闸门后 Gmail > Compose | 每条引用 1 个真实公开观察，发送本文件文案；CTA 只要求脱敏样本，范围为“一个域名、最多三个合法发件源的只读审计和 p=none 上线” |
| Day 9 | 发现访谈 | Calendly > Event types > New event type > 20 min；Google Meet > New meeting | 访谈 3 人，记录当前流程、认证通过率、DMARC 对齐、退信/垃圾率、未知发件源数 基线、禁止自动动作、预算和采购人 |
| Day 10 | 接受客户双里程碑 Offer | Upwork > Messages > 对应会话 > View offer > 核对 milestones > Accept offer > Deliver work > Your active contracts | 确认总价 US$360、两段各 US$180、范围和截止日正确，且里程碑1为 Active/Funded 后才开工；不创建 Catalog、不替客户点击 Fund |
| Day 11 | 画实施流程 | diagrams.net > Create New Diagram；或 Sheets > flow tab | 画 source→deterministic checks→human approval→destination→error queue→rollback；客户确认后再构建 |
| Day 12 | 完成初始只读认证审计 | Google Admin Toolbox > Check MX/Dig；每个合法发件源发 1 封到外部 Gmail > More > Show original；Sheets > baseline | 核对当前 SPF 条数/PermError、每个来源 DKIM 或 aligned SPF、DMARC 记录和 rua 接收状态；只记录基线，不声称已完成 7 天观察 |
| Day 13 | 建立确定性实施表 | Google Workspace：Admin console > Apps > Google Workspace > Gmail > Authenticate email；Microsoft 365：Defender portal > Email & collaboration > Policies & rules > Threat policies > Email authentication settings > DKIM；DNS 主机 > Records | 把 域名、全部发件平台清单、DNS 只读/受控权限、过去退信、联系人 拆成字段、确定性规则、owner、证据和回滚列；只实现合同明确要求的步骤 |
| Day 14 | 冻结变更与回滚单 | DNS 主机 > Records 只读；Docs > change plan；客户书面批准 | 逐条写旧值、新值、TTL、owner、维护窗口和回滚值；测试冲突/权限不足/回滚，未批准不改 DNS |
| Day 15 | 加审计日志 | Google Sheets > logs tab；目标工具 > 活动/错误/运行历史 | 记录 event_id、时间、输入 hash、规则/配置版本、动作、审批人、错误和回滚；不记录无关 PII 或密钥 |
| Day 16 | 做首段初始认证检查 | Google Admin Toolbox > Check MX/Dig；Gmail > Show original；Sheets > milestone-1 QA | 只验收发件源清单、DNS 基线、备份/回滚和测试邮件当前状态；明确 7 天 rua 报告尚未完成，不能把首段或付款写成最终技术通过 |
| Day 17 | 提交里程碑1并等待第二段注资 | Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Contract > Milestones | 提交发件源清单、只读审计、变更/回滚计划；等客户批准且里程碑2显示 Active/Funded 后才上线 p=none，卖方不点击 Fund |
| Day 18 | 上线 p=none 并记录 Day 1/7 | DNS 主机 > Records > 按批准变更；DMARC 报告工具 > rua aggregate report；Google Admin Toolbox > Check MX；Sheets > seven-day log | 仅在里程碑2 Active/Funded 和客户维护窗口内变更；确认 DMARC=p=none、SPF 无 PermError、合法源样本通过，保存前后值和回滚点 |
| Day 19 | 复核 rua Day 2/7 | DMARC 报告工具 > rua aggregate report；Google Admin Toolbox > Check MX；Sheets > seven-day log | 按合法发件源清单逐项记录 pass/fail/alignment/volume/unknown_source；任何未解释合法失败源当天升级 owner，不提高 DMARC policy |
| Day 20 | 复核 rua Day 3/7 | DMARC 报告工具 > rua aggregate report；Google Admin Toolbox > Check MX；Sheets > seven-day log | 按合法发件源清单逐项记录 pass/fail/alignment/volume/unknown_source；任何未解释合法失败源当天升级 owner，不提高 DMARC policy |
| Day 21 | 复核 rua Day 4/7 | DMARC 报告工具 > rua aggregate report；Google Admin Toolbox > Check MX；Sheets > seven-day log | 按合法发件源清单逐项记录 pass/fail/alignment/volume/unknown_source；任何未解释合法失败源当天升级 owner，不提高 DMARC policy |
| Day 22 | 复核 rua Day 5/7 | DMARC 报告工具 > rua aggregate report；Google Admin Toolbox > Check MX；Sheets > seven-day log | 按合法发件源清单逐项记录 pass/fail/alignment/volume/unknown_source；任何未解释合法失败源当天升级 owner，不提高 DMARC policy |
| Day 23 | 复核 rua Day 6/7 | DMARC 报告工具 > rua aggregate report；Google Admin Toolbox > Check MX；Sheets > seven-day log | 按合法发件源清单逐项记录 pass/fail/alignment/volume/unknown_source；任何未解释合法失败源当天升级 owner，不提高 DMARC policy |
| Day 24 | 复核 rua Day 7/7 | DMARC 报告工具 > rua aggregate report；Google Admin Toolbox > Check MX；Sheets > seven-day log | 按合法发件源清单逐项记录 pass/fail/alignment/volume/unknown_source；任何未解释合法失败源当天升级 owner，不提高 DMARC policy |
| Day 25 | 完成 7 天技术验收 | Sheets > seven-day log > Filter；Google Admin Toolbox/Gmail Show original 复测 | 执行最终技术验收：域名只有一条 SPF TXT 且无 PermError；每个授权来源至少 1 封测试邮件通过 DKIM 或 aligned SPF 并显示 DMARC pass；DMARC 为 p=none；7 天报告无未解释的合法失败源；逐日、逐源保留分母和证据，未达标就写未通过 |
| Day 26 | 通过则封版，失败则延长 | Docs > final QA/SOP；Upwork > Messages | 若 7 天验收通过，只整理证据不再改 DNS；若失败，书面说明原因、回滚/修复和新的完整 7 天窗口，本日不提交里程碑2、不伪造连续天数 |
| Day 27 | 满足 7 天条件才提交里程碑2 | Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Sheets > seven-day log | 只有里程碑2 Active/Funded 且完整连续 7 天技术验收通过时，才附报告/SOP/回滚并点 Submit work；否则保持未提交并协商延期或回滚 |
| Day 28 | 提续费 | Gmail > Compose/Reply；粘贴验收与复购话术 | 只把已证明稳定的步骤做月费；列每月上限、响应时间和不包含项 |
| Day 29 | 做案例 | Notion/官网 > New page/draft | 得到书面许可后才发布匿名案例；写基线、样本、结果、局限，不写客户机密 |
| Day 30 | 查款并规模/停止 | Upwork > Manage finances > Financial overview；Manage finances > Transactions；Sheets > decision/cash-ledger | 逐项记录 funded/submitted/approved/pending/available/withdrawn/bank-arrived；只有 bank-arrived 写到账。通过条件：至少 1 个真实付费信号、验收达标、毛利可接受、无重大合规缺口；否则缩窄、换细分或停止 |

## 5. 可复制注册、发布、销售与交付文案

### A. 平台服务页/落地页文案

**标题（直接粘贴）**

> SPF/DKIM/DMARC 邮件送达基础配置｜先做固定范围试点，用真实数据验收，不承诺虚假增长

**副标题（直接粘贴）**

> 面向使用 Google Workspace、Microsoft 365 或邮件营销工具但缺认证的小企业。我会在不改变生产关键动作的前提下，完成「一个域名、最多三个合法发件源的只读审计和 p=none 上线」，并用 认证通过率、DMARC 对齐、退信/垃圾率、未知发件源数 做前后验收。涉及发送、付款、退款、删除、公开发布或高风险判断的步骤默认保留人工批准。

**服务说明（直接粘贴）**

> 你现在可能遇到的问题是：邮件进垃圾箱、域名被冒用、批量发件不满足 Gmail 要求。本项目不会先卖一套昂贵系统，而是先交付一个可回滚试点：只读审计 DNS，建立 SPF、DKIM、DMARC 监控模式、对齐和退订检查，再分阶段收紧。你会收到现状基线、配置/数据文件、测试记录、异常清单、操作 SOP、回滚办法和 14/30 天结果复盘。固定范围外的工作会在开始前单独报价。参考价：审计 ¥1,500–3,000；实施 ¥2,500–8,000；监控 ¥500–1,500/月。

**CTA（直接粘贴）**

> 请发送 1 份脱敏样本、当前工具、每月处理量和最想改善的一个指标。我会先回复“能做/不该做/还缺什么”，不会要求你先开放管理员权限。

### B. 有条件适用的手工冷邮件（发送前先过司法辖区闸门）

**发送闸门（每个联系人都要记录）**

> 先记录发送者国家/地区、收件人国家/地区、收件主体是 corporate subscriber 还是个人/sole trader/partnership、合法基础、隐私告知 URL 和 suppression 状态。英国公司/LLP 等 corporate body 的 PECR 规则与个人不同，但姓名和个人化工作邮箱仍可能受 UK GDPR 约束；sole trader、非 LLP 等部分 partnership 通常按个人处理。类型不明时按个人处理。禁止追踪像素、个人数据拼接、购买名单和自动群发；无法确定规则时，改用 Upwork 平台响应、用户主动订阅、转介绍或公开内容获客。发送前复核收件地最新规则。

**主题：**关于贵司「SPF/DKIM/DMARC 邮件送达基础配置」的一页试点建议

> 你好，{姓名/团队}：  
> 我查看了贵司公开的 {页面/流程/职位信息}，发现一个可以用固定范围验证的问题：邮件进垃圾箱、域名被冒用、批量发件不满足 Gmail 要求。我不是来承诺排名或收入的；我可以先用公开信息或你提供的脱敏样本，做「一个域名、最多三个合法发件源的只读审计和 p=none 上线」，验收只看 认证通过率、DMARC 对齐、退信/垃圾率、未知发件源数。  
> 如果方向不相关，回复“不需要”即可，我不会再联系。若相关，我可以先发一页样例和完整边界，确认后再开任何权限。  
> {你的真实姓名}｜{公司/个人主体}｜{实体邮寄地址}｜{官网/作品集}  
> 退订：回复“不需要”。

**第一次跟进（3 个工作日后）**

> 补充一个具体点：本试点的最小通过条件是「1 个客户为单域名固定范围实施注资/支付 ¥2,500；付款不代替 7 天技术复核」。如果你已有团队在做，我也可以只交只读审计和测试清单；若不相关，回复“不需要”，我会停止联系。

**最后一次跟进（再过 5 个工作日）**

> 这是最后一次跟进。我可以免费发一张脱敏样例，不需要管理员权限。若本季度没有优先级，无需回复；我会关闭这条联系记录。

### C. 发现电话脚本

> 这次 20 分钟只确认四件事：一，当前流程从哪里开始、在哪里结束；二，过去 30 天处理量和基线；三，哪些动作绝不能自动执行；四，什么数字达到才值得继续。若拿不到基线，我们就把试点目标改成“正确性和节省时间”，不编造收入归因。

### D. 固定范围提案

> **项目：**SPF/DKIM/DMARC 邮件送达基础配置 30 天验证  
> **客户：**{客户名}  
> **范围：**一个域名、最多三个合法发件源的只读审计和 p=none 上线  
> **客户提供：**域名、全部发件平台清单、DNS 只读/受控权限、过去退信、联系人  
> **交付：**基线表、实施/配置、测试证据、异常队列、SOP、回滚说明、结果复盘  
> **技术验收：**域名只有一条 SPF TXT 且无 PermError；每个授权来源至少 1 封测试邮件通过 DKIM 或 aligned SPF 并显示 DMARC pass；DMARC 为 p=none；7 天报告无未解释的合法失败源  
> **商业验证：**1 个客户为单域名固定范围实施注资/支付 ¥2,500；付款不代替 7 天技术复核  
> **不包含：**未授权数据、法律/医疗/金融意见、批量群发、平台条款规避、资金代收、自动退款/删除/公开发布  
> **付款路径：**Upwork 固定总价 US$360（报告按 US$1=¥7 约 ¥2,520）：里程碑1 US$180（发件源清单、DNS 只读审计、备份/回滚）；里程碑2 US$180（p=none 上线后连续 7 天报告达到技术验收）。样本不足或有未解释合法失败源时，第 2 段保持未到期。 参考扩展价：审计 ¥1,500–3,000；实施 ¥2,500–8,000；监控 ¥500–1,500/月。技术验收与注资、批准、Pending 和银行到账分开记录。  
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

### DNS 变更包（以下 SPF 只能按真实发件源选一条）

```dns
; Google Workspace only
<DOMAIN>. TXT "v=spf1 include:_spf.google.com ~all"
; Microsoft 365 only
<DOMAIN>. TXT "v=spf1 include:spf.protection.outlook.com -all"
; Google Workspace + Microsoft 365
<DOMAIN>. TXT "v=spf1 include:_spf.google.com include:spf.protection.outlook.com ~all"
; DMARC monitor only
_dmarc.<DOMAIN>. TXT "v=DMARC1; p=none; rua=mailto:dmarc-reports@<DOMAIN>"
```

Google DKIM：`Admin console > Apps > Google Workspace > Gmail > Authenticate email > Generate New Record (2048-bit)`，把界面值原样放 DNS，生效后点 `Start authentication`。Microsoft 365：`Defender portal > Email authentication settings > DKIM`，复制平台给出的 selector1/selector2 CNAME，禁止手工推导目标值。

```bash
dig +short TXT <DOMAIN>
dig +short TXT _dmarc.<DOMAIN>
dig +short TXT google._domainkey.<DOMAIN>
dig +short CNAME selector1._domainkey.<DOMAIN>
dig +short CNAME selector2._domainkey.<DOMAIN>
```

变更单：`记录名 | 类型 | 旧值 | 新值 | TTL | 供应商依据 URL | owner | 生效时间 | 回滚值`。本试点只到 `p=none`，至少观察 7 天且解释所有合法源后才另签收紧项目。




本方法不依赖通用抓取脚本；优先使用客户自有平台的测试/副本/导出能力。

## 7. 主要风险与预设应对

- **风险：错误 SPF/DMARC 阻断合法邮件**　应对：先审计和 p=none，分阶段收紧，每次保留回滚记录
- **风险：客户把技术配置当群发许可**　应对：合同明确不提供名单抓取或群发，营销须满足法律与退订
- **渠道风险：**平台 KYC、收款、费率和功能会变。Day 1 只验证真实账户、税务与收款方式状态；首个真实余额后再验证到账，失败则换合法渠道，不伪造地区。
- **归因风险：**外部销量、转化或中标受多因素影响。只报告试点可测指标、样本量和局限。
- **外联风险：**只做人工、相关、低量外联，使用真实身份/地址/退订；不得抓取、自动私信或骚扰。

## 8. 30 天结束时的 Go / Iterate / Stop

- **Go：**达到本方法的商业验证门槛：“1 个客户为单域名固定范围实施注资/支付 ¥2,500；付款不代替 7 天技术复核”；关键验收达标；贡献毛利可接受；交付不依赖违规或单点人工英雄主义。
- **Iterate：**有人愿付但范围或价格错；只改最大障碍，再跑一个 7–14 天试点。
- **Stop：**Day 30 未达到上述商业验证门槛、存在重大合规/许可问题、收款不可用或价值只能靠不可验证承诺成立。

> **方法28已完成，开始方法29调研。**
