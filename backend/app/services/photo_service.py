"""A planting's photo timeline: listing with keyset pagination. See
docs/architecture.md §4.3/§4.4 for the `photos` table and the
location-derivation decision, and §5 for the
`GET /api/plantings/{planting_id}/photos` contract.
"""

import base64
import binascii
import uuid
from datetime import datetime
from typing import BinaryIO

from sqlalchemy import ColumnElement, func, select, tuple_
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.photo import Photo
from app.schemas.photo import PhotoOut, PhotoPage
from app.services import planting_service
from app.storage.base import StorageBackend

# architecture.md §4.5: `status` exists so an organizer can pull a photo
# offline with a single `UPDATE` — this is the only listing of photos this
# issue builds, and it's public (no admin token), so `hidden` must never
# leak through it, unconditionally.
_PUBLICLY_VISIBLE: ColumnElement[bool] = Photo.status == "published"

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

_CURSOR_SEPARATOR = "|"


class InvalidCursor(ValidationFailedError):
    code = "invalid_cursor"

    def __init__(self, cursor: str) -> None:
        super().__init__(f'Cursor de paginação inválido: "{cursor}".')


class PhotoNotFound(NotFoundError):
    code = "photo_not_found"

    def __init__(self, photo_id: uuid.UUID) -> None:
        # Only ever built from `photo_id` — never `storage_key` — so this
        # message can't leak a storage path even by accident (architecture.md
        # §5.2 / §5.3).
        super().__init__(f'Nenhuma foto encontrada com o id "{photo_id}".')


def _encode_cursor(uploaded_at: datetime, photo_id: uuid.UUID) -> str:
    """Pack the keyset position into one opaque token.

    Callers only ever round-trip this value (read it from one response, send
    it back as the next request's `cursor`) — base64 keeps it from looking
    like something meant to be read or hand-constructed, matching how
    `regions.qr_token` is treated elsewhere in this codebase.
    """
    raw = f"{uploaded_at.isoformat()}{_CURSOR_SEPARATOR}{photo_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        uploaded_at_raw, id_raw = raw.split(_CURSOR_SEPARATOR)
        return datetime.fromisoformat(uploaded_at_raw), uuid.UUID(id_raw)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        # `cursor` is client-supplied input round-tripped from a value this
        # service generated, so any parse failure here means a tampered or
        # stale value — a 422, never a 500.
        raise InvalidCursor(cursor) from exc


def list_planting_photos(
    db: Session,
    planting_id: uuid.UUID,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> PhotoPage:
    """List `published` photos of `planting_id`, most-recently-uploaded first.

    Raises `planting_service.PlantingNotFound` (a `NotFoundError`) if
    `planting_id` doesn't resolve to a visible planting —
    `planting_service.get_planting` is reused rather than re-implementing
    the lookup, so there is still exactly one place that logic lives
    (architecture.md §5). Unlike `Region`, a `Planting` has no slug: the
    identifier here is a plain UUID.

    **Why keyset, not page/offset, pagination.** The listing orders by
    `uploaded_at DESC` on a table that receives inserts constantly — new
    photos always land on top. With page-number/offset pagination, a photo
    inserted between two requests shifts every row below it by one
    position: the client's next `offset` now points one row too early, so
    it either re-sees an item from the previous page or, symmetrically,
    skips one it hasn't seen yet. Keyset pagination sidesteps this because
    it never expresses "page N" as a position count — it expresses "give me
    the rows strictly after the last one I saw" as a `WHERE` predicate on
    `(uploaded_at, id)`. That comparison is anchored to a specific row, not
    a row count, so a fresh insert anywhere in the table — even one that
    lands ahead of everything already returned — cannot move a boundary the
    client has already crossed. `id` breaks ties because `uploaded_at`
    alone isn't unique (same-second uploads), and the composite matches the
    `ix_photos_planting_id_uploaded_at` index's leading columns, so the
    predicate is served by that index rather than a sequential scan.
    """
    planting_service.get_planting(db, planting_id)  # raises PlantingNotFound if missing

    page_size = min(max(limit, 1), MAX_PAGE_SIZE)

    query = (
        select(
            Photo.id,
            Photo.description,
            Photo.contributor_name,
            Photo.captured_at,
            Photo.uploaded_at,
            Photo.width,
            Photo.height,
            func.ST_Y(Photo.location).label("latitude"),
            func.ST_X(Photo.location).label("longitude"),
        )
        .where(Photo.planting_id == planting_id, _PUBLICLY_VISIBLE)
        .order_by(Photo.uploaded_at.desc(), Photo.id.desc())
        # One extra row past `page_size` is the cheapest way to know
        # whether another page exists, without a second COUNT query.
        .limit(page_size + 1)
    )

    if cursor is not None:
        cursor_uploaded_at, cursor_id = _decode_cursor(cursor)
        query = query.where(
            tuple_(Photo.uploaded_at, Photo.id) < tuple_(cursor_uploaded_at, cursor_id)
        )

    rows = db.execute(query).all()

    has_more = len(rows) > page_size
    page_rows = rows[:page_size]
    next_cursor = _encode_cursor(page_rows[-1].uploaded_at, page_rows[-1].id) if has_more else None

    return PhotoPage(
        items=[
            PhotoOut(
                id=row.id,
                description=row.description,
                contributor_name=row.contributor_name,
                captured_at=row.captured_at,
                uploaded_at=row.uploaded_at,
                latitude=row.latitude,
                longitude=row.longitude,
                width=row.width,
                height=row.height,
            )
            for row in page_rows
        ],
        next_cursor=next_cursor,
    )


def open_photo_file(
    db: Session, photo_id: uuid.UUID, storage: StorageBackend
) -> tuple[BinaryIO, str]:
    """Resolve `photo_id` to an open file handle and its content type, for
    `GET /api/photos/{photo_id}/file` (architecture.md §5.2).

    Reuses `_PUBLICLY_VISIBLE` — the same rule `list_planting_photos` applies —
    rather than only checking existence: `region_service.get_region` (and,
    equivalently, `planting_service.get_planting`) already sets the precedent
    that `hidden`/`archived` fully removes a row from every public read path,
    not just listings (its `_PUBLICLY_VISIBLE` filters `get_region`/
    `get_planting` too, not only the listing functions). A `hidden` photo
    follows the same rule here: architecture.md's rationale for `status` is
    letting an
    organizer "pull a photo offline with a single UPDATE", which reads as
    taking it down entirely, not just delisting it while a direct link still
    works — the more conservative reading, given this product's photos are
    of children.

    Raises `PhotoNotFound` for an unknown/hidden id *and* when the row exists
    but its file is missing from storage (e.g. `backend/storage/` wiped
    out-of-band) — from the caller's perspective these are indistinguishable,
    and collapsing them into one 404 is what keeps `storage_key` from ever
    reaching an error message.
    """
    photo = db.execute(
        select(Photo).where(Photo.id == photo_id, _PUBLICLY_VISIBLE)
    ).scalar_one_or_none()
    if photo is None:
        raise PhotoNotFound(photo_id)

    try:
        file = storage.open(photo.storage_key)
    except OSError:
        # Broader than just `FileNotFoundError`: a corrupted `storage_key`
        # pointing at a directory (`IsADirectoryError`) or a filesystem
        # permission misconfiguration (`PermissionError`) must surface the
        # same clean 404 as a missing file, never a raw 500 — all three are
        # `OSError` subclasses.
        raise PhotoNotFound(photo_id) from None

    return file, photo.content_type
