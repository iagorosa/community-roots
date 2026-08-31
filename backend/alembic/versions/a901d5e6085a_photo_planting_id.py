"""photo planting id

Revision ID: a901d5e6085a
Revises: 2803ee9d1124
Create Date: 2026-08-31 16:46:41.741762

Hand-written, not raw autogenerate output — see issue #84 and
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md: a photo
belongs to an individual Planting, not directly to a Region, so `photos`
moves its FK from `region_id` to `planting_id`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a901d5e6085a"
down_revision: str | Sequence[str] | None = "2803ee9d1124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("photos_region_id_fkey", "photos", type_="foreignkey")
    op.drop_index("ix_photos_region_id_uploaded_at", table_name="photos")
    op.alter_column("photos", "region_id", new_column_name="planting_id")
    op.create_foreign_key(
        "photos_planting_id_fkey",
        "photos",
        "plantings",
        ["planting_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_photos_planting_id_uploaded_at",
        "photos",
        ["planting_id", sa.text("uploaded_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_photos_planting_id_uploaded_at", table_name="photos")
    op.drop_constraint("photos_planting_id_fkey", "photos", type_="foreignkey")
    op.alter_column("photos", "planting_id", new_column_name="region_id")
    op.create_foreign_key(
        "photos_region_id_fkey", "photos", "regions", ["region_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(
        "ix_photos_region_id_uploaded_at",
        "photos",
        ["region_id", sa.text("uploaded_at DESC")],
        unique=False,
    )
