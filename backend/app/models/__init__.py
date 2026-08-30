"""Domain models. Imported here so `Base.metadata` — and Alembic autogenerate — sees them."""

from app.models.region import Region

__all__ = ["Region"]
