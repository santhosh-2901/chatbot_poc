"""Answer the MVP's five questions with no LLM involved.

Run this to see exactly what the agent's tools hand the model. Every number is
computed and every passage retrieved; none of it is generated. If a figure looks
wrong in the finished chatbot, it is wrong here first.

Usage:  python scripts/demo_analysis.py
"""

from __future__ import annotations

import _bootstrap  # noqa: F401  # must precede any app import

from app.analysis import (
    affordability_check,
    budget_status,
    compare_months,
    recommend_budget,
    summarize_month,
)
from app.rag import search

USER = "USER001"


def rule(title: str) -> None:
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def question(text: str) -> None:
    print(f'\n  User: "{text}"\n')


def main() -> None:
    rule("1. Where am I spending the most?")
    question("Where am I spending the most money?")
    summary = summarize_month(USER)
    print(f"  summarize_month(user_id={USER!r}) -> month {summary.month}")
    print(f"    income {summary.income:,}   expenses {summary.expenses:,}   "
          f"net {summary.net:,}   savings rate {summary.savings_rate}%")
    for category in summary.categories:
        bar = "#" * round(category.share_of_expenses / 2)
        print(f"    {category.category.value:<15}{category.amount:>8,}  "
              f"{category.share_of_expenses:>5}%  {bar}")

    rule("2. Why did I spend more this month?")
    question("Why did I spend more this month?")
    comparison = compare_months(USER)
    print(f"  compare_months({comparison.previous_month} -> {comparison.current_month})")
    print(f"    expenses {comparison.previous_expenses:,} -> "
          f"{comparison.current_expenses:,}")
    print(f"    change {comparison.expense_change:+,} "
          f"({comparison.percentage_change:+}%)  [{comparison.direction.value}]")
    print("    by category:")
    for change in comparison.category_changes:
        if change.change:
            pct = f"{change.percentage_change:+}%" if change.percentage_change is not None else "new"
            print(f"      {change.category.value:<15}{change.change:>+8,}  ({pct})")
    print(f"    largest increase: {comparison.largest_increase.category.value} "
          f"{comparison.largest_increase.change:+,}")

    rule("3. Can I afford a 40,000 phone?")
    question("Can I afford a 40,000 phone?")
    assessment = affordability_check(USER, 40000)
    print(f"  affordability_check(purchase_amount=40000) -> {assessment.status.value}")
    print(f"    available this month      {assessment.available_discretionary_amount:>8,}")
    print(f"    savings balance           {assessment.savings_balance:>8,}")
    print(f"    upcoming obligations      {assessment.upcoming_expenses_total:>8,}")
    print(f"    savings after those       {assessment.savings_after_upcoming:>8,}")
    print(f"    months to save            {assessment.months_to_save_from_cash_flow:>8}")
    print("    reasons the LLM will narrate:")
    for reason in assessment.reasons:
        print(f"      - {reason}")

    rule("4. What is the 50/30/20 rule?")
    question("What is the 50/30/20 rule?")
    passages, method = search("What is the 50/30/20 rule?", k=2)
    print(f"  search_financial_knowledge() -> {method} retrieval")
    for passage in passages:
        print(f"    [{passage.source} - {passage.section}]")
        first = passage.text.strip().splitlines()
        body = " ".join(line for line in first if not line.startswith("#"))
        print(f"      {body[:150]}...")
    print("     This question needs no user data at all, which is why the")
    print("     router sends it to the knowledge base rather than to a tool.")

    rule("5. How can I reduce my spending?")
    question("How can I reduce my spending based on my transactions?")
    status = budget_status(USER)
    print(f"  budget_status({status.month}) -> "
          f"{status.total_actual:,} spent against {status.total_budgeted:,} budgeted")
    for line in status.lines:
        flag = "OVER" if line.variance > 0 else ""
        print(f"    {line.category.value:<15}{line.actual:>8,} / {line.budgeted:>7,}"
              f"  {line.variance:>+7,}  {line.status.value:<9}{flag}")

    plan = recommend_budget(USER)
    print(f"\n  recommend_budget() based on {', '.join(plan.based_on_months)}")
    for line in plan.lines:
        kind = "essential" if line.essential else "discretionary"
        print(f"    {line.category.value:<15}{line.recommended:>8,}"
              f"   vs average {line.change_from_average:>+7,}   {kind}")
    print(f"    {'Savings':<15}{plan.recommended_savings:>8,}")
    print(f"    method: {plan.method}")
    if plan.notes:
        for note in plan.notes:
            print(f"    note: {note}")

    print(f"\n  {plan.disclaimer}\n")


if __name__ == "__main__":
    main()
