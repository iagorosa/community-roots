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
