"""Unlimited module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep unlimited concerns isolated and readable.

from app.policies.liquidity.base import LiquidityContext, LiquidityPolicy


class UnlimitedLiquidity(LiquidityPolicy):
    def available_quantity(self, context: LiquidityContext) -> int:
        return context.remaining_quantity
