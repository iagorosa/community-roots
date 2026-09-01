"""Unit tests for `app/services/photo_upload_service.py` internals that
aren't easily reached through the HTTP route in
`tests/test_photo_upload_route.py` — the storage-key extension mapping, and
(issue #36) translating a storage write failure into an actionable error.
"""

import io
import uuid
from typing import BinaryIO

import pytest
from fastapi import UploadFile
from geoalchemy2.elements import WKTElement
from PIL import Image
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region
from app.services import photo_upload_service
from app.services.photo_upload_service import (
    IdentifiablePersonConsentRequired,
    PhotoStorageUnavailable,
    _extension_for_content_type,
)

_POINT_WKT = "POINT(-43.3127 -21.8843)"


@pytest.mark.parametrize(
    ("content_type", "expected_extension"),
    [
        ("image/jpeg", "jpg"),
        ("image/png", "png"),
        ("image/webp", "webp"),
    ],
)
def test_extension_for_content_type_matches_the_allowed_formats(
    content_type: str, expected_extension: str
) -> None:
    assert _extension_for_content_type(content_type) == expected_extension


def test_extension_for_content_type_raises_loudly_for_an_unmapped_content_type() -> None:
    """`app/storage/keys.py`'s own docstring states the principle this
    enforces: "a future bug in the Pillow-format-to-extension mapping
    should fail loudly ... instead of writing a malformed storage_key to
    the database." A silent fallback (e.g. a generic ".bin" extension)
    would violate that the moment `settings.allowed_image_formats` grows a
    format this mapping doesn't know about yet.
    """
    with pytest.raises(ValueError, match="image/gif"):
        _extension_for_content_type("image/gif")


class _StorageThatCannotWrite:
    """A `StorageBackend` (satisfied structurally, per its `Protocol`) whose
    `save` always fails the way a permission-denied or read-only `storage/`
    does. Used instead of actually chmod-ing a `tmp_path` directory: real
    filesystem permission enforcement isn't reliable to depend on in a test
    (a process running as root ignores it entirely), where a fake that just
    raises is deterministic everywhere.
    """

    def save(self, key: str, data: BinaryIO, content_type: str) -> None:
        raise PermissionError(13, "Permission denied")

    def open(self, key: str) -> BinaryIO:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        return False


def _add_region(db_session: Session) -> Region:
    region = Region(
        slug=f"canteiro-{uuid.uuid4().hex[:8]}",
        name="Canteiro de teste",
        geom=WKTElement(_POINT_WKT, srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID) -> Planting:
    planting = Planting(region_id=region_id, geom=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(planting)
    db_session.flush()
    db_session.add(QrCode(planting_id=planting.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return planting


def _jpeg_upload_file() -> UploadFile:
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color=(10, 20, 30)).save(buffer, format="JPEG")
    buffer.seek(0)
    return UploadFile(filename="foto.jpg", file=buffer)


def test_upload_photo_translates_a_storage_write_failure_into_an_app_error(
    db_session: Session,
) -> None:
    """Confirmed live (issue #36): with `storage/` made read-only, this same
    `storage.save` call raised a bare `PermissionError` that reached the
    client as Starlette's default "Internal Server Error" — no structure, in
    English, no next step. `upload_photo` must catch that and raise an
    `AppError` instead, so `app.core.errors`' existing translation gives the
    client a real, Portuguese, actionable message.
    """
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    with pytest.raises(PhotoStorageUnavailable) as excinfo:
        photo_upload_service.upload_photo(
            db_session,
            _StorageThatCannotWrite(),
            planting.id,
            file=_jpeg_upload_file(),
            description=None,
            contributor_name=None,
            share_location=False,
        )

    error = excinfo.value
    assert isinstance(error, AppError)
    assert error.status_code == 503
    assert error.detail == "Não foi possível salvar a foto agora. Tente novamente em instantes."


def test_upload_photo_rejects_an_identifiable_person_without_confirmed_consent(
    db_session: Session,
) -> None:
    """Issue #38 (LGPD): the service must enforce this rule itself, not rely
    only on `PhotoUploadForm`'s client-side checkbox pairing — a request
    that skips the frontend entirely must still be rejected.
    """
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    with pytest.raises(IdentifiablePersonConsentRequired) as excinfo:
        photo_upload_service.upload_photo(
            db_session,
            _StorageThatCannotWrite(),  # never reached: rejected before storage is touched
            planting.id,
            file=_jpeg_upload_file(),
            description=None,
            contributor_name=None,
            share_location=False,
            includes_identifiable_person=True,
            identifiable_person_consent_confirmed=False,
        )

    error = excinfo.value
    assert isinstance(error, AppError)
    assert error.status_code == 422
    assert error.code == "identifiable_person_consent_required"
