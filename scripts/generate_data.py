"""Generate the synthetic dataset (spec section 29, Phase 1).

Two properties matter more than realism here:

*Deterministic* - a fixed seed means re-running produces byte-identical files, so
the golden-number tests stay meaningful and a demo never shifts under you.

*Pinned totals* - per-category monthly totals come from MONTHLY_TARGETS rather
than from accumulated randomness. Individual transactions are randomised, but
they are scaled to hit those targets exactly. That is what lets the numbers in
chat_bot_techincal.md actually hold:

    August 2026 income 60,000 / expenses 42,500 / net 17,500   (Tool 2 example)
    July -> August change +6,400 (+17.7%), Shopping +3,200      (Tool 3 example)
    Food +1,800, the second largest increase                    (section 4.2)

Usage:  python scripts/generate_data.py
"""

from __future__ import annotations

import calendar
import json
import random
from pathlib import Path
from typing import Iterable

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

#: Any fixed value works; this one just has to never change.
SEED = 20260830

MONTHS = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]

# Category totals per user per month, in rupees. Subscriptions are absent on
# purpose: they are recurring fixed charges, so their monthly total is derived
# from SUBSCRIPTIONS below rather than stated twice.
MONTHLY_TARGETS: dict[str, dict[str, dict[str, int]]] = {
    "USER001": {
        # Steady months, then a deliberate August spike so "why did I spend more
        # this month?" has a real, explainable answer.
        "2026-03": {"Housing": 15000, "Food": 6200, "Shopping": 3400, "Transport": 3200, "Utilities": 4800},
        "2026-04": {"Housing": 15000, "Food": 6800, "Shopping": 4600, "Transport": 3600, "Utilities": 5100},
        "2026-05": {"Housing": 15000, "Food": 6400, "Shopping": 3900, "Transport": 3300, "Utilities": 4900},
        "2026-06": {"Housing": 15000, "Food": 7100, "Shopping": 5200, "Transport": 3800, "Utilities": 5400},
        "2026-07": {"Housing": 15000, "Food": 6700, "Shopping": 4000, "Transport": 3500, "Utilities": 5200},
        "2026-08": {"Housing": 15000, "Food": 8500, "Shopping": 7200, "Transport": 4100, "Utilities": 6000},
    },
    "USER002": {
        "2026-03": {"Housing": 12000, "Food": 5400, "Shopping": 2800, "Transport": 2600, "Utilities": 3600},
        "2026-04": {"Housing": 12000, "Food": 5800, "Shopping": 3100, "Transport": 2900, "Utilities": 3800},
        "2026-05": {"Housing": 12000, "Food": 5200, "Shopping": 2400, "Transport": 2500, "Utilities": 3500},
        "2026-06": {"Housing": 12000, "Food": 6100, "Shopping": 3600, "Transport": 3100, "Utilities": 4100},
        "2026-07": {"Housing": 12000, "Food": 5600, "Shopping": 2900, "Transport": 2700, "Utilities": 3700},
        "2026-08": {"Housing": 12000, "Food": 5900, "Shopping": 2600, "Transport": 2800, "Utilities": 3900},
    },
}

# Recurring charges: same merchant, same amount, same day, every month.
SUBSCRIPTIONS: dict[str, list[tuple[str, int, int]]] = {
    # user_id: [(merchant, amount, day_of_month), ...]
    "USER001": [
        ("Netflix", 649, 2),
        ("Spotify Premium", 199, 4),
        ("Amazon Prime", 299, 6),
        ("Google One", 130, 9),
        ("YouTube Premium", 149, 11),
        ("Cult.fit Membership", 274, 14),
    ],
    "USER002": [
        ("Netflix Mobile", 199, 3),
        ("Spotify Premium", 119, 5),
        ("Amazon Prime", 299, 8),
        ("Google One", 130, 12),
        ("YouTube Premium", 149, 15),
    ],
}

