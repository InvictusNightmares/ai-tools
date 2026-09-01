#!/usr/bin/env python3
"""Build the 50-method market-opportunity handbook from reviewed source data.

This file intentionally uses only the Python standard library. It creates the
Markdown package and CSV comparison table; comparison.xlsx is built separately
so the spreadsheet artifact can be rendered and verified.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"
METHOD_DIR = ROOT / "methods"
ASSET_DIR = ROOT / "assets"
SOURCES = json.loads((RESEARCH / "sources.json").read_text(encoding="utf-8"))
METHODS = json.loads((RESEARCH / "methods.json").read_text(encoding="utf-8"))

WEIGHTS = (0.20, 0.15, 0.10, 0.15, 0.15, 0.15, 0.10)
SCORE_NAMES = ("需求证据", "验证速度", "低成本", "复购性", "自动化杠杆", "获客可达", "风险可控")
TOP_THREE = (20, 1, 22)
SEARCH_TERMS = {
    1: "HubSpot lead routing automation", 2: "meeting notes CRM automation", 3: "shared inbox triage automation",
    4: "customer support SLA ticket routing", 5: "knowledge base chatbot RAG", 6: "internal knowledge base assistant",
    7: "proposal quote automation", 8: "client onboarding automation", 9: "appointment reminder no show",
    10: "Stripe invoice dunning automation", 11: "KPI dashboard weekly report", 12: "PDF order data extraction automation",
    13: "customer feedback analysis report", 14: "CRM cleanup deduplication", 15: "review request automation",
    16: "Google Business Profile management", 17: "podcast content repurposing", 18: "YouTube dubbing localization QA",
    19: "Shopify product catalog cleanup", 20: "Google Merchant Center disapproved products", 21: "Shopify structured data JSON-LD",
    22: "GA4 ecommerce tracking GTM", 23: "Core Web Vitals Shopify", 24: "WordPress maintenance backup",
    25: "Shopify email automation", 26: "Shopify translation localization", 27: "Shopify customer support macros",
    28: "SPF DKIM DMARC setup", 29: "Google Workspace security audit", 30: "WCAG accessibility audit",
    31: "SAM.gov bid opportunity research", 32: "USAspending contract research", 33: "grant eligibility research",
    34: "EU tender research Chinese", 35: "regulatory monitoring research", 36: "SEC filing sales intelligence",
    37: "Companies House lead research", 38: "FDA food recall monitoring", 39: "EPA ECHO research",
    40: "CFPB complaint data analysis", 41: "building permit market report", 42: "Census US import HS market research",
    43: "competitor price monitoring", 50: "Shopify digital downloads audit",
}


def esc(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def money(value: int) -> str:
    return f"¥{value:,}"


def score(method: dict) -> float:
    return round(sum(v * w for v, w in zip(method["score"], WEIGHTS)), 2)


def execution_ranked() -> list[dict]:
    """Put the three decision-selected starters first, then use weighted score."""
    top_order = {method_id: index for index, method_id in enumerate(TOP_THREE)}
    return sorted(
        METHODS,
        key=lambda method: (
            0 if method["id"] in top_order else 1,
            top_order.get(method["id"], 0),
            -score(method),
            method["id"],
        ),
    )


def max_cost(text: str) -> int:
    numbers = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", text)]
    return max(numbers) if numbers else 0


def first_cny_price(method: dict) -> int:
    validation_values = [int(value.replace(",", "")) for value in re.findall(r"¥\s*([\d,]+)", method.get("validation", ""))]
    if validation_values:
        return max(validation_values)
    price_values = [int(value.replace(",", "")) for value in re.findall(r"¥\s*([\d,]+)", method["price"])]
    return max(price_values) if price_values else method["monthly"][0]


def upwork_usd_amount(method: dict) -> int:
    """Round the CNY test model up to a clean $5 Upwork listing amount."""
    return max(5, math.ceil(first_cny_price(method) / 35) * 5)


def upwork_price_text(method: dict) -> str:
    usd = upwork_usd_amount(method)
    return f"US${usd}（报告统一按 US$1=¥7 折算约 {money(usd * 7)}；执行日以平台/银行实际换汇为准）"


def payment_terms(method: dict) -> str:
    fixed_price = money(first_cny_price(method))
    usd = upwork_usd_amount(method)
    if method["id"] == 20:
        return (
            "Upwork 固定总价 US$500（报告按 US$1=¥7 约 ¥3,500）："
            "里程碑1 US$250（范围/权限/基线/回滚）；"
            "里程碑2 US$150（上游修复并提交重抓/审核）；"
            "里程碑3 US$100（Approved 且目标 visibility 通过）。"
            "Upwork 每次只激活/注资当前里程碑；Processing/Under review 时第 3 段保持未到期。"
        )
    if method["id"] == 28:
        return (
            "Upwork 固定总价 US$360（报告按 US$1=¥7 约 ¥2,520）："
            "里程碑1 US$180（发件源清单、DNS 只读审计、备份/回滚）；"
            "里程碑2 US$180（p=none 上线后连续 7 天报告达到技术验收）。"
            "样本不足或有未解释合法失败源时，第 2 段保持未到期。"
        )
    if method["id"] == 50:
        return (
            "Upwork 使用一个 US$215 Project Catalog fixed-price order，客户购买时全额注资；"
            "完成映射、一次连续测试窗口与恢复结账后只提交一次验收。"
            "客户批准后仍有 5 天安全期，不把注资或 Pending 写成已到账。"
        )
    if method["id"] == 42:
        return (
            "只走一个 US$215 Upwork Project Catalog fixed-price order：客户从已发布项目购买并一次全额注资；"
            "卖方只在订单显示 Active/Funded 后，才从免费中国+2 国/12 月样报扩到中国+5 个替代国/60 月。"
            "Day 28 完整交付后只提交一次；不使用 Propose new contract、自定义里程碑或站外替代账单。"
        )
    first_milestone = math.ceil(usd / 2)
    second_milestone = usd - first_milestone
    return (
        f"Upwork 所有金额以 USD 列示：Project Catalog 输入 {upwork_price_text(method)} 并由客户一次注资；"
        f"若走自定义 fixed-price 合同，则两个里程碑为 US${first_milestone}/US${second_milestone}，合计 US${usd}，"
        "里程碑1交付基线、范围、规则和验收计划，截止 Day 17；里程碑2交付最终结果、QA、SOP和删除/回滚记录，截止 Day 28。"
        "每次只在当前里程碑 Active/Funded 后开工，提交并获批当前段后，等下一段 Active/Funded 才继续。独立获客且从未在 Upwork 建立关系的客户，可另用合规账单按"
        f" {fixed_price} 报价；不得把 Upwork 客户移到站外付款。客户批准后仍有 5 天安全期。"
    )


def digital_route(method: dict) -> tuple[str, str]:
    routes = {
        44: ("Upwork Project Catalog 单次 US$72 订单", "{{upwork_project_url}}"),
        45: ("Patreon 单次 US$19 founding product", "{{patreon_product_url}}"),
        46: ("Upwork Project Catalog 单次 US$29 订单", "{{upwork_project_url}}"),
        47: ("Upwork Project Catalog 单次 US$143 企业直播订单", "{{upwork_project_url}}"),
        48: ("免费 beta 报名表", "{{google_form_url}}"),
        49: ("Patreon US$9/month founding tier", "{{patreon_tier_url}}"),
    }
    return routes[method["id"]]


def normalized_path(value: str) -> str:
    return value.replace(
        "Find Work > Project Catalog > Create Project",
        "Find Work > Your services > Create Project",
    ).replace("备用 Upwork > Project Catalog", "备用 Upwork > Find Work > Your services > Create Project")


def technical_acceptance(method: dict) -> str:
    return method.get(
        "acceptance",
        f"在约定样本/页面上复测“{method['metric']}”，每项都有输入、预期、实际、证据链接与人工签字；付款只验证购买意愿，不作为技术通过条件。",
    )


def payback_model(method: dict) -> str:
    cash = max_cost(method["cost"])
    conservative = max(1, method["monthly"][0])
    hours = method.get("work_hours", {"service": 24, "data": 18, "digital": 32, "app": 40}.get(method["archetype"], 24))
    hourly = 200
    cash_days = max(1, math.ceil(cash / conservative * 30)) if cash else 0
    labor_days = math.ceil((cash + hours * hourly) / conservative * 30)
    cash_text = "首单即覆盖现金成本" if cash == 0 else f"按保守月营收匀速折算约 {cash_days} 天"
    return (
        f"现金口径：{cash_text}；含工时口径：按首月 {hours} 小时、目标时薪 ¥{hourly}/小时，"
        f"需覆盖约 {money(cash + hours * hourly)}，按保守情景折算约 {labor_days} 天。"
        "这是容量模型；真实回本以实际收款日、平台结算期、退款、税和工时为准。"
    )


def scenario_text(method: dict, index: int) -> str:
    parts = method["revenue_basis"].split("；")
    label = parts[index] if index < len(parts) else ("按已验证单价形成重复订单")
    total = method["monthly"][index]
    if "×" not in label and "=" not in label:
        label += f"；归一化校验：1 个该情景订单组合×{money(total)}={money(total)}"
    return f"{label}；模型合计={money(total)}"


def uses_ai(method: dict) -> bool:
    haystack = " ".join(str(method.get(k, "")) for k in ("title", "stack", "outcome"))
    return any(token in haystack for token in ("AI", "Qwen", "百炼", "LLM", "模型"))


def search_term(method: dict) -> str:
    return SEARCH_TERMS.get(method["id"], method["title"])


def validation_days(method: dict) -> int:
    found = re.findall(r"(\d+)[–-](\d+)\s*天", method["time"] + " " + method["validation"])
    if found:
        return int(found[0][1])
    found_single = re.search(r"(\d+)\s*天", method["time"])
    return int(found_single.group(1)) if found_single else 30


def difficulty(method: dict) -> int:
    speed = method["score"][1]
    low_cost = method["score"][2]
    access = method["score"][5]
    return max(1, min(5, round(((6 - speed) + (6 - low_cost) + (6 - access)) / 3)))


def method_source_keys(method: dict) -> list[str]:
    keys = list(method["sources"])
    if "Upwork" in method.get("publish_path", ""):
        if any(token in method.get("publish_path", "") for token in ("Project Catalog", "Your services > Create Project")) and "M30" not in keys:
            keys.append("M30")
        for key in ("P22", "P23", "P27", "P28", "P29", "P31", "P32", "P35"):
            if key not in keys:
                keys.append(key)
    return keys


def source_bullets(method: dict) -> str:
    lines = []
    for key in method_source_keys(method):
        src = SOURCES[key]
        lines.append(
            f"- **{key}｜[{src['title']}]({src['url']})：**{src['fact']} "
            f"**使用边界：**{src['caveat']}"
        )
    return "\n".join(lines)


def common_copy(method: dict) -> str:
    title = method["title"]
    buyer = method["buyer"]
    pain = method["pain"]
    outcome = method["outcome"]
    metric = method["metric"]
    offer = method["offer"]
    price = method["price"]
    validation = method["validation"]
    buyer_phrase = buyer[2:] if buyer.startswith("面向") else buyer
    acceptance = technical_acceptance(method)
    return f"""### A. 平台服务页/落地页文案

**标题（直接粘贴）**

> {title}｜先做固定范围试点，用真实数据验收，不承诺虚假增长

**副标题（直接粘贴）**

> 面向{buyer_phrase}。我会在不改变生产关键动作的前提下，完成「{offer}」，并用 {metric} 做前后验收。涉及发送、付款、退款、删除、公开发布或高风险判断的步骤默认保留人工批准。

**服务说明（直接粘贴）**

> 你现在可能遇到的问题是：{pain}。本项目不会先卖一套昂贵系统，而是先交付一个可回滚试点：{outcome}。你会收到现状基线、配置/数据文件、测试记录、异常清单、操作 SOP、回滚办法和 14/30 天结果复盘。固定范围外的工作会在开始前单独报价。参考价：{price}。

**CTA（直接粘贴）**

> 请发送 1 份脱敏样本、当前工具、每月处理量和最想改善的一个指标。我会先回复“能做/不该做/还缺什么”，不会要求你先开放管理员权限。

### B. 有条件适用的手工冷邮件（发送前先过司法辖区闸门）

**发送闸门（每个联系人都要记录）**

> 先记录发送者国家/地区、收件人国家/地区、收件主体是 corporate subscriber 还是个人/sole trader/partnership、合法基础、隐私告知 URL 和 suppression 状态。英国公司/LLP 等 corporate body 的 PECR 规则与个人不同，但姓名和个人化工作邮箱仍可能受 UK GDPR 约束；sole trader、非 LLP 等部分 partnership 通常按个人处理。类型不明时按个人处理。禁止追踪像素、个人数据拼接、购买名单和自动群发；无法确定规则时，改用 Upwork 平台响应、用户主动订阅、转介绍或公开内容获客。发送前复核收件地最新规则。

**主题：**关于贵司「{title}」的一页试点建议

> 你好，{{姓名/团队}}：  
> 我查看了贵司公开的 {{页面/流程/职位信息}}，发现一个可以用固定范围验证的问题：{pain}。我不是来承诺排名或收入的；我可以先用公开信息或你提供的脱敏样本，做「{offer}」，验收只看 {metric}。  
> 如果方向不相关，回复“不需要”即可，我不会再联系。若相关，我可以先发一页样例和完整边界，确认后再开任何权限。  
> {{你的真实姓名}}｜{{公司/个人主体}}｜{{实体邮寄地址}}｜{{官网/作品集}}  
> 退订：回复“不需要”。

**第一次跟进（3 个工作日后）**

> 补充一个具体点：本试点的最小通过条件是「{validation}」。如果你已有团队在做，我也可以只交只读审计和测试清单；若不相关，回复“不需要”，我会停止联系。

**最后一次跟进（再过 5 个工作日）**

> 这是最后一次跟进。我可以免费发一张脱敏样例，不需要管理员权限。若本季度没有优先级，无需回复；我会关闭这条联系记录。

### C. 发现电话脚本

> 这次 20 分钟只确认四件事：一，当前流程从哪里开始、在哪里结束；二，过去 30 天处理量和基线；三，哪些动作绝不能自动执行；四，什么数字达到才值得继续。若拿不到基线，我们就把试点目标改成“正确性和节省时间”，不编造收入归因。

### D. 固定范围提案

