"""planting model

Revision ID: db4275a589be
Revises: c60d27ca71eb
Create Date: 2026-08-30 23:26:39.529451

Hand-written, not raw autogenerate output — see the "Critério de pronto" in
issue #79 and docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md
for the geometry decision this migration implements (mirrors `regions`).
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db4275a589be"
down_revision: str | Sequence[str] | None = "c60d27ca71eb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "plantings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("region_id", sa.UUID(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "centroid",
            geoalchemy2.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            sa.Computed("ST_Centroid(geom)", persisted=True),
            nullable=False,
        ),
        sa.Column("species", sa.Text(), nullable=True),
        sa.Column("nickname", sa.Text(), nullable=True),
        sa.Column("planted_by", sa.Text(), nullable=True),
        sa.Column("planted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "GeometryType(geom) IN ('POINT', 'POLYGON', 'MULTIPOLYGON')",
            name="ck_plantings_geom_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'draft', 'archived')",
            name="ck_plantings_status",
        ),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_plantings_region_id", "plantings", ["region_id"], unique=False)
    op.create_index(
        "ix_plantings_geom", "plantings", ["geom"], unique=False, postgresql_using="gist"
    )
    op.create_index(
        "ix_plantings_centroid", "plantings", ["centroid"], unique=False, postgresql_using="gist"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_plantings_centroid", table_name="plantings", postgresql_using="gist")
    op.drop_index("ix_plantings_geom", table_name="plantings", postgresql_using="gist")
    op.drop_index("ix_plantings_region_id", table_name="plantings")
    op.drop_table("plantings")
