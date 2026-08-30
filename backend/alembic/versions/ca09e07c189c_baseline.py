"""baseline

Revision ID: ca09e07c189c
Revises: 
Create Date: 2026-08-30 02:05:50.442720

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'ca09e07c189c'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