# How each category's monthly target is broken into individual transactions.
CATEGORY_PLANS: dict[str, dict] = {
    "Housing": {
        "count": (1, 1),
        "minimum": 1000,
        "days": [1],
        "merchants": ["House Rent"],
    },
    "Food": {
        "count": (14, 18),
        "minimum": 60,
        "merchants": [
            "Swiggy", "Zomato", "BigBasket", "Blinkit", "Reliance Fresh",
            "More Supermarket", "Local Kirana Store", "Domino's Pizza",
            "Third Wave Coffee", "Haldiram's", "Barbeque Nation",
        ],
    },
    "Shopping": {
        "count": (3, 6),
        "minimum": 200,
        "merchants": [
            "Amazon", "Flipkart", "Myntra", "Croma", "Decathlon",
            "Reliance Digital", "Nykaa", "IKEA",
        ],
    },
    "Transport": {
        "count": (8, 12),
        "minimum": 40,
        "merchants": [
            "Uber", "Ola", "Rapido", "Indian Oil", "HP Petrol Pump",
            "Namma Metro", "IRCTC",
        ],
    },
    "Utilities": {
        "count": (4, 4),
        "minimum": 300,
        "days": [8, 11, 15, 19],
        "merchants": [
            "BESCOM Electricity", "BWSSB Water", "ACT Fibernet", "Airtel Postpaid",
        ],
    },
}

USERS = [
    {
        "user_id": "USER001",
        "name": "Ananya Iyer",
        "currency": "INR",
        "monthly_income": 60000,
        "savings_balance": 85000,
        "goals": [
            {
                "goal_id": "GOAL001",
                "name": "Emergency Fund",
                # Roughly six months of expenses, the usual guideline. Sitting at
                # ~1.5 months makes the RAG-plus-data demo land properly.
                "target_amount": 240000,
                "saved_amount": 60000,
                "target_date": "2027-06-30",
            },
            {
                "goal_id": "GOAL002",
                "name": "Laptop Upgrade",
                "target_amount": 90000,
                "saved_amount": 15000,
                "target_date": "2026-12-31",
            },
        ],
    },
    {
        "user_id": "USER002",
        "name": "Rohit Menon",
        "currency": "INR",
        "monthly_income": 45000,
        "savings_balance": 52000,
        "goals": [
            {
                "goal_id": "GOAL003",
                "name": "Emergency Fund",
                "target_amount": 168000,
                "saved_amount": 40000,
                "target_date": "2027-09-30",
            },
        ],
    },
]

BUDGETS = [
    {
        "user_id": "USER001",
        "currency": "INR",
        "effective_from": "2026-03-01",
        # 40,000 of categories + 15,000 savings = 55,000 of 60,000 income,
        # leaving a 5,000 buffer. Transport and Utilities are set with enough
        # headroom to absorb normal variation, so the only August breaches are
        # Food and Shopping - the two the spec's narrative actually blames.
        "monthly_budget": {
            "Housing": 15000,
            "Food": 7500,
            "Shopping": 5000,
            "Transport": 4300,
            "Utilities": 6200,
            "Subscriptions": 2000,
        },
        "savings_target": 15000,
        "upcoming_expenses": [
            {"name": "Annual health insurance premium", "amount": 18000, "due_date": "2026-09-15"},
            {"name": "Festival travel booking", "amount": 12000, "due_date": "2026-10-05"},
        ],
    },
    {
        "user_id": "USER002",
        "currency": "INR",
        "effective_from": "2026-03-01",
        "monthly_budget": {
            "Housing": 12000,
            "Food": 6000,
            "Shopping": 3000,
            "Transport": 3000,
            "Utilities": 4000,
            "Subscriptions": 1000,
        },
        "savings_target": 10000,
        "upcoming_expenses": [
            {"name": "Two-wheeler service", "amount": 4500, "due_date": "2026-09-20"},
        ],
    },
]

