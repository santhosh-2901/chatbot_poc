"""Structured results returned by the analysis engine.

Every figure the assistant states must originate in one of these objects.

They are deliberately verbose — shares, percentages, rankings, counts and
averages are all precomputed. That is the point. A field the model needs but
cannot find is an invitation to do mental arithmetic, and mental arithmetic is
exactly what section 25 of the spec forbids. Cheap to compute here, unreliable
to compute there.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.models.schemas import Category, UpcomingExpense

#: Attached to any output that could be mistaken for advice (spec section 26).
DISCLAIMER = (
    "This is an informational assessment based on your recorded transactions, "
    "not professional financial advice."
)


class Frozen(BaseModel):
    """Results are read-only; a caller must not be able to edit a total."""

    model_config = ConfigDict(frozen=True)


class TrendDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    UNCHANGED = "unchanged"


class BudgetLineStatus(str, Enum):
    UNDER = "under"
    ON_TRACK = "on_track"
    OVER = "over"


class AffordabilityStatus(str, Enum):
    COMFORTABLE = "COMFORTABLE"
    CAUTION = "CAUTION"
    NOT_ADVISABLE = "NOT_ADVISABLE"


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

class MonthAmount(Frozen):
    month: str
    amount: int


class MerchantAmount(Frozen):
    merchant: str
    amount: int
    transaction_count: int


class TransactionRef(Frozen):
    """A pointer to one transaction, for when a total needs an example."""

    transaction_id: str
    date: date
    merchant: str
    amount: int


class CategoryAmount(Frozen):
    category: Category
    amount: int
    share_of_expenses: float
    transaction_count: int


# ---------------------------------------------------------------------------
# Tool results
# ---------------------------------------------------------------------------

class MonthlySummary(Frozen):
    """Answers 'what happened this month' and 'where is my money going'."""

    user_id: str
    month: str
    currency: str
    income: int
    expenses: int
    net: int
    savings_rate: float
    transaction_count: int
    categories: tuple[CategoryAmount, ...]
    top_category: CategoryAmount | None


class CategoryAnalysis(Frozen):
    """A deep dive on one category — 'how much did I spend on food?'"""

    user_id: str
    month: str
    currency: str
    category: Category
    total: int
    transaction_count: int
    average_transaction: int
    share_of_expenses: float
    largest_transaction: TransactionRef | None
    top_merchants: tuple[MerchantAmount, ...]
    budgeted: int | None
    budget_variance: int | None
    budget_status: BudgetLineStatus | None
    history: tuple[MonthAmount, ...]
    average_over_history: int
    versus_average: int


class CategoryChange(Frozen):
    category: Category
    current: int
    previous: int
    change: int
    #: ``None`` when the previous month was zero — an undefined percentage,
    #: not an infinite one. The model should say "new spending", not "+inf%".
    percentage_change: float | None


class MonthComparison(Frozen):
    """Answers 'why did I spend more this month?'"""

    user_id: str
    currency: str
    current_month: str
    previous_month: str
    current_expenses: int
    previous_expenses: int
    expense_change: int
    percentage_change: float | None
    direction: TrendDirection
    current_income: int
    previous_income: int
    income_change: int
    current_net: int
    previous_net: int
    category_changes: tuple[CategoryChange, ...]
    largest_increase: CategoryChange | None
    largest_decrease: CategoryChange | None


class BudgetLine(Frozen):
    category: Category
    budgeted: int
    actual: int
    #: Positive means overspent.
    variance: int
    percentage_used: float | None
    status: BudgetLineStatus


class BudgetStatus(Frozen):
    """Actual spending measured against the user's standing budget."""

    user_id: str
    month: str
    currency: str
    lines: tuple[BudgetLine, ...]
    total_budgeted: int
    total_actual: int
    total_variance: int
    breached_categories: tuple[Category, ...]
    savings_target: int
    actual_net: int
    savings_target_met: bool


class RecommendedLine(Frozen):
    category: Category
    recommended: int
    average_actual: int
    #: The target is anchored here rather than on the mean, so one unusual
    #: month cannot inflate the recommendation.
    median_actual: int
    change_from_average: int
    essential: bool


class BudgetRecommendation(Frozen):
    """A proposed budget derived from spending history (spec section 6)."""

    user_id: str
    currency: str
    based_on_months: tuple[str, ...]
    monthly_income: int
    lines: tuple[RecommendedLine, ...]
    recommended_savings: int
    total_allocated: int
    unallocated: int
    method: str
    notes: tuple[str, ...]
    disclaimer: str = DISCLAIMER


class AffordabilityAssessment(Frozen):
    """Answers 'can I afford this?' — with the reasoning made explicit.

    ``reasons`` is generated by code, not the model. The LLM turns these into
    prose; it does not decide what they are.
    """

    user_id: str
    currency: str
    purchase_amount: int
    reference_month: str
    monthly_income: int
    monthly_expenses: int
    monthly_net_cash_flow: int
    available_discretionary_amount: int
    savings_balance: int
    upcoming_expenses_total: int
    upcoming_expenses: tuple[UpcomingExpense, ...]
    savings_after_upcoming: int
    emergency_fund_target: int | None
    emergency_fund_saved: int | None
    emergency_fund_months_covered: float | None
    months_to_save_from_cash_flow: int | None
    status: AffordabilityStatus
    reasons: tuple[str, ...]
    disclaimer: str = DISCLAIMER
