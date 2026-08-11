"""Universe module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep universe concerns isolated and readable.

from decimal import Decimal

DEFAULT_UNIVERSE = [
    {
        "symbol": "AAPL",
        "display_name": "Apple Synthetic",
        "initial_price": Decimal("100.00"),
        "annual_drift": 0.08,
        "annual_volatility": 0.25,
        "minute_liquidity": 100,
    },
    {
        "symbol": "MSFT",
        "display_name": "Microsoft Synthetic",
        "initial_price": Decimal("200.00"),
        "annual_drift": 0.06,
        "annual_volatility": 0.20,
        "minute_liquidity": 80,
    },
    {
        "symbol": "TSLA",
        "display_name": "Tesla Synthetic",
        "initial_price": Decimal("250.00"),
        "annual_drift": 0.10,
        "annual_volatility": 0.40,
        "minute_liquidity": 40,
    },
]
