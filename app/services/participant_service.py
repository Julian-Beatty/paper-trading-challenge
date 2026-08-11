"""Participant Service module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep participant service concerns isolated and readable.

from sqlalchemy.orm import Session

from app.models.entities import Competition, Participant


class ParticipantService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, competition_id: int, name: str, starting_cash):
        competition = self.db.get(Competition, competition_id)
        if competition is None:
            raise ValueError("Competition not found")
        participant = Participant(
            competition_id=competition_id,
            name=name,
            starting_cash=starting_cash,
            cash_balance=starting_cash,
            created_at=competition.current_time,
        )
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant
