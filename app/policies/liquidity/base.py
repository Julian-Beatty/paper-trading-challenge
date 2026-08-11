"""Base module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep base concerns isolated and readable.

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class LiquidityContext:
    competition_id: int
    participant_id: int
    symbol: str
    timestamp: datetime
    market_price: Decimal
    remaining_quantity: int
    configured_capacity: int


class LiquidityPolicy(ABC):
    @abstractmethod
    def available_quantity(self, context: LiquidityContext) -> int:
        raise NotImplementedError
