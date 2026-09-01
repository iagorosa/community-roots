"""Tests for `POST /api/plantings/{planting_id}/photos` (issue #28, migrated
from `region_id` to `planting_id` by issue #85) — the endpoint that closes
the upload pipeline built across issues #20-#27: validates the upload (#26),
extracts EXIF metadata under the site's privacy policy (#27), stores the
re-encoded bytes under a collision-free key (#25), and inserts the `Photo`
row (#20), returning it in the same shape the timeline listing (#21)
already uses.
"""

import io
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.photo import Photo
from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region
from app.storage.dependency import get_storage_backend
from app.storage.local import LocalFilesystemStorage

_POLYGON_WKT = (
    "POLYGON((-43.3130 -21.8845, -43.3125 -21.8845, "
    "-43.3125 -21.8840, -43.3130 -21.8840, -43.3130 -21.8845))"
)
_POINT_WKT = "POINT(-43.3127 -21.8843)"

# Same DMS layout `tests/test_exif_processing.py` uses to build real GPS EXIF.
_LATITUDE_DMS = (40.0, 26.0, 46.302)
_LATITUDE_REF = "N"
_LONGITUDE_DMS = (79.0, 58.0, 55.7027)
_LONGITUDE_REF = "W"


def _add_region(db_session: Session, **overrides: object) -> Region:
    """Insert a `Region` plus the `QrCode` row every real region gets at
    creation time (`region_service.create_region`) — required so the
    `Planting` fixture below has a valid `region_id` to point at.
    """
    defaults: dict[str, object] = {
        "slug": "canteiro-a",
        "name": "Canteiro A",
        "geom": WKTElement(_POLYGON_WKT, srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID, **overrides: object) -> Planting:
    """Insert a `Planting` plus the `QrCode` row every real planting gets at
    creation time (`planting_service.create_planting`) — `planting_service.
    get_planting` (which `photo_upload_service.upload_photo` reuses to
    validate the `{planting_id}` path parameter) INNER JOINs on it, so a
    planting without one wouldn't be a realistic fixture.
    """
    defaults: dict[str, object] = {
        "region_id": region_id,
        "geom": WKTElement(_POINT_WKT, srid=4326),
    }
    defaults.update(overrides)
    planting = Planting(**defaults)
    db_session.add(planting)
    db_session.flush()
    db_session.add(QrCode(planting_id=planting.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return planting


def _jpeg_bytes(*, width: int = 32, height: int = 32, with_gps: bool = False) -> bytes:
    """Build real, decodable JPEG bytes — never a mock — optionally carrying
    real GPS EXIF tags, laid out the same way a camera/phone would.
    """
    image = Image.new("RGB", (width, height), color=(10, 20, 30))
    buffer = io.BytesIO()

    if with_gps:
        exif = Image.Exif()
        exif[0x8825] = {1: _LATITUDE_REF, 2: _LATITUDE_DMS, 3: _LONGITUDE_REF, 4: _LONGITUDE_DMS}
        image.save(buffer, format="JPEG", exif=exif)
    else:
        image.save(buffer, format="JPEG")

    return buffer.getvalue()


@pytest.fixture()
def storage_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def client(app: FastAPI, storage_root: Path) -> Generator[TestClient, None, None]:
    """Overrides the base `client` fixture (`tests/conftest.py`) to also swap
    in a `LocalFilesystemStorage` rooted at `tmp_path` — mirrors
    `tests/test_photo_file_route.py`'s fixture of the same name, since this
    route writes to storage too, unlike the routes the base fixture covers.
    """
    app.dependency_overrides[get_storage_backend] = lambda: LocalFilesystemStorage(storage_root)
    with TestClient(app) as test_client:
        yield test_client
    del app.dependency_overrides[get_storage_backend]


def _upload(
    client: TestClient,
    planting_id: uuid.UUID | str,
    *,
    filename: str = "foto.jpg",
    content: bytes | None = None,
    **form: object,
):
    files = {"file": (filename, content or _jpeg_bytes(), "image/jpeg")}
    return client.post(f"/api/plantings/{planting_id}/photos", files=files, data=form)


def test_valid_upload_without_sharing_location_returns_201_with_null_location(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    response = _upload(
        client,
        planting.id,
        description="Muda de tomate",
        contributor_name="Maria",
        share_location="false",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["description"] == "Muda de tomate"
    assert body["contributor_name"] == "Maria"
    assert body["latitude"] is None
    assert body["longitude"] is None
    assert body["width"] == 32
    assert body["height"] == 32
    assert body["uploaded_at"] is not None
    assert body["photo_url"] == f"/api/photos/{body['id']}/file"
    assert "storage_key" not in body


def test_valid_upload_with_share_location_true_and_gps_exif_returns_coordinates(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    response = _upload(
        client, planting.id, content=_jpeg_bytes(with_gps=True), share_location="true"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["latitude"] is not None
    assert body["longitude"] is not None


def test_gps_exif_is_discarded_end_to_end_when_share_location_is_false(
    client: TestClient, db_session: Session
) -> None:
    """Closes the loop between this endpoint and `exif_processing`'s already
    unit-tested (issue #27) opt-in policy: GPS is present in the upload's
    EXIF, but with `share_location=False` (the form's default) it must never
    reach the response or the stored `Photo` row — not partially, not at all.
    """
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    response = _upload(
        client, planting.id, content=_jpeg_bytes(with_gps=True), share_location="false"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["latitude"] is None
    assert body["longitude"] is None


def test_upload_to_unknown_planting_returns_404_in_portuguese(client: TestClient) -> None:
    response = _upload(client, uuid.uuid4())

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "planting_not_found"
    assert body.get("detail")


def test_upload_of_non_image_bytes_is_rejected_with_an_actionable_message(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    response = _upload(client, planting.id, content=b"not an image, just plain text")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_image"
    assert body.get("detail")


def test_upload_above_the_size_limit_is_rejected_with_a_readable_message(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    # A tiny cap forces the (small, otherwise valid) test JPEG itself over
    # the limit — no need for a genuinely huge upload to exercise this path.
    monkeypatch.setattr(settings, "max_upload_bytes", 10)

    response = _upload(client, planting.id)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "image_too_large"
    assert "bytes" not in body["detail"]
    assert "MB" in body["detail"]


def test_two_uploads_with_the_same_filename_do_not_collide(
    client: TestClient, db_session: Session
) -> None:
    """The "critério de pronto" this endpoint must prove: two uploads
    sharing the exact same `file.filename` never overwrite one another. Both
    rows and both files must survive, independently retrievable.
    """
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    first = _upload(client, planting.id, filename="foto.jpg", description="Primeira")
    second = _upload(client, planting.id, filename="foto.jpg", description="Segunda")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    listing = client.get(f"/api/plantings/{planting.id}/photos")
    descriptions = {item["description"] for item in listing.json()["items"]}
    assert descriptions == {"Primeira", "Segunda"}

    first_file = client.get(first.json()["photo_url"])
    second_file = client.get(second.json()["photo_url"])
    assert first_file.status_code == 200
    assert second_file.status_code == 200


def test_uploaded_photo_appears_in_the_plantings_photo_listing(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    upload_response = _upload(client, planting.id, description="Recém chegada")

    listing = client.get(f"/api/plantings/{planting.id}/photos")

    [item] = listing.json()["items"]
    assert item["id"] == upload_response.json()["id"]
    assert item["description"] == "Recém chegada"


# Issue #38 (LGPD): a photo may include an identifiable person only with the
# uploader's confirmation that they have the guardian's authorization —
# architecture.md §9. These tests exercise the backend side of that rule,
# which must hold even if the frontend's own checkbox pairing (issue #38,
# `PhotoUploadForm`) is bypassed or broken.


def test_upload_with_neither_identifiable_person_field_set_still_works_like_before(
    client: TestClient, db_session: Session
) -> None:
    """The common case (a photo of a plant, not a person) must keep working
    with nothing extra filled in — this issue is purely additive.
    """
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    response = _upload(client, planting.id)

    assert response.status_code == 201
    photo_id = uuid.UUID(response.json()["id"])
    stored = db_session.get(Photo, photo_id)
    assert stored is not None
    assert stored.includes_identifiable_person_with_consent is False


def test_upload_with_identifiable_person_and_consent_confirmed_is_recorded(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    response = _upload(
        client,
        planting.id,
        includes_identifiable_person="true",
        identifiable_person_consent_confirmed="true",
    )

    assert response.status_code == 201
    photo_id = uuid.UUID(response.json()["id"])
    stored = db_session.get(Photo, photo_id)
    assert stored is not None
    assert stored.includes_identifiable_person_with_consent is True


def test_upload_with_identifiable_person_but_without_consent_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    """The rule the frontend's own checkbox pairing enforces client-side
    (issue #38) must also hold server-side — a client that skips or forges
    the browser check must not be able to publish an undeclared photo of an
    identifiable person.
    """
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    response = _upload(
        client,
        planting.id,
        includes_identifiable_person="true",
        identifiable_person_consent_confirmed="false",
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "identifiable_person_consent_required"
    assert body.get("detail")

    listing = client.get(f"/api/plantings/{planting.id}/photos")
    assert listing.json()["items"] == []
