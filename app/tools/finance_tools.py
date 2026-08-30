"""The agent's tools.

Three design decisions carry most of the weight here.

**Tools are bound to one user.** ``build_finance_tools`` closes over a
``user_id`` rather than exposing it as a tool argument. A model that can pass an
arbitrary user id is a model that can read someone else's finances by
hallucinating "USER002", and no prompt reliably prevents that. Removing the
parameter removes the failure mode.

**Failures return, they do not raise.** An invalid month comes back as an
``error`` dict naming the valid months, so the model can correct itself on the
next turn instead of the conversation dying on a stack trace.

**Descriptions are written for routing, not for humans.** Each one says when to
use the tool *and when not to*. That contrast is what stops the model reaching
for ``get_monthly_summary`` when the question is really a comparison. The
concrete month and category lists are appended at build time — a docstring
cannot be an f-string, since that would leave ``__doc__`` empty and ``@tool``
with nothing to describe.
"""

from __future__ import annotations

from typing import Any, Callable

from langchain_core.tools import BaseTool, tool

from app.analysis import (
    affordability_check,
    analyze_category,
    budget_status,
    compare_months,
    recommend_budget,
    summarize_month,
)
from app.models.schemas import EXPENSE_CATEGORIES, Category
from app.services import transaction_service as tx
from app.services.data_loader import DataError
from app.tools.knowledge_tool import build_knowledge_tools

VALID_CATEGORIES = ", ".join(c.value for c in EXPENSE_CATEGORIES)


def _safe(call: Callable[[], Any]) -> dict:
    """Run a tool body, turning expected failures into a reportable result."""
    try:
        result = call()
    except (DataError, ValueError) as exc:
        return {"error": str(exc)}
    return result.model_dump(mode="json")


def _resolve_category(name: str) -> Category:
    """Accept whatever casing the model produces."""
    for category in EXPENSE_CATEGORIES:
        if category.value.casefold() == name.strip().casefold():
            return category
    raise ValueError(f"Unknown category {name!r}. Valid categories: {VALID_CATEGORIES}.")


def build_finance_tools(user_id: str) -> list[BaseTool]:
    """Build the tool set for one user."""

    @tool
    def get_monthly_summary(month: str | None = None) -> dict:
        """Total income, total expenses, net cash flow and the full category
        breakdown for a single month, with categories ranked by amount.

        Use this for: where is my money going, what did I spend in total, what
        is my biggest expense, how much did I earn, what is my savings rate.

        Do NOT use this to compare two months - use compare_two_months. Do NOT
        use it for detail on a single category - use analyze_spending_category.
        """
        return _safe(lambda: summarize_month(user_id, month))

    @tool
    def analyze_spending_category(category: str, month: str | None = None) -> dict:
        """Detail on ONE spending category in one month: total, transaction
        count, average transaction, largest single transaction, top merchants,
        the budget for that category, and the month-by-month history.

        Use this for: how much did I spend on food, where did my shopping money
        go, am I over budget on transport, is my food spending unusual.
        """
        return _safe(
            lambda: analyze_category(user_id, _resolve_category(category), month)
        )

    @tool
    def compare_two_months(
        current_month: str | None = None, previous_month: str | None = None
    ) -> dict:
        """Compare two months' spending and return the per-category change,
        ranked, plus the largest increase and the largest decrease.

        Use this whenever the user asks why spending changed: why did I spend
        more, what drove my expenses up, how does this month compare with last
        month, did I improve.

        Both arguments are optional. By default this compares the most recent
        month with the one before it, which is what "this month versus last
        month" almost always means.
        """
        return _safe(lambda: compare_months(user_id, current_month, previous_month))

    @tool
    def check_budget(month: str | None = None) -> dict:
        """Compare actual spending against the user's existing budget, line by
        line, and list which categories were breached.

        Use this for: am I over budget, how am I tracking, which categories did
        I overspend on, where can I cut back.

        Do NOT use this to propose a new budget - use suggest_budget.
        """
        return _safe(lambda: budget_status(user_id, month))

    @tool
    def suggest_budget(lookback_months: int = 3) -> dict:
        """Propose a new monthly budget derived from recent spending history.

        Use this for: help me make a budget, how should I plan next month, what
        should I be spending, give me a savings plan.

        Do NOT use this to check performance against the current budget - use
        check_budget.

        Args:
            lookback_months: How many recent months to base the plan on, 1 to 12.
        """
        return _safe(lambda: recommend_budget(user_id, lookback_months))

    @tool
    def check_affordability(purchase_amount: int, month: str | None = None) -> dict:
        """Assess whether a one-off purchase is affordable, weighing monthly
        surplus, savings, upcoming obligations and emergency-fund coverage.

        Returns a status of COMFORTABLE, CAUTION or NOT_ADVISABLE together with
        the specific reasons behind it. Report the status and those reasons as
        given - do not soften, upgrade or override the verdict.

        Use this for: can I afford X, should I buy X, is now a good time to
        spend X.

        Args:
            purchase_amount: The cost in whole rupees, for example 40000.
        """
        return _safe(lambda: affordability_check(user_id, purchase_amount, month))

    @tool
    def list_transactions(
        month: str | None = None, category: str | None = None, limit: int = 10
    ) -> dict:
        """List individual transactions, newest first.

        Use this only when the user wants to see actual line items: what did I
        buy, show me my recent transactions, where did I shop. This tool does
        not aggregate - for totals use get_monthly_summary.

        Args:
            limit: Maximum number of transactions to return, 1 to 50.
        """
        try:
            resolved = tx.resolve_month(user_id, month) if month else None
            chosen = _resolve_category(category) if category else None
            rows = tx.get_transactions(user_id, month=resolved, category=chosen)
        except (DataError, ValueError) as exc:
            return {"error": str(exc)}

        newest = sorted(rows, key=lambda t: (t.date, t.transaction_id), reverse=True)
        capped = newest[: max(1, min(limit, 50))]
        return {
            "month": resolved,
            "category": chosen.value if chosen else None,
            "returned": len(capped),
            "total_matching": len(rows),
            "transactions": [
                {
                    "date": t.date.isoformat(),
                    "merchant": t.merchant,
                    "category": t.category.value,
                    "type": t.type.value,
                    "amount": t.amount,
                }
                for t in capped
            ],
        }

    tools: list[BaseTool] = [
        *build_knowledge_tools(),
        get_monthly_summary,
        analyze_spending_category,
        compare_two_months,
        check_budget,
        suggest_budget,
        check_affordability,
        list_transactions,
    ]

    # Ground the descriptions in this user's actual data, so the model never has
    # to guess whether a month exists or invent a category name.
    months = ", ".join(tx.available_months(user_id))
    latest = tx.latest_month(user_id)
    month_hint = (
        f"\n\nMonths are YYYY-MM. This user has data for: {months}. "
        f"Omit the month argument to use the most recent month ({latest}). "
        "Never invent a month outside that list."
    )
    category_hint = f"\n\nValid categories: {VALID_CATEGORIES}."

    for item in tools:
        arguments = item.args
        if "month" in arguments or "current_month" in arguments:
            item.description = item.description.rstrip() + month_hint
        if "category" in arguments:
            item.description = item.description.rstrip() + category_hint

    return tools
