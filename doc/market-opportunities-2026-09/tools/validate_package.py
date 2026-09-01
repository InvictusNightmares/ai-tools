#!/usr/bin/env python3
"""Validate the generated research package without network access."""

from __future__ import annotations

import json
import re
from pathlib import Path

from feed_alert import spreadsheet_safe_cell


ROOT = Path(__file__).resolve().parents[1]
METHODS = json.loads((ROOT / "research" / "methods.json").read_text(encoding="utf-8"))
SOURCES = json.loads((ROOT / "research" / "sources.json").read_text(encoding="utf-8"))
REQUIRED = [
    "## 0. 执行卡",
    "## 1. 为什么现在能赚钱",
    "## 2. 产品、价格与单位经济",
    "## 3. 最小验证方案",
    "## 4. Day 1–30 落地日历",
    "## 5. 可复制注册、发布、销售与交付文案",
    "## 6. 可直接使用的实施包、提示词与自动化边界",
    "## 7. 主要风险与预设应对",
    "## 8. 30 天结束时的 Go / Iterate / Stop",
]


def main() -> None:
    errors: list[str] = []
    files = sorted((ROOT / "methods").glob("*.md"))
    if len(files) != 50:
        errors.append(f"expected 50 method files, found {len(files)}")
    if [m["id"] for m in METHODS] != list(range(1, 51)):
        errors.append("method IDs are not exactly 1..50")
    for method in METHODS:
        path = ROOT / "methods" / f"{method['id']:02d}-{method['slug']}.md"
        if not path.exists():
            errors.append(f"missing {path.name}")
            continue
        text = path.read_text(encoding="utf-8")
        days = [int(x) for x in re.findall(r"^\| Day (\d+) \|", text, flags=re.MULTILINE)]
        if days != list(range(1, 31)):
            errors.append(f"{path.name}: day rows are not exactly 1..30: {days}")
        for heading in REQUIRED:
            if heading not in text:
                errors.append(f"{path.name}: missing {heading}")
        if "月收益情景" not in text or "保守" not in text or "中性" not in text or "乐观" not in text:
            errors.append(f"{path.name}: missing revenue scenarios")
        expected_transition = f"方法{method['id']}已完成"
        if expected_transition not in text:
            errors.append(f"{path.name}: missing transition sentence")
        go_section = text.split("## 8. 30 天结束时的 Go / Iterate / Stop", 1)[-1]
        if method["validation"] not in go_section:
            errors.append(f"{path.name}: Go gate does not preserve the method's commercial validation threshold")
        for key in method["sources"]:
            if key not in SOURCES:
                errors.append(f"{path.name}: unknown source {key}")
            elif f"**{key}｜[" not in text:
                errors.append(f"{path.name}: source {key} not rendered")
        for rel in re.findall(r"\]\((?!https?://|#)([^)]+)\)", text):
            if not (path.parent / rel).resolve().exists():
                errors.append(f"{path.name}: broken local link {rel}")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for method in METHODS:
        rel = f"methods/{method['id']:02d}-{method['slug']}.md"
        if rel not in readme:
            errors.append(f"README missing link {rel}")
    local_links = re.findall(r"\]\((?!https?://|#)([^)]+)\)", readme)
    for rel in local_links:
        if not (ROOT / rel).exists():
            errors.append(f"README broken local link: {rel}")
    for tool in ("unit_economics.py", "feed_alert.py", "validate_package.py"):
        if not (ROOT / "tools" / tool).exists():
            errors.append(f"missing tool {tool}")

    # Release gates for the highest-risk commercial and operational boundaries.
    method35 = (ROOT / "methods" / "35-regulatory-radar.md").read_text(encoding="utf-8")
    for phrase in (
        "filter%5BagencyId%5D=FDA",
        "Postman > Vault > Local Vault > Add new secret",
        "Allowed domain",
        "api.regulations.gov",
        "X-Api-Key: {{vault:REGULATIONS_GOV_API_KEY}}",
        "agencyId=FDA",
        "**P30｜[",
    ):
        if phrase not in method35:
            errors.append(f"method 35 missing FDA/Vault gate: {phrase}")
    for phrase in ("X-Api-Key: {{REGULATIONS_GOV_API_KEY}}", "变量类型 Secret", "Postman > Environments > Add"):
        if phrase in method35:
            errors.append(f"method 35 contains superseded Postman secret path: {phrase}")

    method39 = (ROOT / "methods" / "39-epa-echo-leads.md").read_text(encoding="utf-8")
    for phrase in (
        "p_st=DC&p_act=Y&p_maj=Y",
        "FacDateLastInspection",
        "FacDateLastFormalAction",
        "FacDateLastPenalty",
        "[as_of-29d, as_of]",
        "RegistryID|event_type|event_date",
        "窗口内为 0 条时如实交付零事件报告",
    ):
        if phrase not in method39:
            errors.append(f"method 39 missing narrow executable ECHO gate: {phrase}")
    for phrase in ("设施类型", "许可变化", "许可与合规事件"):
        if phrase in method39:
            errors.append(f"method 39 overclaims unsupported ECHO scope: {phrase}")

    method42 = (ROOT / "methods" / "42-census-us-import-brief.md").read_text(encoding="utf-8")
    for phrase in (
        "Census 对美进口 HS6",
        "CENSUS_API_KEY",
        "{{vault:CENSUS_API_KEY}}",
        "Allowed domains",
        "GEN_VAL_MO",
        "GEN_VAL_YR",
        "LAST_UPDATE",
        "from+2025-01+to+2026-06",
        "from+2021-01+to+2026-06",
        "passed_equations / checked_equations",
        "容差为 0",
        "Active/Funded",
        "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.",
        "US$215",
        "feed_alert.py",
        "**D30｜[",
        "**D31｜[",
    ):
        if phrase not in method42:
            errors.append(f"method 42 missing Census data gate: {phrase}")
    for phrase in (
        "UN Comtrade",
        "active Premium",
        "subscriptions@un.org",
        "Current value",
        "key={{CENSUS_API_KEY}}",
        "集中度",
        "US$108/US$107",
        "Fund milestone",
        "Upwork milestone/合法账单",
        "只有单一 JSON 响应与许可、schema、分页都已确认时",
    ):
        if phrase in method42:
            errors.append(f"method 42 contains superseded source path: {phrase}")
    method42_submit_days = re.findall(r"^\| Day (\d+) \|[^\n]*Submit work", method42, flags=re.MULTILINE)
    if method42_submit_days != ["28"]:
        errors.append(f"method 42 must submit its one Catalog order only on Day 28, found days {method42_submit_days}")
    if "提交唯一 Project Catalog 最终交付" not in method42 or "只点一次 Submit work" not in method42:
        errors.append("method 42 Day 28 must submit the one funded Catalog order exactly once")
    day7 = re.search(r"^\| Day 7 \|.*$", method42, flags=re.MULTILINE)
    day19 = re.search(r"^\| Day 19 \|.*$", method42, flags=re.MULTILINE)
    if not day7 or "中国+2" not in day7.group(0) or "18 个月" not in day7.group(0) or "60 月保持待办" not in day7.group(0):
        errors.append("method 42 Day 7 must remain a three-country sample and defer the 60-month scope")
    if not day19 or "Active/Funded" not in day19.group(0) or "66 个月" not in day19.group(0) or "60 个月" not in day19.group(0):
        errors.append("method 42 Day 19 must run the full paid scope only after funding")

    method6 = (ROOT / "methods" / "06-internal-sop-assistant.md").read_text(encoding="utf-8")
    for phrase in ("注资/支付 ¥6,000", "30 问引用正确率至少 90%", "付款只验证购买意愿"):
        if phrase not in method6:
            errors.append(f"method 6 missing paid/technical split: {phrase}")

    technical_validation_terms = (
        "准确率", "召回率", "零差异", "节省至少", "全部走通", "零阻断", "术语抽检",
        "恢复成功", "功能测试通过", "指标改善", "无重复任务", "宏采用率", "行动项",
    )
    for method_id in range(1, 31):
        method = METHODS[method_id - 1]
        if not method.get("acceptance"):
            errors.append(f"method {method_id} must have an explicit technical acceptance separate from payment")
        if not any(marker in method["validation"] for marker in ("注资", "支付", "购买", "首月")):
            errors.append(f"method {method_id} validation must be a real commercial payment signal")
        mixed = [term for term in technical_validation_terms if term in method["validation"]]
        if mixed:
            errors.append(f"method {method_id} validation mixes technical criteria into the commercial gate: {mixed}")

    upwork_method_ids = list(range(1, 45)) + [46, 47, 50]
    for method_id in upwork_method_ids:
        method = METHODS[method_id - 1]
        path = ROOT / "methods" / f"{method_id:02d}-{method['slug']}.md"
        text = path.read_text(encoding="utf-8")
        for phrase in (
            "Deliver work > Your active contracts",
            "Manage finances > Financial overview",
            "**P31｜[",
            "**P32｜[",
            "**P35｜[",
        ):
            if phrase not in text:
                errors.append(f"{path.name}: missing Upwork closure path: {phrase}")
        for phrase in (
            "Contract workroom > Submit work",
            "Reports > Pending/Available",
            "试点固定价 ¥",
            "固定试点价 ¥",
        ):
            if phrase in text:
                errors.append(f"{path.name}: contains superseded Upwork path or CNY price: {phrase}")
    for method_id in range(1, 44):
        method = METHODS[method_id - 1]
        path = ROOT / "methods" / f"{method_id:02d}-{method['slug']}.md"
        text = path.read_text(encoding="utf-8")
        if method_id not in (20, 28) and "Upwork Price 字段输入 US$" not in text:
            errors.append(f"{path.name}: missing explicit Upwork USD Price field")

    for method_id in range(1, 31):
        method = METHODS[method_id - 1]
        text = (ROOT / "methods" / f"{method_id:02d}-{method['slug']}.md").read_text(encoding="utf-8")
        for phrase in ("Messages > 对应会话 > View offer", "Accept offer", "Active/Funded"):
            if phrase not in text:
                errors.append(f"method {method_id} missing executable Offer acceptance path: {phrase}")
        if "卖方不点击 Fund" not in text and "不替客户点击 Fund" not in text:
            errors.append(f"method {method_id} must state that the seller never funds the client milestone/order")

    for method_id, total, milestones in ((20, "US$500", "US$250/US$150/US$100"), (28, "US$360", "两段各 US$180")):
        method = METHODS[method_id - 1]
        text = (ROOT / "methods" / f"{method_id:02d}-{method['slug']}.md").read_text(encoding="utf-8")
        for forbidden in ("Your services > Create Project", "**M30｜["):
            if forbidden in text:
                errors.append(f"method {method_id} must not publish a conflicting one-payment Catalog project: {forbidden}")
        for phrase in ("Apply now", "View offer", "Accept offer", total, milestones, "不创建 Catalog"):
            if phrase not in text:
                errors.append(f"method {method_id} missing custom milestone-only path: {phrase}")

    method20 = (ROOT / "methods" / "20-merchant-feed-repair.md").read_text(encoding="utf-8")
    method20_submit_days = re.findall(r"^\| Day (\d+) \|[^\n]*Submit work", method20, flags=re.MULTILINE)
    if method20_submit_days != ["17", "27", "28"]:
        errors.append(f"method 20 must submit its three funded milestones on Days 17, 27, 28 only: {method20_submit_days}")

    method28 = (ROOT / "methods" / "28-email-deliverability.md").read_text(encoding="utf-8")
    method28_submit_days = re.findall(r"^\| Day (\d+) \|[^\n]*Submit work", method28, flags=re.MULTILINE)
    if method28_submit_days != ["17", "27"]:
        errors.append(f"method 28 must submit milestone 1 then the completed seven-day milestone only: {method28_submit_days}")
    day16_28 = re.search(r"^\| Day 16 \|.*$", method28, flags=re.MULTILINE)
    day25_28 = re.search(r"^\| Day 25 \|.*$", method28, flags=re.MULTILINE)
    day27_28 = re.search(r"^\| Day 27 \|.*$", method28, flags=re.MULTILINE)
    if not day16_28 or "尚未完成" not in day16_28.group(0):
        errors.append("method 28 Day 16 must be an initial check, not the seven-day acceptance")
    if not day25_28 or "7 天技术验收" not in day25_28.group(0):
        errors.append("method 28 must finish the complete seven-day technical check on Day 25")
    if not day27_28 or "完整连续 7 天技术验收通过" not in day27_28.group(0):
        errors.append("method 28 Day 27 must submit milestone 2 only after the full seven-day pass")

    method50 = (ROOT / "methods" / "50-shopify-digital-delivery-audit.md").read_text(encoding="utf-8")
    for phrase in (
        "价格字段输入 US$215",
        "不走替代账单",
        "只开一次连续测试窗口",
        "只提交一次",
        "不重开 test mode",
    ):
        if phrase not in method50:
            errors.append(f"method 50 missing single-order/window gate: {phrase}")
    if "试点固定价 ¥1,505" in method50 or "或等值合法账单" in method50:
        errors.append("method 50 contains a conflicting currency or alternate payment path")
    if "另签新窗口" in method50 or "只记录为 Day 30 后的独立合同候选" not in method50:
        errors.append("method 50 must defer any new test window or order until after Day 30")
    day30_50 = re.search(r"^\| Day 30 \|.*$", method50, flags=re.MULTILINE)
    if not day30_50 or METHODS[49]["validation"] not in day30_50.group(0):
        errors.append("method 50 Day 30 must preserve its exact one-order commercial gate")
    method50_submit_days = re.findall(r"^\| Day (\d+) \|[^\n]*Submit work", method50, flags=re.MULTILINE)
    if method50_submit_days != ["16"]:
        errors.append(f"method 50 must click Submit work only on Day 16, found days {method50_submit_days}")

    for method_id, expected in ((44, "2 个独立全额注资订单"), (46, "3 个独立全额注资订单")):
        method = METHODS[method_id - 1]
        text = (ROOT / "methods" / f"{method_id:02d}-{method['slug']}.md").read_text(encoding="utf-8")
        day17 = re.search(r"^\| Day 17 \|.*$", text, flags=re.MULTILINE)
        if not day17 or "逐单交付并逐单提交" not in day17.group(0) or expected not in day17.group(0) or "同一订单不得重复提交" not in day17.group(0):
            errors.append(f"method {method_id} Day 17 does not preserve its independent-order threshold")
        day30 = re.search(r"^\| Day 30 \|.*$", text, flags=re.MULTILINE)
        if "独立客户各自购买并全额注资" not in method["validation"] or not day30 or method["validation"] not in day30.group(0):
            errors.append(f"method {method_id} must preserve the exact independent-customer gate through Day 30")

    for method_id in (45, 49):
        method = METHODS[method_id - 1]
        text = (ROOT / "methods" / f"{method_id:02d}-{method['slug']}.md").read_text(encoding="utf-8")
        for phrase in ("87.1%", "1.55%+US$0.25", "不逐笔扣 2.5% FX"):
            if phrase not in text:
                errors.append(f"method {method_id} missing corrected Patreon fee boundary: {phrase}")
        if "84.6%" in text:
            errors.append(f"method {method_id} still applies Patreon FX per order")
        day30 = re.search(r"^\| Day 30 \|.*$", text, flags=re.MULTILINE)
        if not day30 or method["validation"] not in day30.group(0):
            errors.append(f"method {method_id} Day 30 must preserve its exact commercial gate")

    method47 = (ROOT / "methods" / "47-udemy-role-ai-course.md").read_text(encoding="utf-8")
    for phrase in ("**P33｜[", "**P34｜[", "This course contains the use of artificial intelligence."):
        if phrase not in method47:
            errors.append(f"method 47 missing Udemy AI rule: {phrase}")
    day30_47 = re.search(r"^\| Day 30 \|.*$", method47, flags=re.MULTILINE)
    if not day30_47 or METHODS[46]["validation"] not in day30_47.group(0):
        errors.append("method 47 Day 30 must preserve its exact commercial gate")

    if "Day 1 先过账户、权限、数据许可和收款方式 Active 闸门" in readme:
        errors.append("README incorrectly claims all methods complete commercial gates on Day 1")
    if "首次发布、报价或签约前" not in readme:
        errors.append("README missing the cross-method pre-publication commercial gate")

    top_positions = [readme.find(f"methods/{method_id:02d}-") for method_id in (20, 1, 22)]
    if any(position < 0 for position in top_positions) or top_positions != sorted(top_positions):
        errors.append("README top-three order is not 20, 1, 22")

    feed_script = (ROOT / "tools" / "feed_alert.py").read_text(encoding="utf-8")
    for phrase in ("old_origin != new_origin", "refusing cross-origin redirect"):
        if phrase not in feed_script:
            errors.append(f"feed_alert.py missing redirect secret-safety gate: {phrase}")
    for payload in ("=1+1", "+SUM(A1:A2)", "-2+3", "@cmd", "  =HYPERLINK(\"https://example.invalid\")", "\tformula"):
        if not str(spreadsheet_safe_cell(payload)).startswith("'"):
            errors.append(f"feed_alert.py failed to neutralize spreadsheet formula payload: {payload!r}")
    for payload in ("ordinary text", "https://example.org/source", 42):
        if spreadsheet_safe_cell(payload) != payload:
            errors.append(f"feed_alert.py changed a safe CSV value: {payload!r}")
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"VALIDATION OK: {len(files)} methods, 1,500 day rows, {len(SOURCES)} source records")


if __name__ == "__main__":
    main()
