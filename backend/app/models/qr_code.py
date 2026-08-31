"""`QrCode` — a printable token pointing at exactly one `Region` or one
`Planting`, never both. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.

Two nullable FKs + a CHECK, not a polymorphic `target_type`/`target_id` pair:
keeps real Postgres foreign-key integrity (a dangling QR code is impossible
by construction) at the cost of a new column if a third QR-able entity ever
shows up — the spec's documented trade-off.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class QrCode(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "qr_codes"
    __table_args__ = (
        CheckConstraint(
            "(region_id IS NOT NULL) != (planting_id IS NOT NULL)",
            name="ck_qr_codes_exactly_one_target",
        ),
    )

    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # `unique=True` on both: at most one QrCode per Region/Planting — the
    # create flows (region_service.create_region,
    # planting_service.create_planting) only ever insert one.
    region_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regions.id", ondelete="CASCADE"), unique=True
    )
    planting_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plantings.id", ondelete="CASCADE"), unique=True
    )
