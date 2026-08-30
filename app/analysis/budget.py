"""Budget tracking and budget recommendation.

Two distinct jobs that are easy to conflate:

``budget_status`` measures actual spending against the budget the user already
has. ``recommend_budget`` proposes a new one from spending history (spec
section 6). The first reports, the second suggests.
"""

from __future__ import annotations

from app.analysis.summary import _budget_line_status, summarize_month
from app.analysis.utils import mean, median, percentage, round_money, round_to
from app.models.analysis import (
    BudgetLine,
    BudgetRecommendation,
    BudgetStatus,
    RecommendedLine,
)
from app.models.schemas import ESSENTIAL_CATEGORIES, Category
from app.services import transaction_service as tx
from app.services.data_loader import DataError, get_budget, get_user

#: Share of income the recommendation aims to save before allocating anything
#: discretionary. Loosely the "20" of 50/30/20, which the knowledge base will
#: explain in Phase 3.
TARGET_SAVINGS_RATE = 0.20

#: How many months of history the recommendation looks at by default.
DEFAULT_LOOKBACK = 3


def budget_status(user_id: str, month: str | None = None) -> BudgetStatus:
    """Compare a month's actual spending with the user's standing budget."""
    user = get_user(user_id)
    month = tx.resolve_month(user_id, month)

    budget = get_budget(user_id)
    if budget is None:
        raise DataError(f"{user_id} has no budget set")

    summary = summarize_month(user_id, month)
    actuals = {c.category: c.amount for c in summary.categories}

    lines = tuple(
        BudgetLine(
            category=category,
            budgeted=budgeted,
            actual=actuals.get(category, 0),
            variance=actuals.get(category, 0) - budgeted,
            percentage_used=percentage(actuals.get(category, 0), budgeted),
            status=_budget_line_status(actuals.get(category, 0), budgeted),
        )
        for category, budgeted in sorted(
            budget.monthly_budget.items(), key=lambda kv: -kv[1]
        )
    )

    total_budgeted = sum(line.budgeted for line in lines)
    total_actual = sum(line.actual for line in lines)

    return BudgetStatus(
        user_id=user_id,
        month=month,
        currency=user.currency,
        lines=lines,
        total_budgeted=total_budgeted,
        total_actual=total_actual,
        total_variance=total_actual - total_budgeted,
        breached_categories=tuple(
            line.category for line in lines if line.variance > 0
        ),
        savings_target=budget.savings_target,
        actual_net=summary.net,
        savings_target_met=summary.net >= budget.savings_target,
    )


def recommend_budget(
    user_id: str, lookback_months: int = DEFAULT_LOOKBACK
) -> BudgetRecommendation:
    """Propose a monthly budget from recent spending.

    The method, in order:

    1. Take each category's *median* over the last ``lookback_months``.
    2. Fund essentials at that median.
    3. Aim to save 20% of income.
    4. Give whatever remains to discretionary categories, scaled proportionally
       to how the user actually spends rather than split evenly.
    5. If essentials alone leave no room, cut the savings target rather than
       proposing a budget that cannot be followed — and say so in ``notes``.

    The median, not the mean, is deliberate. A budget built on the mean is
    dragged upward by exactly the bad month the user wants to correct, and it
    hands fixed costs like rent headroom they cannot use. The median gives a
    target the user has already met in half of the recent months — demanding,
    but demonstrably achievable.

    Every number is a proposal, not a prediction. ``notes`` carries the
    caveats so the model does not have to invent them.
    """
    if lookback_months < 1:
        raise ValueError("lookback_months must be at least 1")

    user = get_user(user_id)
    months = tx.available_months(user_id)[-lookback_months:]
    if not months:
        raise DataError(f"{user_id} has no transactions to base a budget on")

    notes: list[str] = []

    averages: dict[Category, int] = {}
    medians: dict[Category, int] = {}
    for category in {c.category for m in months for c in summarize_month(user_id, m).categories}:
        per_month = [
            sum(t.amount for t in tx.get_transactions(user_id, month=m, category=category))
            for m in months
        ]
        averages[category] = round_money(mean(per_month))
        medians[category] = round_money(median(per_month))

    income = round_money(
        mean([sum(t.amount for t in tx.income_in(user_id, m)) for m in months])
    )

    essentials = {c: v for c, v in medians.items() if c in ESSENTIAL_CATEGORIES}
    discretionary = {c: v for c, v in medians.items() if c not in ESSENTIAL_CATEGORIES}

    essential_plan = {
        category: round_to(amount, 100) for category, amount in essentials.items()
    }
    essential_total = sum(essential_plan.values())

    savings = round_to(income * TARGET_SAVINGS_RATE, 500)
    available = income - essential_total - savings

    if available < 0:
        # Essentials plus the savings goal exceed income. Savings gives way
        # first: a budget that cannot be met is worse than a modest one.
        shortfall = -available
        savings = max(0, savings - shortfall)
        available = income - essential_total - savings
        notes.append(
            "Essential spending leaves little room, so the savings target was "
            "reduced below the usual 20% guideline."
        )

    discretionary_total = sum(discretionary.values())
    discretionary_plan: dict[Category, int] = {}

    if discretionary_total == 0:
        pass
    elif available <= 0:
        discretionary_plan = {category: 0 for category in discretionary}
        notes.append(
            "Essential spending consumes the full income; discretionary "
            "categories could not be funded."
        )
    elif discretionary_total <= available:
        discretionary_plan = {
            category: round_to(amount, 100) for category, amount in discretionary.items()
        }
    else:
        # Scale proportionally so the cut lands where the money actually goes.
        scale = available / discretionary_total
        discretionary_plan = {
            category: round_to(amount * scale, 100)
            for category, amount in discretionary.items()
        }
        notes.append(
            f"Discretionary spending was trimmed by "
            f"{round(100 - scale * 100)}% to fund the savings target."
        )

    plan = {**essential_plan, **discretionary_plan}
    total_allocated = sum(plan.values())

    # Rounding can leave a few rupees adrift; the surplus goes to savings so
    # the recommendation always reconciles against income.
    savings += max(0, income - total_allocated - savings)

    lines = tuple(
        sorted(
            (
                RecommendedLine(
                    category=category,
                    recommended=amount,
                    average_actual=averages[category],
                    median_actual=medians[category],
                    change_from_average=amount - averages[category],
                    essential=category in ESSENTIAL_CATEGORIES,
                )
                for category, amount in plan.items()
            ),
            key=lambda line: -line.recommended,
        )
    )

    if len(months) < DEFAULT_LOOKBACK:
        notes.append(
            f"Based on only {len(months)} month(s) of history, so the averages "
            "may not be representative."
        )

    return BudgetRecommendation(
        user_id=user_id,
        currency=user.currency,
        based_on_months=tuple(months),
        monthly_income=income,
        lines=lines,
        recommended_savings=savings,
        total_allocated=total_allocated + savings,
        unallocated=income - total_allocated - savings,
        method=(
            f"Median of {len(months)} months per category; essentials funded at "
            f"that median; savings targeted at {int(TARGET_SAVINGS_RATE * 100)}% "
            "of income; discretionary categories scaled to fit what remains; "
            "any surplus added to savings so the plan reconciles to income."
        ),
        notes=tuple(notes),
    )
