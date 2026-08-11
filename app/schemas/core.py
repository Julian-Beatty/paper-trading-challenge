"""Core module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep core concerns isolated and readable.

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import OrderSide, OrderType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StockSpec(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    display_name: str | None = Field(default=None, max_length=120)
    initial_price: Decimal = Field(gt=0)
    annual_drift: Decimal = Field(default=Decimal("0.05"))
    annual_volatility: Decimal = Field(gt=0)
    minute_liquidity: int = Field(default=100, ge=1)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol cannot be blank")
        return normalized

    @model_validator(mode="after")
    def default_display_name(self):
        if self.display_name is None or not self.display_name.strip():
            self.display_name = self.symbol
        else:
            self.display_name = self.display_name.strip()
        return self


class CompetitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    trading_date: date
    starting_hour: int = Field(default=9, ge=0, le=23)
    starting_minute: int = Field(default=30, ge=0, le=59)
    minutes: int = Field(default=390, ge=1)
    random_seed: int = 12345
    liquidity_policy: str = "fixed_minute"
    stocks: list[StockSpec] | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_universe(self):
        if self.stocks is not None:
            if not self.stocks:
                raise ValueError("stocks must contain at least one instrument")
            symbols = [stock.symbol for stock in self.stocks]
            if len(symbols) != len(set(symbols)):
                raise ValueError("stock symbols must be unique within a competition")
        return self


class CompetitionRead(ORMModel):
    id: int
    name: str
    trading_date: date
    market_open: datetime
    market_close: datetime
    current_time: datetime
    random_seed: int
    liquidity_policy: str
    status: str


class ParticipantCreate(BaseModel):
    name: str
    starting_cash: Decimal = Field(gt=0)


class ParticipantRead(ORMModel):
    id: int
    competition_id: int
    name: str
    starting_cash: Decimal
    cash_balance: Decimal


class OrderCreate(BaseModel):
    participant_id: int
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_price(self):
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        if self.order_type == OrderType.MARKET and self.limit_price is not None:
            raise ValueError("limit_price is not allowed for MARKET orders")
        self.symbol = self.symbol.strip().upper()
        return self


class OrderReplace(BaseModel):
    quantity: int = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)


class OrderRead(ORMModel):
    id: int
    competition_id: int
    participant_id: int
    side: str
    order_type: str
    quantity: int
    filled_quantity: int
    limit_price: Decimal | None
    average_fill_price: Decimal | None
    status: str
    created_at: datetime
    replaces_order_id: int | None


class PositionRead(BaseModel):
    symbol: str
    quantity: int
    average_price: Decimal
    market_price: Decimal
    market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal


class PortfolioRead(BaseModel):
    participant_id: int
    cash_balance: Decimal
    reserved_cash: Decimal
    available_cash: Decimal
    positions_market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_portfolio_value: Decimal
    positions: list[PositionRead]


class LeaderboardEntry(BaseModel):
    rank: int
    tie_group: int
    participant_id: int
    participant_name: str
    pnl: Decimal
    return_pct: Decimal
    portfolio_value: Decimal
    maximum_drawdown: Decimal | None = None
