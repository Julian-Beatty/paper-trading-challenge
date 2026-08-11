# Paper Trading Challenge

A deterministic FastAPI backend for a long-only paper-trading competition.

## Features

- Competition-specific stock universe with fully configurable symbols, starting prices, GBM drift/volatility, and per-minute liquidity (default universe still included)
- Reproducible one-minute GBM price paths
- Forward-only simulation time
- Market and limit orders
- Cancel-and-replace order semantics
- Required order states: `NEW`, `ACKNOWLEDGED`, `PARTIALLY_FILLED`, `FILLED`, `CANCELLED`, `REJECTED`
- Modular liquidity policy (`fixed_minute` and `unlimited` included)
- Cash reservations and share reservations for active orders
- Long-only positions with weighted-average cost
- Realized and unrealized P&L
- Minute-level portfolio snapshots
- Daily and overall leaderboards
- Maximum drawdown in the overall performance response

## Architecture

```text
FastAPI routes -> application services -> domain rules/policies -> SQLAlchemy -> SQLite
```

`BrokerService` depends on a `LiquidityPolicy`, so another competition can use a different fill-capacity rule without changing order or portfolio accounting.

## Simulation order

For every minute:

1. Advance the competition clock.
2. Reveal the pre-generated price for that minute.
3. Evaluate active market and limit orders.
4. Generate partial or complete execution reports.
5. Update cash, positions, average cost, and realized P&L.
6. Save one portfolio snapshot per participant.

Future prices are stored internally but API price queries expose only prices at or before `competition.current_time`.

## Liquidity

The default policy gives every participant an independent per-symbol fill capacity each minute. This avoids participants being disadvantaged by API request ordering. Each instrument defines its own `minute_liquidity`. The default universe uses:

- AAPL: 100 shares/minute
- MSFT: 80 shares/minute
- TSLA: 40 shares/minute

A custom competition can provide different capacities for every stock.


## Custom stock universe

`POST /competitions` accepts an optional `stocks` array. Each competition can therefore define its own simulated market:

```json
{
  "name": "Energy Trading Contest",
  "trading_date": "2026-08-06",
  "starting_hour": 9,
  "starting_minute": 30,
  "minutes": 390,
  "random_seed": 12345,
  "liquidity_policy": "fixed_minute",
  "stocks": [
    {
      "symbol": "USO",
      "display_name": "Synthetic Oil Fund",
      "initial_price": 75.0,
      "annual_drift": 0.04,
      "annual_volatility": 0.30,
      "minute_liquidity": 120
    },
    {
      "symbol": "XOM",
      "display_name": "Synthetic Energy Major",
      "initial_price": 115.0,
      "annual_drift": 0.06,
      "annual_volatility": 0.18,
      "minute_liquidity": 80
    }
  ]
}
```

Symbols are normalized to uppercase and must be unique within the competition. If `stocks` is omitted, the application uses the default AAPL/MSFT/TSLA universe.

## P&L

```text
portfolio value = cash + sum(position quantity * current price)
unrealized P&L = sum(quantity * (current price - average price))
realized P&L on sale = sold quantity * (sale price - average price)
daily P&L = closing value - opening value
daily return = daily P&L / opening value
```

Realized P&L is not added separately to portfolio value because it is already reflected in cash.

## Ranking

Daily rankings use:

1. Daily percentage return
2. Daily P&L
3. Closing portfolio value
4. Participant ID for stable display ordering

Economically identical entries share the same competition rank. Inactive participants remain invested in cash and receive a zero return, absent price exposure or cash interest.

The overall ladder uses cumulative percentage return, then cumulative P&L. Maximum drawdown is reported as an additional risk metric but does not affect official rank.

## Run

Windows Command Prompt:

```cmd
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --reload
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## Test

```bash
pytest -q
```

## Main API flow

```text
POST /competitions
POST /competitions/{id}/participants
GET  /competitions/{id}/instruments
POST /competitions/{id}/orders
POST /competitions/{id}/advance?minutes=1
GET  /participants/{id}/portfolio
POST /orders/{id}/cancel
POST /orders/{id}/replace
POST /competitions/{id}/close-day
GET  /competitions/{id}/leaderboards/daily/{date}
GET  /competitions/{id}/leaderboards/overall
```

## Assumptions and limitations

- One synthetic trading day per competition
- Stocks only, integer shares, long positions only
- No commissions, dividends, interest, margin, shorting, or corporate actions
- One mid-price per minute; fills occur at that price
- The clock cannot move backward
- Advance requests that overshoot the configured market close are clamped to the final minute and automatically close the competition
- Closed competitions reject further clock advancement and new orders with HTTP 409 Conflict
- A custom stock universe may be supplied at competition creation; omitting it loads the default synthetic universe
- SQLite and synchronous processing are appropriate for the challenge, not high-throughput production use

## Production changes

Use PostgreSQL, row-level locking or optimistic concurrency, idempotency keys, authentication/authorization, background event processing, external market-data ingestion, migrations, structured logging, metrics, and stronger audit/event sequencing.

## Portfolio plots

The backend can render portfolio trajectories directly as PNG images:

```text
GET /participants/{participant_id}/portfolio-plot?metric=value
GET /participants/{participant_id}/portfolio-plot?metric=return
GET /competitions/{competition_id}/portfolio-plot?metric=return
GET /competitions/{competition_id}/portfolio-plot?metric=value
```

`metric=value` plots dollar portfolio value. `metric=return` normalizes each participant by their own starting cash and plots cumulative percentage return, which is the fairest comparison when starting balances differ. Plots include concise time labels, currency/percentage formatting, a zero-return reference line, endpoint markers, and cleaner presentation styling.

Swagger may offer the PNG as a downloadable response. To view it directly in the browser, open a URL such as:

```text
http://127.0.0.1:8000/participants/2/portfolio-plot?metric=value
```

## Source layout

The project intentionally keeps the architecture compact. API endpoints live in `app/api/routes.py`; the old one-line API re-export modules were removed. Services query SQLAlchemy directly, so unused repository placeholder modules were also removed rather than keeping empty abstractions.

```text
app/
├── api/             # FastAPI routes
├── analytics/       # Returns, drawdown, volatility, turnover, and plots
├── domain/          # Enums, exceptions, and order-state rules
├── models/          # SQLAlchemy entities
├── policies/        # Swappable liquidity, execution-price, and ranking policies
├── schemas/         # Pydantic request/response models
├── services/        # Trading and competition workflows
└── simulation/      # Forward-only clock, GBM paths, and default universe
```

Each Python file starts with a module-level explanation and a short responsibility comment so a reviewer can quickly understand why the file exists.


## Performance ranking and plot annotations

Daily and overall rankings use the same deterministic hierarchy: **highest percentage return**, then **lowest maximum drawdown**, then **highest closing/current portfolio value**. Participants whose values are identical across all three criteria share the same competition rank; participant ID is used only to make display ordering stable. Inactive participants remain invested in cash and are ranked normally.

The participant portfolio plot supports `metric=value|return` and `show_trades=true|false`. Trade annotations are based on actual executions, not order submission time. Partial executions from the same order are grouped into one BUY/SELL marker showing total executed quantity, number of fills, and weighted-average execution price. Competition overlay plots remain unannotated by default to avoid visual clutter.

Realized P&L is retained even after a position is fully closed; zero-quantity positions are hidden from current holdings but their accumulated realized P&L still contributes to participant and snapshot totals.

For local development, `python reset_db.py` drops and recreates the SQLite schema after an explicit `RESET` confirmation.
