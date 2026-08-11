"""Cumulative Return module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep cumulative return concerns isolated and readable.

from app.policies.ranking.base import RankingPolicy


class CumulativeReturnRanking(RankingPolicy):
    def sort_key(self, entry):
        return (-entry["return_pct"], -entry["pnl"], entry["participant_id"])
