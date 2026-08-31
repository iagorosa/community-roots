"""`GET`/`POST`/`PATCH /api/plantings` and `GET /api/plantings/{id}/qr-code`.
Mirrors `app/api/routes/regions.py`. Writes are admin-only (`X-Admin-Token`),
same rule as regions.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.schemas.planting import (
    PlantingCreate,
    PlantingFeature,
    PlantingFeatureCollection,
    PlantingUpdate,
)
from app.services import planting_service, qr_service

router = APIRouter(prefix="/api/plantings", tags=["plantings"])


@router.get("", response_model=PlantingFeatureCollection)
def list_plantings(
    region_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> PlantingFeatureCollection:
    return planting_service.list_plantings(db, region_id=region_id)


@router.get("/{planting_id}", response_model=PlantingFeature)
def get_planting(
    planting_id: uuid.UUID,
    db: Session = Depends(get_db),  # noqa: B008
) -> PlantingFeature:
    return planting_service.get_planting(db, planting_id)


@router.get("/{planting_id}/qr-code")
def get_planting_qr_code(
    planting_id: uuid.UUID,
    format: Literal["png", "svg"] = Query(default="png"),
    size: int | None = Query(default=None, gt=0, le=qr_service.MAX_BOX_SIZE),
    db: Session = Depends(get_db),  # noqa: B008
) -> Response:
    """Public (no admin token) — same visibility rule as
    `GET /{planting_id}` (`planting_service.get_planting` 404s for a
    `draft`/`archived` planting here too, same rationale as the region
    QR route)."""
    feature = planting_service.get_planting(db, planting_id)
    image_bytes, content_type = qr_service.generate_qr_code(
        feature.properties.qr_token, format=format, size=size
    )
    return Response(content=image_bytes, media_type=content_type)


@router.post(
    "",
    response_model=PlantingFeature,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_token)],
)
def create_planting(
    payload: PlantingCreate,
    db: Session = Depends(get_db),  # noqa: B008
) -> PlantingFeature:
    return planting_service.create_planting(db, payload)


@router.patch(
    "/{planting_id}",
    response_model=PlantingFeature,
    dependencies=[Depends(require_admin_token)],
)
def update_planting(
    planting_id: uuid.UUID,
    payload: PlantingUpdate,
    db: Session = Depends(get_db),  # noqa: B008
) -> PlantingFeature:
    return planting_service.update_planting(db, planting_id, payload)
