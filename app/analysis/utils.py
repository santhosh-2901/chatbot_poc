"""Shared arithmetic helpers.

Small, but centralised on purpose: rounding that varies between modules would
make totals stop reconciling with their parts, and reconciliation is the whole
promise of this layer.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def round_money(value: float) -> int:
    """Round to whole rupees, half away from zero.

    Python's built-in :func:`round` uses banker's rounding, so ``round(2.5)``
    is ``2``. Harmless in isolation, surprising in a financial report.
    """
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def round_to(value: float, step: int) -> int:
    """Round to the nearest multiple of ``step`` — budgets in tidy numbers."""
    if step < 1:
        raise ValueError("step must be positive")
    return round_money(value / step) * step


def percentage(part: float, whole: float, digits: int = 1) -> float | None:
    """``part`` as a percentage of ``whole``.

    Returns ``None`` when ``whole`` is zero. That is deliberate: an undefined
    percentage must stay undefined all the way to the model, so it can say
    "new spending this month" instead of narrating a fabricated number.
    """
    if not whole:
        return None
    return round(part / whole * 100, digits)


def mean(values: list[int] | tuple[int, ...]) -> float:
    return sum(values) / len(values) if values else 0.0


def median(values: list[int] | tuple[int, ...]) -> float:
    """The middle value.

    Preferred over the mean for budget targets: one unusual month should not
    drag the recommendation up toward it, and a fixed cost like rent has a
    median equal to itself, so it gets no spurious headroom.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[midpoint])
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2
