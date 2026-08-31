"""Photo routes: `GET /api/plantings/{planting_id}/photos` (a planting's
photo timeline, issue #21, migrated from `region_id` by issue #84) and
`GET /api/photos/{photo_id}/file` (streaming the image bytes, issue #22).

Both live in this one module — matching docs/architecture.md's project tree,
which lists `photos.py` as a single sibling of `regions.py` under
`api/routes/` — but as two routers, `router` and `file_router`, because their
paths don't share a common prefix (`/api/plantings/{planting_id}/photos` vs.
`/api/photos/{photo_id}/file`). Both are registered the same way in
`app/api/routes/__init__.py`, so this doesn't add a second registration
pattern, only a second router instance.
"""

import uuid
from collections.abc import Generator
from typing import BinaryIO

from fastapi import APIRouter, Depends, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.photo import PhotoOut, PhotoPage
from app.services import photo_service, photo_upload_service
from app.storage.base import StorageBackend
from app.storage.dependency import get_storage_backend

router = APIRouter(prefix="/api/plantings", tags=["photos"])
file_router = APIRouter(prefix="/api/photos", tags=["photos"])

# The image bytes behind a given photo_id never change post-upload — there's
# no photo-edit endpoint in the MVP — so a year-long, "immutable" cache is
# safe (architecture.md §5.2).
_IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"

# Chosen as a plain, unremarkable buffer size for chunked reads — no
# measurement behind it, just "not the whole file at once, not one byte at a
# time".
_STREAM_CHUNK_BYTES = 64 * 1024


@router.get("/{planting_id}/photos", response_model=PhotoPage)
def list_planting_photos(
    planting_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(
        default=photo_service.DEFAULT_PAGE_SIZE,
        ge=1,
        le=photo_service.MAX_PAGE_SIZE,
    ),
    db: Session = Depends(get_db),  # noqa: B008 — FastAPI's DI relies on this call-in-default pattern.
) -> PhotoPage:
    return photo_service.list_planting_photos(db, planting_id, cursor=cursor, limit=limit)


@router.post("/{planting_id}/photos", response_model=PhotoOut, status_code=201)
def upload_photo(
    planting_id: uuid.UUID,
    file: UploadFile,
    description: str | None = Form(default=None),
    contributor_name: str | None = Form(default=None),
    # "desmarcado por padrão" (architecture.md §6.2): sharing GPS location is
    # opt-in, never assumed just because the client omitted the field.
    share_location: bool = Form(default=False),
    db: Session = Depends(get_db),  # noqa: B008
    storage: StorageBackend = Depends(get_storage_backend),  # noqa: B008
) -> PhotoOut:
    """Public (no admin token — anyone, including anonymously, can
    contribute a photo). See `app.services.photo_upload_service.upload_photo`
    for the validate/store/record pipeline this delegates to.

    NOTE (issue #84 scope): `photo_upload_service.upload_photo` still
    resolves its third argument as a Region identifier (`region_service.
    get_region`) — it hasn't been migrated to Planting yet. That migration
    is issue #85's scope (Task 7 of the pivot plan), tracked separately so
    this route's path/param rename could land on its own. Until #85 lands,
    a real upload through this route 404s (no Region has `planting_id`'s
    value), which is expected and covered by the currently-skipped/updated
    upload tests.
    """
    return photo_upload_service.upload_photo(
        db,
        storage,
        planting_id,
        file=file,
        description=description,
        contributor_name=contributor_name,
        share_location=share_location,
    )


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
