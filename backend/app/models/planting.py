"""`Planting` — an individual seedling planted by someone, inside a `Region`.
See docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Planting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plantings"
    __table_args__ = (
        # Same three shapes `Region.geom` allows — a Planting starts as a
        # point today but may become a small polygon later without a schema
        # change (see the spec's geometry decision).
        CheckConstraint(
            "GeometryType(geom) IN ('POINT', 'POLYGON', 'MULTIPOLYGON')",
            name="ck_plantings_geom_type",
        ),
        CheckConstraint(
            "status IN ('active', 'draft', 'archived')",
            name="ck_plantings_status",
        ),
        Index("ix_plantings_geom", "geom", postgresql_using="gist"),
        Index("ix_plantings_centroid", "centroid", postgresql_using="gist"),
    )

    region_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
        nullable=False,
    )
    centroid: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        Computed("ST_Centroid(geom)", persisted=True),
    )

    species: Mapped[str | None] = mapped_column(Text)
    nickname: Mapped[str | None] = mapped_column(Text)
    planted_by: Mapped[str | None] = mapped_column(Text)
    planted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
