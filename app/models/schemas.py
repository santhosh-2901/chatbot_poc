"""Data contracts for users, transactions and budgets.

These models are the boundary between raw JSON on disk and every calculation the
assistant performs. Validation happens once, at load time, so the analysis tools
in Phase 2 can assume clean data and the LLM never sees a malformed record.

Amounts are whole rupees (``int``). Money is never a float here: the spec
(section 25) makes Python the source of truth for arithmetic, and binary floats
would quietly break the exact-total guarantees the tests assert.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Category(str, Enum):
    """Every category the dataset may use.

    A closed set matters: the agent's category-analysis tool reports over these
    names, so an unexpected string on disk should fail loudly at load rather
    than silently produce a category the LLM then invents an explanation for.
    """

    HOUSING = "Housing"
    FOOD = "Food"
    SHOPPING = "Shopping"
    TRANSPORT = "Transport"
    UTILITIES = "Utilities"
    SUBSCRIPTIONS = "Subscriptions"
    INCOME = "Income"


#: Spending categories, i.e. everything except the income bucket.
EXPENSE_CATEGORIES: tuple[Category, ...] = tuple(
    c for c in Category if c is not Category.INCOME
)

#: Categories treated as non-negotiable when proposing a budget (spec section 6).
#: Food sits here because you cannot stop eating — but note that the *level* of
#: food spending is very much discretionary, which is why the recommendation
#: engine still reports it against its historical average.
ESSENTIAL_CATEGORIES: frozenset[Category] = frozenset(
    {Category.HOUSING, Category.UTILITIES, Category.FOOD, Category.TRANSPORT}
)

DISCRETIONARY_CATEGORIES: frozenset[Category] = (
    frozenset(EXPENSE_CATEGORIES) - ESSENTIAL_CATEGORIES
)


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Transaction(BaseModel):
    """A single money movement.

    Frozen so that a cached dataset cannot be mutated by one caller and observed
    as changed by the next.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    date: date
    merchant: str = Field(min_length=1)
    category: Category
    type: TransactionType
    amount: int = Field(gt=0, description="Whole rupees, always positive")
    currency: str = Field(default="INR", min_length=3, max_length=3)

    @property
    def month(self) -> str:
        """The ``YYYY-MM`` bucket this transaction falls in."""
        return f"{self.date.year:04d}-{self.date.month:02d}"

    @model_validator(mode="after")
    def _category_agrees_with_type(self) -> Transaction:
        is_income_category = self.category is Category.INCOME
        is_income_type = self.type is TransactionType.INCOME
        if is_income_category != is_income_type:
            raise ValueError(
                f"{self.transaction_id}: category {self.category.value!r} and "
                f"type {self.type.value!r} disagree; the Income category and the "
                "income type must always be used together"
            )
        return self


class Goal(BaseModel):
    """A savings goal, used by the affordability tool in Phase 2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    goal_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    target_amount: int = Field(gt=0)
    saved_amount: int = Field(ge=0)
    target_date: date

    @model_validator(mode="after")
    def _saved_within_target(self) -> Goal:
        if self.saved_amount > self.target_amount:
            raise ValueError(
                f"{self.goal_id}: saved_amount {self.saved_amount} exceeds "
                f"target_amount {self.target_amount}"
            )
        return self


class User(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    monthly_income: int = Field(gt=0, description="Expected recurring income")
    savings_balance: int = Field(ge=0)
    goals: tuple[Goal, ...] = ()


class UpcomingExpense(BaseModel):
    """A known future obligation the affordability check must not ignore."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    amount: int = Field(gt=0)
    due_date: date


class Budget(BaseModel):
    """A user's standing monthly plan.

    This is the budget the user already has. The ``calculate_budget`` tool in a
    later phase *proposes* one from history; the two are deliberately separate.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: str = Field(min_length=1)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    effective_from: date
    monthly_budget: dict[Category, int]
    savings_target: int = Field(ge=0)
    upcoming_expenses: tuple[UpcomingExpense, ...] = ()

    @model_validator(mode="after")
    def _budget_covers_only_expenses(self) -> Budget:
        if Category.INCOME in self.monthly_budget:
            raise ValueError(
                f"{self.user_id}: a budget allocates spending, so it cannot "
                "contain the Income category"
            )
        negative = {c.value: v for c, v in self.monthly_budget.items() if v < 0}
        if negative:
            raise ValueError(f"{self.user_id}: negative budget lines {negative}")
        return self

    @property
    def total_allocated(self) -> int:
        """Category allocations plus the savings target."""
        return sum(self.monthly_budget.values()) + self.savings_target
