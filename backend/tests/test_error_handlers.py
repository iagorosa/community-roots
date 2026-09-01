"""Tests for the catch-all exception handler (issue #36).

Before this handler existed, anything that wasn't an `AppError` subclass —
a dropped database connection, a permission-denied write to `storage/`, any
other bug — reached `ServerErrorMiddleware` with no registered handler for
bare `Exception`, which sends back Starlette's own default: plain-text
"Internal Server Error", in English, with no indication of what to do next.
Confirmed live against this app (backend/DB stopped, then `storage/` made
read-only) before writing this test — both scenarios produced exactly that
response. `register_error_handlers` now registers a handler for `Exception`
itself, so every unhandled failure gets the same generic, Portuguese,
actionable shape as a `NotFoundError`/`ValidationFailedError`, and the real
exception is only ever logged server-side, never sent to the client.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_unhandled_exception_returns_generic_portuguese_error(app: FastAPI) -> None:
    @app.get("/__boom")
    def _boom() -> None:
        raise RuntimeError("segredo interno que nunca deve vazar")

    # `raise_server_exceptions=False`: the default `TestClient` re-raises an
    # exception even after a registered handler has already turned it into a
    # response (a Starlette debugging convenience) — which would hide the
    # very response this test needs to inspect.
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/__boom")

    assert response.status_code == 500
    body = response.json()
    assert body == {
        "detail": "Ocorreu um erro inesperado. Tente novamente em instantes.",
        "code": "internal_error",
    }
    # The original exception's message must never reach the client — that's
    # exactly the kind of internal detail (here, a deliberately suspicious
    # string) this handler exists to swallow.
    assert "segredo interno" not in response.text
    assert "Internal Server Error" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_unhandled_exception_from_a_real_route_still_gets_generic_error(
    app: FastAPI, monkeypatch: object
) -> None:
    """Closer to the real finding behind this issue: `GET /api/regions`
    itself blows up with something that isn't an `AppError` — standing in
    for what a dropped Postgres connection raises (`sqlalchemy.exc.
    OperationalError`, also a plain `Exception` subclass) — and the response
    is still the same generic shape, not the framework's default.
    """
    from app.services import region_service

    def _raise_like_a_dead_connection(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("connection to server at ... failed")

    monkeypatch.setattr(region_service, "list_regions", _raise_like_a_dead_connection)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/regions")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Ocorreu um erro inesperado. Tente novamente em instantes.",
        "code": "internal_error",
    }


def test_app_error_is_unaffected_by_the_catch_all_handler(app: FastAPI) -> None:
    """A registered `AppError` handler must still win over the new catch-all
    — this app relies on `NotFoundError`/`ValidationFailedError` etc. having
    their own status codes and messages, not the generic 500 shape.
    """
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(f"/api/regions/{'nao-existe'}")

    assert response.status_code == 404
    assert response.json()["code"] == "region_not_found"
