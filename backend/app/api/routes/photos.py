"""Photo routes: `GET /api/regions/{region}/photos` (the region's photo
timeline, issue #21) and `GET /api/photos/{photo_id}/file` (streaming the
image bytes, issue #22).

Both live in this one module — matching docs/architecture.md's project tree,
which lists `photos.py` as a single sibling of `regions.py` under
`api/routes/` — but as two routers, `router` and `file_router`, because their
paths don't share a common prefix (`/api/regions/{region}/photos` vs.
`/api/photos/{photo_id}/file`). Both are registered the same way in
`app/api/routes/__init__.py`, so this doesn't add a second registration
pattern, only a second router instance.
"""

import uuid
from collections.abc import Generator
from typing import BinaryIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.photo import PhotoPage
from app.services import photo_service
from app.storage.base import StorageBackend
from app.storage.dependency import get_storage_backend

router = APIRouter(prefix="/api/regions", tags=["photos"])
file_router = APIRouter(prefix="/api/photos", tags=["photos"])

# The image bytes behind a given photo_id never change post-upload — there's
# no photo-edit endpoint in the MVP — so a year-long, "immutable" cache is
# safe (architecture.md §5.2).
_IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"

# Chosen as a plain, unremarkable buffer size for chunked reads — no
# measurement behind it, just "not the whole file at once, not one byte at a
# time".
_STREAM_CHUNK_BYTES = 64 * 1024


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


def _iter_file_chunks(file: BinaryIO) -> Generator[bytes, None, None]:
    """Yield the file in fixed-size chunks instead of reading it whole into
    memory before responding — the point of `StreamingResponse` over
    returning bytes directly.
    """
    try:
        while chunk := file.read(_STREAM_CHUNK_BYTES):
            yield chunk
    finally:
        file.close()


@file_router.get("/{photo_id}/file")
def get_photo_file(
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),  # noqa: B008
    storage: StorageBackend = Depends(get_storage_backend),  # noqa: B008
) -> StreamingResponse:
    file, content_type = photo_service.open_photo_file(db, photo_id, storage)
    return StreamingResponse(
        _iter_file_chunks(file),
        media_type=content_type,
        headers={"Cache-Control": _IMMUTABLE_CACHE_CONTROL},
    )
