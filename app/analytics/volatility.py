"""Volatility module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep volatility concerns isolated and readable.

from decimal import Decimal
from statistics import pstdev


def return_volatility(returns: list[Decimal]) -> Decimal:
    if len(returns) < 2:
        return Decimal("0")
    return Decimal(str(pstdev(float(r) for r in returns)))
