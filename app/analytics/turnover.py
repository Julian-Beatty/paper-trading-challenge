"""Turnover module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep turnover concerns isolated and readable.

from decimal import Decimal


def turnover(gross_traded_value: Decimal, average_portfolio_value: Decimal) -> Decimal:
    if average_portfolio_value <= 0:
        return Decimal("0")
    return gross_traded_value / average_portfolio_value
