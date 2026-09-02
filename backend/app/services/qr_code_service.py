"""Create and resolve `QrCode` rows for `Region`/`Planting`. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.

Kept separate from `qr_service.py`, which stays a pure image-generation
function (token in, image bytes out) untouched by this pivot — this module
is the only place that reads/writes the `qr_codes` table.
"""

import secrets
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.qr_code import QrCode
from app.models.region import Region


class QrTokenNotFound(NotFoundError):
    code = "qr_token_not_found"

    def __init__(self, token: str) -> None:
        super().__init__(f'Nenhum QR code encontrado para o token "{token}".')


@dataclass(frozen=True)
class QrCodeTarget:
    """What a scanned token resolves to: a region (by `slug`) or a planting
    (by `id`) — a planting has no slug, see
    docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md."""

    kind: Literal["region", "planting"]
    identifier: str


def create_region_qr_code(db: Session, region_id: uuid.UUID) -> str:
    """Insert a new `QrCode` row for `region_id` and return its token.

    Does not commit — the caller (`region_service.create_region`) controls
    the transaction, same as every other write in this codebase.
    """
    token = secrets.token_urlsafe(9)
    db.add(QrCode(region_id=region_id, token=token))
    return token


def create_planting_qr_code(db: Session, planting_id: uuid.UUID) -> str:
    """Insert a new `QrCode` row for `planting_id` and return its token."""
    token = secrets.token_urlsafe(9)
    db.add(QrCode(planting_id=planting_id, token=token))
    return token


def ensure_region_qr_code(db: Session, region_id: uuid.UUID) -> str | None:
    """Create a `QrCode` for `region_id` if it doesn't already have one.

    Returns the newly created token, or `None` if `region_id` already had a
    `QrCode` (nothing done). Used by `scripts/seed.py`'s "region already
    exists" branch and by `backfill_missing_region_qr_codes` below — every
    real region should get its `QrCode` at creation time
    (`region_service.create_region`), but regions seeded before issue #80
    introduced the model never did (issue #108).
    """
    already_has_one = db.execute(
        select(QrCode.id).where(QrCode.region_id == region_id)
    ).scalar_one_or_none()
    if already_has_one is not None:
        return None
    return create_region_qr_code(db, region_id)


def backfill_missing_region_qr_codes(db: Session) -> int:
    """Create a `QrCode` for every `Region` that doesn't have one yet.

    Data-only fix for issue #108: `region_service._region_query()` INNER
    JOINs on `qr_codes` by design (see that function's docstring), so a
    region missing its `QrCode` silently disappears from every public
    listing instead of erroring. No application code in current use can
    create such a region (`region_service.create_region` always creates
    both in the same transaction) — this exists for regions seeded before
    issue #80 introduced the `QrCode` model, and is reused by both the
    `5c04f25680ac_backfill_missing_region_qr_codes` data migration and
    `scripts/seed.py`.

    Does not commit — same convention as `create_region_qr_code`. Returns
    the number of `QrCode`s created.
    """
    region_ids_missing_qr_code = (
        db.execute(
            select(Region.id).where(
                Region.id.not_in(select(QrCode.region_id).where(QrCode.region_id.is_not(None)))
            )
        )
        .scalars()
        .all()
    )

    for region_id in region_ids_missing_qr_code:
        create_region_qr_code(db, region_id)

    return len(region_ids_missing_qr_code)


def resolve_qr_token(db: Session, token: str) -> QrCodeTarget:
    """Resolve a scanned `token` to the region or planting it points at.

    Raises `QrTokenNotFound` for an unknown token.
    """
    qr_code = db.execute(select(QrCode).where(QrCode.token == token)).scalar_one_or_none()
    if qr_code is None:
        raise QrTokenNotFound(token)

    if qr_code.region_id is not None:
        slug = db.execute(select(Region.slug).where(Region.id == qr_code.region_id)).scalar_one()
        return QrCodeTarget(kind="region", identifier=slug)

    return QrCodeTarget(kind="planting", identifier=str(qr_code.planting_id))
