"""Admin-token gate for write endpoints.

A placeholder until real authentication exists (architecture.md §9): the
write paths are already isolated behind this single dependency, so swapping
it out later is a contained change.
"""

import secrets

from fastapi import Header

from app.core.config import settings
from app.core.errors import UnauthorizedError


def require_admin_token(
    x_admin_token: str | None = Header(default=None),
) -> None:
    token_matches = x_admin_token is not None and secrets.compare_digest(
        x_admin_token, settings.admin_api_token
    )
    if not token_matches:
        raise UnauthorizedError("Token administrativo ausente ou inválido.")
