"""Order Rules module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep order rules concerns isolated and readable.

from app.domain.enums import OrderStatus
from app.domain.exceptions import StateTransitionError


ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.ACKNOWLEDGED, OrderStatus.REJECTED},
    OrderStatus.ACKNOWLEDGED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
    },
}


def validate_transition(current: OrderStatus, target: OrderStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise StateTransitionError(f"Invalid order transition: {current} -> {target}")
