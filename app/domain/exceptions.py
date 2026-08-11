"""Exceptions module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep exceptions concerns isolated and readable.

class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class StateTransitionError(DomainError):
    pass


class InsufficientFundsError(DomainError):
    pass


class InsufficientPositionError(DomainError):
    pass