> **项目：**{title} 30 天验证  
> **客户：**{{客户名}}  
> **范围：**{offer}  
> **客户提供：**{method['input']}  
> **交付：**基线表、实施/配置、测试证据、异常队列、SOP、回滚说明、结果复盘  
> **技术验收：**{acceptance}  
> **商业验证：**{validation}  
> **不包含：**未授权数据、法律/医疗/金融意见、批量群发、平台条款规避、资金代收、自动退款/删除/公开发布  
> **付款路径：**{payment_terms(method)} 参考扩展价：{price}。技术验收与注资、批准、Pending 和银行到账分开记录。  
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

> 本轮范围已完成。基线为 {{数值}}，试点结果为 {{数值}}，样本量 {{N}}；已知局限是 {{局限}}。附件含配置、测试记录、异常、SOP 和回滚。若继续，建议只把「{{已证明稳定的低风险步骤}}」转为月度维护；其余仍人工批准。你若愿意评价，请只描述真实交付和结果，不需要给五星，也没有任何奖励。
"""


def platform_copy(method: dict) -> str:
    if method["id"] in (44, 46):
        product_name = "垂直行业 Sales Deck Beta" if method["id"] == 44 else "单行业商品图 Beta Template Pack"
        files = (
            "01-deck-beta.pptx、02-preview.pdf、03-roi-input.xlsx、04-speaker-notes.pdf、README.txt"
            if method["id"] == 44
            else "01-template-links.pdf、02-copy-fields.csv、03-size-guide.pdf、04-preview.pdf、README.txt"
        )
        compatibility = "PowerPoint 2021+/Microsoft 365；Canva 网页版" if method["id"] == 44 else "Canva 网页版；CSV 使用 UTF-8"
        return f"""### G. Creative Market 完成品字段（44/46 专用）

> **Product title:** {product_name} — Original, Editable, Commercial-Use Template System  
> **Files included:** {files}  
> **Compatible with:** {compatibility}  
> **Included:** 可立即下载的完整 beta、真实页面预览、编辑说明、版本号、支持邮箱。  
> **Not included:** 字体/照片/图标库素材本体、商标、客户品牌、广告效果、定制服务或未完成的未来页面。  
> **License:** 购买时以 Creative Market 显示的 Personal/Commercial/Extended Commercial 许可为准；本 ZIP 不另造“团队许可”。团队定制通过独立 Upwork 服务合同购买。  
> **Asset disclosure:** 本 Creative Market ZIP 中的可售资产均由卖家本人创作并属于卖家独占 IP；第三方素材未打包。Canva Pro Content 若用于另行定制版本，只通过 Canva 允许的 template link 使用并单独列出。  
> **AI disclosure:** {{选择一项：No generative AI was used / Generative AI was used only for {{用途}} and every output was materially edited and rights-reviewed by the seller.}}  
> **Support:** 购买后 14 天内处理文件损坏、缺页或链接不可访问；不包含品牌定制、策略咨询或软件培训。
> **Payout note:** USD 提现一般最低 US$20；若选本币付款，通常需等值 US$1,030 且随币种变化，可有 2.5% FX 费。以 Tax and Payout Setup 实际显示为准。
"""
    if method["id"] == 45:
        return """### G. Patreon one-time product 字段（45 专用）

> **Product name:** Sponsor-Ready Media Kit + Revenue Tracker  
> **Price:** US$19 founding / US$59 professional（不要填写 CNY）  
> **Short description:** A 12-page editable media kit, sponsor inventory planner, rate-card worksheet, outreach CRM and self-filled CPM/revenue calculator for active creators.  
> **You receive:** Canva template link、Google Sheets copy link、PDF setup guide、sample data、version changelog。  
> **You do not receive:** sponsor leads, guaranteed rates, guaranteed revenue, legal/tax advice, or third-party media assets.  
> **Refund/support:** If a file or copy link cannot be opened, contact {{support email}} within 14 days. I will repair access or refund where Patreon policy requires; preference changes or lack of sponsor sales are not a performance guarantee.  
> **Rights/AI:** All saleable layouts and formulas are original. Third-party assets are not redistributed. AI use: {{none / describe exact use and human review}}.
> **Fee model:** 创作者 payout currency、商品和成员支付均为 USD 且使用网页信用卡时，整笔提现前的基准可计收入为售价×87.1%−US$0.30/成功笔（10% 平台费、2.9% 处理费）；币种一致，不逐笔扣 2.5% FX。转入中国 CNY 本地银行时，再从每次整笔提现扣 1.55%+US$0.25。iOS、非美国 PayPal、税、退款和实际费用必须以 Earnings 替换。
"""
    if method["id"] == 47:
        return """### G. 直播服务与 Udemy 填写字段（47 专用）

**四个学习目标（直接粘贴 Udemy Intended learners）**

1. Map five recurring tasks in one job role into measurable, human-approved AI workflows.  
2. Write structured inputs and acceptance checks that prevent unsupported facts.  
3. Decide which steps may be drafted, routed or must be escalated to a human.  
4. Run a before/after experiment and document time saved, errors and stop conditions.

**课程结构（至少 30 分钟、5 节）**

> Lecture 1 — Baseline and task selection (6 min)  
> Lecture 2 — Safe input and data boundary (6 min)  
> Lecture 3 — Workflow 1–2 live build (8 min)  
> Lecture 4 — Workflow 3–5 and human approval (8 min)  
> Lecture 5 — QA rubric, failure replay and 30-day plan (7 min)  
> Download: five templates, gold-set worksheet and answer key.

**AI 披露**

> This course contains the use of artificial intelligence. AI is demonstrated as a tool inside the course. The instructor designed, recorded, edited and verified the teaching content. Any AI-generated material is identified in the relevant lecture and is not presented as independent professional advice.

**独立直播改期/退款文案**

> Live workshop date: {{date/time/timezone}}. One attendee substitution is allowed before the start. If I cancel, you may choose a full refund or one rescheduled date. If you cannot attend and notify me at least 24 hours before start, choose one reschedule; later no-shows receive the materials and recording only where consent permits. Upwork contract/refund rules prevail over this summary.
"""
    if method["id"] == 48:
        return """### G. KDP 书籍字段与免费 beta 文案（48 专用）

> **Title:** 30 Days of AI Workflow Experiments for {{ROLE}}  
> **Subtitle:** A Human-Reviewed Workbook for Baselines, Quality Checks, Risk Logs and Stop Decisions  
> **Description:** Stop collecting generic prompts. This workbook turns 30 recurring {{ROLE}} tasks into small, measurable experiments. Each day includes a baseline, allowed inputs, a step-by-step workflow, an evidence checklist, a human-approval gate and a stop rule. You will record time, errors and uncertainty instead of assuming AI output is correct. This is a practical learning workbook, not legal, medical, financial or employment advice.  
> **Keywords:** {{role}} workflow; AI quality checklist; human in the loop; productivity experiment; prompt evaluation; risk log; 30 day workbook  
> **Categories:** choose the two closest current KDP categories shown in your Bookshelf; do not insert unrelated bestseller categories.  
> **AI disclosure:** {{No AI-generated text/images/translations / AI-generated {{type}} was used and substantially reviewed by the author}}. Answer KDP’s disclosure question truthfully.  
> **Price:** US$9.99 Kindle eBook.  

**免费 beta 招募/交付文案**

> I’m recruiting 10 unpaid beta readers for a seven-day sample of “30 Days of AI Workflow Experiments for {{ROLE}}”. You receive a watermarked, versioned PDF for personal review only. Please complete Days 1–3 and return the short feedback form by {{date}}. There is no payment, no review requirement and no promise of a free final book. I will delete your contact record within 30 days after the beta unless you opt in to updates.
"""
    if method["id"] == 49:
        return """### G. Patreon tier 与欢迎消息（49 专用）

> **Tier name:** Shopify Localization & Accessibility Operator  
> **Price:** US$9/month（个人）  
> **Benefits:** every Tuesday: one source-linked change brief; one impact checklist; one copyable SOP; members-only Q&A thread.  
> **Agency tier:** US$39/month，最多 5 名内部成员；不得转售原文或共享登录。  
> **Four-week promise:** Week 1 translation gaps; Week 2 Markets/locale QA; Week 3 alt text and keyboard checks; Week 4 change log + test matrix. Every issue links to a public primary source and states what is still uncertain.  
> **Welcome message:** Welcome. Start with the pinned “Scope & Sources” post, copy the weekly checklist, and reply with one workflow you want tested. This membership does not provide legal advice or guarantee platform compliance.  
> **Cancellation:** Cancel in Patreon before the next billing date to stop future charges. Access and refund handling follow Patreon’s current policy. If I cannot publish the promised weekly issue, I will post a delay notice and replacement date; repeated missed issues trigger a pause/refund review.  
> **Currency/fees:** Creator payout currency、tier 和成员支付均为 USD，不填 CNY。网页信用卡的整笔提现前基准可计收入为 price×87.1%−US$0.30/成功笔：10% 平台费加 2.9% 处理费；币种一致，不逐笔扣 2.5% FX。转入中国 CNY 本地银行时，再从每次整笔提现扣 1.55%+US$0.25。非美国 PayPal、税、iOS、退款和实际费用以 Earnings 替换。
"""
    return ""


def digital_copy(method: dict) -> str:
    route_name, route_url = digital_route(method)
    beta_action = (
        f"这是免费 beta，不需下单。愿意参加请填写 {route_url}；不要提供密码或敏感数据，也不需提交 Amazon 评价。"
        if method["id"] == 48
        else f"愿意参加请只使用 {route_name}：{route_url}。不接受站外代付，也不要求好评。"
    )
    service_contract = ""
    if method["id"] in (44, 46, 47):
        usd_price = {44: 72, 46: 29, 47: 143}[method["id"]]
        service_contract = f"""### C. Upwork beta/直播固定范围提案

> **Project:** {method['title']} paid pilot  
> **Scope:** {method['offer']}  
> **Client receives:** 完成品/直播、README 或讲义、版本号、许可/使用边界、一次阻塞问题修复。  
> **Acceptance:** {technical_acceptance(method)}  
> **Purchase route:** Project Catalog 单次固定价 US${usd_price}；客户下单时一次注资，不混用两阶段里程碑。完成后走 `Deliver work > Your active contracts > 目标合同 > Submit work`；客户批准后仍有 5 天安全期。  
> **Not included:** 未完成商品冒充现货、虚假评价/销量、第三方素材转售、广告/学习收入保证、未列明定制。  
> **Changes/refund:** 新增页面、尺寸、岗位、语言或直播场次另行书面报价；平台合同和退款规则优先。
> **Availability:** `Account settings > Withdrawals > Add a method > Direct to Local Bank > Set up`；中国 CNY 可用、新方式 3 天激活、US$0.99/次，提现后通常 4 天内到银行。姓名必须与验证身份一致。
"""
    return f"""### A. 商品/会员页通用字段

> **Title:** {method['title']}  
> **For:** {method['buyer']}  
> **Problem:** {method['pain']}  
> **What you receive:** {method['outcome']}  
> **MVP scope:** {method['offer']}  
> **Not included:** 收益保证、虚假稀缺/评价、未授权字体/图片/商标、法律/税务/医疗/金融意见、未列明定制。  
> **Support:** {{支持邮箱}}；回复时限 {{24/48 小时}}；版本 {{v1.0}}；最后更新 {{YYYY-MM-DD}}。  
> **Price:** {method['price']}。平台显示的税、许可、退款、结算和地区规则优先。

### B. beta/首发招募文案

> 我正在验证「{method['title']}」，范围只有：{method['offer']}。你会先看到真实预览、明确文件/场次、交付日、许可和退款边界；我不承诺收入、排名或评价。验证门槛是：{method['validation']}。{beta_action}

**交付消息**

> 感谢购买。你的交付链接/访问入口是 {{link}}，版本 {{version}}，适用工具 {{compatibility}}。先按 README 完成第一步；若文件损坏、链接不可访问或与商品页所列内容不一致，请在 {{support_window}} 内发送截图和订单号。我会按平台政策修复访问或处理退款。没有任何好评、转发或续费要求。

{service_contract}

{platform_copy(method)}
"""


def prompt_block(method: dict) -> str:
    return f"""### 结构化提示词（先在脱敏样本上运行）

```text
你是“{method['title']}”的质量辅助器，不是最终决策者。

业务目标：{method['outcome']}
目标客户：{method['buyer']}
允许输入：{method['input']}
验收指标：{method['metric']}

硬规则：
1. 不得补造任何输入中不存在的事实、价格、日期、资格、政策、人物或联系方式。
2. 如证据不足，status 必须为 NEEDS_HUMAN，并写出 missing_fields。
3. 涉及付款、退款、删除、改价、公开回复、投标、法律/医疗/金融判断时，action 只能是 ESCALATE。
4. 每个结论必须返回 evidence_quote 或 source_id；没有证据就不下结论。
5. 只输出下列 JSON，不输出解释性前后缀。

输出 JSON Schema：
{{
  "status": "OK|NEEDS_HUMAN|REJECT_INPUT",
  "category": "string",
  "confidence": 0.0,
  "summary": "string",
  "evidence_quote": "string",
  "source_id": "string",
  "missing_fields": ["string"],
  "recommended_action": "DRAFT|ROUTE|ESCALATE|NO_ACTION",
  "qa_checks": [{{"check": "string", "passed": true, "note": "string"}}]
}}

待处理输入：
{{{{在此粘贴一条脱敏样本}}}}
```

**上线闸门：**先跑黄金测试集；任何高风险漏报都会让模型步骤退回“只建议/不执行”。
"""


def implementation_pack(method: dict) -> str:
    packs: dict[int, str] = {
        1: r'''### 可运行的 HubSpot → Qwen → 人工审批最小包

**HubSpot Contact properties**

```text
lead_route | Dropdown | sales_a,sales_b,sales_c,needs_human
lead_priority | Dropdown | high,medium,low
route_confidence | Number | 0..1
route_reason | Multi-line text | 只写输入中可验证的理由
route_status | Dropdown | draft,approved,rejected_by_human
```

**Make 模块顺序**

```text
1 HubSpot > Watch CRM Objects (Contact)
2 HubSpot > Get a CRM Object
3 Tools > Set multiple variables（确定性 territory/industry/blocked 规则）
4 HTTP > Make a request（仅规则不能决定时调用 Qwen）
5 JSON > Parse JSON
6 Router：confidence<0.80 OR priority=high -> needs_human；否则仅写 draft 字段
7 HubSpot > Update a CRM Object（只写上述 5 个测试字段）
8 Slack/Gmail > Create draft/approval message（不得自动拒绝或外发）
```

**Qwen OpenAI-compatible 请求（终端可运行；密钥只从环境变量读取）**

```bash
curl -sS https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer ${DASHSCOPE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"qwen-plus",
    "temperature":0,
    "response_format":{"type":"json_object"},
    "messages":[
      {"role":"system","content":"Return JSON only: lead_route, lead_priority, route_confidence, route_reason, missing_fields. Never reject a lead. If evidence is missing, lead_route=needs_human."},
      {"role":"user","content":"company_size=12; country=DE; use_case=integration; urgency=30_days; free_text=Need a CRM integration quote"}
    ]
  }'
```

验收用 20 条客户标注记录；正确路由至少 17 条、高价值漏报为 0、低置信度全部人工审批，并检查 Email/Record ID 去重。模型名、端点和地区可用性在执行日以客户自有百炼控制台为准。
''',
        10: '''### Stripe sandbox 分支与催款文案包

```text
T01 due_soon -> 只生成友好提醒草稿
T02 due_today -> 只生成到期提醒草稿
T03 past_due_3d -> 生成第二提醒草稿
T04 invoice.paid -> 立即停止后续提醒
T05 payment_failed -> 通知客户更新支付方式，不索取卡号
T06 dispute/open_case -> 停催并升级财务负责人
T07 customer_requested_pause -> suppression=true
T08 missing_contract_or_fee_basis -> NEEDS_HUMAN，不发送逾期费措辞
```

**客户批准前不得发送的模板草稿**

> Subject: Reminder: invoice {{invoice_number}} due {{due_date}}  
> Hello {{company}}, our records show invoice {{invoice_number}} for {{amount/currency}} is {{status}}. You can review the invoice through the secure Stripe-hosted link: {{hosted_invoice_url}}. If payment has already been made or the invoice is disputed, reply to this message and reminders will pause for human review. We will never ask for card or bank credentials by email.  
> {{legal sender name}} | {{contact}} | {{address}}

`late fee`、利息、停服或法律威胁字段默认禁用；只有客户合同、收件地法律和客户法务/财务书面批准后才能加入。试点只在 Stripe sandbox/Simulations，真实回款另签生产授权。
''',
        20: '''### Merchant Center 单问题代码验收表

```text
item_id | country | data_source | issue_code | old_value | source_of_truth | new_value | page_matches | issue_gone | product_status | destination_visibility | evidence_url | rollback
```

1. `Products & store > Products > Needs attention` 选一个 issue code 并下载受影响商品。  
2. `Settings > Data sources` 找真实上游；只在 Shopify/WooCommerce/feed 源修字段，禁止只改会被覆盖的下游值。  
3. 更新数据源后等待平台处理；只有界面提供 `Request review` 时才提交。  
4. `Processing`/`Under review` 不是通过；必须看到 `Approved`，并按合同核对目标 destination visibility。  
5. GTIN、brand、price、availability 均来自制造商/商家系统和可见页面；未知就留空，不补造。

审核延迟与实施工期分开；平台批准不保证展示、点击或销售。
''',
        21: '''### Shopify Liquid / JSON-LD 可复制实现

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
''',
        22: '''### GA4 五事件合同与去重包

| event | 必需/本试点字段 | 通过条件 |
|---|---|---|
| `view_item` | `currency`,`value`,`items[]` | items 至少含 `item_id` 或 `item_name` |
| `add_to_cart` | `currency`,`value`,`items[]` | 数量、单价与页面一致 |
| `view_cart` | `currency`,`value`,`items[]` | 购物车页展示的商品、数量和金额一致 |
| `begin_checkout` | `currency`,`value`,`items[]`,`coupon` 可选 | 结账开始仅触发一次 |
| `purchase` | `transaction_id`,`currency`,`value`,`items[]`,`tax/shipping` 可选 | 两笔不同 ID 各一次；重复触发不新增 purchase |

```javascript
window.dataLayer = window.dataLayer || [];
dataLayer.push({
  event: "purchase",
  ecommerce: {
    transaction_id: "TEST-ORDER-1001",
    currency: "USD",
    value: 49.90,
    items: [{item_id: "SKU-1", item_name: "Test product", price: 49.90, quantity: 1}]
  }
});
```

先在 `GTM > Workspace > Preview` 用 Tag Assistant 连接测试 URL，再到 `GA4 > Admin > Data display > DebugView`。跑 3 条旅程和 2 个不同订单；约 24 小时后在标准报表/Explore/Looker 再对账。只保留一条主发送路径，防止 gtag.js 与 GTM 双发。
''',
        28: '''### DNS 变更包（以下 SPF 只能按真实发件源选一条）

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
''',
        29: '''### 十项安全卫生证据清单

| # | 检查 | 最小证据 | 通过条件 |
|---:|---|---|---|
| 1 | 资产与 owner | 租户/域名/网站/备份系统 | 全部有 owner 与恢复联系人 |
| 2 | 用户生命周期 | 用户、状态、最后登录、离职名单 | 离职/未知账号已禁用或有截止日 |
| 3 | MFA | Workspace 2SV 或 Entra methods activity | 管理员 100%，例外有 owner |
| 4 | 特权账号 | Admin roles / Roles & admins | 无共享管理员，每个角色有理由 |
| 5 | 紧急恢复 | 恢复方式、保管人、测试日 | 客户控制的路径可用 |
| 6 | 更新与补丁 | SaaS/网站/插件/终端状态 | 缺口有 owner 与日期 |
| 7 | 备份覆盖与隔离 | 成功时间、范围、保留、权限 | 关键数据覆盖且不与生产同毁 |
| 8 | 隔离恢复 | 测试文件、隔离目标、校验值 | 成功且未覆盖生产 |
| 9 | 日志与告警 | 管理/登录日志、告警 owner | 可读且至少一次复核留痕 |
| 10 | 钓鱼与事件响应 | 报告入口、联系人、演练 | 一次桌面演练完成 |

每项记录：`时间戳 | 来源菜单 | 状态 | 证据截图/导出 | owner | 下一步 | 截止日`。任何权限修改前先验证客户控制的恢复路径；恢复只到隔离文件夹/测试用户，路径不明就保持只读。
''',
        30: '''### WCAG 2.2 A/AA 最小人工测试矩阵

| 检查 | WCAG 2.2 SC | 动作 | 通过证据 |
|---|---|---|---|
| 图片 | 1.1.1 | 有意义图检查 alt，装饰图 alt="" | DOM+截图 |
| 结构 | 1.3.1,2.4.6 | heading/list/table/label 语义与顺序 | DOM+读屏 |
| 对比 | 1.4.3,1.4.11 | 文本、控件、焦点、图标 | 色值+比率 |
| 缩放/reflow | 1.4.4,1.4.10 | 200% 与 320 CSS px | 前后截图 |
| 键盘 | 2.1.1,2.1.2 | Tab/Shift+Tab/Enter/Space/Esc/箭头 | 全任务录屏 |
| 焦点 | 2.4.3,2.4.7,2.4.11 | 顺序、可见、不被遮挡 | 每组件证据 |
| 名称 | 2.4.4,2.5.3 | 可见标签包含于 accessible name | Accessibility tree |
| 表单/状态 | 3.3.1,3.3.2,4.1.3 | 空值、格式错、失败、状态播报 | 输入+读屏结果 |
| 动态组件 | 4.1.2 | modal/menu/tabs 的 name/role/value/state | Tree+录屏 |
| 完整流程 | WCAG-EM | 登录/搜索/购物/表单逐状态 | 环境矩阵 |

发现记录：`ID | URL | 页面状态 | 浏览器/AT | SC | 严重度 | 复现 | 实际 | 期望 | 修复 | 复测 | 第三方 owner`。

> 本报告仅覆盖列明的 5 个页面/状态、测试环境和成功准则，是范围抽样评估；不构成整站 WCAG 符合性声明或法律意见。
''',
        31: '''### SAM.gov 公共检索、金额边界与人工评分包

**无需 API key 的 MVP**

1. `SAM.gov > Search > Contract Opportunities`。  
2. `Filters` 依次填 `Keywords`、`Federal Organizations`（可选）、`Notice Type`、`NAICS`、`Set Aside`、`Place of Performance` 和 `Response Date`，点 `Apply`。  
3. 打开一条结果，复制 `Notice ID`、响应截止日和浏览器地址；退出登录后用 Notice ID 再搜一次，确认客户能访问公共回链。  
4. Sheet 字段：`notice_id,official_url,notice_type,naics,pop_state,pop_zip,published_date,response_deadline,set_aside,amount_disclosed,amount_value,qualification,matched_reason,bid_no_bid,human_verified,fetched_at`。

**必须粘贴进 rules tab 的硬规则**

```text
1. 必须条件只用 NAICS、关键词、履约州/邮编、公告类型、set-aside、资格与响应截止窗口。
2. SAM.gov Opportunities v2 请求参数没有最小/最大金额过滤器。
3. data.award.amount 只在记录含 award information 时可能返回，不等同于待投机会预算。
4. 原公告明确披露金额时写 amount_disclosed=yes 和原值；否则 amount_value=unknown。
5. 不从历史 award、相似公告或客户预算偏好推断金额；客户预算只做人工软评分。
6. 每条必须保留 notice ID、公共回链、抓取时间和 human_verified；投标决定必须回源。
```

商业表述固定为：“本服务不承诺按预算区间筛净机会；预算匹配只做人工软评分，并标明公告已披露或未知。”SAM API key 位于请求 query，故本通用 `feed_alert.py` 不支持该认证方式；首单用公共 UI/Postman Secret，绝不把含 key URL 放报告、日志或命令历史。
''',
        32: '''### USAspending 可复制 Postman 请求

`Postman > New > HTTP Request`，Method 选 `POST`，URL 填：

```text
https://api.usaspending.gov/api/v2/search/spending_by_award/
```

`Authorization > No Auth`；`Headers` 新增 `Content-Type: application/json`；`Body > raw > JSON` 粘贴：

```json
{
  "subawards": false,
  "limit": 100,
  "page": 1,
  "filters": {
    "award_type_codes": ["A", "B", "C", "D"],
    "time_period": [{"start_date": "2023-09-01", "end_date": "2026-09-01"}],
    "agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}],
    "naics_codes": {"require": ["541512"]}
  },
  "fields": ["Award ID", "Recipient Name", "Start Date", "End Date", "Award Amount", "Awarding Agency", "Awarding Sub Agency", "NAICS", "Description", "generated_internal_id"],
  "sort": "End Date",
  "order": "desc"
}
```

点 `Send`；把 `page` 逐页加一，直到 `page_metadata.hasNext=false`。官方回链=`https://www.usaspending.gov/award/{generated_internal_id}/`。`time_period` 只是历史奖项筛选期；“续约窗口”必须标 `analyst_inference=yes` 并由人打开 award 页面核验，不能写成未来采购承诺。
''',
        34: '''### TED Search API 可复制 Postman 请求

`Postman > New > HTTP Request`，Method=`POST`，URL=`https://api.ted.europa.eu/v3/notices/search`；`Authorization > No Auth`；Header=`Content-Type: application/json`；`Body > raw > JSON`：

```json
{
  "query": "publication-date = (20260801 <> 20260831) AND classification-cpv = 72* AND place-of-performance IN (DEU)",
  "fields": ["publication-number", "notice-title", "publication-date", "buyer-name", "classification-cpv", "place-of-performance", "deadline-receipt-tender-date-lot"],
  "page": 1,
  "limit": 100,
  "scope": "ALL",
  "checkQuerySyntax": false,
  "paginationMode": "PAGE_NUMBER",
  "onlyLatestVersions": true
}
```

点 `Send` 后逐页增加 `page`。`checkQuerySyntax=true` 只用来检查语法，真正取数改回 `false`。PAGE_NUMBER 每页最多 250、最多 15,000 条；超过则改 `paginationMode=ITERATION` 并把响应 `iterationNextToken` 传给下一次请求。回链优先保存 `links.html.ENG`，没有 ENG 时取 `links.html` 任一官方语言 URL，不自行拼第三方地址。关键资格保留原文；中文只作辅助摘要。
''',
        35: '''### Federal Register 与 Regulations.gov 两源请求包

两源必须分开保存，不能用一条请求冒充。

**Federal Register：**`Postman > New > HTTP Request > GET`，`Authorization > No Auth`，Body none：

```text
https://www.federalregister.gov/api/v1/documents.json?per_page=20&page=1&order=newest&conditions%5Bagencies%5D%5B%5D=food-and-drug-administration&conditions%5Bpublication_date%5D%5Bgte%5D=2026-08-01&conditions%5Bterm%5D=food
```

跟随响应 `next_page_url` 到 `null`；报告回链用 `results[].html_url`，法律依赖打开 `results[].pdf_url` 的 GovInfo PDF。

**Regulations.gov：**先在官网申请 key。打开 `Postman > Vault > Local Vault > Add new secret`：Key=`REGULATIONS_GOV_API_KEY`，Value 粘贴 key，Allowed domain 只填 `api.regulations.gov`；不要 Share，也不要另建 Environment 变量。新建 GET：

```text
https://api.regulations.gov/v4/documents?filter%5BagencyId%5D=FDA&filter%5BsearchTerm%5D=food&filter%5BpostedDate%5D%5Bge%5D=2026-08-01&filter%5BpostedDate%5D%5Ble%5D=2026-09-01&sort=-postedDate&page%5Bsize%5D=25&page%5Bnumber%5D=1
```

`Authorization > No Auth`；Header `X-Api-Key: {{vault:REGULATIONS_GOV_API_KEY}}`；Body none。增加 `page[number]` 到 `meta.lastPage=true`，`page[size]` 不得低于 5。逐页确认 `data[].attributes.agencyId=FDA`；官方回链=`https://www.regulations.gov/document/{data[].id}`。key 不写 URL、环境、collection、报告、截图或日志；默认排除评论者姓名、联系方式和附件。
''',
        38: '''### openFDA 历史请求、回链与增量快照包

`Postman > New > HTTP Request > GET`，URL：

```text
https://api.fda.gov/food/enforcement.json?search=report_date:%5B20260801+TO+20260831%5D&sort=report_date:asc&limit=100&skip=0
```

低量 smoke test 可 `Authorization > No Auth`；生产前申请免费 key，并在 Postman `Authorization > Basic Auth` 将 Username 设 `{{OPENFDA_API_KEY}}`、Password 留空，现场验证认证、429 与配额。官方文档的 key/no-key 表述不一致，因此不承诺长期 keyless。分页按 `skip=0,100,200...`；limit 最大 1,000，skip 最大 25,000。

响应没有 `source_url` 字段。每条必须用 `recall_number` 生成无 key 官方回链：

```text
https://api.fda.gov/food/enforcement.json?search=recall_number:%22{URL_ENCODED_RECALL_NUMBER}%22&limit=1
```

不是恰好一条就标 `NEEDS_HUMAN`。每次先 GET `https://api.fda.gov/download.json`，读取 `results.food.enforcement.export_date` 和全部 `partitions[].file`；export_date 变化才下载全部分区并与上一完整快照比较。默认键=`recall_number`，重复时改 `recall_number|event_id|product_description|code_info`；对白名单字段做规范化 hash，新键=`NEW_RECORD`、同键变化=`FDA_DATA_REVISED`、消失=`NEEDS_HUMAN`，不得写成召回撤销。保存 `fetched_at,export_date,source_url,human_verified`，绝不保存含 key URL。

用途仅限客户内部专业人员的“候选记录与官方数据修订简报”；不得向公众发布安全警报、替代 FDA 通知、跟踪完整生命周期或自动触发下架/医疗/法律决定。交付前由客户食品安全负责人逐条回源。
''',
        39: '''### EPA ECHO 两步查询包

通用单响应脚本不能宣称直接支持。`Postman > New > HTTP Request > GET`：

```text
https://echodata.epa.gov/echo/echo_rest_services.get_facilities?output=JSON&p_st=DC&p_act=Y&p_maj=Y&responseset=20
```

`Authorization > No Auth`、Body none。读取 `Results.QueryID`，再新建 GET：

```text
https://echodata.epa.gov/echo/echo_rest_services.get_qid?qid={{QueryID}}&output=JSON&pageno=1&responseset=20
```

增加 `pageno`，直到 Facilities 为空/少于 responseset，或已达到 `QueryRows`。`QueryID` 只是会话标识，不作 source ID；稳定 ID 用 `RegistryID`。官方回链=`https://echo.epa.gov/detailed-facility-report?fid={RegistryID}`。“过去 30 天”必须在本地对白名单日期字段后过滤；上述请求本身没有完成日期过滤。措辞只写“官方记录显示/待客户核验”，不写“当前违法”。

只允许读取三项日期：`FacDateLastInspection`、`FacDateLastFormalAction`、`FacDateLastPenalty`。运行日记为 `as_of`，窗口严格为 `[as_of-29d, as_of]`；每个非空且落窗的日期展开成一条事件，`event_type` 分别写 `inspection`、`formal_action`、`penalty`，去重键=`RegistryID|event_type|event_date`。输出只保留 `RegistryID,FacName,event_type,event_date,source_url,fetched_at,human_verified`。不得扩大到响应未返回的其他事件或类别筛选；窗口内为 0 条时如实交付零事件报告，不用旧记录填满 20 条。
''',
        42: '''### Census 对美进口 HS6 可运行请求

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
''',
        44: '''### Sales Deck 文件与 QA 清单

```text
slide_id | purpose | source_or_assumption | editable | font_owned | image_owned | exclusive_ip | notes_present | accessibility | preview_matches | pass
```

8 页 beta 必须完整可用：封面、问题、现状证据、方案、流程、ROI 输入、反对意见、CTA。Creative Market ZIP 只含自制独占资产；`README.txt` 列文件、兼容软件、平台许可、支持和版本。Canva Pro 内容只能留在允许的 template link/定制版本，不能打包成 Creative Market 可售资产。
''',
        45: '''### Media Kit + Tracker 验收字段

```text
asset | open_test | formula_test | sample_data_removed | rights | mobile_preview | support_link | pass
media-kit.pdf | ...
canva-template-link | ...
sponsor-tracker-sheet | ...
rate-card-calculator | ...
```

Tracker 至少含 `brand,contact_channel,inventory,quoted_price,status,next_action,due_date,deliverable,invoice_status`；CPM/收入数字全部由买家输入，不内置“行业保证价”。Patreon 商品用 USD，订单后才能测试实际访问与结算。
''',
        46: '''### 商品图模板系统验收字段

```text
template_id | size_px | placement | editable_fields | safe_area | sample_sku | self_created_assets | canva_pro | blank_account_open | export_test | pass
```

10 个 beta 模板必须覆盖已承诺尺寸，并用 3 个虚构/授权 SKU 做完整演示。Creative Market 版本只含自制独占资产和平台许可；使用 Canva Pro 内容的定制版本只交允许的 template link，不把素材本体打包。
''',
        47: '''### 直播/成课 QA 清单

```text
learning_objective | lecture | video_minutes | exercise | answer_key | source | ai_disclosure | audio_l_r | resolution | preview_ok
```

直播服务先验证一个企业买方；录制课程达到总视频至少 30 分钟、至少 5 节、720p/1080p、双声道音频、完整落地页和 AI 披露后，才点击 Udemy `Submit for Review`。30 天内的 Udemy 销售只记订单/应计讲师收入，平台通常第 3 月且达到 25 美元才付款。
''',
        48: '''### KDP 终稿与预售 QA 清单

```text
chapter | experiment | baseline | allowed_input | steps | evidence_check | human_gate | stop_rule | source | rights | ai_disclosure | preview_pass
```

终稿前逐项检查 30 个实验、目录跳转、手机/平板 Previewer、封面、关键词、类别、版权和 AI disclosure。`Bookshelf > Create eBook > Pre-order` 只用于新 Kindle eBook；必须在 deadline 前上传终稿并提交。免费 beta 与 KDP 销售分开：发行前 30 天只在 Pre-Order Report 统计净预售单和取消；发行交付后才进版税报告，且通常约销售月末 60 天后才到账。
''',
        49: '''### Patreon 四周发布运行表

```text
week | primary_sources | checked_at | claim | caveat | impact | test_steps | sop_asset | publish_date | member_questions | correction
```

预先完成 4 期草稿，每条事实回链公开一手来源并写检查日。Tier 用 USD，不用 CNY；按个人 US$9、代理商 US$39 填写权益、欢迎消息和取消说明。首个真实余额后、扩量前再测试到账；不承诺打开率、续费或合规结果。
''',
        50: '''### Shopify 数字交付确定性审计表

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
''',
    }
    if method["id"] in packs:
        return packs[method["id"]]
    return f"""### 确定性实施与证据模板

