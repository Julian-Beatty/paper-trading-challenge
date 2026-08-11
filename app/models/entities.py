"""Entities module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep entities concerns isolated and readable.

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


MONEY = Numeric(18, 4)


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    trading_date: Mapped[date] = mapped_column(Date)
    market_open: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    market_close: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    random_seed: Mapped[int] = mapped_column(Integer)
    liquidity_policy: Mapped[str] = mapped_column(String(50), default="fixed_minute")
    status: Mapped[str] = mapped_column(String(30), default="CREATED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("competition_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    starting_cash: Mapped[Decimal] = mapped_column(MONEY)
    cash_balance: Mapped[Decimal] = mapped_column(MONEY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("competition_id", "symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    initial_price: Mapped[Decimal] = mapped_column(MONEY)
    annual_drift: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    annual_volatility: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    minute_liquidity: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MarketPrice(Base):
    __tablename__ = "market_prices"
    __table_args__ = (UniqueConstraint("competition_id", "instrument_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    price: Mapped[Decimal] = mapped_column(MONEY)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    side: Mapped[str] = mapped_column(String(10))
    order_type: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    limit_price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    average_fill_price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaces_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    replaced_by_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(250), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    instrument: Mapped[Instrument] = relationship()

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(MONEY)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer)


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("competition_id", "participant_id", "instrument_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    average_price: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    instrument: Mapped[Instrument] = relationship()


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (UniqueConstraint("competition_id", "participant_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cash_balance: Mapped[Decimal] = mapped_column(MONEY)
    reserved_cash: Mapped[Decimal] = mapped_column(MONEY)
    positions_market_value: Mapped[Decimal] = mapped_column(MONEY)
    realized_pnl: Mapped[Decimal] = mapped_column(MONEY)
    unrealized_pnl: Mapped[Decimal] = mapped_column(MONEY)
    total_portfolio_value: Mapped[Decimal] = mapped_column(MONEY)


class DailySnapshot(Base):
    __tablename__ = "daily_snapshots"
    __table_args__ = (UniqueConstraint("competition_id", "participant_id", "trading_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), index=True)
    trading_date: Mapped[date] = mapped_column(Date)
    opening_value: Mapped[Decimal] = mapped_column(MONEY)
    closing_value: Mapped[Decimal] = mapped_column(MONEY)
    daily_pnl: Mapped[Decimal] = mapped_column(MONEY)
    daily_return: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    daily_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tie_group: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
