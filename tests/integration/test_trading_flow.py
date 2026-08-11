"""Test Trading Flow module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep test trading flow concerns isolated and readable.

from datetime import date


def create_competition(client, minutes=3):
    response = client.post(
        "/competitions",
        json={
            "name": "Demo",
            "trading_date": str(date(2026, 8, 5)),
            "minutes": minutes,
            "random_seed": 42,
            "liquidity_policy": "fixed_minute",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_participant(client, competition_id, name="Alice", cash="100000"):
    response = client.post(
        f"/competitions/{competition_id}/participants",
        json={"name": name, "starting_cash": cash},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_market_order_partial_fill_portfolio_and_close(client):
    competition = create_competition(client, minutes=3)
    alice = create_participant(client, competition["id"])

    order_response = client.post(
        f"/competitions/{competition['id']}/orders",
        json={
            "participant_id": alice["id"],
            "symbol": "AAPL",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 250,
        },
    )
    assert order_response.status_code == 200, order_response.text
    order_id = order_response.json()["id"]

    client.post(f"/competitions/{competition['id']}/advance?minutes=1")
    order = client.get(f"/orders/{order_id}").json()
    assert order["status"] == "PARTIALLY_FILLED"
    assert order["filled_quantity"] == 100

    client.post(f"/competitions/{competition['id']}/advance?minutes=2")
    order = client.get(f"/orders/{order_id}").json()
    assert order["status"] == "FILLED"
    assert order["filled_quantity"] == 250

    portfolio = client.get(f"/participants/{alice['id']}/portfolio")
    assert portfolio.status_code == 200, portfolio.text
    payload = portfolio.json()
    assert payload["positions"][0]["quantity"] == 250
    assert len(client.get(f"/participants/{alice['id']}/portfolio-history").json()) == 3

    close = client.post(f"/competitions/{competition['id']}/close-day")
    assert close.status_code == 200, close.text
    leaderboard = client.get(
        f"/competitions/{competition['id']}/leaderboards/daily/2026-08-05"
    )
    assert leaderboard.status_code == 200, leaderboard.text
    assert leaderboard.json()[0]["participant_name"] == "Alice"


def test_limit_order_cancel_and_replace(client):
    competition = create_competition(client, minutes=2)
    alice = create_participant(client, competition["id"])
    current = client.get(f"/competitions/{competition['id']}/instruments").json()[0]["current_price"]

    order = client.post(
        f"/competitions/{competition['id']}/orders",
        json={
            "participant_id": alice["id"],
            "symbol": "AAPL",
            "side": "BUY",
            "order_type": "LIMIT",
            "quantity": 10,
            "limit_price": "1.00",
        },
    ).json()

    replacement = client.post(
        f"/orders/{order['id']}/replace",
        json={"quantity": 5, "limit_price": "1.00"},
    )
    assert replacement.status_code == 200, replacement.text
    old = client.get(f"/orders/{order['id']}").json()
    assert old["status"] == "CANCELLED"
    new_order = replacement.json()
    assert new_order["replaces_order_id"] == order["id"]

    cancelled = client.post(f"/orders/{new_order['id']}/cancel")
    assert cancelled.status_code == 200
    client.post(f"/competitions/{competition['id']}/advance?minutes=1")
    assert client.get(f"/orders/{new_order['id']}").json()["status"] == "CANCELLED"


def test_portfolio_plot_endpoints_return_png(client):
    competition = create_competition(client, minutes=2)
    alice = create_participant(client, competition["id"], name="Alice")
    bob = create_participant(client, competition["id"], name="Bob")

    order = client.post(
        f"/competitions/{competition['id']}/orders",
        json={
            "participant_id": alice["id"],
            "symbol": "AAPL",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 10,
        },
    )
    assert order.status_code == 200, order.text

    advanced = client.post(f"/competitions/{competition['id']}/advance?minutes=2")
    assert advanced.status_code == 200, advanced.text

    participant_plot = client.get(
        f"/participants/{alice['id']}/portfolio-plot?metric=value&show_trades=true"
    )
    assert participant_plot.status_code == 200, participant_plot.text
    assert participant_plot.headers["content-type"] == "image/png"
    assert participant_plot.content.startswith(b"\x89PNG\r\n\x1a\n")

    clean_participant_plot = client.get(
        f"/participants/{alice['id']}/portfolio-plot?metric=value&show_trades=false"
    )
    assert clean_participant_plot.status_code == 200, clean_participant_plot.text
    assert clean_participant_plot.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert clean_participant_plot.content != participant_plot.content

    competition_plot = client.get(
        f"/competitions/{competition['id']}/portfolio-plot?metric=return"
    )
    assert competition_plot.status_code == 200, competition_plot.text
    assert competition_plot.headers["content-type"] == "image/png"
    assert competition_plot.content.startswith(b"\x89PNG\r\n\x1a\n")

    # Bob has history even while inactive because a snapshot is captured each minute.
    bob_history = client.get(f"/participants/{bob['id']}/portfolio-history")
    assert len(bob_history.json()) == 2


def test_competition_accepts_custom_stock_universe(client):
    response = client.post(
        "/competitions",
        json={
            "name": "Energy Contest",
            "trading_date": "2026-08-05",
            "minutes": 3,
            "random_seed": 77,
            "liquidity_policy": "fixed_minute",
            "stocks": [
                {
                    "symbol": "uso",
                    "display_name": "Synthetic Oil Fund",
                    "initial_price": "75.00",
                    "annual_drift": "0.04",
                    "annual_volatility": "0.30",
                    "minute_liquidity": 120,
                },
                {
                    "symbol": "XOM",
                    "initial_price": "115.00",
                    "annual_drift": "0.06",
                    "annual_volatility": "0.18",
                    "minute_liquidity": 80,
                },
            ],
        },
    )
    assert response.status_code == 200, response.text
    competition_id = response.json()["id"]

    instruments = client.get(
        f"/competitions/{competition_id}/instruments"
    ).json()
    assert [item["symbol"] for item in instruments] == ["USO", "XOM"]
    assert instruments[0]["display_name"] == "Synthetic Oil Fund"
    assert instruments[0]["initial_price"] == 75.0
    assert instruments[0]["annual_volatility"] == 0.3
    assert instruments[0]["minute_liquidity"] == 120
    assert instruments[1]["display_name"] == "XOM"

    participant = create_participant(client, competition_id)
    order = client.post(
        f"/competitions/{competition_id}/orders",
        json={
            "participant_id": participant["id"],
            "symbol": "USO",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 150,
        },
    )
    assert order.status_code == 200, order.text
    order_id = order.json()["id"]

    client.post(f"/competitions/{competition_id}/advance?minutes=1")
    partially_filled = client.get(f"/orders/{order_id}").json()
    assert partially_filled["status"] == "PARTIALLY_FILLED"
    assert partially_filled["filled_quantity"] == 120


def test_custom_universe_rejects_duplicate_symbols(client):
    response = client.post(
        "/competitions",
        json={
            "name": "Invalid Contest",
            "trading_date": "2026-08-05",
            "stocks": [
                {
                    "symbol": "ABC",
                    "initial_price": 100,
                    "annual_volatility": 0.2,
                },
                {
                    "symbol": "abc",
                    "initial_price": 90,
                    "annual_volatility": 0.3,
                },
            ],
        },
    )
    assert response.status_code == 422


def test_advance_past_close_clamps_and_auto_closes(client):
    # A five-minute request against a three-minute competition should process
    # only the three available minutes, stop exactly at market close, and close.
    competition = create_competition(client, minutes=3)
    alice = create_participant(client, competition["id"])

    response = client.post(
        f"/competitions/{competition['id']}/advance?minutes=5"
    )
    assert response.status_code == 200, response.text
    advanced = response.json()
    assert advanced["current_time"] == advanced["market_close"]
    assert advanced["status"] == "CLOSED"

    # Automatic closure writes the same final daily snapshot that the explicit
    # close-day endpoint would have produced.
    leaderboard = client.get(
        f"/competitions/{competition['id']}/leaderboards/daily/2026-08-05"
    )
    assert leaderboard.status_code == 200, leaderboard.text
    assert leaderboard.json()[0]["participant_id"] == alice["id"]


def test_closed_competition_rejects_advance_and_new_orders(client):
    competition = create_competition(client, minutes=2)
    alice = create_participant(client, competition["id"])

    # Overshooting closes the competition automatically.
    closed = client.post(
        f"/competitions/{competition['id']}/advance?minutes=3"
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "CLOSED"

    # Once closed, neither time advancement nor new trading is permitted.
    advance_again = client.post(
        f"/competitions/{competition['id']}/advance?minutes=1"
    )
    assert advance_again.status_code == 409, advance_again.text

    new_order = client.post(
        f"/competitions/{competition['id']}/orders",
        json={
            "participant_id": alice["id"],
            "symbol": "AAPL",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 1,
        },
    )
    assert new_order.status_code == 409, new_order.text


def test_realized_pnl_survives_full_position_close(client):
    """Selling every share must not erase the realized P&L from the portfolio."""
    competition = create_competition(client, minutes=3)
    alice = create_participant(client, competition["id"], cash="100000")

    buy = client.post(
        f"/competitions/{competition['id']}/orders",
        json={
            "participant_id": alice["id"],
            "symbol": "AAPL",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 10,
        },
    )
    assert buy.status_code == 200, buy.text
    client.post(f"/competitions/{competition['id']}/advance?minutes=1")
    buy_execution = client.get(f"/orders/{buy.json()['id']}/executions").json()[0]

    sell = client.post(
        f"/competitions/{competition['id']}/orders",
        json={
            "participant_id": alice["id"],
            "symbol": "AAPL",
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": 10,
        },
    )
    assert sell.status_code == 200, sell.text
    client.post(f"/competitions/{competition['id']}/advance?minutes=1")
    sell_execution = client.get(f"/orders/{sell.json()['id']}/executions").json()[0]

    portfolio = client.get(f"/participants/{alice['id']}/portfolio")
    assert portfolio.status_code == 200, portfolio.text
    payload = portfolio.json()
    expected = 10 * (float(sell_execution["price"]) - float(buy_execution["price"]))

    assert payload["positions"] == []
    assert abs(float(payload["realized_pnl"]) - expected) < 1e-6
    assert float(payload["unrealized_pnl"]) == 0.0


def test_leaderboard_tiebreakers_are_return_drawdown_then_closing_value(client, db):
    """Return wins first, lower MDD second, closing value third, then true ties remain tied."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from app.models.entities import DailySnapshot, PortfolioSnapshot

    competition = create_competition(client, minutes=3)
    alice = create_participant(client, competition["id"], name="Alice", cash="100")
    bob = create_participant(client, competition["id"], name="Bob", cash="100")
    charlie = create_participant(client, competition["id"], name="Charlie", cash="200")
    dave = create_participant(client, competition["id"], name="Dave", cash="100")

    # All four participants finish +10%. Charlie and Bob/Dave have 2% maximum
    # drawdowns, while Alice has 5%. Charlie then wins the closing-value tiebreaker.
    paths = {
        alice["id"]: (Decimal("100"), [Decimal("95"), Decimal("110")]),
        bob["id"]: (Decimal("100"), [Decimal("98"), Decimal("110")]),
        charlie["id"]: (Decimal("200"), [Decimal("196"), Decimal("220")]),
        dave["id"]: (Decimal("100"), [Decimal("98"), Decimal("110")]),
    }
    base_time = datetime(2026, 8, 5, 9, 30, tzinfo=timezone.utc)
    for participant_id, (opening, values) in paths.items():
        for minute, value in enumerate(values, start=1):
            db.add(
                PortfolioSnapshot(
                    competition_id=competition["id"],
                    participant_id=participant_id,
                    timestamp=base_time.replace(minute=30 + minute),
                    cash_balance=value,
                    reserved_cash=Decimal("0"),
                    positions_market_value=Decimal("0"),
                    realized_pnl=value - opening,
                    unrealized_pnl=Decimal("0"),
                    total_portfolio_value=value,
                )
            )
        closing = values[-1]
        db.add(
            DailySnapshot(
                competition_id=competition["id"],
                participant_id=participant_id,
                trading_date=date(2026, 8, 5),
                opening_value=opening,
                closing_value=closing,
                daily_pnl=closing - opening,
                daily_return=(closing - opening) / opening,
                created_at=base_time.replace(minute=32),
            )
        )
    db.commit()

    daily = client.get(
        f"/competitions/{competition['id']}/leaderboards/daily/2026-08-05"
    )
    assert daily.status_code == 200, daily.text
    daily_rows = daily.json()
    assert [row["participant_name"] for row in daily_rows] == [
        "Charlie",
        "Bob",
        "Dave",
        "Alice",
    ]
    assert [row["rank"] for row in daily_rows] == [1, 2, 2, 4]
    assert float(daily_rows[0]["maximum_drawdown"]) == 0.02
    assert float(daily_rows[-1]["maximum_drawdown"]) == 0.05

    overall = client.get(
        f"/competitions/{competition['id']}/leaderboards/overall"
    )
    assert overall.status_code == 200, overall.text
    overall_rows = overall.json()
    assert [row["participant_name"] for row in overall_rows] == [
        "Charlie",
        "Bob",
        "Dave",
        "Alice",
    ]
    assert [row["rank"] for row in overall_rows] == [1, 2, 2, 4]