```text
case_id | source/input | expected | actual | evidence_url | owner | approval | rollback | status
```

先按 `{method['setup_path']}` 建最小副本/测试环境，再按 `{method['test_path']}` 跑 5 条正常样本、1 条空值、1 条重复、1 条权限拒绝和 1 条回滚。技术通过条件：{technical_acceptance(method)} 任何涉及发送、付款、退款、删除、公开发布、法律/医疗/金融判断的动作保持人工批准。
"""


def service_days(m: dict) -> list[tuple[str, str, str]]:
    search_query = search_term(m)
    fixed_price = upwork_price_text(m)
    ai = uses_ai(m)
    build_day = (
        ("配置结构化模型草稿", "阿里云百炼 > Model Studio > API Key；Make > Scenario > HTTP > Make a request", "使用客户自有 key；模型选客户区域可用的 Qwen，Authorization 只放 Make secret；body 放本文件 JSON 提示词，输出映射到 draft_* 字段")
        if ai
        else ("建立确定性实施表", m["setup_path"], f"把 {m['input']} 拆成字段、确定性规则、owner、证据和回滚列；只实现合同明确要求的步骤")
    )
    qa_day = (
        ("加人工审批", "Make > Scenario > Router > Filter；目标工具 > Draft/approval queue", "低置信度、缺字段或高风险只进入 NEEDS_HUMAN；不得自动发送、拒绝、删除、支付、退款或发布")
        if ai
        else ("做反例与回滚测试", m["test_path"], "测试空值、重复、冲突、权限不足、断网和回滚；每例写预期/实际/证据，任何生产写入须客户逐项批准")
    )
    flow = (
        "source→deterministic rules→AI draft→human approval→destination→error queue→rollback"
        if ai
        else "source→deterministic checks→human approval→destination→error queue→rollback"
    )
    log_fields = "规则与模型版本" if ai else "规则/配置版本"
    edge_text = (
        "至少加入空值、重复、冲突、超长、权限拒绝、网络失败、回滚、恶意提示和低置信度各 1 例"
        if ai
        else "至少加入空值、重复、冲突、超长、权限拒绝、网络失败和回滚各 1 例"
    )
    days = [
        ("定边界", "Google Sheets > Blank spreadsheet；建 scope、baseline、risk 三个 tab", f"写入买方“{m['buyer']}”、固定范围“{m['offer']}”；产出一页范围，禁止扩到高风险动作"),
        ("核证据", "打开本文件“市场证据”中的全部官方链接；浏览器 > Bookmark folder", "逐条记录发布日期、事实与局限；如果关键链接失效，暂停宣传该事实"),
        ("建 30 个 ICP", f"Upwork > Find Work > Search jobs > 输入 {search_query}；公司官网只看 Contact/Team 通用入口", f"Sheets targets 列 company/source_url/why_fit/jurisdiction/entity_type/status；只录与“{m['pain']}”直接相关的 30 个主体，不抓个人数据"),
        ("量基线", "Google Sheets > baseline tab", f"输入最近 30 天 {m['metric']}；没有数字就记录样本量、当前耗时和错误例子"),
        ("开最小工具", m["setup_path"], f"只开试点所需功能；栈：{m['stack']}；保存账号 owner、权限、关闭/回滚路径截图"),
        ("收脱敏样本", "Google Drive > New > Folder > Share > Restricted", f"向测试客户索取：{m['input']}；密码/API key 不放文档"),
        ("发布固定价服务", normalized_path(m["publish_path"]), f"Upwork Price 字段输入 {fixed_price}；粘贴标题/范围/不包含项，技术验收与付款分开；账号或收款方式未 Active 就用另一合法平台，不伪造地区"),
        ("首批手工触达", "Upwork > Find Work > Search jobs > 打开 10 个强相关职位 > Apply now；或通过司法辖区闸门后 Gmail > Compose", f"每条引用 1 个真实公开观察，发送本文件文案；CTA 只要求脱敏样本，范围为“{m['offer']}”"),
        ("发现访谈", "Calendly > Event types > New event type > 20 min；Google Meet > New meeting", f"访谈 3 人，记录当前流程、{m['metric']} 基线、禁止自动动作、预算和采购人"),
        ("接受合法 Offer 并核验注资", "普通职位 > Apply now > 等客户 Offer > Messages > 对应会话 > View offer > Accept offer > Deliver work > Your active contracts；已至少付款一次的当前/旧客户 > Messages > 对应会话 > View contract > … > Propose new contract；有效 Project Catalog 主动询盘 > Messages > Propose new contract", f"直接购买 Catalog 的客户沿用现有已注资订单，不另发合同。所有分支都先核对范围、金额、截止日并确认当前 fixed-price milestone/order 为 Active/Funded；卖方不点击 Fund。付款路径：{payment_terms(m)} 商业验证是注资/付款；技术通过只看“{technical_acceptance(m)}”"),
        ("画实施流程", "diagrams.net > Create New Diagram；或 Sheets > flow tab", f"画 {flow}；客户确认后再构建"),
        ("做第一版规则", m["test_path"], f"先只处理 5 条/1 页/1 个对象；字段来自“{m['input']}”；保存 expected/actual/evidence，不做未经批准的生产写入"),
        build_day,
        qa_day,
        ("加审计日志", "Google Sheets > logs tab；目标工具 > 活动/错误/运行历史", f"记录 event_id、时间、输入 hash、{log_fields}、动作、审批人、错误和回滚；不记录无关 PII 或密钥"),
        ("回放约定样本", m["test_path"], f"执行技术验收：{technical_acceptance(m)}；另记录商业验证阈值：{m['validation']}"),
        ("提交首段并开下一段闸门", "Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Contract > Milestones", f"先完成本阶段技术验收与边界记录：{edge_text}。自定义多里程碑合同点击 Submit work 后，等客户批准且下一里程碑已注资才继续；若是一次注资的 Project Catalog 订单，只保留阶段证据，不提前提交整单"),
        ("隐私与回滚", "Google Docs > Blank > Data handling & rollback；Share > Restricted", "写数据区、最小权限、保留期、删除、撤权、备份、回滚负责人和恢复时间；客户书面确认"),
        ("录 90 秒证据演示", "QuickTime Player > File > New Screen Recording；或 OBS > Start Recording", f"按问题20秒→{m['offer']}30秒→测试30秒→边界10秒；遮住账号、密钥和客户数据"),
        ("第二批 10 个触达", "Upwork > Saved searches/Jobs；或已过闸门的 Gmail drafts", "只复用已验证的一页样例；每个对象写不同的公开观察，不自动化、不买名单"),
        ("一次跟进", "Upwork > Messages；或 Gmail > Sent > 对应线程 > Reply", "只跟进已联系对象一次，新增一条真实证据；退订立即写 suppression，之后停止"),
        ("确认执行范围未变", "Google Docs > Proposal > Version history；Upwork > Contract > Milestones", f"对照 Day 10 已注资合同，确认“{m['offer']}”、技术验收、权限、日期和停止条件未变；不重新谈或重复收试点"),
        ("运行已注资阶段", m["test_path"], "自定义合同只在下一里程碑已注资后运行；Project Catalog 只在整单已注资后运行。按客户批准的最小权限先 5、再 20、再到约定上限；高风险错误、真实扣款或不可回滚变更立即停"),
        ("每日 QA", "Sheets > logs/QA tab > Create a filter", f"每天抽查至少 10 条或全部小样本；只计算 {m['metric']}，保留分母、失败和不能归因部分"),
        ("读结果", "Sheets > baseline vs pilot；Looker Studio 可选", f"只对比 {m['metric']}；写样本量和不能归因的部分"),
        ("修一次", f"{m['stack']} > Duplicate/Clone/Version；仅在测试或副本中改", "只修最大的一类错误；保留 v1/v2、变更说明、回放结果和恢复点，不同时改多个变量"),
        ("交付并提交当前里程碑", "Google Docs > New > SOP；Drive > Restricted folder；Upwork > Deliver work > Your active contracts > 目标合同 > Submit work", "交付配置清单、账号 owner、日常检查、异常、回滚、数据删除和录屏并撤销多余权限；在 Upwork 写明本次交付、附文件/受限链接并点 Submit work，确认状态进入 in review；只发 Drive/邮件不算平台提交"),
        ("提续费", "Gmail > Compose/Reply；粘贴验收与复购话术", "只把已证明稳定的步骤做月费；列每月上限、响应时间和不包含项"),
        ("做案例", "Notion/官网 > New page/draft", "得到书面许可后才发布匿名案例；写基线、样本、结果、局限，不写客户机密"),
        ("查款并规模/停止", "Upwork > Manage finances > Financial overview；Manage finances > Transactions；Sheets > decision/cash-ledger", "逐项记录 funded/submitted/approved/pending/available/withdrawn/bank-arrived；只有 bank-arrived 写到账。通过条件：至少 1 个真实付费信号、验收达标、毛利可接受、无重大合规缺口；否则缩窄、换细分或停止")
    ]
    if m["id"] == 20:
        days[6] = ("投递三里程碑固定价方案", "Upwork > Find Work > Search jobs > Google Merchant Center feed > 打开匹配职位 > Apply now；Profile > Portfolio > Add project", "proposal 的 Fixed-price 总价填 US$500，并在附信写 US$250/US$150/US$100 三段交付与条件；这里只申请并附脱敏案例，不创建 Project Catalog、不替客户发 Offer 或 Fund")
        days[9] = ("接受客户三里程碑 Offer", "Upwork > Messages > 对应会话 > View offer > 核对 milestones > Accept offer > Deliver work > Your active contracts", "确认总价 US$500、三段为 US$250/US$150/US$100、范围和截止日正确，且里程碑1为 Active/Funded 后才开工；不创建 Catalog、不替客户点击 Fund")
        days[16] = ("提交里程碑1并等待第二段注资", "Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Contract > Milestones", "提交范围、权限、基线和回滚证据；等客户批准且里程碑2显示 Active/Funded 后才改上游数据，不提前做第2/3段")
        days[22] = ("只运行已注资的里程碑2", m["test_path"], "只有里程碑2 Active/Funded 才做约定上游修复并提交重抓/审核；保存 before/after 和 issue code，Processing/Under review 不算技术通过")
        days[27] = ("满足条件才提交第三里程碑", "Merchant Center > Products > Needs attention/All products > Status/Visibility；Upwork > Contract > Milestones > milestone 3 Funded；Deliver work > Your active contracts > Submit work", "只有里程碑2已批准、里程碑3已注资、目标商品为 Approved 且目标 destination visibility 通过时，才附证据并提交 US$100 第三里程碑；Processing/Under review/Not visible 时不提交、不宣称成功")
    if m["id"] == 28:
        days[6] = ("投递双里程碑固定价方案", "Upwork > Find Work > Search jobs > SPF DKIM DMARC > 打开匹配职位 > Apply now；Profile > Portfolio > Add project", "proposal 的 Fixed-price 总价填 US$360，并在附信写 US$180 审计/变更计划、US$180 p=none 上线后 7 天验收；这里只申请并附脱敏案例，不创建 Project Catalog、不替客户发 Offer 或 Fund")
        days[9] = ("接受客户双里程碑 Offer", "Upwork > Messages > 对应会话 > View offer > 核对 milestones > Accept offer > Deliver work > Your active contracts", "确认总价 US$360、两段各 US$180、范围和截止日正确，且里程碑1为 Active/Funded 后才开工；不创建 Catalog、不替客户点击 Fund")
        days[11] = ("完成初始只读认证审计", "Google Admin Toolbox > Check MX/Dig；每个合法发件源发 1 封到外部 Gmail > More > Show original；Sheets > baseline", "核对当前 SPF 条数/PermError、每个来源 DKIM 或 aligned SPF、DMARC 记录和 rua 接收状态；只记录基线，不声称已完成 7 天观察")
        days[13] = ("冻结变更与回滚单", "DNS 主机 > Records 只读；Docs > change plan；客户书面批准", "逐条写旧值、新值、TTL、owner、维护窗口和回滚值；测试冲突/权限不足/回滚，未批准不改 DNS")
        days[15] = ("做首段初始认证检查", "Google Admin Toolbox > Check MX/Dig；Gmail > Show original；Sheets > milestone-1 QA", "只验收发件源清单、DNS 基线、备份/回滚和测试邮件当前状态；明确 7 天 rua 报告尚未完成，不能把首段或付款写成最终技术通过")
        days[16] = ("提交里程碑1并等待第二段注资", "Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Contract > Milestones", "提交发件源清单、只读审计、变更/回滚计划；等客户批准且里程碑2显示 Active/Funded 后才上线 p=none，卖方不点击 Fund")
        monitor_paths = "DMARC 报告工具 > rua aggregate report；Google Admin Toolbox > Check MX；Sheets > seven-day log"
        days[17] = ("上线 p=none 并记录 Day 1/7", "DNS 主机 > Records > 按批准变更；" + monitor_paths, "仅在里程碑2 Active/Funded 和客户维护窗口内变更；确认 DMARC=p=none、SPF 无 PermError、合法源样本通过，保存前后值和回滚点")
        for offset in range(1, 7):
            day_index = 17 + offset
            days[day_index] = (f"复核 rua Day {offset + 1}/7", monitor_paths, "按合法发件源清单逐项记录 pass/fail/alignment/volume/unknown_source；任何未解释合法失败源当天升级 owner，不提高 DMARC policy")
        days[24] = ("完成 7 天技术验收", "Sheets > seven-day log > Filter；Google Admin Toolbox/Gmail Show original 复测", f"执行最终技术验收：{technical_acceptance(m)}；逐日、逐源保留分母和证据，未达标就写未通过")
        days[25] = ("通过则封版，失败则延长", "Docs > final QA/SOP；Upwork > Messages", "若 7 天验收通过，只整理证据不再改 DNS；若失败，书面说明原因、回滚/修复和新的完整 7 天窗口，本日不提交里程碑2、不伪造连续天数")
        days[26] = ("满足 7 天条件才提交里程碑2", "Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Sheets > seven-day log", "只有里程碑2 Active/Funded 且完整连续 7 天技术验收通过时，才附报告/SOP/回滚并点 Submit work；否则保持未提交并协商延期或回滚")
    if m["id"] == 50:
        days[0] = ("收款与范围双闸门", "Upwork > Account settings > Withdrawals > Add a method > Direct to Local Bank > Set up；Shopify 只读范围表", "中国 CNY 收款方式真实姓名一致；新方式 3 天激活、US$0.99/次，客户批准后还有 5 天安全期。范围只含 20 商品/variant、3 测试单和一次连续维护窗口")
        days[4] = ("做 5 商品只读样例", "Shopify Admin > Apps > Digital Products > Dashboard > Has digital file/No digital file > 点击商品 > Digital Products block；Sheets > sample", "逐 variant 记录 expected/actual asset、version、attachment status、fulfillment、download limit 和证据；只展示至少 1 条真实缺口，不替换或删除文件")
        days[6] = ("发布 US$215 固定价服务", "Upwork > Find Work > Your services > Create Project", "价格字段输入 US$215（按 US$1=¥7 折算约 ¥1,505）；粘贴标题、20 商品/3 测试单/一个连续窗口的范围和不包含项，不把人民币金额填进 USD 价格字段")
        days[9] = ("客户购买唯一完整试点", "Upwork > Find Work > Your services > 已发布 US$215 Project > 客户 Buy project > Fund", "一个 US$215 Project Catalog 订单一次全额注资；范围固定为映射表、20 商品、3 测试单、一次连续窗口、恢复结账、SOP 和技术验收，不另收第二个试点、不走替代账单")
        days[10] = ("完成 20 商品审计", "Shopify Admin > Apps > Digital Products > Dashboard > 点击商品 > Digital Products block；Sheets > mapping/QA", "20 商品每个 variant 都写 expected_asset/actual_asset/version/status/result/evidence；缺失、错版、链接和权限问题单列")
        days[11] = ("只做客户批准的修复", "Digital Products > Dashboard > 目标商品 > Digital Products block；Sheets > approval", "客户逐项勾选 approved 后才改附件、链接或限制；每项先记录既有买家影响、before 值和回滚值")
        days[12] = ("冻结测试计划", "Google Calendar > Create event；Shopify > Settings > Payments 只读截图", "书面确认 Day 14 低流量连续窗口、owner、三种订单、测试邮箱、入口前后截图和立即关闭步骤；明确 test mode 期间真实客户不能下单")
        days[13] = ("只开一次连续测试窗口", "Settings > Payments > Shopify Payments > Manage > Test mode > Enable test mode；完成单 variant/多 variant/版本补发 3 单；Apps > Digital Products > Orders > 订单 > Resend download email；Manage > Disable test mode", "Day 14 一次完成全部 3 单和补发，每单核对文件/链接/版本/邮件；立即关闭 test mode，用设置和真实结账页截图确认恢复，此后原试点不再重开")
        days[14] = ("整理唯一验收包", "Sheets > QA filter；Digital Products > Dashboard/Orders；Drive > Restricted folder", f"执行技术验收：{technical_acceptance(m)}；整理映射、三单、补发、test mode 已关闭、真实结账恢复、已知例外与 SOP；付款信号单列")
        days[15] = ("只提交一次", "Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Sheets > approval", "Day 16 写明完整交付、附验收包并只点一次 Submit work，确认进入 in review；之后只回应已交内容的问题，不追加测试窗口、不重复提交或重新议价")
        days[16] = ("处理一次验收反馈", "Upwork > Messages；Sheets > exceptions", "只澄清已交证据或修正文档；若必须重开 test mode 或扩大商品范围，只记录为 Day 30 后的独立合同候选；本轮不重开 test mode、不新增订单、不再次使用平台提交按钮")
        days[22] = ("只查付款状态", "Upwork > Manage finances > Financial overview；Manage finances > Transactions；Shopify > Settings > Payments", "Day 23 只记录 submitted/in review/approved、5 天安全期、pending/available 与真实结账仍恢复；不把注资/pending 写成银行到账，不重跑测试")
        days[25] = ("只修离线文档", "Sheets > mapping/exceptions > Duplicate v1 to v2；Docs > SOP > Version history", "只修映射表、例外说明或 SOP 的一类错误并保留 v1/v2；不进入 Shopify Payments、不重开 test mode、不改附件。需要再次实测或生产修改时另签后续独立窗口")
        days[26] = ("归档唯一提交后的最终证据", "Google Docs > SOP > Version history；Drive > Restricted；Upwork > Messages", "把最终映射表、SOP、录屏和删除/撤权记录归档到 Day 16 已提交的受限交付目录；只在 Messages 回答客户对已交内容的问题，不再使用平台提交按钮，不重置审核期")
        days[29] = ("按唯一订单门槛关闭试点", "Upwork > Manage finances > Transactions > Available balance > Withdraw earnings > Withdraw now；Shopify > Settings > Users and permissions；Sheets > closeout", f"Day 30 逐字核验商业门槛：{m['validation']}。同时记录 funded/approved/pending/available/withdrawn/bank-arrived，只有 bank-arrived 写到账；撤销多余权限并确认 test mode 关闭。本轮不重开测试、不新增订单；后续需求只能在本轮关闭后成为独立合同")
    return days


def data_days(m: dict) -> list[tuple[str, str, str]]:
    fixed_price = upwork_price_text(m)
    search_query = search_term(m)
    days = [
        ("定一条窄线", "Google Sheets > Blank > scope tab", f"写唯一买方“{m['buyer']}”、唯一数据主题和试点“{m['offer']}”；不先建泛平台"),
        ("查许可", "打开本文件全部官方来源 > Terms/API docs", "记录允许用途、署名/声明、限流、第三方权利和更新时间；许可不清时不收费、不处理真实数据、不交付，先取得书面分类"),
        ("取 10–20 条官方样本", m["setup_path"], "优先用官方 UI、Saved Search、CSV 或 Postman；保存筛选条件、日期、状态码/导出名和 official ID，不假设通用脚本支持该来源"),
        ("定义 schema", "Google Sheets > schema tab", "字段至少含 source_id、source_url、published_at、fetched_at、status、matched_reason、human_verified"),
        ("做人工样本", m["test_path"], "人工筛 20 条并逐条回链；把“真有用/无关/不确定”作为黄金标签"),
        ("写匹配规则", "Sheets > rules tab", f"输入：{m['input']}；把必须条件、加分项、排除词和人工核验写成可见规则"),
        ("保存官方筛选/请求", m["setup_path"], "保存官方 Saved Search、导出参数或 Postman collection；POST body、分页、认证和限流按该来源官方文档逐项记录，不用一个通用命令冒充全覆盖"),
        ("做增量与去重", "Google Sheets > Data > Data cleanup > Remove duplicates；以 official ID+status 建复合键", "只保留字段白名单；状态变化作为新事件，标题微调不重复推送；个人字段默认排除"),
        ("保留证据", "Sheets > output tab", "每条结果包含原链接、日期、抓取时间、匹配理由、原文短摘和人工核验状态"),
        ("出首份样报", "Google Docs > New from blank", f"只放 5–15 条最相关结果；页首写用途、来源和局限；结果目标：{m['outcome']}"),
        ("双人/二遍 QA", "Sheets > QA tab", "隔 24 小时重新核对 10 条或请同伴复核；记录误报和遗漏原因"),
        ("补人工增值", "Docs > sample report > Insert > Building blocks/Checklist", "加入资格/影响/材料缺口/行动问题、no-fit 原因、截止提醒和源链接；不只转发官方免费提醒"),
        ("发布固定价服务", normalized_path(m["publish_path"]), f"Upwork Price 字段输入 {fixed_price}；粘贴标题、样报、来源许可和免责声明，先卖人工报告，不卖未完成订阅软件"),
        ("列 20 个买方", f"Upwork > Find Work > Search jobs > 输入 {search_query}；Sheets > targets", "记录 company/source_url/why_fit/jurisdiction/entity_type；只用公司级通用入口，不抓个人邮箱或社媒数据"),
        ("首批 10 个触达", "Upwork > 打开匹配职位 > Apply now；或通过司法辖区闸门后 Gmail > Compose", "逐封附 3 条公开样报；真实身份、实体地址、隐私告知和退订齐全，不用追踪像素"),
        ("访谈并进入合法合同路径", "Calendly > Event types > 20 min；普通职位 > Apply now 后等待客户 Offer；仅已付款旧客户或主动从 Project Catalog 发消息的客户 > Propose new contract", f"访谈 3 人：上次错过什么、哪些字段最值钱、谁批准；Upwork 总价输入 {fixed_price}。普通职位客户必须由客户发送 Offer，卖方不能把 Propose new contract 当通用按钮；技术验收与付款分开"),
        ("核验首个付费阶段已注资", "Upwork > Offers/Your active contracts > Fixed-price > 当前 milestone/Project Catalog order > status", f"客户侧完成购买或注资；卖方只在当前段显示 Active/Funded 后接受/开工，绝不代客户点击 Fund。商业验证：{m['validation']}；未注资只保留样报，不继续做软件或批量采集"),
        ("重做筛选", "Sheets > rules tab > Duplicate v1 to v2", "只改最大误报来源；用原 20 条黄金集重新算精确率/召回率并保留 v1"),
        ("启动付费实时周", m["test_path"], "按官方更新频率手工/官方导出运行；每次记录筛选、响应/导出、条数、失败、版本和抓取日"),
        ("每日人审", "Sheets > human_verified filter", "发布前逐条打开原链接；状态不确定、权利不清或高风险一律不推送"),
        ("交付首段并开下一段", "Google Docs > File > Download > PDF；Upwork > Deliver work > Your active contracts > 目标合同 > Submit work；Contract > Milestones", "交付源链接、抓取日、匹配理由、局限和行动清单，不镜像第三方附件；自定义合同提交当前里程碑后，等客户批准并注资下一里程碑才继续；一次注资 Project Catalog 订单只发中期预览，不提前提交整单"),
        ("确认下一段已注资再看使用", "Upwork > Contract > Milestones；Sheets > customer feedback tab", f"自定义合同只在下一里程碑为 Active/Funded 后继续；询问哪些结果被打开/采取行动，只看 {m['metric']}，不把外部成交全部归因给报告"),
        ("修噪声", "Sheets > false-positive pivot", "按原因汇总误报；加入排除词或最小样本阈值，保留变更日志"),
        ("有条件半自动化", "仅兼容单一 JSON 响应时：终端 > python3 tools/feed_alert.py --help；否则继续官方 Saved Search/导出", "只有客户已付款、许可明确、字段白名单和 source-specific 请求/分页已写清时才自动抓取；通用脚本不替代 schema/权限判断，人审不取消"),
        ("验证字段最小化", "Sheets > schema > 保留 source_id/source_url/date/status/matched_reason；删除无关列", "检查输出、缓存和日志无 API key、含 key URL、评论者/联系人等无关个人数据；写删除日期"),
        ("一次跟进", "Upwork > Messages；或 Gmail > Sent > 对应线程 > Reply", "对未回复者只跟进一次并新增真实信号；收到退订立即写 suppression tab，之后停止"),
        ("设续费", "Google Calendar > Create recurring reminder；Upwork milestone/合法账单", "提前 7 天发真实使用摘要、下月范围和取消方式，不暗扣"),
        ("提交最终交付", "Google Docs > final report；Upwork > Deliver work > Your active contracts > 目标合同 > Submit work", "附最终 PDF/SOP/受限证据链接，在 Upwork 写明当前已注资里程碑的交付并点 Submit work；确认进入 in review。只发 Drive/邮件不启动审核期"),
        ("检查许可/成本与款项", "来源条款 + Sheets unit economics；Upwork > Manage finances > Financial overview/Transactions", "重查 API/许可/限流/人工分钟；逐项记录 funded/submitted/approved/pending/available，任何漂移立即调整或停更，不把 pending 写成到账"),
        ("查款并规模/停止", "Upwork > Manage finances > Financial overview；Manage finances > Transactions；Sheets > decision/cash-ledger", "记录 funded/submitted/approved/pending/available/withdrawn/bank-arrived；只有 bank-arrived 写到账。继续条件：至少 1 个真实付费信号、样报被实际使用、数据许可清楚、毛利可达；否则换垂直而非堆功能")
    ]
    exact_requests = {
        31: (
            "SAM.gov > Search > Contract Opportunities > Filters > NAICS/Place of Performance/Notice Type/Set Aside/Response Date > Apply",
            "严格按本文件 SAM 实施包取 10–20 条 notice ID；金额不是 API 硬过滤，缺失写 unknown；退出登录后逐条用 notice ID 回查公共链接",
            "Sheets > rules tab；SAM.gov 公共 Saved Search/筛选截图",
            "粘贴本文件六条金额硬规则，保存 filters、checked_at 和 public URL；SAM key 在 query 中，禁止交给通用 feed_alert.py 或写入报告",
        ),
        32: (
            "Postman > New > HTTP Request > POST > https://api.usaspending.gov/api/v2/search/spending_by_award/ > Body > raw > JSON",
            "原样粘贴本文件 USAspending JSON，点 Send；保存前 20 条 generated_internal_id，并用 https://www.usaspending.gov/award/{id}/ 回查",
            "Postman > Body > raw > JSON > page；Response > page_metadata.hasNext",
            "按本文件请求把 page=1,2...，到 hasNext=false；保存 collection。time_period 不得写成未来续约期，推断列必须 analyst_inference=yes",
        ),
        34: (
            "Postman > New > HTTP Request > POST > https://api.ted.europa.eu/v3/notices/search > Body > raw > JSON",
            "粘贴本文件 TED JSON，先可用 checkQuerySyntax=true 查语法，再改 false 取数；抽查 links.html.ENG 与双语字段",
            "Postman > Body > paginationMode/page/iterationNextToken；Response > links.html",
            "PAGE_NUMBER 增 page；超过 15,000 改 ITERATION 并传 token。只保存响应官方语言回链，不拼第三方 URL",
        ),
        35: (
            "Postman > New > HTTP Request；分别建立 Federal Register GET；Regulations.gov 先 Vault > Local Vault > Add new secret",
            "逐字粘贴本文件两个 URL；前者 No Auth，后者 Allowed domain=api.regulations.gov、Header X-Api-Key={{vault:REGULATIONS_GOV_API_KEY}}；确认 agencyId=FDA 后分别保存最多 10 条",
            "Postman > Federal Register next_page_url；Regulations.gov page[number]/meta.lastPage",
            "两源分别分页和落表；Federal Register 法律依赖打开 pdf_url，Regulations key 不进 URL/报告/日志，默认排除 comments 个人数据",
        ),
        38: (
            "Postman > New > GET > 本文件 report_date openFDA URL；低量 No Auth，生产 Basic Auth Username={{OPENFDA_API_KEY}}/Password blank",
            "按 skip=0,100...取样；用 recall_number 无 key 查询 URL 回链，非恰好 1 条标 NEEDS_HUMAN；不读取不存在的 source_url 字段",
            "Postman > GET https://api.fda.gov/download.json；Sheets > snapshots/hash",
            "先比 export_date；变化才下载全部 food.enforcement partitions 并做完整快照 diff，按 NEW_RECORD/FDA_DATA_REVISED/NEEDS_HUMAN 标记，不公开发布安全警报",
        ),
        39: (
            "Postman > New > GET > 本文件 ECHO get_facilities URL；Response > Results.QueryID",
            "复制 QueryID 到 get_qid URL，按 pageno 拉取；稳定 source_id 用 RegistryID，并打开 Detailed Facility Report 回查；只读取 FacDateLastInspection/FacDateLastFormalAction/FacDateLastPenalty",
            "Postman > get_qid > pageno；Sheets > events/date-filter",
            "到 Facilities 为空/少于 responseset 或达到 QueryRows；按 [as_of-29d, as_of] 过滤，以 RegistryID|event_type|event_date 去重；窗口内不足 20 条或为 0 条都如实报告",
        ),
        42: (
            "Census Developers > Request a Key；Postman > Vault > Local Vault > Add new secret > CENSUS_API_KEY；Allowed domains=api.census.gov；New > GET",
            "原样填 get/time=from+2025-01+to+2026-06/CTY_CODE=5700/I_COMMODITY=850440/key={{vault:CENSUS_API_KEY}}，点 Send；付款前只取样报所需 18 个月，保存 LAST_UPDATE、fetched_at 和不含 key 的官方回链",
            "Postman > Duplicate request > Params > CTY_CODE；Sheets > provenance",
            "付款前只为中国+2 个替代国各跑一个 18 个月请求，用前 6 个月对账、样报仅展示后 12 个月；其余三国和完整 60 月保持待办。月趋势只用 GEN_VAL_MO；key 不进截图/collection/report/log",
        ),
    }
    if m["id"] in exact_requests:
        day3_path, day3_action, day7_path, day7_action = exact_requests[m["id"]]
        days[2] = ("跑官方精确请求", day3_path, day3_action)
        days[6] = ("保存分页/增量契约", day7_path, day7_action)
    if m["id"] == 42:
        days[0] = ("定一个美国进口问题", "Google Sheets > Blank > scope tab", "唯一买方、一个 HS6、中国+5 个替代供应国、过去 60 个月；写明进口额只是需求代理，不承诺订单")
        days[1] = ("核条款、Vault 与归因声明", "打开 D15/D27/D29/D30/D31/P30；Docs > source-policy", "抄录允许 search/display/analyze/retrieve 的用途、访问限制、时间语法、字段定义、Schedule C 代码、Vault secret 路径和声明；报告显著写 This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau")
        days[4] = ("完成逐月/年累计等式 QA", "Sheets > QA > 按 CTY_CODE/I_COMMODITY/LAST_UPDATE/month 排序；Census 官方单月结果抽查", "1 月核 GEN_VAL_YR=GEN_VAL_MO；2–12 月核 YR(t)-YR(t-1)=MO(t)，跨年重置、容差 0；写 checked_equations、passed_equations、pass_rate，所有已取月份 100% 才通过")
        days[9] = ("出一页真实样报", "Google Docs > New；Sheets > pivot/chart", "只展示中国+2 国、最近 12 个月的真实官方数据、来源声明、修订日和局限；不把进口额写成销售或订单")
        days[15] = ("访谈并只给合法购买路径", "Calendly > Event types > 20 min；Upwork 普通职位 > Apply now；Project Catalog 主动询盘 > Messages", "访谈 3 人；普通职位等待客户 Offer，不使用 Propose new contract。需要试点者从已发布 US$215 Project Catalog 页面购买；卖方不点击 Fund、不走站外账单")
        days[16] = ("确认唯一订单已 Active/Funded", "Upwork > Deliver work > Your active contracts > 目标 US$215 Project Catalog order > status", "客户完成 Buy project 和一次全额注资；只有订单显示 Active/Funded 才开完整范围。未注资只保留中国+2 国/12 月样报，不取其余国家或 60 月数据")
        days[18] = ("启动已注资的完整取数", "Postman > Duplicate request > Params；time=from+2021-01+to+2026-06；Sheets > paid-run", "订单 Active/Funded 后，对中国+5 个替代国各跑一个 66 个月范围请求，用前 6 个月做累计值对账，最终只展示 2021-07 至 2026-06 的 60 个月；记录 LAST_UPDATE/fetched_at")
        days[20] = ("发送中期预览但不提交整单", "Upwork > Messages；Drive > Restricted preview；Sheets > QA", "只发 6 国 QA 结果、异常清单和报告目录；Project Catalog 是一次注资整单，Day 28 完成前不使用平台提交按钮，不把预览写成最终交付")
        days[21] = ("看客户如何使用 shortlist", "Upwork > Messages；Sheets > customer feedback", "询问哪些信号进入访谈/报价清单；只记录逐月值/年累计对账通过率、shortlist 采用数、后续访谈/报价数，不把外部成交全部归因给报告")
        days[23] = ("只做来源专用半自动化", "Postman Collection Runner 或客户批准的来源专用脚本；Sheets > runbook", "每国一个 time range 请求、低频缓存；Census key 必须在 query，所以禁止交给 feed_alert.py，分享请求前删已解析 key")
        days[26] = ("只起草后续范围，不提前收费", "Google Docs > follow-on draft；Upwork > Messages 保持草稿", "只写下月 HS6、国家、更新频率、价格与取消方式；当前 Project Catalog 订单尚未最终提交，不建新订单、不发站外账单、不暗扣")
        days[27] = ("提交唯一 Project Catalog 最终交付", "Google Docs > final report；Upwork > Deliver work > Your active contracts > 目标 US$215 Project Catalog order > Submit work", "附最终 PDF、QA、方法说明和受限证据链接，只点一次 Submit work 并确认进入 in review；不拆单、不重复提交、不把 Messages 预览算最终交付")
        days[28] = ("重查更新与单位经济", "Census API Terms/variables/LAST_UPDATE；Sheets > unit economics", "重查 key、字段、条款、4 月修订和人工分钟；记录本期 LAST_UPDATE，任何漂移先停更再修")
        days[29] = ("按商业门槛查款并决定", "Upwork > Manage finances > Financial overview；Manage finances > Transactions；Sheets > decision/cash-ledger", "记录 funded/submitted/approved/pending/available/withdrawn/bank-arrived，只有 bank-arrived 写到账；仅当 1 个 US$215 独立 Project Catalog 订单已 Active/Funded 且逐月/年累计等式 QA 100% 通过才 Go，否则 Stop 或缩窄范围")
    return days


def digital_days(m: dict) -> list[tuple[str, str, str]]:
    days = [
        ("先过账户/收款闸门", m["setup_path"], "用真实身份完成 KYC、税务和收款方式设置，记录 Active/Pending/Rejected；新账号无余额时不声称完成提现。首个真实订单后、扩量前再验证实际到账；失败则换合法渠道，不伪造地区"),
        ("锁定一个买方", "Google Sheets > Blank > audience tab", f"只写“{m['buyer']}”中的一个最窄子群和一个高频问题：{m['pain']}"),
        ("手工竞品表", "目标平台 > Search；Sheets > competitors tab", "手工记录 20 个相近商品的价格、页数/文件、差评和缺口；不抓取，不复制内容"),
        ("写最小购买承诺", "Google Docs > New", f"承诺只写“{m['outcome']}”；固定 MVP：{m['offer']}；区分已完成可交付 beta、服务预售和平台预售规则，不承诺收入"),
        ("建权利清单", "Sheets > rights tab", "每个字体、照片、图标、数据、音频标 own/license/source/allowed-use；不明权利立即替换"),
        ("做 20% MVP", "Canva/Docs/课程工具 > Create", "只完成可展示的 20%，使用真实结构和虚构示例；先不做多语言/大套装"),
        ("加完整示例", "产品编辑器 > Duplicate template/page", f"用一个完整示例演示输入→使用→结果；验收指标：{m['metric']}"),
        ("可用性测试", m["test_path"], "在新账户/无缓存环境从购买文件开始操作；记录缺字体、权限、公式、链接、移动端问题"),
        ("打包", "Finder > New Folder；Docs > README", "文件名版本化；加入安装/复制、许可、退款/支持、更新日期和联系入口"),
        ("写商品页", "Google Docs > listing-copy", "粘贴本文件标题、卖点、包含/不含、适用/不适用、FAQ、许可和真实预览"),
        ("做预览", "Canva > Share > View-only/Download；视频 > 60–90 秒", "预览展示实际页面和操作，不用虚假销量、评价或倒计时"),
        ("招 5–10 个 beta", "行业社群/客户网络；逐个手工联系", "发带水印预览和明确 beta 价格；只联系强相关对象，拒绝刷单/互评"),
        ("定价格", "Sheets > unit economics", f"参考“{m['price']}”；算平台费、退款、支持工时和税前毛利，低于 70% 就缩支持范围"),
        ("打开首个合法付费入口", normalized_path(m["publish_path"]), f"按最小验证执行：{m['validation']}；未完成数字商品不得冒充可即时交付产品，服务合同写交付日、改期和退款条件"),
        ("首批手工推广", "Gmail/社群允许的发帖入口 > Compose", "发布一个有用的免费片段和真实制作过程；不群发、不自动私信、不买假互动"),
        ("一次跟进", "Gmail > Sent > Reply；社群原帖更新", "只跟进已表达兴趣的人，补一个具体预览；不回复即停止"),
        ("交付 beta", "平台 > Orders/Members/Students > Message/Post", "按承诺发送，附 README、许可、版本和支持入口；记录每位 beta 是否能打开"),
        ("收结构化反馈", "Google Forms > Blank form", "问：购买原因、首次使用卡点、最有用/多余内容、愿付价格、是否愿意退款；不要求好评"),
        ("只修前三项", "产品源文件 > Duplicate v0.1 to v0.2", "按出现频次修 3 个阻塞问题；保留 changelog，不无限加功能"),
        ("正式发布", normalized_path(m["publish_path"]), "上传 v1、真实预览、准确标签、AI/素材披露、许可、退款/支持和更新日期；平台审核/到账延迟单独记录"),
        ("首周支持", "平台 > Messages/Comments；Sheets > support log", "24–48 小时内回复；把重复问题写 FAQ，不承诺未排期功能"),
        ("做教程内容", "YouTube/图文平台 > Create draft", "发布 3 个免费教程：常见错误、完整示例、适用边界；每条指向商品页但先提供价值"),
        ("找 3 个伙伴", "行业作者/顾问官网 > Contact；手工邮件", "提出演示/分成/团队许可；明确披露关联关系，不买暗广"),
        ("优化检索", "平台 > Edit listing > Title/Description/Tags", "只用买家真实用词；不塞无关品牌、竞品名或受保护商标"),
        ("做一项加购", "源文件 > New add-on", "只做用户已请求的加购，如团队许可/定制/更新包；不捆绑无关内容"),
        ("检查可访问/本地化", "产品编辑器 > Accessibility/语言检查", "检查对比度、alt、键盘/字体和一个目标语言；法律文本不机械翻译"),
        ("看真实数据", "平台 > Analytics/Sales；Sheets > dashboard", f"记录访问、预售、退款、支持和 {m['metric']}；小样本不外推"),
        ("完善退款/支持", "平台 > Settings > Policies/FAQ", "写清数字商品访问问题处理、版本、支持时限和合理退款；遵守平台强制政策"),
        ("排 30 天 backlog", "Notion/Sheets > backlog", "只按购买者频次、收入和维护成本排序；未付款意见不自动进入路线图"),
        ("按商业门槛规模/停止", "Sheets > decision tab", f"逐字核验商业门槛：{m['validation']}。只有该门槛达到、收款/KYC 通过、权利清楚且支持可控才 Go；否则交付/退款现有承诺并停止或换细分")
    ]
    if m["id"] in (44, 46, 47):
        platform_path = (
            "Creative Market > Open a Shop > Tax and Payout Setup"
            if m["id"] in (44, 46)
            else "Udemy > Instructor > Payout settings"
        )
        days[0] = (
            "先过 Upwork/平台收款闸门",
            f"Upwork > Account settings > Withdrawals > Add a method > Direct to Local Bank > Set up；{platform_path}",
            "真实姓名与银行一致；中国 CNY 可用，新收款方式 3 天激活，US$0.99/次，提现后通常 4 天内到银行。Project Catalog/fixed-price 客户批准后还有 5 天安全期；Day 1 只记录 Active/Pending/Rejected，不伪造地区或到账。",
        )
        days[16] = ("交付并提交唯一订单", "平台交付文件/直播；Upwork > Deliver work > Your active contracts > 目标合同 > Submit work", "完成约定 beta/直播后，在 Upwork 写明交付、附文件/受限链接并点一次 Submit work，确认进入 in review；只发消息/Drive 不启动审核期，不拆第二订单")
        days[26] = ("看销售与收益状态", "目标平台 > Analytics/Sales；Upwork > Manage finances > Financial overview；Manage finances > Transactions；Sheets > cash-ledger", f"记录 {m['metric']} 及 Upwork submitted/in review/approved/pending/available/withdrawn/bank-arrived；只有 bank-arrived 写到账，小样本不外推")
    if m["id"] in (44, 46):
        days[4] = ("建立双渠道权利清单", "Sheets > rights tab；每项填 channel/creator/source/exclusive_ip/canva_pro", "Creative Market ZIP 只允许 self-created + exclusive_ip=yes；Canva Pro 素材仅在允许的 template link/定制版本中使用，不进入 CM 产品文件")
        days[5] = ("完成可交付 beta", "Canva/PowerPoint > Create/Duplicate；Finder > Compress", f"完整做出本方法约定的 8/10 个 beta 资产和 README，而非 20% 占位；结果必须能立即交付：{m['offer']}")
        usd_price = 72 if m["id"] == 44 else 29
        target_orders = 2 if m["id"] == 44 else 3
        days[13] = ("用 Project Catalog 卖单次 beta", "Upwork > Find Work > Your services > Create Project > Publish > Copy project URL", f"单次固定价 US${usd_price}，客户直接购买并一次注资；不用 Propose new contract 联系陌生客户。验证：{m['validation']}；Creative Market Add a Product 只在完整文件完成后使用")
        days[16] = ("逐单交付并逐单提交", "每个已成交订单 > 平台交付文件；Upwork > Deliver work > Your active contracts > 对应合同 > Submit work", f"对每个独立客户的 US${usd_price} Project Catalog 订单，完成该单约定 beta 后分别附交付并各点一次 Submit work；同一订单不得重复提交，也不得把同一客户范围拆单凑数。Day 30 需达到 {target_orders} 个独立全额注资订单")
        days[19] = ("完整商品再上架", "Creative Market > Shop > Add a Product > Upload Product ZIP > Screenshots > Price > Publish", "ZIP 只含自制独占资产；选择平台许可、列文件格式/兼容软件/包含与不含、AI 披露，不自创“团队许可”冒充平台许可")
    elif m["id"] == 47:
        days[13] = ("售卖企业直播试点", "Upwork > Find Work > Your services > Create Project > Publish > Copy project URL", "单次固定价 US$143，客户直接购买并一次注资；交付 60 分钟直播+5 个模板，写改期/退款；15 分钟样课只作预览，不能提交 Udemy")
        days[19] = ("满足标准后提交 Udemy", "Udemy Instructor > Courses > Curriculum > 检查总视频≥30分钟且 lectures≥5 > Submit for Review", "补齐学习目标、课程描述、讲师资料、720p/1080p、双声道音频和 AI 披露后才提交")
    elif m["id"] == 48:
        days[11] = ("邀请 10 名免费 beta", "行业社群允许的发帖入口/客户网络 > 手工发布；Google Forms > Send", "粘贴本文件免费 beta 文案；不收款、不要求 Amazon 评价、不自动私信，Drive 链接 Restricted/Viewer")
        days[13] = ("招募免费 beta 读者", "Google Forms > Blank form；Drive > Restricted viewer link", "免费提供 7 天带版本水印样章，不收人民币 PDF 款；记录 10 人中完成 Day1–3 的人数")
        days[16] = ("收回 beta 反馈", "Forms > Responses > Link to Sheets", "至少 5 人完成 Day1–3 才继续；只修理解阻塞、错误和排版问题")
        days[19] = ("终稿后创建 KDP 预售", "KDP > Bookshelf > + Create > Create eBook > Pre-order > release date > 选择 Day 27 GMT > Upload final manuscript > Submit for pre-order", "只有 60–100 页终稿、封面、元数据和 Previewer 通过后提交；截图保存 Day 27 发行日与提交 deadline，发行前只统计 Pre-Order Report 净预售单，不写版税")
        days[22] = ("找 3 名岗位专家核读", "行业作者/顾问官网 > Contact；手工邮件", "邀请核对事实、流程和风险，不要求 Amazon 评价；贡献须获书面许可并在致谢/来源中准确披露")
        days[24] = ("做勘误与样章页", "Google Docs > New > Errata；KDP > Edit details 可选", "只维护公开勘误、版本和免费样章，不销售站外团队许可或未经授权的附件")
        days[26] = ("确认 Day 27 已发行", "KDP > Bookshelf > 目标 eBook > Status；打开 Amazon 商品页；KDP > Reports > Pre-Orders Report", "只有状态为 Live 且预售已在发行日交付才通过；记录 live_at、预售单、取消和净预售数，未 Live 就停止宣传并处理平台提示")
        days[27] = ("无重复地核对净付费购买", "KDP > Reports > Pre-Orders Report；Orders/Month-to-Date；Sheets > reconciliation", "净付费购买=净预售单+发行后非预售净销量；按订单来源/日期去重，不能把同一预售在交付后再算一次")
        days[28] = ("只记录实际显示的版税", "KDP > Reports > Royalties Estimator/Prior Months' Royalties；Sheets > cash ledger", "只抄报表已显示金额并标 estimated/earned/paid；Day 28 没显示就写 0/unknown，不用销量×70% 冒充已应计或到账")
        days[29] = ("按 Live 与净付费购买决策", "Sheets > decision tab；KDP > Bookshelf/Reports", "继续条件：eBook 已 Live、净付费购买至少 5 单、无权利/审核缺口且支持可控；否则兑现现有订单与支持、记录原因并停止扩量")
    elif m["id"] == 45:
        days[5] = ("完成可即时交付商品", "Canva > Create a design > Presentation；Google Sheets > Share > Make a copy link；Finder > Compress", "完成 12 页 media kit、tracker、示例数据、README、许可和版本；Day 14 Patreon 发布后买家会立即解锁，因此不能只做 20% 占位")
    return days


def app_days(m: dict) -> list[tuple[str, str, str]]:
    days = digital_days(m)
    replacements = {
        3: ("做人工 concierge", "Shopify Admin > Products > Export；Sheets > diff tab", "先不用代码，手工完成 100 SKU 审计并收第一笔钱；确认客户真的在乎 diff/no-translate"),
        4: ("写最小 PRD", "Google Docs > New PRD", "只保留读取商品/翻译、diff、禁译命中、CSV 导出、人工批准；排除订单/客户/自动写回"),
        5: ("建权限清单", "Shopify docs > Protected customer data/API scopes", "列 read_products/read_translations 等最小权限、保留期、删除和卸载 webhook"),
        6: ("建测试店", "Shopify Partner/Dev Dashboard > Stores > Add store", "创建 20 个测试 SKU、2 个语言、5 个故意错误；不使用客户真实订单/个人数据"),
        7: ("搭骨架", "终端 > Shopify CLI/Node project；Git > new private repo", "实现 OAuth/session、只读查询、SQLite 和 CSV；密钥仅放环境变量"),
        8: ("实现 diff", "Shopify GraphiQL > products/translations query；本地测试", "对 source/target 做版本 hash、no-translate/单位规则和 NEEDS_REVIEW 状态"),
        9: ("安全/错误处理", "本地 app > logs；Shopify webhook test", "实现卸载删除、限流重试、空字段、分页和权限拒绝；日志不含客户内容全文"),
        10: ("装单店 custom app", m["setup_path"], "客户 owner 明确批准 scopes；先只读 20 SKU，再到 100 SKU；不自动写回"),
        11: ("跑验收", m["test_path"], f"执行：{m['validation']}；记录发现、误报、人工分钟和失败"),
        12: ("收 custom pilot", "Upwork fixed contract/合法账单", "按固定范围收费，签数据处理/支持/删除边界；未付款不走公开 App Store"),
        13: ("做用户测试", "Meet > screen share；Forms > feedback", "观察商家自己找 3 个过期翻译、导出 CSV、标记已审；不要代替用户点击"),
        14: ("修最大阻塞", "Git > branch fix-pilot；测试店", "只修导致不能完成核心任务的前三项；跑回归和权限测试"),
        15: ("写隐私与支持", "Docs > Privacy policy/Support/Security", "写收集字段、用途、地区、保留、删除、联系、SLA；不复制模板后不改"),
        16: ("决定是否付 $19", "Sheets > decision tab；Shopify Partner > Apps", "只有 ≥1 个付费 pilot 且每月节省 ≥2 小时才注册公开分发"),
        17: ("准备 App listing", m["publish_path"], "真实截图、定价、scope、支持、隐私、演示店；不写未经证明的翻译准确率"),
        18: ("准备审核", "Shopify App requirements checklist", "测试安装、计费、卸载删除、GDPR webhooks、错误页和帮助文档"),
        19: ("第二家 pilot", "Shopify custom distribution；客户自有测试店", "用不同主题/目录验证分页和兼容；仍保持只读和人工批准"),
        20: ("发布或继续服务", m["publish_path"], "审核成本可控才提交；否则保留高毛利人工审计+custom app，不强行 SaaS")
    }
    for index, value in replacements.items():
        days[index - 1] = value
    return days


def day_plan(method: dict) -> str:
    if method["archetype"] == "service":
        days = service_days(method)
    elif method["archetype"] == "data":
        days = data_days(method)
    elif method["archetype"] == "app":
        days = app_days(method)
    else:
        days = digital_days(method)
    assert len(days) == 30, (method["id"], len(days))
    rows = ["| 天 | 今天具体做什么 | 工具/点击路径 | 输入、输出与通过条件 |", "|---:|---|---|---|"]
    for number, (action, path, io) in enumerate(days, 1):
        rows.append(f"| Day {number} | {esc(action)} | {esc(path)} | {esc(io)} |")
    return "\n".join(rows)


def method_markdown(m: dict) -> str:
    risks = "\n".join(f"- **风险：{r[0]}**　应对：{r[1]}" for r in m["risks"])
    scores = " / ".join(f"{name} {value}" for name, value in zip(SCORE_NAMES, m["score"]))
    source_keys = "、".join(method_source_keys(m))
    next_line = (
        f"方法{m['id']}已完成，开始方法{m['id'] + 1}调研。"
        if m["id"] < 50
        else "方法50已完成，开始最终对比表与执行优先级排序。"
    )
    c, b, o = m["monthly"]
    buyer_phrase = m["buyer"][2:] if m["buyer"].startswith("面向") else m["buyer"]
    ai_prompt = prompt_block(m) if uses_ai(m) else ""
    copy_material = digital_copy(m) if m["archetype"] == "digital" else common_copy(m)
    if m["id"] == 42:
        automation_note = "本方法明确不使用通用 `feed_alert.py`：Census key 位于 query。只使用 Postman Local Vault/Collection Runner 或客户批准的来源专用脚本，并在分享、截图和日志前移除已解析 key。"
    elif m["archetype"] == "data":
        automation_note = "本方法的 MVP 以官方 UI、Saved Search、CSV/导出、Postman 与人工核验为准。只有单一 JSON 响应与许可、schema、分页都已确认时，才可选用 [字段白名单 Feed 增量脚本](../tools/feed_alert.py)；它不提供来源专用分页、权限判断或多源实体匹配。"
    else:
        automation_note = "本方法不依赖通用抓取脚本；优先使用客户自有平台的测试/副本/导出能力。"
    return f"""# 方法 {m['id']:02d}｜{m['title']}

