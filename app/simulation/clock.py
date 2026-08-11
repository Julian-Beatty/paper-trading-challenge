"""Clock module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep clock concerns isolated and readable.

from datetime import datetime, timedelta


class SimulationClock:
    def __init__(self, current_time: datetime):
        self._current_time = current_time

    def now(self) -> datetime:
        return self._current_time

    def set(self, new_time: datetime) -> datetime:
        if new_time < self._current_time:
            raise ValueError("Simulation clock cannot move backward")
        self._current_time = new_time
        return self._current_time

    def advance(self, minutes: int = 1) -> datetime:
        if minutes <= 0:
            raise ValueError("Clock must advance by a positive number of minutes")
        self._current_time += timedelta(minutes=minutes)
        return self._current_time
