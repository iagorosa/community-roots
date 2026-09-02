"""backfill missing region qr codes

Revision ID: 5c04f25680ac
Revises: 46d95962438a
Create Date: 2026-09-01 22:09:19.414965

Data-only migration for issue #108 — no schema change, so hand-written
without `--autogenerate`. Every `Region` created through the application
(`region_service.create_region`) gets a `QrCode` in the same transaction, so
this exists only for regions seeded before issue #80 introduced the
`QrCode` model, which no rerun of `scripts/seed.py` ever backfilled until
that script was also fixed alongside this migration (see
`app.services.qr_code_service.backfill_missing_region_qr_codes`, which this
reuses instead of reimplementing the token generation it depends on).
"""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from alembic import op
from app.services.qr_code_service import backfill_missing_region_qr_codes

# revision identifiers, used by Alembic.
revision: str = "5c04f25680ac"
down_revision: str | Sequence[str] | None = "46d95962438a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade data: give every QrCode-less Region one."""
    session = Session(bind=op.get_bind())
    backfill_missing_region_qr_codes(session)
    session.commit()


def downgrade() -> None:
    """No-op, documented: this migration can't tell apart the QrCodes it
    created from ones created normally afterward (both look identical —
    same table, same shape, no marker column), so there is no safe way to
    undo just this migration's inserts without risking deleting a QrCode a
    real Region now depends on. Leaving the backfilled QrCodes in place on
    downgrade is safe either way: `region_service._region_query()`'s INNER
    JOIN only cares that a QrCode exists, never how it got there.
    """
