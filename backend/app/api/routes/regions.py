"""`GET`/`POST`/`PATCH /api/regions` — architecture.md §5. Writes are
admin-only (`X-Admin-Token`, architecture.md §9)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.schemas.region import RegionCreate, RegionFeature, RegionFeatureCollection, RegionUpdate
from app.services import region_service

router = APIRouter(prefix="/api/regions", tags=["regions"])


@router.get("", response_model=RegionFeatureCollection)
def list_regions(
    db: Session = Depends(get_db),  # noqa: B008 — FastAPI's DI relies on this call-in-default pattern.
) -> RegionFeatureCollection:
    return region_service.list_regions(db)


@router.get("/{region}", response_model=RegionFeature)
def get_region(
    region: str,
    db: Session = Depends(get_db),  # noqa: B008 — FastAPI's DI relies on this call-in-default pattern.
) -> RegionFeature:
    return region_service.get_region(db, region)


@router.post(
    "",
    response_model=RegionFeature,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_token)],
)
def create_region(
    payload: RegionCreate,
    db: Session = Depends(get_db),  # noqa: B008 — FastAPI's DI relies on this call-in-default pattern.
) -> RegionFeature:
    return region_service.create_region(db, payload)


@router.patch(
    "/{region}",
    response_model=RegionFeature,
    dependencies=[Depends(require_admin_token)],
)
def update_region(
    region: str,
    payload: RegionUpdate,
    db: Session = Depends(get_db),  # noqa: B008 — FastAPI's DI relies on this call-in-default pattern.
) -> RegionFeature:
    return region_service.update_region(db, region, payload)
