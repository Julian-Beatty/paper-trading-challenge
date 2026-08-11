"""Current Price module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep current price concerns isolated and readable.

from decimal import Decimal
from app.policies.execution_price.base import ExecutionPricePolicy


class CurrentMarketPricePolicy(ExecutionPricePolicy):
    def fill_price(self, market_price: Decimal, **kwargs) -> Decimal:
        return market_price
