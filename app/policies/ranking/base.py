"""Base module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep base concerns isolated and readable.

from abc import ABC, abstractmethod


class RankingPolicy(ABC):
    @abstractmethod
    def sort_key(self, entry):
        raise NotImplementedError
