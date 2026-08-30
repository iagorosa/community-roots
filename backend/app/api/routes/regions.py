"""`GET /api/regions` and `GET /api/regions/{region}` — architecture.md §5."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.region import RegionFeature, RegionFeatureCollection
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
