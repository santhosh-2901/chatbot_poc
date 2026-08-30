"""Deterministic financial analysis.

The source of truth for every number the assistant states. Nothing in this
package knows that an LLM exists — these are plain functions over validated
data, and they are tested without a model in the loop (spec section 25).

Phase 5 wraps these in LangChain tools. That wrapping layer adds descriptions
and argument schemas; it adds no arithmetic.
"""

from app.analysis.affordability import affordability_check
from app.analysis.budget import budget_status, recommend_budget
from app.analysis.comparison import compare_months
from app.analysis.summary import (
    analyze_category,
    average_monthly,
    cash_flow,
    summarize_month,
    total_expenses,
    total_income,
)

__all__ = [
    "affordability_check",
    "analyze_category",
    "average_monthly",
    "budget_status",
    "cash_flow",
    "compare_months",
    "recommend_budget",
    "summarize_month",
    "total_expenses",
    "total_income",
]
