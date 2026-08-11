"""Base module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep base concerns isolated and readable.

from abc import ABC, abstractmethod
from decimal import Decimal


class ExecutionPricePolicy(ABC):
    @abstractmethod
    def fill_price(self, market_price: Decimal, **kwargs) -> Decimal:
        raise NotImplementedError
