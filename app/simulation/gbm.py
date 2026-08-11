"""Gbm module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep gbm concerns isolated and readable.

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

import numpy as np


CENT = Decimal("0.01")


def simulate_gbm_path(
    *,
    initial_price: Decimal,
    annual_drift: float,
    annual_volatility: float,
    start_time: datetime,
    minutes: int,
    seed: int,
) -> list[tuple[datetime, Decimal]]:
    if initial_price <= 0:
        raise ValueError("initial_price must be positive")
    if annual_volatility < 0:
        raise ValueError("annual_volatility cannot be negative")
    if minutes <= 0:
        raise ValueError("minutes must be positive")

    rng = np.random.default_rng(seed)
    dt = 1.0 / (252.0 * 390.0)
    prices = [float(initial_price)]
    for shock in rng.standard_normal(minutes):
        next_price = prices[-1] * np.exp(
            (annual_drift - 0.5 * annual_volatility**2) * dt
            + annual_volatility * np.sqrt(dt) * shock
        )
        prices.append(next_price)

    return [
        (
            start_time + timedelta(minutes=i),
            Decimal(str(price)).quantize(CENT, rounding=ROUND_HALF_UP),
        )
        for i, price in enumerate(prices)
    ]
