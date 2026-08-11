"""Test Drawdown module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep test drawdown concerns isolated and readable.

from decimal import Decimal

from app.analytics.drawdown import drawdown_series


def test_maximum_drawdown():
    _, maximum = drawdown_series([
        Decimal("100"), Decimal("110"), Decimal("99"), Decimal("105")
    ])
    assert maximum == Decimal("0.1")
