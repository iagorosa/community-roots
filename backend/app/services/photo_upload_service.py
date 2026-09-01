"""Photo upload: the write side of the photo timeline — `POST
/api/plantings/{planting_id}/photos` (issue #28, migrated from `region_id`
to `planting_id` by issue #85), the endpoint that finally calls every piece
issues #20-#27 built (`Photo`, storage, upload validation, EXIF/privacy
extraction) but never wired to a write path.

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
from app.core.errors import AppError
from app.models.photo import Photo
from app.schemas.photo import PhotoOut
from app.services import planting_service
from app.services.exif_processing import process_photo_metadata
from app.services.image_processing import validate_upload
from app.storage.base import StorageBackend
from app.storage.keys import generate_storage_key


class IdentifiablePersonConsentRequired(AppError):
    """Raised when the upload declares an identifiable person
    (`includes_identifiable_person=True`) without also confirming the
    guardian's authorization (`identifiable_person_consent_confirmed`).

    Issue #38 (LGPD): the project's decision is that photos of identifiable
    people are allowed, but only with self-declared consent — the two
    `PhotoUploadForm` checkboxes this mirrors. Enforced here too, not just
    in the frontend, since a request can always skip the browser
    altogether. `422` (not `400`): matches `image_too_large`/`invalid_image`
    below, which use the same status for "the request is well-formed but
    its content violates a rule".
    """

    status_code = 422
    code = "identifiable_person_consent_required"

    def __init__(self) -> None:
        super().__init__(
            "Para enviar fotos com pessoas identificáveis, é preciso confirmar "
            "que você tem autorização do responsável."
        )


class PhotoStorageUnavailable(AppError):
    """Raised when `storage.save` fails for a filesystem reason (permission
    denied, disk full, `storage/` missing or wiped out from under the
    process) — confirmed live (issue #36) as a gap: left uncaught, this
    reached the client as a raw `PermissionError`/`OSError`, translated by
    nothing into `app.core.errors`' structured shape, so it fell through to
    the framework's own English, no-next-step default. `503` (not `500`):
    this is specifically "the storage dependency is unavailable right now",
    which is what actually happened and what makes "tente novamente" true —
    a retry is expected to succeed once the disk/mount is healthy again,
    unlike a generic server bug.
    """

    status_code = 503
    code = "photo_storage_unavailable"

    def __init__(self) -> None:
        super().__init__("Não foi possível salvar a foto agora. Tente novamente em instantes.")


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
    planting_id: uuid.UUID,
    *,
    file: UploadFile,
    description: str | None,
    contributor_name: str | None,
    share_location: bool,
    includes_identifiable_person: bool = False,
    identifiable_person_consent_confirmed: bool = False,
) -> PhotoOut:
    """Validate, store and record a new photo for `planting_id`.

    Propagates `planting_service.PlantingNotFound`, `image_processing.
    ImageTooLarge` and `image_processing.InvalidImage` unchanged — all
    `AppError` subclasses `app.core.errors.register_error_handlers` already
    translates into a structured `{"detail", "code"}` response, so none of
    them are caught here. `storage.save` failing with an `OSError` is the
    one exception this function does translate itself, into
    `PhotoStorageUnavailable` — see that class's docstring.

    `includes_identifiable_person`/`identifiable_person_consent_confirmed`
    default to `False` so every existing caller (and the common case, a
    photo with no person in it) keeps working unchanged — issue #38 is
    purely additive. Checked before anything else in this function — no
    image bytes are read, no planting lookup happens — because it's the
    cheapest possible rejection and doesn't depend on either.
    """
    if includes_identifiable_person and not identifiable_person_consent_confirmed:
        raise IdentifiablePersonConsentRequired()

    planting_service.get_planting(db, planting_id)  # raises PlantingNotFound if missing

    image = validate_upload(file.file, max_bytes=settings.max_upload_bytes)
    metadata = process_photo_metadata(image, share_location=share_location)

    extension = _extension_for_content_type(metadata.content_type)
    storage_key = generate_storage_key(planting_id, extension=extension)
    try:
        storage.save(storage_key, io.BytesIO(metadata.image_bytes), metadata.content_type)
    except OSError as exc:
        raise PhotoStorageUnavailable() from exc

    location = None
    if metadata.latitude is not None and metadata.longitude is not None:
        location = WKTElement(f"POINT({metadata.longitude} {metadata.latitude})", srid=4326)

    photo = Photo(
        planting_id=planting_id,
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
        # Reached only when the two are consistent (the guard above already
        # rejected `True`/`False`), but spelled out as `and` rather than
        # just `includes_identifiable_person` so the column's own invariant
        # ("only true when both checkboxes were checked") is visible here
        # too, not just enforced upstream.
        includes_identifiable_person_with_consent=(
            includes_identifiable_person and identifiable_person_consent_confirmed
        ),
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
