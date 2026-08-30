"""Domain exceptions and their translation into HTTP responses.

No domain model exists yet (see docs/architecture.md §3, phase 2), so only the
base shape from architecture.md §5.3 is defined here. Concrete exceptions such
as a future `RegionNotFound` or `InvalidImage` subclass these base classes
once the corresponding model lands.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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


def register_error_handlers(app: FastAPI) -> None:
    """Wire domain exceptions to their HTTP translation. Called once by the app factory."""
    app.add_exception_handler(AppError, _handle_app_error)
