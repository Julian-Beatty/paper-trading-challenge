"""Enums module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep enums concerns isolated and readable.

from enum import StrEnum


class CompetitionStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    CLOSED = "CLOSED"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(StrEnum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


ACTIVE_ORDER_STATUSES = {
    OrderStatus.NEW,
    OrderStatus.ACKNOWLEDGED,
    OrderStatus.PARTIALLY_FILLED,
}
TERMINAL_ORDER_STATUSES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELLED,
    OrderStatus.REJECTED,
}
