"""Affordability assessment.

Backs ``affordability_check`` (spec section 10, tool 5) — the feature that
separates this from an expense tracker (section 5).

The verdict is decided here, in code, and so are the reasons behind it. The
model receives a status and a list of factual statements and turns them into
prose. It does not get to decide whether something is affordable.
"""

from __future__ import annotations

import math

from app.analysis.summary import summarize_month
from app.analysis.utils import round_money
from app.models.analysis import AffordabilityAssessment, AffordabilityStatus
from app.services import transaction_service as tx
from app.services.data_loader import get_budget, get_user

#: A savings pot is only a buffer if something is left in it. A purchase that
#: consumes more than this share of savings-after-obligations is flagged even
#: when the money is technically there.
SAVINGS_COMFORT_SHARE = 0.5


def affordability_check(
    user_id: str, purchase_amount: int, month: str | None = None
) -> AffordabilityAssessment:
    """Assess a one-off purchase against income, spending, savings and obligations.

    The ladder:

    ``COMFORTABLE``   payable from this month's surplus alone.
    ``CAUTION``       payable, but only by drawing on savings.
    ``NOT_ADVISABLE`` exceeds savings once known obligations are set aside.
    """
    if purchase_amount <= 0:
        raise ValueError("purchase_amount must be positive")

    user = get_user(user_id)
    month = tx.resolve_month(user_id, month)
    summary = summarize_month(user_id, month)
    budget = get_budget(user_id)

    upcoming = budget.upcoming_expenses if budget else ()
    upcoming_total = sum(e.amount for e in upcoming)

    # Savings genuinely available once committed obligations are set aside.
    savings_after_upcoming = user.savings_balance - upcoming_total

    emergency_fund = next(
        (g for g in user.goals if "emergency" in g.name.casefold()), None
    )
    average_expenses = round_money(
        sum(summarize_month(user_id, m).expenses for m in tx.available_months(user_id))
        / len(tx.available_months(user_id))
    )
    months_covered = (
        round(emergency_fund.saved_amount / average_expenses, 1)
        if emergency_fund and average_expenses
        else None
    )

    reasons: list[str] = []

    if purchase_amount <= summary.net:
        status = AffordabilityStatus.COMFORTABLE
        reasons.append(
            f"The purchase fits within {month}'s surplus of "
            f"{summary.net:,} {user.currency} without touching savings."
        )
    elif purchase_amount <= savings_after_upcoming:
        status = AffordabilityStatus.CAUTION
        reasons.append(
            f"The purchase exceeds {month}'s surplus of {summary.net:,} "
            f"{user.currency}, so it would have to come from savings."
        )
        share = purchase_amount / savings_after_upcoming if savings_after_upcoming else 1
        if share > SAVINGS_COMFORT_SHARE:
            reasons.append(
                f"It would consume {round(share * 100)}% of the savings "
                "remaining after known upcoming expenses."
            )
    else:
        status = AffordabilityStatus.NOT_ADVISABLE
        reasons.append(
            f"The purchase exceeds the {savings_after_upcoming:,} {user.currency} "
            "of savings left after known upcoming expenses."
        )

    if upcoming_total:
        names = ", ".join(f"{e.name} ({e.amount:,})" for e in upcoming)
        reasons.append(f"Known upcoming expenses total {upcoming_total:,}: {names}.")

    if months_covered is not None and months_covered < 3:
        reasons.append(
            f"The emergency fund currently covers about {months_covered} months "
            "of average spending, below the 3-6 months commonly suggested."
        )

    months_to_save = (
        math.ceil(purchase_amount / summary.net) if summary.net > 0 else None
    )
    if months_to_save and status is not AffordabilityStatus.COMFORTABLE:
        reasons.append(
            f"Saving the full amount from the current surplus would take about "
            f"{months_to_save} months."
        )

    return AffordabilityAssessment(
        user_id=user_id,
        currency=user.currency,
        purchase_amount=purchase_amount,
        reference_month=month,
        monthly_income=summary.income,
        monthly_expenses=summary.expenses,
        monthly_net_cash_flow=summary.net,
        available_discretionary_amount=summary.net,
        savings_balance=user.savings_balance,
        upcoming_expenses_total=upcoming_total,
        upcoming_expenses=tuple(upcoming),
        savings_after_upcoming=savings_after_upcoming,
        emergency_fund_target=emergency_fund.target_amount if emergency_fund else None,
        emergency_fund_saved=emergency_fund.saved_amount if emergency_fund else None,
        emergency_fund_months_covered=months_covered,
        months_to_save_from_cash_flow=months_to_save,
        status=status,
        reasons=tuple(reasons),
    )
