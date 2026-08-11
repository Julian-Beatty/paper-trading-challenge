"""Competition Service module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep competition service concerns isolated and readable.

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.exceptions import StateTransitionError
from app.models.entities import Competition, DailySnapshot, Instrument, MarketPrice, Participant
from app.schemas.core import CompetitionCreate
from app.services.broker_service import BrokerService
from app.services.portfolio_service import get_portfolio
from app.services.snapshot_service import SnapshotService
from app.simulation.gbm import simulate_gbm_path
from app.simulation.universe import DEFAULT_UNIVERSE


class CompetitionService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, request: CompetitionCreate) -> Competition:
        market_open = datetime.combine(
            request.trading_date,
            time(request.starting_hour, request.starting_minute),
            tzinfo=timezone.utc,
        )
        market_close = market_open + timedelta(minutes=request.minutes)
        competition = Competition(
            name=request.name,
            trading_date=request.trading_date,
            market_open=market_open,
            market_close=market_close,
            current_time=market_open,
            random_seed=request.random_seed,
            liquidity_policy=request.liquidity_policy,
            status="RUNNING",
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(competition)
        self.db.flush()

        universe = request.stocks if request.stocks is not None else DEFAULT_UNIVERSE

        for index, spec in enumerate(universe):
            instrument = Instrument(
                competition_id=competition.id,
                symbol=spec.symbol if hasattr(spec, "symbol") else spec["symbol"],
                display_name=spec.display_name if hasattr(spec, "display_name") else spec["display_name"],
                initial_price=spec.initial_price if hasattr(spec, "initial_price") else spec["initial_price"],
                annual_drift=Decimal(str(spec.annual_drift if hasattr(spec, "annual_drift") else spec["annual_drift"])),
                annual_volatility=Decimal(str(spec.annual_volatility if hasattr(spec, "annual_volatility") else spec["annual_volatility"])),
                minute_liquidity=spec.minute_liquidity if hasattr(spec, "minute_liquidity") else spec["minute_liquidity"],
                is_active=True,
            )
            self.db.add(instrument)
            self.db.flush()
            path = simulate_gbm_path(
                initial_price=spec.initial_price if hasattr(spec, "initial_price") else spec["initial_price"],
                annual_drift=float(spec.annual_drift if hasattr(spec, "annual_drift") else spec["annual_drift"]),
                annual_volatility=float(spec.annual_volatility if hasattr(spec, "annual_volatility") else spec["annual_volatility"]),
                start_time=market_open,
                minutes=request.minutes,
                seed=request.random_seed + index,
            )
            self.db.add_all([
                MarketPrice(
                    competition_id=competition.id,
                    instrument_id=instrument.id,
                    timestamp=timestamp,
                    price=price,
                )
                for timestamp, price in path
            ])
        self.db.commit()
        self.db.refresh(competition)
        return competition

    def advance(self, competition_id: int, minutes: int = 1) -> Competition:
        competition = self.db.get(Competition, competition_id)
        if competition is None:
            raise ValueError("Competition not found")
        if competition.status != "RUNNING":
            raise StateTransitionError("Competition is already closed")
        if minutes <= 0:
            raise ValueError("minutes must be positive")

        # If the requested advance extends beyond the configured market close,
        # process only the remaining market minutes and then finalize the day.
        requested_end = competition.current_time + timedelta(minutes=minutes)
        overshoots_close = requested_end > competition.market_close
        remaining_minutes = int(
            (competition.market_close - competition.current_time).total_seconds() // 60
        )
        minutes_to_process = min(minutes, max(remaining_minutes, 0))

        for _ in range(minutes_to_process):
            next_time = competition.current_time + timedelta(minutes=1)
            competition.current_time = next_time
            self.db.commit()

            # Reveal the pre-generated price for this minute and let the broker
            # process active orders using the competition's liquidity policy.
            instruments = self.db.scalars(
                select(Instrument).where(Instrument.competition_id == competition_id)
            ).all()
            broker = BrokerService(self.db, competition.liquidity_policy)
            for instrument in instruments:
                price = self.db.scalar(
                    select(MarketPrice.price).where(
                        MarketPrice.competition_id == competition_id,
                        MarketPrice.instrument_id == instrument.id,
                        MarketPrice.timestamp == next_time,
                    )
                )
                broker.process_symbol(competition_id, instrument, Decimal(price), next_time)

            # Capture one valuation snapshot per participant after all fills for
            # the minute have been applied.
            participants = self.db.scalars(
                select(Participant).where(Participant.competition_id == competition_id)
            ).all()
            snapshots = SnapshotService(self.db)
            for participant in participants:
                snapshots.capture(competition_id, participant.id, next_time)

        # Overshooting is intentionally clamped rather than treated as an error.
        # Reaching the boundary exactly still permits the explicit close-day API;
        # asking to move beyond the boundary finalizes the day automatically.
        if overshoots_close:
            self._finalize_day(competition)

        self.db.refresh(competition)
        return competition

    def close_day(self, competition_id: int):
        competition = self.db.get(Competition, competition_id)
        if competition is None:
            raise ValueError("Competition not found")
        if competition.status == "CLOSED":
            raise StateTransitionError("Competition already closed")
        if competition.current_time != competition.market_close:
            raise StateTransitionError(
                "Advance simulation to market close before closing the day"
            )
        return self._finalize_day(competition)

    def _finalize_day(self, competition: Competition):
        """Persist final daily results and mark a competition closed."""
        participants = self.db.scalars(
            select(Participant).where(
                Participant.competition_id == competition.id
            )
        ).all()
        snapshots = []
        for participant in participants:
            portfolio = get_portfolio(
                self.db, participant.id, competition.current_time
            )
            opening = Decimal(participant.starting_cash)
            closing = Decimal(portfolio["total_portfolio_value"])
            pnl = closing - opening
            daily_return = pnl / opening
            snapshot = DailySnapshot(
                competition_id=competition.id,
                participant_id=participant.id,
                trading_date=competition.trading_date,
                opening_value=opening,
                closing_value=closing,
                daily_pnl=pnl,
                daily_return=daily_return,
                created_at=competition.current_time,
            )
            self.db.add(snapshot)
            snapshots.append(snapshot)

        competition.status = "CLOSED"
        competition.closed_at = competition.current_time
        self.db.commit()
        return snapshots
