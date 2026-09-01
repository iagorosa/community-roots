"""Domain exceptions and their translation into HTTP responses.

No domain model exists yet (see docs/architecture.md §3, phase 2), so only the
base shape from architecture.md §5.3 is defined here. Concrete exceptions such
as a future `RegionNotFound` or `InvalidImage` subclass these base classes
once the corresponding model lands.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Shown for literally anything that isn't an `AppError` — a dropped database
# connection, a permission-denied write to `storage/`, a bug. Generic on
# purpose: unlike `AppError.detail`, there's no domain context to report
# here, only that something failed and a retry is the one universally safe
# next step (issue #36's "todo estado de erro diz o que fazer em seguida").
_UNEXPECTED_ERROR_DETAIL = "Ocorreu um erro inesperado. Tente novamente em instantes."


class AppError(Exception):
    """Base class for exceptions that should surface as a structured HTTP error.

    Subclasses fix `status_code` and `code`; `detail` is set per instance and
    is user-facing text, safe to display directly (architecture.md §5.3).
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_failed"


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for any exception that isn't an `AppError` — confirmed live
    (issue #36) as the gap that let a database outage and a storage-write
    failure both reach the browser as Starlette's default plain-text
    "Internal Server Error": in English, with no next step, and — had DEBUG
    ever been enabled — a full traceback. FastAPI wires a handler registered
    for the bare `Exception` type into `ServerErrorMiddleware` itself (the
    outermost layer, past `AppError`'s own `ExceptionMiddleware`
    registration), so this is what runs for anything neither this module nor
    a route already handles.

    The real exception is logged here, with its traceback, purely
    server-side — `exc` itself never reaches `content` below.
    """
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": _UNEXPECTED_ERROR_DETAIL, "code": "internal_error"},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Wire domain exceptions to their HTTP translation. Called once by the app factory."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
