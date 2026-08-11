"""Development utility for resetting the local paper-trading database.

Run this script only when you intentionally want a clean local database.
"""

# Responsibility: provide an explicit, guarded local-development database reset.

from app.database import Base, engine
from app.models import entities  # noqa: F401 - registers all ORM tables with Base.


def reset_database() -> None:
    """Drop all application tables and recreate an empty schema after confirmation."""
    print("WARNING: This permanently deletes all local competition data.")
    confirmation = input("Type RESET to continue: ")
    if confirmation != "RESET":
        print("Database reset cancelled.")
        return

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Database reset complete.")


if __name__ == "__main__":
    reset_database()
