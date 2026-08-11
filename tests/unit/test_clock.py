"""Test Clock module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep test clock concerns isolated and readable.

from datetime import datetime, timezone

import pytest

from app.simulation.clock import SimulationClock


def test_clock_only_moves_forward():
    clock = SimulationClock(datetime(2026, 8, 5, 9, 30, tzinfo=timezone.utc))
    assert clock.advance(1).minute == 31
    with pytest.raises(ValueError):
        clock.set(datetime(2026, 8, 5, 9, 30, tzinfo=timezone.utc))
