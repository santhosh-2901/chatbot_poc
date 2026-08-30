"""Monthly totals and category breakdowns.

Backs two of the spec's tools: ``calculate_monthly_summary`` (section 10,
tool 2) and ``analyze_category_spending`` (tool 4).
"""

from __future__ import annotations

from collections import defaultdict

from app.analysis.utils import mean, percentage, round_money
from app.models.analysis import (
    BudgetLineStatus,
    CategoryAmount,
    CategoryAnalysis,
    MerchantAmount,
    MonthAmount,
    MonthlySummary,
    TransactionRef,
)
from app.models.schemas import Category, Transaction, TransactionType
from app.services import transaction_service as tx
from app.services.data_loader import get_budget, get_user


def _totals_by_category(transactions: tuple[Transaction, ...]) -> dict[Category, list[Transaction]]:
    grouped: dict[Category, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        grouped[transaction.category].append(transaction)
    return grouped


def summarize_month(user_id: str, month: str | None = None) -> MonthlySummary:
    """Income, expenses, net and the category breakdown for one month.

    Categories are ranked by spend, so "where am I spending the most?" is
    answered by reading the first entry rather than by the model sorting.
    """
    user = get_user(user_id)
    month = tx.resolve_month(user_id, month)

    expenses = tx.expenses_in(user_id, month)
    income_rows = tx.income_in(user_id, month)

    total_expenses = sum(t.amount for t in expenses)
    total_income = sum(t.amount for t in income_rows)

    grouped = _totals_by_category(expenses)
    categories = tuple(
        sorted(
            (
                CategoryAmount(
                    category=category,
                    amount=sum(t.amount for t in rows),
                    share_of_expenses=percentage(
                        sum(t.amount for t in rows), total_expenses
                    )
                    or 0.0,
                    transaction_count=len(rows),
                )
                for category, rows in grouped.items()
            ),
            key=lambda c: -c.amount,
        )
    )

    return MonthlySummary(
        user_id=user_id,
        month=month,
        currency=user.currency,
        income=total_income,
        expenses=total_expenses,
        net=total_income - total_expenses,
        savings_rate=percentage(total_income - total_expenses, total_income) or 0.0,
        transaction_count=len(expenses) + len(income_rows),
        categories=categories,
        top_category=categories[0] if categories else None,
    )


def analyze_category(
    user_id: str, category: Category, month: str | None = None
) -> CategoryAnalysis:
    """Everything worth knowing about one category in one month.

    Includes the full month-by-month history so the model can speak to a trend
    ("higher than your usual") without inferring one from a single number.
    """
    user = get_user(user_id)
    month = tx.resolve_month(user_id, month)

    if category is Category.INCOME:
        raise ValueError(
            "Income is not a spending category; use summarize_month for income."
        )

    rows = tx.get_transactions(user_id, month=month, category=category)
    total = sum(t.amount for t in rows)
    month_expenses = sum(t.amount for t in tx.expenses_in(user_id, month))

    merchants: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in rows:
        merchants[transaction.merchant].append(transaction)

    top_merchants = tuple(
        sorted(
            (
                MerchantAmount(
                    merchant=name,
                    amount=sum(t.amount for t in items),
                    transaction_count=len(items),
                )
                for name, items in merchants.items()
            ),
            key=lambda m: -m.amount,
        )[:5]
    )

    largest = max(rows, key=lambda t: t.amount) if rows else None

    history = tuple(
        MonthAmount(
            month=past,
            amount=sum(
                t.amount
                for t in tx.get_transactions(user_id, month=past, category=category)
            ),
        )
        for past in tx.available_months(user_id)
    )
    average = round_money(mean([h.amount for h in history]))

    budget = get_budget(user_id)
    budgeted = budget.monthly_budget.get(category) if budget else None
    variance = total - budgeted if budgeted is not None else None

    return CategoryAnalysis(
        user_id=user_id,
        month=month,
        currency=user.currency,
        category=category,
        total=total,
        transaction_count=len(rows),
        average_transaction=round_money(mean([t.amount for t in rows])),
        share_of_expenses=percentage(total, month_expenses) or 0.0,
        largest_transaction=(
            TransactionRef(
                transaction_id=largest.transaction_id,
                date=largest.date,
                merchant=largest.merchant,
                amount=largest.amount,
            )
            if largest
            else None
        ),
        top_merchants=top_merchants,
        budgeted=budgeted,
        budget_variance=variance,
        budget_status=_budget_line_status(total, budgeted),
        history=history,
        average_over_history=average,
        versus_average=total - average,
    )


def _budget_line_status(actual: int, budgeted: int | None) -> BudgetLineStatus | None:
    """Classify spend against a budget line.

    'On track' spans 90-100% — close enough to the limit that calling it
    "under budget" would be misleading.
    """
    if budgeted is None:
        return None
    if budgeted == 0:
        return BudgetLineStatus.OVER if actual > 0 else BudgetLineStatus.UNDER
    used = actual / budgeted * 100
    if used > 100:
        return BudgetLineStatus.OVER
    if used >= 90:
        return BudgetLineStatus.ON_TRACK
    return BudgetLineStatus.UNDER


def total_income(user_id: str, month: str) -> int:
    """Spec section 29, ``calculate_total_income``."""
    return sum(t.amount for t in tx.income_in(user_id, tx.resolve_month(user_id, month)))


def total_expenses(user_id: str, month: str) -> int:
    """Spec section 29, ``calculate_total_expenses``."""
    return sum(t.amount for t in tx.expenses_in(user_id, tx.resolve_month(user_id, month)))


def cash_flow(user_id: str, month: str | None = None) -> int:
    """Spec section 29, ``calculate_cash_flow``. Income minus expenses."""
    month = tx.resolve_month(user_id, month)
    return total_income(user_id, month) - total_expenses(user_id, month)


def average_monthly(user_id: str, transaction_type: TransactionType) -> int:
    """Mean monthly income or expenditure across all available history."""
    months = tx.available_months(user_id)
    if not months:
        return 0
    totals = [
        sum(
            t.amount
            for t in tx.get_transactions(user_id, month=m, transaction_type=transaction_type)
        )
        for m in months
    ]
    return round_money(mean(totals))
