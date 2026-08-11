"""Factory module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep factory concerns isolated and readable.

from app.policies.liquidity.base import LiquidityPolicy
from app.policies.liquidity.fixed import FixedMinuteLiquidity
from app.policies.liquidity.unlimited import UnlimitedLiquidity


def build_liquidity_policy(name: str) -> LiquidityPolicy:
    if name == "fixed_minute":
        return FixedMinuteLiquidity()
    if name == "unlimited":
        return UnlimitedLiquidity()
    raise ValueError(f"Unknown liquidity policy: {name}")
