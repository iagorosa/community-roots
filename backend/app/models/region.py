"""`Region` — a large planting-area grouping (e.g. "AAMA — Matias
Barbosa"). QR codes live in `app.models.qr_code.QrCode`, not on this model.
See docs/architecture.md §4.1/§4.2 and
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import CheckConstraint, Computed, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Region(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "regions"
    __table_args__ = (
        # `geom` stays a permissive generic type (architecture.md §4.1) rather
        # than a typmod-restricted one, so this CHECK is what actually keeps
        # the column within what the map can draw.
        CheckConstraint(
            "GeometryType(geom) IN ('POINT', 'POLYGON', 'MULTIPOLYGON')",
            name="ck_regions_geom_type",
        ),
        CheckConstraint(
            "status IN ('active', 'draft', 'archived')",
            name="ck_regions_status",
        ),
        # Declared here (not left to GeoAlchemy2's own DDL-event index
        # management) so `Base.metadata` and the hand-written migration agree
        # on their existence — otherwise autogenerate sees them as orphaned
        # and proposes dropping them.
        Index("ix_regions_geom", "geom", postgresql_using="gist"),
        Index("ix_regions_centroid", "centroid", postgresql_using="gist"),
    )

    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # `spatial_index=False`: index management is handled by the `Index(...)`
    # entries in `__table_args__` above, not by GeoAlchemy2's own DDL events.
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
        nullable=False,
    )
    # Stored and PostGIS-generated on every insert/update of `geom`, rather
    # than recomputed per request (architecture.md §4.1).
    centroid: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        Computed("ST_Centroid(geom)", persisted=True),
    )

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
