"""Database engine, session factory and the `get_db` FastAPI dependency.

Kept separate from `app/db/base.py` so importing the declarative base (e.g.
from Alembic's `env.py`) never has the side effect of opening a connection.
"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine: Engine = create_engine(settings.database_url, pool_pre_ping=True)

# `expire_on_commit=False` so objects returned to a route stay usable after
# the session closes at the end of the request, without triggering a lazy
# reload attempt on an already-closed connection.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields one session per request, always closed after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
