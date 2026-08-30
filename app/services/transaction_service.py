"""Querying and filtering transactions.

Sits between the raw loader and the analysis engine. Everything here is a
lookup — no aggregation, no judgement. Month arithmetic lives here too, so that
"the previous month" means one thing across the whole system.
"""

from __future__ import annotations

import re
from datetime import date

from app.models.schemas import Category, Transaction, TransactionType
from app.services import data_loader
from app.services.data_loader import DataError

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class UnknownMonthError(DataError):
    """A month was requested that the user has no data for."""


def parse_month(month: str) -> tuple[int, int]:
    """Split ``YYYY-MM`` into ``(year, month)``, rejecting anything malformed."""
    if not isinstance(month, str) or not MONTH_PATTERN.match(month):
        raise UnknownMonthError(
            f"{month!r} is not a valid month. Expected YYYY-MM, for example '2026-08'."
        )
    year, month_number = month.split("-")
    return int(year), int(month_number)


def format_month(year: int, month_number: int) -> str:
    return f"{year:04d}-{month_number:02d}"


def previous_month(month: str) -> str:
    """The calendar month before ``month``. Handles the year boundary."""
    year, month_number = parse_month(month)
    if month_number == 1:
        return format_month(year - 1, 12)
    return format_month(year, month_number - 1)


def next_month(month: str) -> str:
    year, month_number = parse_month(month)
    if month_number == 12:
        return format_month(year + 1, 1)
    return format_month(year, month_number + 1)


def available_months(user_id: str) -> tuple[str, ...]:
    """Sorted months the user has any transaction in."""
    return data_loader.available_months(user_id)


def latest_month(user_id: str) -> str:
    """The most recent month with data — the default 'this month'."""
    months = available_months(user_id)
    if not months:
        raise UnknownMonthError(f"{user_id} has no transactions")
    return months[-1]


def resolve_month(user_id: str, month: str | None = None) -> str:
    """Validate a month, or fall back to the latest one the user has.

    Every entry point funnels through this, so an unknown month produces one
    clear error listing what *is* available rather than a silent empty result
    the model would then narrate as "you spent nothing".
    """
    months = available_months(user_id)
    if month is None:
        return latest_month(user_id)

    parse_month(month)
    if month not in months:
        raise UnknownMonthError(
            f"{user_id} has no data for {month}. "
            f"Available: {', '.join(months)}."
        )
    return month


def get_transactions(
    user_id: str,
    month: str | None = None,
    category: Category | None = None,
    transaction_type: TransactionType | None = None,
    merchant: str | None = None,
) -> tuple[Transaction, ...]:
    """Filter a user's transactions, oldest first.

    ``month=None`` means every month, not the latest one — callers wanting the
    latest should resolve it explicitly.
    """
    transactions = data_loader.get_transactions(user_id)

    if month is not None:
        parse_month(month)
        transactions = tuple(t for t in transactions if t.month == month)
    if category is not None:
        transactions = tuple(t for t in transactions if t.category is category)
    if transaction_type is not None:
        transactions = tuple(t for t in transactions if t.type is transaction_type)
    if merchant is not None:
        needle = merchant.casefold()
        transactions = tuple(t for t in transactions if needle in t.merchant.casefold())

    return tuple(sorted(transactions, key=lambda t: (t.date, t.transaction_id)))


def expenses_in(user_id: str, month: str) -> tuple[Transaction, ...]:
    return get_transactions(user_id, month=month, transaction_type=TransactionType.EXPENSE)


def income_in(user_id: str, month: str) -> tuple[Transaction, ...]:
    return get_transactions(user_id, month=month, transaction_type=TransactionType.INCOME)


def recent_transactions(user_id: str, limit: int = 10) -> tuple[Transaction, ...]:
    """The newest ``limit`` transactions, most recent first (dashboard use)."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    ordered = sorted(
        data_loader.get_transactions(user_id),
        key=lambda t: (t.date, t.transaction_id),
        reverse=True,
    )
    return tuple(ordered[:limit])


def transactions_between(
    user_id: str, start: date, end: date
) -> tuple[Transaction, ...]:
    """Inclusive date range."""
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    return tuple(
        t for t in data_loader.get_transactions(user_id) if start <= t.date <= end
    )