> **一页结论：**面向{buyer_phrase}，用「{m['offer']}」先收费验证。启动现金成本 {m['cost']}，目标是 {m['metric']}。这里的报价和收益是**本报告的测试模型，不是行业均价或收益保证**。

## 0. 执行卡

| 项目 | 内容 |
|---|---|
| 分类 | {m['category']} |
| 买方 | {m['buyer']} |
| 当前痛点 | {m['pain']} |
| 可交付结果 | {m['outcome']} |
| 最小试点 | {m['offer']} |
| 工具栈 | {m['stack']} |
| 启动成本 | {m['cost']}（不含自己的人工） |
| 时间 | {m['time']} |
| 技能 | {m['skills']} |
| 参考测试报价 | {m['price']} |
| 最小验证 | {m['validation']} |
| 综合分 | {score(m):.2f}/5；{scores} |

## 1. 为什么现在能赚钱

赚钱逻辑不是“AI/数据/模板很火”，而是把 **{m['pain']}** 变成一个买方能验收的固定范围结果：**{m['outcome']}**。先用人工和低成本工具交付，客户确认价值后才把重复步骤自动化；这样现金投入低，也避免先做没人买的软件。

### 当前市场证据

{source_bullets(m)}

### 竞品与切入

{m['competitor']}。因此不要卖“我会某个工具”，要卖一条窄结果、真实回放、人工审批、可回滚交付和后续维护。

