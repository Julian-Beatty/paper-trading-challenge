"""Order Service module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep order service concerns isolated and readable.

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ACTIVE_ORDER_STATUSES, OrderSide, OrderStatus, OrderType
from app.domain.exceptions import (
    InsufficientFundsError,
    InsufficientPositionError,
    StateTransitionError,
    ValidationError,
)
from app.models.entities import Competition, Instrument, Order, Participant, Position
from app.schemas.core import OrderCreate, OrderReplace
from app.services.portfolio_service import get_portfolio, latest_price, reserved_shares


class OrderService:
    def __init__(self, db: Session):
        self.db = db

    def submit(self, competition_id: int, request: OrderCreate) -> Order:
        competition = self.db.get(Competition, competition_id)
        participant = self.db.get(Participant, request.participant_id)
        instrument = self.db.scalar(
            select(Instrument).where(
                Instrument.competition_id == competition_id,
                Instrument.symbol == request.symbol,
                Instrument.is_active.is_(True),
            )
        )
        if competition is None or participant is None or participant.competition_id != competition_id:
            raise ValidationError("Invalid competition or participant")
        if instrument is None:
            raise ValidationError("Symbol is not in the active stock universe")
        if competition.status == "CLOSED":
            raise StateTransitionError("Competition is closed")

        self._validate_resources(competition, participant, instrument, request)

        now = competition.current_time
        order = Order(
            competition_id=competition_id,
            participant_id=participant.id,
            instrument_id=instrument.id,
            side=request.side.value,
            order_type=request.order_type.value,
            quantity=request.quantity,
            filled_quantity=0,
            limit_price=request.limit_price,
            status=OrderStatus.ACKNOWLEDGED.value,
            created_at=now,
            acknowledged_at=now,
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def _validate_resources(self, competition, participant, instrument, request):
        if request.side == OrderSide.BUY:
            portfolio = get_portfolio(self.db, participant.id, competition.current_time)
            reservation_price = (
                Decimal(request.limit_price)
                if request.order_type == OrderType.LIMIT
                else latest_price(self.db, competition.id, instrument.id, competition.current_time)
            )
            required = Decimal(request.quantity) * reservation_price
            if portfolio["available_cash"] < required:
                raise InsufficientFundsError("Insufficient available cash")
        else:
            position = self.db.scalar(
                select(Position).where(
                    Position.participant_id == participant.id,
                    Position.instrument_id == instrument.id,
                )
            )
            owned = 0 if position is None else position.quantity
            available = owned - reserved_shares(self.db, participant.id, instrument.id)
            if available < request.quantity:
                raise InsufficientPositionError("Insufficient available shares")

    def cancel(self, order_id: int) -> Order:
        order = self.db.get(Order, order_id)
        if order is None:
            raise ValidationError("Order not found")
        if order.status not in {OrderStatus.ACKNOWLEDGED.value, OrderStatus.PARTIALLY_FILLED.value}:
            raise ValidationError("Only active orders can be cancelled")
        competition = self.db.get(Competition, order.competition_id)
        order.status = OrderStatus.CANCELLED.value
        order.cancelled_at = competition.current_time
        order.version += 1
        self.db.commit()
        self.db.refresh(order)
        return order

    def replace(self, order_id: int, request: OrderReplace) -> Order:
        old = self.db.get(Order, order_id)
        if old is None:
            raise ValidationError("Order not found")
        if old.status not in {OrderStatus.ACKNOWLEDGED.value, OrderStatus.PARTIALLY_FILLED.value}:
            raise ValidationError("Only active orders can be replaced")
        instrument = self.db.get(Instrument, old.instrument_id)
        replacement_request = OrderCreate(
            participant_id=old.participant_id,
            symbol=instrument.symbol,
            side=OrderSide(old.side),
            order_type=OrderType(old.order_type),
            quantity=request.quantity,
            limit_price=request.limit_price if old.order_type == OrderType.LIMIT.value else None,
        )
        self.cancel(old.id)
        new = self.submit(old.competition_id, replacement_request)
        new.replaces_order_id = old.id
        old.replaced_by_order_id = new.id
        self.db.commit()
        self.db.refresh(new)
        return new
