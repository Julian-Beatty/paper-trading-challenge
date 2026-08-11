"""Routes module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep routes concerns isolated and readable.

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.plots import (
    PortfolioPoint,
    PortfolioSeries,
    TradeMarker,
    competition_portfolio_plot,
    participant_portfolio_plot,
)
from app.database import get_db
from app.domain.exceptions import DomainError, StateTransitionError
from app.models.entities import Competition, Execution, Instrument, MarketPrice, Order, Participant, PortfolioSnapshot, Position
from app.schemas.core import (
    CompetitionCreate,
    CompetitionRead,
    LeaderboardEntry,
    OrderCreate,
    OrderRead,
    OrderReplace,
    ParticipantCreate,
    ParticipantRead,
    PortfolioRead,
)
from app.services.competition_service import CompetitionService
from app.services.order_service import OrderService
from app.services.participant_service import ParticipantService
from app.services.portfolio_service import get_portfolio
from app.services.ranking_service import RankingService

router = APIRouter()


def run(action):
    try:
        return action()
    except StateTransitionError as exc:
        # HTTP 409 communicates that the request is valid but conflicts with
        # the competition's current lifecycle state (for example, CLOSED).
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (DomainError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/competitions", response_model=CompetitionRead)
def create_competition(request: CompetitionCreate, db: Session = Depends(get_db)):
    return run(lambda: CompetitionService(db).create(request))


@router.get("/competitions/{competition_id}", response_model=CompetitionRead)
def get_competition(competition_id: int, db: Session = Depends(get_db)):
    competition = db.get(Competition, competition_id)
    if competition is None:
        raise HTTPException(404, "Competition not found")
    return competition


@router.post("/competitions/{competition_id}/advance", response_model=CompetitionRead)
def advance_competition(
    competition_id: int,
    minutes: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
):
    return run(lambda: CompetitionService(db).advance(competition_id, minutes))


@router.post("/competitions/{competition_id}/close-day")
def close_day(competition_id: int, db: Session = Depends(get_db)):
    snapshots = run(lambda: CompetitionService(db).close_day(competition_id))
    return {"closed": True, "participants": len(snapshots)}


@router.post("/competitions/{competition_id}/participants", response_model=ParticipantRead)
def create_participant(
    competition_id: int,
    request: ParticipantCreate,
    db: Session = Depends(get_db),
):
    return run(lambda: ParticipantService(db).create(competition_id, request.name, request.starting_cash))


@router.get("/competitions/{competition_id}/participants", response_model=list[ParticipantRead])
def list_participants(competition_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(Participant).where(Participant.competition_id == competition_id)).all()


@router.get("/competitions/{competition_id}/instruments")
def list_instruments(competition_id: int, db: Session = Depends(get_db)):
    competition = db.get(Competition, competition_id)
    instruments = db.scalars(select(Instrument).where(Instrument.competition_id == competition_id)).all()
    return [
        {
            "symbol": i.symbol,
            "display_name": i.display_name,
            "initial_price": i.initial_price,
            "annual_drift": i.annual_drift,
            "annual_volatility": i.annual_volatility,
            "minute_liquidity": i.minute_liquidity,
            "current_price": db.scalar(
                select(MarketPrice.price)
                .where(
                    MarketPrice.instrument_id == i.id,
                    MarketPrice.timestamp <= competition.current_time,
                )
                .order_by(MarketPrice.timestamp.desc())
                .limit(1)
            ),
        }
        for i in instruments
    ]


@router.post("/competitions/{competition_id}/orders", response_model=OrderRead)
def submit_order(competition_id: int, request: OrderCreate, db: Session = Depends(get_db)):
    return run(lambda: OrderService(db).submit(competition_id, request))


@router.get("/orders/{order_id}", response_model=OrderRead)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Order not found")
    return order


@router.get("/participants/{participant_id}/orders", response_model=list[OrderRead])
def list_orders(participant_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(Order).where(Order.participant_id == participant_id).order_by(Order.id)).all()


@router.post("/orders/{order_id}/cancel", response_model=OrderRead)
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    return run(lambda: OrderService(db).cancel(order_id))


@router.post("/orders/{order_id}/replace", response_model=OrderRead)
def replace_order(order_id: int, request: OrderReplace, db: Session = Depends(get_db)):
    return run(lambda: OrderService(db).replace(order_id, request))


@router.get("/orders/{order_id}/executions")
def order_executions(order_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(Execution).where(Execution.order_id == order_id).order_by(Execution.id)).all()


@router.get("/participants/{participant_id}/portfolio", response_model=PortfolioRead)
def portfolio(participant_id: int, db: Session = Depends(get_db)):
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(404, "Participant not found")
    competition = db.get(Competition, participant.competition_id)
    return run(lambda: get_portfolio(db, participant_id, competition.current_time))


@router.get("/participants/{participant_id}/portfolio-history")
def portfolio_history(participant_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.participant_id == participant_id)
        .order_by(PortfolioSnapshot.timestamp)
    ).all()
    return [
        {
            "timestamp": row.timestamp,
            "portfolio_value": row.total_portfolio_value,
            "realized_pnl": row.realized_pnl,
            "unrealized_pnl": row.unrealized_pnl,
        }
        for row in rows
    ]


@router.get(
    "/participants/{participant_id}/portfolio-plot",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def participant_portfolio_plot_endpoint(
    participant_id: int,
    metric: str = Query(default="value", pattern="^(value|return)$"),
    show_trades: bool = Query(
        default=True,
        description="Annotate grouped executed buy/sell orders on the trajectory.",
    ),
    db: Session = Depends(get_db),
):
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(404, "Participant not found")

    rows = db.scalars(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.participant_id == participant_id)
        .order_by(PortfolioSnapshot.timestamp)
    ).all()
    trade_markers = []
    if show_trades:
        # Executions are grouped by order so a large order filled over multiple
        # minutes receives one readable annotation rather than one label per fill.
        execution_rows = db.execute(
            select(Execution, Order, Instrument)
            .join(Order, Order.id == Execution.order_id)
            .join(Instrument, Instrument.id == Execution.instrument_id)
            .where(Execution.participant_id == participant_id)
            .order_by(Execution.executed_at, Execution.id)
        ).all()
        grouped = {}
        for execution, order, instrument in execution_rows:
            group = grouped.setdefault(
                order.id,
                {
                    "timestamp": execution.executed_at,
                    "side": order.side,
                    "symbol": instrument.symbol,
                    "quantity": 0,
                    "notional": Decimal("0"),
                    "fill_count": 0,
                },
            )
            group["timestamp"] = min(group["timestamp"], execution.executed_at)
            group["quantity"] += execution.quantity
            group["notional"] += Decimal(execution.price) * execution.quantity
            group["fill_count"] += 1

        trade_markers = [
            TradeMarker(
                timestamp=group["timestamp"],
                side=group["side"],
                symbol=group["symbol"],
                quantity=group["quantity"],
                average_price=group["notional"] / Decimal(group["quantity"]),
                fill_count=group["fill_count"],
            )
            for group in grouped.values()
        ]

    png = run(
        lambda: participant_portfolio_plot(
            participant_name=participant.name,
            metric=metric,
            starting_value=Decimal(participant.starting_cash),
            trade_markers=trade_markers,
            points=[
                PortfolioPoint(
                    timestamp=row.timestamp,
                    value=row.total_portfolio_value,
                )
                for row in rows
            ],
        )
    )
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                f'inline; filename="participant-{participant_id}-{metric}.png"'
            )
        },
    )


@router.get(
    "/competitions/{competition_id}/portfolio-plot",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def competition_portfolio_plot_endpoint(
    competition_id: int,
    metric: str = Query(default="return", pattern="^(value|return)$"),
    db: Session = Depends(get_db),
):
    competition = db.get(Competition, competition_id)
    if competition is None:
        raise HTTPException(404, "Competition not found")

    participants = db.scalars(
        select(Participant)
        .where(Participant.competition_id == competition_id)
        .order_by(Participant.id)
    ).all()

    plot_series = []
    for participant in participants:
        rows = db.scalars(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.participant_id == participant.id)
            .order_by(PortfolioSnapshot.timestamp)
        ).all()
        plot_series.append(
            PortfolioSeries(
                label=participant.name,
                starting_value=participant.starting_cash,
                points=tuple(
                    PortfolioPoint(
                        timestamp=row.timestamp,
                        value=row.total_portfolio_value,
                    )
                    for row in rows
                ),
            )
        )

    png = run(
        lambda: competition_portfolio_plot(
            competition_name=competition.name,
            series=plot_series,
            metric=metric,
        )
    )
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                f'inline; filename="competition-{competition_id}-{metric}.png"'
            )
        },
    )


@router.get("/", include_in_schema=False)
def root():
    """Send browser users directly to the interactive Swagger documentation."""
    return RedirectResponse(url="/docs")


@router.get("/competitions/{competition_id}/leaderboards/daily/{trading_date}", response_model=list[LeaderboardEntry])
def daily_leaderboard(competition_id: int, trading_date: date, db: Session = Depends(get_db)):
    rows = RankingService(db).daily(competition_id, trading_date)
    db.commit()
    return rows


@router.get("/competitions/{competition_id}/leaderboards/overall", response_model=list[LeaderboardEntry])
def overall_leaderboard(competition_id: int, db: Session = Depends(get_db)):
    return RankingService(db).overall(competition_id)
