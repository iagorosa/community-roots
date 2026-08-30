"""`GET /api/regions/{region}/photos` — the region's photo timeline.

Kept in its own router (rather than added to `regions.py`) because
docs/architecture.md's project tree lists `photos.py` as a sibling of
`regions.py` under `api/routes/` — `POST /api/regions/{region}/photos` and
`GET /api/photos/{photo_id}/file` (future issues) belong here too, once
built. The path still nests under `/api/regions/{region}` either way.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.photo import PhotoPage
from app.services import photo_service

router = APIRouter(prefix="/api/regions", tags=["photos"])


@router.get("/{region}/photos", response_model=PhotoPage)
def list_region_photos(
    region: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(
        default=photo_service.DEFAULT_PAGE_SIZE,
        ge=1,
        le=photo_service.MAX_PAGE_SIZE,
    ),
    db: Session = Depends(get_db),  # noqa: B008 — FastAPI's DI relies on this call-in-default pattern.
) -> PhotoPage:
    return photo_service.list_region_photos(db, region, cursor=cursor, limit=limit)
