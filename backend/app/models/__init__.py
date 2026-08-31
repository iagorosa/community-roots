"""Domain models. Imported here so `Base.metadata` — and Alembic autogenerate — sees them."""

from app.models.photo import Photo
from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region

__all__ = ["Photo", "Planting", "QrCode", "Region"]