# Irregular income, to prove the aggregation handles more than one salary line.
EXTRA_INCOME: dict[str, list[tuple[str, str, int, int]]] = {
    # user_id: [(month, merchant, amount, day), ...]
    "USER002": [
        ("2026-04", "Freelance Project", 8000, 18),
        ("2026-06", "Freelance Project", 12000, 21),
        ("2026-08", "Freelance Project", 6000, 19),
    ],
}


def split_amount(rng: random.Random, total: int, count: int, minimum: int) -> list[int]:
    """Break ``total`` into ``count`` positive amounts that sum to it exactly.

    Amounts are rounded to the nearest 10 to look like real spending; the
    rounding drift is absorbed by the largest amount so the sum stays exact.
    """
    if count < 1:
        raise ValueError("count must be at least 1")
    if total < minimum * count:
        raise ValueError(
            f"cannot split {total} into {count} amounts of at least {minimum}"
        )

    weights = [rng.uniform(0.65, 1.55) for _ in range(count)]
    scale = total / sum(weights)
    amounts = [max(minimum, round(weight * scale / 10) * 10) for weight in weights]

    drift = total - sum(amounts)
    largest = amounts.index(max(amounts))
    amounts[largest] += drift

    if amounts[largest] < minimum:
        raise ValueError(f"drift correction pushed an amount below {minimum}")
    assert sum(amounts) == total
    return amounts


def _days_for(rng: random.Random, plan: dict, count: int, year: int, month: int) -> list[int]:
    last_day = calendar.monthrange(year, month)[1]
    fixed = plan.get("days")
    if fixed:
        return [min(day, last_day) for day in fixed[:count]]
    return sorted(rng.randint(1, last_day) for _ in range(count))


def build_expenses(
    rng: random.Random, user_id: str, currency: str, month: str
) -> list[dict]:
    """Every expense row for one user in one month."""
    year, month_number = (int(part) for part in month.split("-"))
    rows: list[dict] = []

    for category, target in MONTHLY_TARGETS[user_id][month].items():
        plan = CATEGORY_PLANS[category]
        low, high = plan["count"]
        count = rng.randint(low, high)
        amounts = split_amount(rng, target, count, plan["minimum"])
        days = _days_for(rng, plan, count, year, month_number)
        merchants = plan["merchants"]

        for index, (amount, day) in enumerate(zip(amounts, days)):
            # Fixed-day categories pair merchant to slot; the rest pick freely.
            merchant = (
                merchants[index % len(merchants)]
                if plan.get("days")
                else rng.choice(merchants)
            )
            rows.append(
                {
                    "user_id": user_id,
                    "date": f"{year:04d}-{month_number:02d}-{day:02d}",
                    "merchant": merchant,
                    "category": category,
                    "type": "expense",
                    "amount": amount,
                    "currency": currency,
                }
            )

    last_day = calendar.monthrange(year, month_number)[1]
    for merchant, amount, day in SUBSCRIPTIONS[user_id]:
        rows.append(
            {
                "user_id": user_id,
                "date": f"{year:04d}-{month_number:02d}-{min(day, last_day):02d}",
                "merchant": merchant,
                "category": "Subscriptions",
                "type": "expense",
                "amount": amount,
                "currency": currency,
            }
        )
    return rows


def build_income(user: dict, month: str) -> list[dict]:
    """Salary plus any irregular income for one user in one month."""
    year, month_number = (int(part) for part in month.split("-"))
    rows = [
        {
            "user_id": user["user_id"],
            "date": f"{year:04d}-{month_number:02d}-01",
            "merchant": "Salary",
            "category": "Income",
            "type": "income",
            "amount": user["monthly_income"],
            "currency": user["currency"],
        }
    ]
    for extra_month, merchant, amount, day in EXTRA_INCOME.get(user["user_id"], []):
        if extra_month == month:
            rows.append(
                {
                    "user_id": user["user_id"],
                    "date": f"{year:04d}-{month_number:02d}-{day:02d}",
                    "merchant": merchant,
                    "category": "Income",
                    "type": "income",
                    "amount": amount,
                    "currency": user["currency"],
                }
            )
    return rows


