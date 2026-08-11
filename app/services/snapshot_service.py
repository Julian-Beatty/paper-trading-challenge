"""Snapshot Service module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep snapshot service concerns isolated and readable.

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.entities import PortfolioSnapshot
from app.services.portfolio_service import get_portfolio


class SnapshotService:
    def __init__(self, db: Session):
        self.db = db

    def capture(self, competition_id: int, participant_id: int, timestamp) -> PortfolioSnapshot:
        p = get_portfolio(self.db, participant_id, timestamp)
        snapshot = PortfolioSnapshot(
            competition_id=competition_id,
            participant_id=participant_id,
            timestamp=timestamp,
            cash_balance=p["cash_balance"],
            reserved_cash=p["reserved_cash"],
            positions_market_value=p["positions_market_value"],
            realized_pnl=p["realized_pnl"],
            unrealized_pnl=p["unrealized_pnl"],
            total_portfolio_value=p["total_portfolio_value"],
        )
        self.db.merge(snapshot)
        self.db.commit()
        return snapshot
