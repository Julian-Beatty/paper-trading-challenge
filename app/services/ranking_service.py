"""Ranking Service module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: rank participants deterministically using return, drawdown, and closing value.

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.drawdown import drawdown_series
from app.models.entities import DailySnapshot, Participant, PortfolioSnapshot


class RankingService:
    """Build daily and overall competition ladders from persisted portfolio history."""

    def __init__(self, db: Session):
        self.db = db

    def daily(self, competition_id: int, trading_date):
        """Rank one trading day by return, then lower drawdown, then closing value."""
        rows = self.db.execute(
            select(DailySnapshot, Participant)
            .join(Participant, Participant.id == DailySnapshot.participant_id)
            .where(
                DailySnapshot.competition_id == competition_id,
                DailySnapshot.trading_date == trading_date,
            )
        ).all()

        entries = []
        for snapshot, participant in rows:
            maximum_drawdown = self._daily_drawdown(
                competition_id=competition_id,
                participant_id=participant.id,
                trading_date=trading_date,
                opening_value=Decimal(snapshot.opening_value),
            )
            entries.append(
                (
                    snapshot,
                    participant,
                    Decimal(snapshot.daily_return),
                    maximum_drawdown,
                    Decimal(snapshot.closing_value),
                )
            )

        # Lower maximum drawdown is better, while return and closing value are
        # ranked from highest to lowest. Participant ID is display ordering only.
        entries.sort(key=lambda entry: (-entry[2], entry[3], -entry[4], entry[1].id))
        return self._assign_daily_ranks(entries)

    def overall(self, competition_id: int):
        """Rank cumulative performance using the same deterministic tie-breakers."""
        participants = self.db.scalars(
            select(Participant).where(Participant.competition_id == competition_id)
        ).all()
        entries = []
        for participant in participants:
            snapshots = self.db.scalars(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.participant_id == participant.id)
                .order_by(PortfolioSnapshot.timestamp)
            ).all()
            starting_value = Decimal(participant.starting_cash)
            latest_value = (
                starting_value
                if not snapshots
                else Decimal(snapshots[-1].total_portfolio_value)
            )
            pnl = latest_value - starting_value
            ret = pnl / starting_value

            # Include starting cash as the initial high-water mark. Otherwise a
            # loss in the first simulated minute could be omitted from drawdown.
            values = [starting_value] + [
                Decimal(snapshot.total_portfolio_value) for snapshot in snapshots
            ]
            _, maximum_drawdown = drawdown_series(values)
            entries.append(
                (participant, latest_value, pnl, ret, maximum_drawdown)
            )

        entries.sort(key=lambda entry: (-entry[3], entry[4], -entry[1], entry[0].id))

        result = []
        previous_key = None
        rank = 0
        for index, entry in enumerate(entries, start=1):
            # Participant ID never breaks an economic tie; it only stabilizes
            # output ordering for participants whose financial results are equal.
            key = (entry[3], entry[4], entry[1])
            if key != previous_key:
                rank = index
                previous_key = key
            result.append({
                "rank": rank,
                "tie_group": rank,
                "participant_id": entry[0].id,
                "participant_name": entry[0].name,
                "pnl": entry[2],
                "return_pct": entry[3],
                "portfolio_value": entry[1],
                "maximum_drawdown": entry[4],
            })
        return result

    def _daily_drawdown(
        self,
        *,
        competition_id: int,
        participant_id: int,
        trading_date,
        opening_value: Decimal,
    ) -> Decimal:
        """Calculate maximum drawdown from the opening value and that day's snapshots."""
        snapshots = self.db.scalars(
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.competition_id == competition_id,
                PortfolioSnapshot.participant_id == participant_id,
            )
            .order_by(PortfolioSnapshot.timestamp)
        ).all()
        values = [opening_value] + [
            Decimal(snapshot.total_portfolio_value)
            for snapshot in snapshots
            if snapshot.timestamp.date() == trading_date
        ]
        _, maximum_drawdown = drawdown_series(values)
        return maximum_drawdown

    @staticmethod
    def _assign_daily_ranks(entries):
        """Assign competition ranks while preserving true ties."""
        result = []
        previous_key = None
        rank = 0
        for index, entry in enumerate(entries, start=1):
            snapshot, participant, daily_return, maximum_drawdown, closing_value = entry
            key = (daily_return, maximum_drawdown, closing_value)
            if key != previous_key:
                rank = index
                previous_key = key
            snapshot.daily_rank = rank
            snapshot.tie_group = rank
            result.append({
                "rank": rank,
                "tie_group": rank,
                "participant_id": participant.id,
                "participant_name": participant.name,
                "pnl": Decimal(snapshot.daily_pnl),
                "return_pct": daily_return,
                "portfolio_value": closing_value,
                "maximum_drawdown": maximum_drawdown,
            })
        return result
