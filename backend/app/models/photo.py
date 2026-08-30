"""`Photo` — a photo uploaded to a region's timeline. See docs/architecture.md §4.3/§4.4."""

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class Photo(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "photos"

    region_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Opaque key meaningful only to the storage backend — never used to
    # rebuild a filesystem/bucket path from user input.
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Kept for display only; like `storage_key`, never used to build a path.
    original_filename: Mapped[str | None] = mapped_column(Text)
    # Determined by decoding the image bytes server-side, not trusted from
    # the client's upload header.
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    # Lets the frontend reserve layout space up front and avoid page jump.
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    description: Mapped[str | None] = mapped_column(Text)
    contributor_name: Mapped[str | None] = mapped_column(Text)

    # From the EXIF `DateTimeOriginal` tag, when present.
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Server clock, set on insert.
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # A single point of truth (architecture.md §4.4) instead of loose
    # `latitude`/`longitude` floats: this is what lets "which region contains
    # this photo?" reuse the same GiST index the regions already use, rather
    # than an ad hoc construction on every query. `latitude`/`longitude` are
    # derived for the API response layer (out of scope for this issue).
    #
    # `spatial_index=False`: index management is handled by the explicit
    # `Index(...)` entry in `__table_args__` below, not by GeoAlchemy2's own
    # DDL events — see the equivalent comment in app/models/region.py.
    location: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
    )
    # `"exif"` today; `"manual"` and `"browser"` are future values.
    location_source: Mapped[str | None] = mapped_column(Text)

    # No admin UI reads/writes this in the MVP — it exists so an organizer
    # can pull a photo offline with a single `UPDATE`, not a migration, given
    # the product involves public uploads by and about children.
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="published")

    __table_args__ = (
        CheckConstraint(
            "status IN ('published', 'hidden')",
            name="ck_photos_status",
        ),
        # `region_id` leads this composite index, so it also serves plain
        # `WHERE region_id = ...` lookups (e.g. the FK) without a second,
        # redundant single-column index.
        #
        # The timeline query orders by `uploaded_at DESC`, so the index is
        # built with that same direction (`.desc()`) rather than the default
        # ascending — that's what lets the planner walk it without an extra
        # `Sort` step.
        Index("ix_photos_region_id_uploaded_at", region_id, uploaded_at.desc()),
        Index("ix_photos_location", location, postgresql_using="gist"),
    )
