"""`GET`/`POST`/`PATCH /api/regions` — architecture.md §5. Writes are
admin-only (`X-Admin-Token`, architecture.md §9)."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.schemas.region import (
    RegionCreate,
    RegionFeature,
    RegionFeatureCollection,
    RegionImportFeatureCollection,
    RegionImportSummary,
    RegionUpdate,
)
from app.services import qr_service, region_service

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


@router.get("/{region}/qr-code")
def get_region_qr_code(
    region: str,
    format: Literal["png", "svg"] = Query(default="png"),
    size: int | None = Query(default=None, gt=0, le=qr_service.MAX_BOX_SIZE),
    db: Session = Depends(get_db),  # noqa: B008 — FastAPI's DI relies on this call-in-default pattern.
) -> Response:
    """Public (no admin token): same visibility as `GET /{region}` above —
    `region_service.get_region` 404s for a `draft`/`archived` region here
    too. Exempting this route from that would let anyone who knows/guesses a
    hidden region's slug mint a working `/r/{qr_token}` link (the future
    `/r/{qr_token}` redirect resolves by token alone, not `status`) to a
    region `status` exists specifically to keep out of public view
    (architecture.md §4.5/§7). See `tests/test_region_qr_route.py::
    test_get_qr_code_returns_404_for_draft_region` for the documented
    decision and rationale in full.

    `size` outside `1..qr_service.MAX_BOX_SIZE` is rejected by
    `Query(..., gt=0, le=...)` — native FastAPI 422 — before
    `qr_service.generate_qr_code` (which enforces the identical bounds for
    callers that reach it directly, e.g. tests, or a future print-sheet
    endpoint) is ever called. The upper bound exists because `size` maps to
    `box_size`, which scales the rendered pixel buffer large enough to OOM
    a worker from a single unauthenticated request if left unbounded — see
    `qr_service.MAX_BOX_SIZE`'s comment for the measurements behind the
    chosen cap.
    """
    feature = region_service.get_region(db, region)
    image_bytes, content_type = qr_service.generate_qr_code(
        feature.properties.qr_token, format=format, size=size
    )
    return Response(content=image_bytes, media_type=content_type)


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


@router.post(
    "/import",
    response_model=RegionImportSummary,
    dependencies=[Depends(require_admin_token)],
)
def import_regions(
    payload: RegionImportFeatureCollection,
    db: Session = Depends(get_db),  # noqa: B008 — FastAPI's DI relies on this call-in-default pattern.
) -> RegionImportSummary:
    return region_service.import_regions(db, payload)
