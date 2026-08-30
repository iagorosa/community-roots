"""Photo upload: the write side of the photo timeline — `POST
/api/regions/{region}/photos` (issue #28), the endpoint that finally calls
every piece issues #20-#27 built (`Photo`, storage, upload validation, EXIF/
privacy extraction) but never wired to a write path.

Kept in its own module rather than folded into `photo_service.py`, even
though `region_service.py` shows the opposite precedent (one file, both
`list_regions`/`get_region` and `create_region`/`update_region`): the write
path here pulls in three collaborators — `image_processing`,
`exif_processing`, `storage` — that the read/listing path never touches, so
merging them would turn `photo_service.py` into a grab-bag of imports for a
reader who only cares about the timeline query. `region_service.py`'s reads
and writes share the same collaborators (just `Region`/PostGIS), which is
why splitting *there* wouldn't buy the same clarity.
"""

import io
import uuid

from fastapi import UploadFile
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.photo import Photo
from app.schemas.photo import PhotoOut
from app.services import region_service
from app.services.exif_processing import process_photo_metadata
from app.services.image_processing import validate_upload
from app.storage.base import StorageBackend
from app.storage.keys import generate_storage_key

# Maps the Pillow-decoded format (what `image_processing`/`exif_processing`
# actually validated and re-encoded) to the extension used in `storage_key`.
# architecture.md §6.1: the extension must come from here, never from the
# client's filename/`file.filename` — a client sending "foto.png" for actual
# JPEG bytes (or a malicious path fragment as a "filename") must never
# influence the key.
_EXTENSIONS_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _extension_for_content_type(content_type: str) -> str:
    """Look up the storage-key extension for `content_type`, raising instead
    of guessing when it isn't mapped.

    Today every `content_type` this function sees is one `exif_processing.
    _content_type_for` produced from `settings.allowed_image_formats`
    (JPEG/PNG/WEBP), so this branch is unreachable in the shipped config —
    but `app/storage/keys.py`'s own docstring states the principle this
    enforces: a future bug or drift (an operator adding a format to
    `allowed_image_formats` without updating this map) must fail loudly
    here, not silently write a storage_key with a made-up/generic
    extension that then mismatches the actual file format.
    """
    try:
        return _EXTENSIONS_BY_CONTENT_TYPE[content_type]
    except KeyError:
        msg = f"nenhuma extensão de storage mapeada para content_type {content_type!r}"
        raise ValueError(msg) from None


def upload_photo(
    db: Session,
    storage: StorageBackend,
    region_identifier: str,
    *,
    file: UploadFile,
    description: str | None,
    contributor_name: str | None,
    share_location: bool,
) -> PhotoOut:
    """Validate, store and record a new photo for the region
    `region_identifier` resolves to.

    Propagates `region_service.RegionNotFound`, `image_processing.
    ImageTooLarge` and `image_processing.InvalidImage` unchanged — all
    `AppError` subclasses `app.core.errors.register_error_handlers` already
    translates into a structured `{"detail", "code"}` response, so none of
    them are caught here.
    """
    region = region_service.get_region(db, region_identifier)
    region_id = uuid.UUID(region.id)

    image = validate_upload(file.file, max_bytes=settings.max_upload_bytes)
    metadata = process_photo_metadata(image, share_location=share_location)

    extension = _extension_for_content_type(metadata.content_type)
    storage_key = generate_storage_key(region_id, extension=extension)
    storage.save(storage_key, io.BytesIO(metadata.image_bytes), metadata.content_type)

    location = None
    if metadata.latitude is not None and metadata.longitude is not None:
        location = WKTElement(f"POINT({metadata.longitude} {metadata.latitude})", srid=4326)

    photo = Photo(
        region_id=region_id,
        storage_key=storage_key,
        original_filename=file.filename,
        content_type=metadata.content_type,
        byte_size=len(metadata.image_bytes),
        width=metadata.width,
        height=metadata.height,
        description=description,
        contributor_name=contributor_name,
        captured_at=metadata.captured_at,
        location=location,
        location_source=metadata.location_source,
    )
    db.add(photo)
    db.commit()

    # Built straight from `photo`/`metadata` rather than re-querying (as
    # `region_service.create_region` does via `_fetch_feature_by_id`):
    # Postgres returns every server-generated column (`id`, `uploaded_at`)
    # via `RETURNING` on the `INSERT` SQLAlchemy just issued, so they're
    # already populated on `photo` — and `latitude`/`longitude` are cheaper
    # taken straight from `metadata` than re-derived from `location` through
    # `ST_X`/`ST_Y`, with no risk of float round-tripping through PostGIS
    # producing a different value than what was just written.
    return PhotoOut(
        id=photo.id,
        description=photo.description,
        contributor_name=photo.contributor_name,
        captured_at=photo.captured_at,
        uploaded_at=photo.uploaded_at,
        latitude=metadata.latitude,
        longitude=metadata.longitude,
        width=photo.width,
        height=photo.height,
    )
