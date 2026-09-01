"""Application settings, loaded once at import time.

Fields are validated eagerly (see `settings` at the bottom of this module) so a
broken or incomplete `.env` fails as soon as the app starts, instead of
surfacing later inside a request handler.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# The placeholder shipped in backend/.env.example — never a real secret.
# A production instance must never carry this value in ADMIN_API_TOKEN.
_INSECURE_ADMIN_TOKEN_PLACEHOLDER = "troque-isto-localmente"

# Resolved relative to this file, not the process cwd, so `.env` loads
# correctly regardless of the directory uvicorn was launched from.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # No default: a database URL is environment-specific and must never be
    # guessed, let alone hardcoded, by the application itself.
    database_url: str
    test_database_url: str | None = None

    public_web_base_url: AnyHttpUrl
    cors_allowed_origins: Annotated[list[str], NoDecode]

    admin_api_token: str

    storage_backend: Literal["local"] = "local"
    local_storage_path: str = "./storage"
    max_upload_bytes: int = 10_485_760
    allowed_image_formats: Annotated[list[str], NoDecode] = ["JPEG", "PNG", "WEBP"]

    seed_center_lat: float = -21.883859
    seed_center_lon: float = -43.312459
    seed_planting_count: int = 40

    @field_validator("cors_allowed_origins", "allowed_image_formats", mode="before")
    @classmethod
    def _split_comma_separated_list(cls, raw_value: str | list[str]) -> list[str]:
        if isinstance(raw_value, str):
            return [item.strip() for item in raw_value.split(",") if item.strip()]
        return raw_value

    @model_validator(mode="after")
    def _reject_insecure_admin_token_in_production(self) -> "Settings":
        if self.environment != "production":
            return self

        token_is_placeholder = self.admin_api_token == _INSECURE_ADMIN_TOKEN_PLACEHOLDER
        token_is_empty = not self.admin_api_token.strip()
        if token_is_placeholder or token_is_empty:
            raise ValueError(
                "ADMIN_API_TOKEN precisa de um valor real, não vazio, antes de subir em produção."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached accessor — usable as a FastAPI dependency once routes exist."""
    return Settings()


# Instantiated eagerly: importing this module is itself the configuration
# check the "Critério de pronto" of issue #2 relies on.
settings = get_settings()
