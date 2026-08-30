"""photo model

Revision ID: c60d27ca71eb
Revises: 9d020b4a3f2a
Create Date: 2026-08-30 11:59:13.193708

Hand-written, not raw autogenerate output — see the "Critério de pronto" in
issue #20 and docs/architecture.md §4.3/§4.4 for the `location` decision this
migration implements.
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c60d27ca71eb"
down_revision: str | Sequence[str] | None = "9d020b4a3f2a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "photos",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("region_id", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contributor_name", sa.Text(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "location",
            geoalchemy2.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("location_source", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="published", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('published', 'hidden')",
            name="ck_photos_status",
        ),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_photos_location",
        "photos",
        ["location"],
        unique=False,
        postgresql_using="gist",
    )
    # `region_id` leads the composite index, so it also serves plain
    # `WHERE region_id = ...` lookups without a second, redundant index. The
    # timeline query orders by `uploaded_at DESC`, so the index is built
    # with that same direction rather than the default ascending.
    op.create_index(
        "ix_photos_region_id_uploaded_at",
        "photos",
        ["region_id", sa.text("uploaded_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_photos_region_id_uploaded_at", table_name="photos")
    op.drop_index("ix_photos_location", table_name="photos", postgresql_using="gist")
    op.drop_table("photos")