**证据依赖提醒：**本方法使用来源 {source_keys}。它们支持市场/渠道/工具事实，但不直接证明你的细分客户会购买；付费意愿必须由本方案的预售试点验证。

## 2. 产品、价格与单位经济

### 固定范围产品

- **名称：**{m['title']} 30 天验证包
- **交付：**{m['offer']}；另附基线、测试记录、异常清单、SOP、回滚/删除说明。
- **客户输入：**{m['input']}
- **验收指标：**{m['metric']}
- **参考报价：**{m['price']}

### 月收益情景（税前可计收入；数字平台按文中分成/版税模型）

| 情景 | 本报告假设 | 预估月营收 |
|---|---|---:|
| 保守 | {scenario_text(m, 0)} | {money(c)} |
| 中性 | {scenario_text(m, 1)} | {money(b)} |
| 乐观 | {scenario_text(m, 2)} | {money(o)} |

- **回本周期：**{payback_model(m)}
- **毛利闸门：**试点结束统计实际工时、工具费、平台费、退款与支持。税前贡献毛利低于 60% 时，不扩量，先提价或缩范围。
- **停止条件：**30 天无付费、关键验收失败、平台/KYC 不可用、数据许可不清或必须靠违规抓取/群发才能获客，立即停止或换细分。

## 3. 最小验证方案