def generate_transactions() -> list[dict]:
    rng = random.Random(SEED)
    rows: list[dict] = []

    for user in USERS:
        for month in MONTHS:
            rows.extend(build_income(user, month))
            rows.extend(
                build_expenses(rng, user["user_id"], user["currency"], month)
            )

    # Chronological, with a stable tiebreak so ids never shuffle between runs.
    rows.sort(key=lambda r: (r["date"], r["user_id"], r["category"], r["merchant"], r["amount"]))
    for index, row in enumerate(rows, start=1):
        row["transaction_id"] = f"TXN{index:04d}"

    field_order = [
        "transaction_id", "user_id", "date", "merchant",
        "category", "type", "amount", "currency",
    ]
    return [{key: row[key] for key in field_order} for row in rows]


def verify(transactions: list[dict]) -> None:
    """Fail loudly if the generated data drifts from the spec's worked examples."""

    def expenses(user_id: str, month: str) -> int:
        return sum(
            t["amount"] for t in transactions
            if t["user_id"] == user_id and t["date"].startswith(month)
            and t["type"] == "expense"
        )

    def income(user_id: str, month: str) -> int:
        return sum(
            t["amount"] for t in transactions
            if t["user_id"] == user_id and t["date"].startswith(month)
            and t["type"] == "income"
        )

    checks = [
        ("USER001 August income", income("USER001", "2026-08"), 60000),
        ("USER001 August expenses", expenses("USER001", "2026-08"), 42500),
        ("USER001 July expenses", expenses("USER001", "2026-07"), 36100),
    ]
    for label, actual, expected in checks:
        if actual != expected:
            raise AssertionError(f"{label}: expected {expected}, generated {actual}")

    change = expenses("USER001", "2026-08") - expenses("USER001", "2026-07")
    if change != 6400:
        raise AssertionError(f"July->August change: expected 6400, generated {change}")


def category_totals(transactions: Iterable[dict], user_id: str, month: str) -> dict[str, int]:
    totals: dict[str, int] = {}
    for t in transactions:
        if t["user_id"] == user_id and t["date"].startswith(month) and t["type"] == "expense":
            totals[t["category"]] = totals.get(t["category"], 0) + t["amount"]
    return dict(sorted(totals.items(), key=lambda kv: -kv[1]))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> None:
    transactions = generate_transactions()
    verify(transactions)

    write_json(DATA_DIR / "users.json", USERS)
    write_json(DATA_DIR / "budgets.json", BUDGETS)
    write_json(DATA_DIR / "transactions.json", transactions)

    print(f"Wrote {len(transactions)} transactions to {DATA_DIR}")
    print(f"  users.json         {len(USERS)} users")
    print(f"  budgets.json       {len(BUDGETS)} budgets")
    print(f"  transactions.json  {MONTHS[0]} to {MONTHS[-1]}\n")

    for user in USERS:
        user_id = user["user_id"]
        print(f"{user_id} ({user['name']})")
        print(f"  {'month':<10}{'income':>10}{'expenses':>10}{'net':>10}")
        for month in MONTHS:
            rows = [t for t in transactions if t["user_id"] == user_id and t["date"].startswith(month)]
            income = sum(t["amount"] for t in rows if t["type"] == "income")
            spent = sum(t["amount"] for t in rows if t["type"] == "expense")
            print(f"  {month:<10}{income:>10,}{spent:>10,}{income - spent:>10,}")
        print()

    print("USER001 August 2026 by category")
    for category, amount in category_totals(transactions, "USER001", "2026-08").items():
        print(f"  {category:<16}{amount:>9,}")


if __name__ == "__main__":
    main()
