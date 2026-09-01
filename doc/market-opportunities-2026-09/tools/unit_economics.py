#!/usr/bin/env python3
"""Small unit-economics calculator for a project or monthly offer."""

from __future__ import annotations

import argparse
import json
import math


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Calculate revenue and contribution margin before tax.")
    p.add_argument("--orders", type=int, required=True, help="Paid orders or subscribers in the period")
    p.add_argument("--price", type=float, required=True, help="Revenue per order")
    p.add_argument("--platform-fee-pct", type=float, default=0.0, help="Platform/payment fee percentage, e.g. 10")
    p.add_argument("--tool-per-order", type=float, default=0.0)
    p.add_argument("--hours-per-order", type=float, default=0.0)
    p.add_argument("--hourly-cost", type=float, default=0.0, help="Your target hourly cost; do not treat your labor as free")
    p.add_argument("--fixed-cost", type=float, default=0.0)
    p.add_argument("--currency", default="CNY")
    return p


def main() -> None:
    args = parser().parse_args()
    if args.orders < 0 or args.price < 0 or not 0 <= args.platform_fee_pct <= 100:
        raise SystemExit("orders/price must be non-negative and fee must be between 0 and 100")
    revenue = args.orders * args.price
    platform_fee = revenue * args.platform_fee_pct / 100
    tools = args.orders * args.tool_per_order
    labor = args.orders * args.hours_per_order * args.hourly_cost
    contribution = revenue - platform_fee - tools - labor - args.fixed_cost
    margin = contribution / revenue * 100 if revenue else 0.0
    break_even_orders = None
    unit_contribution = args.price * (1 - args.platform_fee_pct / 100) - args.tool_per_order - args.hours_per_order * args.hourly_cost
    if unit_contribution > 0:
        break_even_orders = math.ceil(args.fixed_cost / unit_contribution)
    result = {
        "currency": args.currency,
        "orders": args.orders,
        "revenue": round(revenue, 2),
        "platform_fee": round(platform_fee, 2),
        "tools": round(tools, 2),
        "labor": round(labor, 2),
        "fixed_cost": round(args.fixed_cost, 2),
        "contribution": round(contribution, 2),
        "contribution_margin_pct": round(margin, 2),
        "break_even_orders": break_even_orders,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
