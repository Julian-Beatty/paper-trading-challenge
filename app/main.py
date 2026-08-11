"""Main module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: keep main concerns isolated and readable.

from fastapi import FastAPI

from app.api.routes import router
from app.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Paper Trading Challenge", version="0.1.0")
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