1. 不先做完整产品；只做「{m['offer']}」。
2. 使用公开信息或客户主动提供的脱敏样本，不先索要管理员、支付或生产写权限。
3. **商业验证门槛：**{m['validation']}
4. **技术验收门槛：**{technical_acceptance(m)}
5. 只做 10–30 个强相关潜在买方的人工触达；不买名单、不抓 LinkedIn、不做自动群发。
6. 失败也要留数据：拒绝原因、价格、真实工时、误报/漏报和客户不用的功能，作为是否换细分的依据。

## 4. Day 1–30 落地日历

{day_plan(m)}

## 5. 可复制注册、发布、销售与交付文案

{copy_material}

## 6. 可直接使用的实施包、提示词与自动化边界

{implementation_pack(m)}

{ai_prompt}

{automation_note}

## 7. 主要风险与预设应对

{risks}
- **渠道风险：**平台 KYC、收款、费率和功能会变。Day 1 只验证真实账户、税务与收款方式状态；首个真实余额后再验证到账，失败则换合法渠道，不伪造地区。
- **归因风险：**外部销量、转化或中标受多因素影响。只报告试点可测指标、样本量和局限。
- **外联风险：**只做人工、相关、低量外联，使用真实身份/地址/退订；不得抓取、自动私信或骚扰。

