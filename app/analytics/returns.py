"""Returns module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep returns concerns isolated and readable.

from decimal import Decimal


def simple_return(start: Decimal, end: Decimal) -> Decimal:
    if start <= 0:
        raise ValueError("start must be positive")
    return (end - start) / start
