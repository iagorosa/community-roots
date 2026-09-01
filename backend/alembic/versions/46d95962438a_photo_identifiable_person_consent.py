"""photo identifiable person consent

Revision ID: 46d95962438a
Revises: a901d5e6085a
Create Date: 2026-09-01 14:54:17.890227

Hand-written, not raw autogenerate output — see issue #38 and
docs/architecture.md §9: the project's LGPD consent policy for photos of
identifiable people was decided, and needs somewhere to be recorded per
photo.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "46d95962438a"
down_revision: str | Sequence[str] | None = "a901d5e6085a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "photos",
        sa.Column(
            "includes_identifiable_person_with_consent",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("photos", "includes_identifiable_person_with_consent")
