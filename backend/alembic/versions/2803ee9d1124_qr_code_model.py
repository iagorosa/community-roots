"""qr code model

Revision ID: 2803ee9d1124
Revises: db4275a589be
Create Date: 2026-08-30 23:35:29.231592

Hand-written, not raw autogenerate output — see the "Critério de pronto" in
issue #80 and docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md
for why `qr_codes` replaces `regions.qr_token` with two nullable FKs + a CHECK.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2803ee9d1124"
down_revision: str | Sequence[str] | None = "db4275a589be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "qr_codes",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("region_id", sa.UUID(), nullable=True),
        sa.Column("planting_id", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(region_id IS NOT NULL) != (planting_id IS NOT NULL)",
            name="ck_qr_codes_exactly_one_target",
        ),
        sa.UniqueConstraint("token", name="uq_qr_codes_token"),
        sa.UniqueConstraint("region_id", name="uq_qr_codes_region_id"),
        sa.UniqueConstraint("planting_id", name="uq_qr_codes_planting_id"),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["planting_id"], ["plantings.id"], ondelete="CASCADE"),
    )

    # `regions.qr_token` is superseded by `qr_codes` — no production data
    # exists yet (confirmed in the pivot brainstorm), so this drops the
    # column outright rather than migrating values.
    op.drop_constraint("uq_regions_qr_token", "regions", type_="unique")
    op.drop_column("regions", "qr_token")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("regions", sa.Column("qr_token", sa.Text(), nullable=True))
    op.execute("UPDATE regions SET qr_token = 'restored-' || id::text WHERE qr_token IS NULL")
    op.alter_column("regions", "qr_token", nullable=False)
    op.create_unique_constraint("uq_regions_qr_token", "regions", ["qr_token"])

    op.drop_table("qr_codes")
