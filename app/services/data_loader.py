"""Read and validate the JSON dataset.

The only module that touches ``data/*.json``. Everything downstream works with
validated model objects, so swapping JSON for SQLite later (spec section 13)
means rewriting this file and nothing else.

Results are cached because the dataset is small, read-only and read constantly.
Tuples rather than lists are returned so a caller cannot mutate the cache.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.models.schemas import Budget, Transaction, User

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

USERS_FILE = DATA_DIR / "users.json"
TRANSACTIONS_FILE = DATA_DIR / "transactions.json"
BUDGETS_FILE = DATA_DIR / "budgets.json"


class DataError(RuntimeError):
    """The dataset is missing, unreadable or internally inconsistent."""


class UnknownUserError(DataError):
    """A user id was requested that does not exist in the dataset."""


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise DataError(
            f"{path.name} not found at {path}. Run: python scripts/generate_data.py"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"{path.name} is not valid JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise DataError(f"{path.name} must contain a JSON array, got {type(payload).__name__}")
    return payload


def _parse_all(path: Path, model: type, rows: list[dict[str, Any]]) -> tuple:
    parsed = []
    for index, row in enumerate(rows):
        try:
            parsed.append(model(**row))
        except ValidationError as exc:
            raise DataError(f"{path.name}[{index}] failed validation:\n{exc}") from exc
    return tuple(parsed)


@lru_cache(maxsize=1)
def load_users() -> tuple[User, ...]:
    rows = _read_json_array(USERS_FILE)
    users = _parse_all(USERS_FILE, User, rows)
    duplicates = _duplicates(u.user_id for u in users)
    if duplicates:
        raise DataError(f"users.json has duplicate user ids: {sorted(duplicates)}")
    return users


@lru_cache(maxsize=1)
def load_transactions() -> tuple[Transaction, ...]:
    rows = _read_json_array(TRANSACTIONS_FILE)
    transactions = _parse_all(TRANSACTIONS_FILE, Transaction, rows)
    duplicates = _duplicates(t.transaction_id for t in transactions)
    if duplicates:
        raise DataError(
            f"transactions.json has duplicate transaction ids: {sorted(duplicates)}"
        )
    return transactions


@lru_cache(maxsize=1)
def load_budgets() -> tuple[Budget, ...]:
    rows = _read_json_array(BUDGETS_FILE)
    budgets = _parse_all(BUDGETS_FILE, Budget, rows)
    duplicates = _duplicates(b.user_id for b in budgets)
    if duplicates:
        raise DataError(f"budgets.json has more than one budget for: {sorted(duplicates)}")
    return budgets


def _duplicates(values) -> set[str]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return repeated


def get_user(user_id: str) -> User:
    """Return one user, or raise if the id is unknown."""
    for user in load_users():
        if user.user_id == user_id:
            return user
    known = ", ".join(u.user_id for u in load_users())
    raise UnknownUserError(f"No such user {user_id!r}. Known users: {known}")


def get_budget(user_id: str) -> Budget | None:
    """Return the user's standing budget, or ``None`` if they have not set one."""
    get_user(user_id)  # surface an unknown id rather than returning a bare None
    for budget in load_budgets():
        if budget.user_id == user_id:
            return budget
    return None


def get_transactions(user_id: str) -> tuple[Transaction, ...]:
    """Every transaction belonging to one user, oldest first."""
    get_user(user_id)
    return tuple(t for t in load_transactions() if t.user_id == user_id)


def available_months(user_id: str) -> tuple[str, ...]:
    """Sorted ``YYYY-MM`` buckets the user has data for."""
    return tuple(sorted({t.month for t in get_transactions(user_id)}))


def validate_dataset() -> None:
    """Check cross-file integrity. Raises :class:`DataError` on any problem.

    Per-record validation is handled by the models; this covers the invariants
    that only make sense across files.
    """
    users = load_users()
    transactions = load_transactions()
    budgets = load_budgets()

    known_ids = {u.user_id for u in users}

    orphans = sorted({t.user_id for t in transactions} - known_ids)
    if orphans:
        raise DataError(f"transactions.json references unknown users: {orphans}")

    orphan_budgets = sorted({b.user_id for b in budgets} - known_ids)
    if orphan_budgets:
        raise DataError(f"budgets.json references unknown users: {orphan_budgets}")

    currency_by_user = {u.user_id: u.currency for u in users}
    for transaction in transactions:
        expected = currency_by_user[transaction.user_id]
        if transaction.currency != expected:
            raise DataError(
                f"{transaction.transaction_id} is in {transaction.currency} but "
                f"{transaction.user_id} operates in {expected}; mixed currencies "
                "would make every total meaningless"
            )

    for user in users:
        if not any(t.user_id == user.user_id for t in transactions):
            raise DataError(f"{user.user_id} has no transactions")


def clear_cache() -> None:
    """Drop cached data. Call after regenerating the JSON files in one process."""
    load_users.cache_clear()
    load_transactions.cache_clear()
    load_budgets.cache_clear()
