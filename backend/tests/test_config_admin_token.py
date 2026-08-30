"""Tests for the production admin-token guard in `app/core/config.py` (issue #12).

architecture.md §9: the backend must refuse to boot with an empty or
default `ADMIN_API_TOKEN` when `ENVIRONMENT=production`.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_BASE_KWARGS = {
    "database_url": "postgresql+psycopg://user:pass@localhost/db",
    "public_web_base_url": "http://localhost:5173",
    "cors_allowed_origins": ["http://localhost:5173"],
}


def test_rejects_placeholder_token_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            admin_api_token="troque-isto-localmente",
            **_BASE_KWARGS,
        )


def test_rejects_empty_token_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", admin_api_token="", **_BASE_KWARGS)


def test_rejects_whitespace_only_token_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", admin_api_token="   ", **_BASE_KWARGS)


def test_accepts_real_token_in_production() -> None:
    settings = Settings(
        environment="production",
        admin_api_token="a-real-secret-token",
        **_BASE_KWARGS,
    )

    assert settings.admin_api_token == "a-real-secret-token"


def test_accepts_placeholder_token_outside_production() -> None:
    settings = Settings(
        environment="development",
        admin_api_token="troque-isto-localmente",
        **_BASE_KWARGS,
    )

    assert settings.admin_api_token == "troque-isto-localmente"
