"""Shared pytest fixtures: app, client and a rolled-back database session.

Tests run against the real `community_roots_test` PostGIS database (see
docs/architecture.md §10) — never a mock — so a fixture chain that opens one
connection per test and rolls it back is what keeps the suite from leaking
state between tests or into the development database.

The session/connection/transaction fixtures use SQLAlchemy's "join a Session
into an external transaction" recipe: the outer transaction, started on the
raw connection, is what actually gets rolled back at the end of each test.
A nested SAVEPOINT is restarted after every `session.commit()` so that even
route code that commits (as future CRUD endpoints will) stays contained
inside the outer, always-rolled-back transaction.
"""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.main import create_app


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    """One engine for the whole run, bound to `TEST_DATABASE_URL`.

    A missing `TEST_DATABASE_URL` fails loudly here rather than letting a
    test silently fall back to `DATABASE_URL` (the development database).
    """
    if not settings.test_database_url:
        pytest.fail(
            "TEST_DATABASE_URL não configurada em backend/.env — "
            "os testes nunca devem rodar contra DATABASE_URL."
        )

    engine = create_engine(settings.test_database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """One connection + outer transaction per test, rolled back on teardown."""
    connection = test_engine.connect()
    outer_transaction = connection.begin()

    session = Session(bind=connection, autoflush=False, expire_on_commit=False)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(session: Session, transaction: object) -> None:
        # A commit (or rollback) inside route code ends the SAVEPOINT; open a
        # fresh one immediately so later statements in the same test are
        # still contained by `outer_transaction`, not auto-committed to disk.
        if connection.in_transaction() and not connection.in_nested_transaction():
            session.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def app(db_session: Session) -> Generator[FastAPI, None, None]:
    """App instance with `get_db` overridden to the transactional test session."""

    def _get_test_db() -> Generator[Session, None, None]:
        yield db_session

    application = create_app()
    application.dependency_overrides[get_db] = _get_test_db
    yield application
    application.dependency_overrides.clear()


@pytest.fixture()
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
