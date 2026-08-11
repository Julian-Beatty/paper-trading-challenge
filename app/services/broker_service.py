"""Broker Service module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep broker service concerns isolated and readable.

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import OrderSide, OrderStatus, OrderType
from app.models.entities import Instrument, Order
from app.policies.liquidity.base import LiquidityContext
from app.policies.liquidity.factory import build_liquidity_policy
from app.services.execution_service import ExecutionService


class BrokerService:
    def __init__(self, db: Session, liquidity_policy_name: str):
        self.db = db
        self.policy = build_liquidity_policy(liquidity_policy_name)
        self.execution_service = ExecutionService(db)

    def process_symbol(self, competition_id: int, instrument: Instrument, price: Decimal, timestamp) -> None:
        participants = self.db.scalars(
            select(Order.participant_id)
            .where(
                Order.competition_id == competition_id,
                Order.instrument_id == instrument.id,
                Order.status.in_([OrderStatus.ACKNOWLEDGED.value, OrderStatus.PARTIALLY_FILLED.value]),
            )
            .distinct()
        ).all()

        for participant_id in participants:
            capacity = instrument.minute_liquidity
            orders = self.db.scalars(
                select(Order)
                .where(
                    Order.competition_id == competition_id,
                    Order.participant_id == participant_id,
                    Order.instrument_id == instrument.id,
                    Order.status.in_([OrderStatus.ACKNOWLEDGED.value, OrderStatus.PARTIALLY_FILLED.value]),
                )
                .order_by(Order.created_at, Order.id)
            ).all()
            orders.sort(key=self._priority_key)
            for order in orders:
                if capacity <= 0:
                    break
                if not self._marketable(order, price):
                    continue
                context = LiquidityContext(
                    competition_id=competition_id,
                    participant_id=participant_id,
                    symbol=instrument.symbol,
                    timestamp=timestamp,
                    market_price=price,
                    remaining_quantity=order.remaining_quantity,
                    configured_capacity=capacity,
                )
                allowed = min(capacity, self.policy.available_quantity(context))
                fill_quantity = min(order.remaining_quantity, allowed)
                if fill_quantity > 0:
                    self.execution_service.apply_fill(order, fill_quantity, price, timestamp)
                    capacity -= fill_quantity

    @staticmethod
    def _marketable(order: Order, price: Decimal) -> bool:
        if order.order_type == OrderType.MARKET.value:
            return True
        if order.side == OrderSide.BUY.value:
            return price <= Decimal(order.limit_price)
        return price >= Decimal(order.limit_price)

    @staticmethod
    def _priority_key(order: Order):
        market_priority = 0 if order.order_type == OrderType.MARKET.value else 1
        if order.order_type == OrderType.MARKET.value:
            aggressiveness = Decimal("0")
        elif order.side == OrderSide.BUY.value:
            aggressiveness = -Decimal(order.limit_price)
        else:
            aggressiveness = Decimal(order.limit_price)
        return market_priority, aggressiveness, order.created_at, order.id
