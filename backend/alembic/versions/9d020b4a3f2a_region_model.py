"""region model

Revision ID: 9d020b4a3f2a
Revises: ca09e07c189c
Create Date: 2026-08-30 06:48:38.142693

Hand-written, not raw autogenerate output — see the "Critério de pronto" in
issue #9 and docs/architecture.md §4.1/§4.2 for the geometry decision this
migration implements.
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d020b4a3f2a"
down_revision: str | Sequence[str] | None = "ca09e07c189c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Idempotent: the Compose init script already enables this for local dev
    # (infrastructure/postgres/init/01-init.sql), but a migration should not
    # assume that script ran — a managed production database won't have it.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "regions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("qr_token", sa.Text(), nullable=False),
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
            name="ck_regions_geom_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'draft', 'archived')",
            name="ck_regions_status",
        ),
        sa.UniqueConstraint("slug", name="uq_regions_slug"),
        sa.UniqueConstraint("qr_token", name="uq_regions_qr_token"),
    )
    op.create_index(
        "ix_regions_geom",
        "regions",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "ix_regions_centroid",
        "regions",
        ["centroid"],
        unique=False,
        postgresql_using="gist",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_regions_centroid", table_name="regions", postgresql_using="gist")
    op.drop_index("ix_regions_geom", table_name="regions", postgresql_using="gist")
    op.drop_table("regions")