## 8. 30 天结束时的 Go / Iterate / Stop

- **Go：**达到本方法的商业验证门槛：“{m['validation']}”；关键验收达标；贡献毛利可接受；交付不依赖违规或单点人工英雄主义。
- **Iterate：**有人愿付但范围或价格错；只改最大障碍，再跑一个 7–14 天试点。
- **Stop：**Day 30 未达到上述商业验证门槛、存在重大合规/许可问题、收款不可用或价值只能靠不可验证承诺成立。

> **{next_line}**
"""


def build_readme() -> str:
    ranked = execution_ranked()
    rows = [
        "| 排名 | 方法 | 类型 | 启动成本 | 难度 | 付费验证 | 保守/月 | 中性/月 | 乐观/月 | 杠杆 | 综合分 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, m in enumerate(ranked, 1):
        path = f"methods/{m['id']:02d}-{m['slug']}.md"
        rows.append(
            f"| {rank} | [{m['id']:02d} {esc(m['title'])}]({path}) | {esc(m['category'])} | {esc(m['cost'])} | {difficulty(m)}/5 | {validation_days(m)} 天 | {money(m['monthly'][0])} | {money(m['monthly'][1])} | {money(m['monthly'][2])} | {m['score'][4]}/5 | {score(m):.2f} |"
        )
    index_lines = []
    for m in METHODS:
        index_lines.append(f"{m['id']:02d}. [{m['title']}](methods/{m['id']:02d}-{m['slug']}.md) — {m['offer']}")
    top_methods = {m["id"]: m for m in METHODS}
    return f"""# 2026 年 50 个低成本赚钱项目：完整执行包

> **研究快照：2026-09-01。** 适用对象是中国境内个人或 1–3 人团队，优先面向全球线上客户；默认现金预算不超过 ¥10,000，优先低于 ¥2,000，并要求 30 天内能验证真实付费。所有收益均为透明情景假设，不是保证；涉及 USD 的统一换算模型为 US$1=¥7，执行日必须以平台与银行实际汇率/费用替换。

## 先做哪三个最稳

1. **[{top_methods[20]['title']}](methods/20-{top_methods[20]['slug']}.md)**：Google Merchant Center 直接给出 issue code、Product status 和 destination visibility；现金成本近零，先修一个错误类别即可收费。技术尾款只在商品 Approved 且目标 visibility 通过后触发，不承诺展示、点击或销量。
2. **[{top_methods[1]['title']}](methods/01-{top_methods[1]['slug']}.md)**：企业 AI 落地仍低，而 Upwork 的 AI integration 需求增长；这个项目直接缩短首响和减少漏单，可按设置费+监控费销售。关键是规则优先、人工审批、不自动拒绝。
3. **[{top_methods[22]['title']}](methods/22-{top_methods[22]['slug']}.md)**：GA4 电商事件必须显式实施，测试订单可以做金额、币种和去重验收；交付边界清楚，失败也能定位到具体事件，而不是争论“营销有没有变好”。

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

{chr(10).join(index_lines)}

## 整体执行优先级与清晰对比表

排名 1–3 是综合当前买方可达性、技术验收确定性和中国执行边界后人工选出的首做顺序；第 4 名起按统一加权综合分排序。难度 1 最低、5 最高；杠杆 5 最高。服务/数据项目列为税前毛营收；数字平台项目按方法文中的分成/版税假设折算可计收入。均未扣人工、税、退款和支持，不是利润或收入保证。

{chr(10).join(rows)}

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
"""


def build_report_source() -> str:
    source_rows = ["| ID | 来源 | 本报告采用事实 | 局限/边界 |", "|---|---|---|---|"]
    for key, src in SOURCES.items():
        source_rows.append(f"| {key} | [{esc(src['title'])}]({src['url']}) | {esc(src['fact'])} | {esc(src['caveat'])} |")
    candidate_rows = ["| ID | 方法 | 类别 | 分数 | 关键来源 | 最小付费验证 |", "|---:|---|---|---:|---|---|"]
    for m in METHODS:
        candidate_rows.append(f"| {m['id']} | {esc(m['title'])} | {esc(m['category'])} | {score(m):.2f} | {', '.join(method_source_keys(m))} | {esc(m['validation'])} |")
    return f"""# 研究底稿：50 个赚钱项目

## 范围与时间

- 快照日：2026-09-01。
- 执行者：中国境内个人或 1–3 人团队，允许服务全球客户，但不绕地区、支付、数据或平台限制。
- 启动现金优先低于 ¥2,000、上限默认 ¥10,000；30 天内必须能验证真实付费。
- 本底稿保留“来源事实 → 方法假设 → 最小付费验证”的链条。

## 第一轮候选与停止条件

三条互斥通道共扫描 105 个候选：34 个 B2B/AI/电商服务、36 个公共数据/情报、35 个数字产品/平台机会。达到每条通道至少 25 个候选、关键来源饱和、主要渠道/许可边界可判定后停止广搜。最终选择 50 个，优先结果可测、低成本、快收费、可复购、可自动化和风险可控。

## 统一评分

`总分 = 需求证据×20% + 验证速度×15% + 低成本×10% + 复购性×15% + 自动化杠杆×15% + 获客可达×15% + 风险可控×10%`。每项 1–5 分。分数用于排序，不替代真实预售。

## 证据账本

{chr(10).join(source_rows)}

## 50 个方法的 Claim-to-Source 映射

{chr(10).join(candidate_rows)}

## 主要矛盾和处理

- AI 专业整合需求上升，但低复杂度 AI 执行收入下降：因此只保留有业务指标、规则、评测和人工审批的结果型服务。
- Shopify/Canva 等平台已内置大量功能：因此不卖“打开开关”，而卖目录清理、QA、数据一致性、测试和持续运营。
- 免费公共数据充足，但付费意愿不是数据本身：因此公共数据项目先逐源确认商业用途；许可清楚后才卖人工、窄领域、带资格/行动清单的周报，预售后才自动化。许可不清则只用合成数据演示结构，不收费、不交付真实数据。
- 数字产品可高杠杆但同质化和收款风险更高：因此只选有具体买方、完整示例、许可层和可行渠道的 6 个产品；先 KYC/提现、再制作。
- 平台/供应商数据可能带偏：每个来源保留局限，关键市场判断由不同类型来源交叉支撑，最终仍用 30 天付费实验裁决。
"""


def write_csvs() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    ranked = execution_ranked()
    with (ASSET_DIR / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["排名", "ID", "方法", "类别", "启动成本", "难度1-5", "验证周期天", "保守月营收", "中性月营收", "乐观月营收", "杠杆1-5", "综合分", "参考报价", "最小验证"])
        for rank, m in enumerate(ranked, 1):
            writer.writerow([rank, m["id"], m["title"], m["category"], m["cost"], difficulty(m), validation_days(m), *m["monthly"], m["score"][4], score(m), m["price"], m["validation"]])
    with (ASSET_DIR / "lead-tracker.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["公司", "公开通用入口", "相关公开观察", "方法ID", "首次人工联系日期", "状态", "下次动作", "退订/勿扰", "备注"])
        writer.writerow(["示例公司-请删除", "contact@example.com", "只填真实公开观察", "20", "2026-09-01", "未联系", "个性化后发送", "否", "禁止自动群发或抓个人数据"])
    with (ASSET_DIR / "unit-economics.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["项目", "订单数", "单价", "平台费率", "每单工具费", "每单工时", "目标时薪", "固定成本", "营收", "贡献毛利"])
        writer.writerow(["示例-请替换", 3, 5000, 0.1, 100, 8, 200, 300, "=B2*C2", "=I2-I2*D2-B2*E2-B2*F2*G2-H2"])
    with (ASSET_DIR / "experiment-log.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["日期", "方法ID", "假设", "动作", "样本量", "现金花费", "工时", "结果", "证据链接/文件", "继续/迭代/停止", "下一步"])


def main() -> None:
    assert len(METHODS) == 50
    ids = [m["id"] for m in METHODS]
    assert ids == list(range(1, 51)), ids
    for m in METHODS:
        for key in m["sources"]:
            assert key in SOURCES, (m["id"], key)
    METHOD_DIR.mkdir(parents=True, exist_ok=True)
    for m in METHODS:
        path = METHOD_DIR / f"{m['id']:02d}-{m['slug']}.md"
        path.write_text(method_markdown(m), encoding="utf-8")
    (ROOT / "README.md").write_text(build_readme(), encoding="utf-8")
    (RESEARCH / "report-source.md").write_text(build_report_source(), encoding="utf-8")
    write_csvs()
    print(f"built {len(METHODS)} methods in {ROOT}")


if __name__ == "__main__":
    main()
