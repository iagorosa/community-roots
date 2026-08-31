"""`GET /api/qr/{token}` — resolves a scanned QR token to the region or
planting it points at. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import qr_code_service

router = APIRouter(prefix="/api/qr", tags=["qr"])


class QrResolution(BaseModel):
    """Where a scanned token points. The frontend builds the destination
    path itself: `/regions/{identifier}` for a region, `/plantings/{identifier}`
    for a planting — this endpoint only tells it which."""

    type: Literal["region", "planting"]
    identifier: str


@router.get("/{token}", response_model=QrResolution)
def resolve_qr_token(
    token: str,
    db: Session = Depends(get_db),  # noqa: B008 — FastAPI's DI relies on this call-in-default pattern.
) -> QrResolution:
    target = qr_code_service.resolve_qr_token(db, token)
    return QrResolution(type=target.kind, identifier=target.identifier)
