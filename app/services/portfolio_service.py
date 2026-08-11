"""Portfolio Service module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep portfolio service concerns isolated and readable.

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ACTIVE_ORDER_STATUSES, OrderSide, OrderType
from app.models.entities import Instrument, MarketPrice, Order, Participant, Position


ZERO = Decimal("0")


def latest_price(db: Session, competition_id: int, instrument_id: int, at_time) -> Decimal:
    price = db.scalar(
        select(MarketPrice.price)
        .where(
            MarketPrice.competition_id == competition_id,
            MarketPrice.instrument_id == instrument_id,
            MarketPrice.timestamp <= at_time,
        )
        .order_by(MarketPrice.timestamp.desc())
        .limit(1)
    )
    if price is None:
        raise ValueError("No revealed market price available")
    return Decimal(price)


def reserved_cash(db: Session, participant: Participant, at_time) -> Decimal:
    orders = db.scalars(
        select(Order).where(
            Order.participant_id == participant.id,
            Order.side == OrderSide.BUY.value,
            Order.status.in_([s.value for s in ACTIVE_ORDER_STATUSES]),
        )
    ).all()
    total = ZERO
    for order in orders:
        if order.order_type == OrderType.LIMIT.value:
            reservation_price = Decimal(order.limit_price)
        else:
            reservation_price = latest_price(db, participant.competition_id, order.instrument_id, at_time)
        total += Decimal(order.remaining_quantity) * reservation_price
    return total


def reserved_shares(db: Session, participant_id: int, instrument_id: int) -> int:
    orders = db.scalars(
        select(Order).where(
            Order.participant_id == participant_id,
            Order.instrument_id == instrument_id,
            Order.side == OrderSide.SELL.value,
            Order.status.in_([s.value for s in ACTIVE_ORDER_STATUSES]),
        )
    ).all()
    return sum(o.remaining_quantity for o in orders)


def get_portfolio(db: Session, participant_id: int, at_time):
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise ValueError("Participant not found")

    # Load every position row, including positions whose quantity has returned to
    # zero. A fully closed position can still contain realized P&L that belongs
    # in the participant-level total even though it is no longer an active holding.
    positions = db.scalars(
        select(Position).where(Position.participant_id == participant_id)
    ).all()

    position_rows = []
    market_value = ZERO
    realized = sum((Decimal(position.realized_pnl) for position in positions), ZERO)
    unrealized = ZERO
    for position in positions:
        # Closed positions contribute to realized P&L above but should not appear
        # in the current-positions list or contribute market/unrealized value.
        if position.quantity <= 0:
            continue

        price = latest_price(db, participant.competition_id, position.instrument_id, at_time)
        value = Decimal(position.quantity) * price
        upnl = Decimal(position.quantity) * (price - Decimal(position.average_price))
        market_value += value
        unrealized += upnl
        position_rows.append({
            "symbol": position.instrument.symbol,
            "quantity": position.quantity,
            "average_price": Decimal(position.average_price),
            "market_price": price,
            "market_value": value,
            "realized_pnl": Decimal(position.realized_pnl),
            "unrealized_pnl": upnl,
        })

    reserved = reserved_cash(db, participant, at_time)
    cash = Decimal(participant.cash_balance)
    return {
        "participant_id": participant.id,
        "cash_balance": cash,
        "reserved_cash": reserved,
        "available_cash": cash - reserved,
        "positions_market_value": market_value,
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "total_portfolio_value": cash + market_value,
        "positions": position_rows,
    }
