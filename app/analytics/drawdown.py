"""Drawdown module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep drawdown concerns isolated and readable.

from decimal import Decimal


def drawdown_series(values: list[Decimal]) -> tuple[list[Decimal], Decimal]:
    if not values:
        return [], Decimal("0")
    peak = values[0]
    max_drawdown = Decimal("0")
    result: list[Decimal] = []
    for value in values:
        peak = max(peak, value)
        drawdown = Decimal("0") if peak == 0 else (peak - value) / peak
        result.append(drawdown)
        max_drawdown = max(max_drawdown, drawdown)
    return result, max_drawdown
