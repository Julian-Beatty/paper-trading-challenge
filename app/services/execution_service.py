"""Execution Service module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep execution service concerns isolated and readable.

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import OrderSide, OrderStatus
from app.domain.exceptions import InsufficientFundsError, InsufficientPositionError, ValidationError
from app.models.entities import Competition, Execution, Order, Participant, Position


class ExecutionService:
    def __init__(self, db: Session):
        self.db = db

    def apply_fill(self, order: Order, quantity: int, price: Decimal, timestamp) -> Execution:
        if quantity <= 0 or price <= 0 or quantity > order.remaining_quantity:
            raise ValidationError("Invalid fill")
        if order.status not in {OrderStatus.ACKNOWLEDGED.value, OrderStatus.PARTIALLY_FILLED.value}:
            raise ValidationError("Order is not fillable")

        participant = self.db.get(Participant, order.participant_id)
        position = self.db.scalar(
            select(Position).where(
                Position.participant_id == participant.id,
                Position.instrument_id == order.instrument_id,
            )
        )
        if position is None:
            position = Position(
                competition_id=order.competition_id,
                participant_id=participant.id,
                instrument_id=order.instrument_id,
                quantity=0,
                average_price=Decimal("0"),
                realized_pnl=Decimal("0"),
                updated_at=timestamp,
            )
            self.db.add(position)
            self.db.flush()

        trade_value = Decimal(quantity) * Decimal(price)
        if order.side == OrderSide.BUY.value:
            if Decimal(participant.cash_balance) < trade_value:
                raise InsufficientFundsError("Insufficient cash at execution")
            old_cost = Decimal(position.quantity) * Decimal(position.average_price)
            participant.cash_balance = Decimal(participant.cash_balance) - trade_value
            position.quantity += quantity
            position.average_price = (old_cost + trade_value) / Decimal(position.quantity)
        else:
            if position.quantity < quantity:
                raise InsufficientPositionError("Insufficient shares at execution")
            participant.cash_balance = Decimal(participant.cash_balance) + trade_value
            position.realized_pnl = Decimal(position.realized_pnl) + Decimal(quantity) * (
                Decimal(price) - Decimal(position.average_price)
            )
            position.quantity -= quantity
            if position.quantity == 0:
                position.average_price = Decimal("0")
        position.updated_at = timestamp

        previous_value = Decimal(order.filled_quantity) * Decimal(order.average_fill_price or 0)
        order.filled_quantity += quantity
        order.average_fill_price = (previous_value + trade_value) / Decimal(order.filled_quantity)
        order.status = (
            OrderStatus.FILLED.value
            if order.filled_quantity == order.quantity
            else OrderStatus.PARTIALLY_FILLED.value
        )
        order.version += 1

        sequence = self.db.scalar(
            select(func.count(Execution.id)).where(Execution.competition_id == order.competition_id)
        ) or 0
        execution = Execution(
            competition_id=order.competition_id,
            order_id=order.id,
            participant_id=order.participant_id,
            instrument_id=order.instrument_id,
            quantity=quantity,
            price=price,
            executed_at=timestamp,
            sequence_number=sequence + 1,
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution
