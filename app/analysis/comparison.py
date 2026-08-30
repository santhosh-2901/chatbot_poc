"""Month-over-month comparison.

Backs ``compare_months`` (spec section 10, tool 3) — the tool behind "why did I
spend more this month?". The *why* is a ranked list of category deltas computed
here; the model's contribution is turning that ranking into a sentence.
"""

from __future__ import annotations

from app.analysis.utils import percentage
from app.models.analysis import CategoryChange, MonthComparison, TrendDirection
from app.models.schemas import Category
from app.services import transaction_service as tx
from app.services.data_loader import get_user


def _category_totals(user_id: str, month: str) -> dict[Category, int]:
    totals: dict[Category, int] = {}
    for transaction in tx.expenses_in(user_id, month):
        totals[transaction.category] = totals.get(transaction.category, 0) + transaction.amount
    return totals


def compare_months(
    user_id: str,
    current_month: str | None = None,
    previous_month: str | None = None,
) -> MonthComparison:
    """Compare two months' spending, category by category.

    Defaults to the latest month against the one before it. Categories present
    in either month appear in the result, so a category that dropped to zero is
    still visible as a decrease rather than vanishing from the comparison.
    """
    user = get_user(user_id)
    current = tx.resolve_month(user_id, current_month)
    previous = tx.resolve_month(
        user_id, previous_month if previous_month is not None else tx.previous_month(current)
    )

    if current == previous:
        raise ValueError(f"Cannot compare {current} with itself")

    current_totals = _category_totals(user_id, current)
    previous_totals = _category_totals(user_id, previous)

    changes = tuple(
        sorted(
            (
                CategoryChange(
                    category=category,
                    current=current_totals.get(category, 0),
                    previous=previous_totals.get(category, 0),
                    change=current_totals.get(category, 0) - previous_totals.get(category, 0),
                    percentage_change=percentage(
                        current_totals.get(category, 0) - previous_totals.get(category, 0),
                        previous_totals.get(category, 0),
                    ),
                )
                for category in set(current_totals) | set(previous_totals)
            ),
            key=lambda c: -c.change,
        )
    )

    current_expenses = sum(current_totals.values())
    previous_expenses = sum(previous_totals.values())
    expense_change = current_expenses - previous_expenses

    current_income = sum(t.amount for t in tx.income_in(user_id, current))
    previous_income = sum(t.amount for t in tx.income_in(user_id, previous))

    increases = [c for c in changes if c.change > 0]
    decreases = [c for c in changes if c.change < 0]

    if expense_change > 0:
        direction = TrendDirection.INCREASE
    elif expense_change < 0:
        direction = TrendDirection.DECREASE
    else:
        direction = TrendDirection.UNCHANGED

    return MonthComparison(
        user_id=user_id,
        currency=user.currency,
        current_month=current,
        previous_month=previous,
        current_expenses=current_expenses,
        previous_expenses=previous_expenses,
        expense_change=expense_change,
        percentage_change=percentage(expense_change, previous_expenses),
        direction=direction,
        current_income=current_income,
        previous_income=previous_income,
        income_change=current_income - previous_income,
        current_net=current_income - current_expenses,
        previous_net=previous_income - previous_expenses,
        category_changes=changes,
        largest_increase=increases[0] if increases else None,
        largest_decrease=decreases[-1] if decreases else None,
    )
