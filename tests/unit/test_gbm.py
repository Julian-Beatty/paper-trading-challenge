"""Test Gbm module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep test gbm concerns isolated and readable.

from datetime import datetime, timezone
from decimal import Decimal

from app.simulation.gbm import simulate_gbm_path


def test_gbm_is_positive_and_reproducible():
    kwargs = dict(
        initial_price=Decimal("100"),
        annual_drift=0.08,
        annual_volatility=0.20,
        start_time=datetime(2026, 8, 5, 9, 30, tzinfo=timezone.utc),
        minutes=10,
        seed=7,
    )
    first = simulate_gbm_path(**kwargs)
    second = simulate_gbm_path(**kwargs)
    assert first == second
    assert len(first) == 11
    assert all(price > 0 for _, price in first)
