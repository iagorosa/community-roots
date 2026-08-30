"""Liveness/readiness probe that reports the database's real state.

A bare "the process is up" response is useless for detecting a dead
connection pool or an unreachable Postgres instance, so this endpoint runs
an actual `SELECT 1` through `get_db` on every call instead of caching or
assuming success.
"""

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
def check_health(
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008 — FastAPI's DI relies on this call-in-default pattern.
) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Logged server-side with the full traceback; the client only ever
        # sees a generic status so we never leak connection details (host,
        # credentials) that a raw exception message could contain.
        logger.exception("Health check failed: database is unreachable")
        response.status_code = 503
        return {"status": "degraded", "database": "error"}

    return {"status": "ok", "database": "ok"}
