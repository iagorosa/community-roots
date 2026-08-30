"""Tests for `GET /api/photos/{photo_id}/file` (issue #22). See
docs/architecture.md §5.2 for why every photo is served through this route
rather than a direct storage path.
"""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.photo import Photo
from app.models.region import Region
from app.storage.dependency import get_storage_backend
from app.storage.local import LocalFilesystemStorage

_POLYGON_WKT = (
    "POLYGON((-43.3130 -21.8845, -43.3125 -21.8845, "
    "-43.3125 -21.8840, -43.3130 -21.8840, -43.3130 -21.8845))"
)

# A distinctive key, deliberately shaped like something that would be
# embarrassing to leak, so the "never exposes storage_key" tests below have
# something specific to assert the *absence* of.
_SECRET_STORAGE_KEY = "photos/2026/do-not-leak-this-key.png"
_FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-png-but-good-enough-for-streaming" * 4


def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": "canteiro-a",
        "name": "Canteiro A",
        "geom": WKTElement(_POLYGON_WKT, srid=4326),
        "qr_token": "token-a",
    }
    defaults.update(overrides)
    return Region(**defaults)


def _make_photo(region_id: object, **overrides: object) -> Photo:
    defaults: dict[str, object] = {
        "region_id": region_id,
        "storage_key": _SECRET_STORAGE_KEY,
        "content_type": "image/png",
        "byte_size": len(_FAKE_PNG_BYTES),
        "width": 10,
        "height": 10,
    }
    defaults.update(overrides)
    return Photo(**defaults)


@pytest.fixture()
def storage_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def client(app: FastAPI, storage_root: Path) -> Generator[TestClient, None, None]:
    """Overrides `client` from `conftest.py` to also swap in a
    `LocalFilesystemStorage` rooted at `tmp_path` — the file-serving route
    needs a storage backend, unlike the routes the base `client` fixture was
    written for.
    """
    app.dependency_overrides[get_storage_backend] = lambda: LocalFilesystemStorage(storage_root)
    with TestClient(app) as test_client:
        yield test_client
    del app.dependency_overrides[get_storage_backend]


def _write_photo_file(storage_root: Path, key: str, data: bytes = _FAKE_PNG_BYTES) -> None:
    path = storage_root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_serves_the_file_with_the_stored_content_type_and_an_immutable_cache_control(
    client: TestClient, db_session: Session, storage_root: Path
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    photo = _make_photo(region.id)
    db_session.add(photo)
    db_session.commit()
    _write_photo_file(storage_root, photo.storage_key)

    response = client.get(f"/api/photos/{photo.id}/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.content == _FAKE_PNG_BYTES


def test_returns_404_for_an_unknown_photo_id(client: TestClient) -> None:
    response = client.get(f"/api/photos/{uuid.uuid4()}/file")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "photo_not_found"
    assert "detail" in body


def test_returns_404_for_a_hidden_photo(
    client: TestClient, db_session: Session, storage_root: Path
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    photo = _make_photo(region.id, status="hidden")
    db_session.add(photo)
    db_session.commit()
    _write_photo_file(storage_root, photo.storage_key)

    response = client.get(f"/api/photos/{photo.id}/file")

    assert response.status_code == 404
    assert response.json()["code"] == "photo_not_found"


def test_returns_404_when_the_row_exists_but_the_file_is_missing_from_storage(
    client: TestClient, db_session: Session
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    photo = _make_photo(region.id)
    db_session.add(photo)
    db_session.commit()
    # Deliberately not writing the file to `storage_root`.

    response = client.get(f"/api/photos/{photo.id}/file")

    assert response.status_code == 404
    assert response.json()["code"] == "photo_not_found"


def test_response_never_contains_the_storage_key_in_body_or_headers(
    client: TestClient, db_session: Session, storage_root: Path
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    photo = _make_photo(region.id)
    db_session.add(photo)
    db_session.commit()
    _write_photo_file(storage_root, photo.storage_key)

    ok_response = client.get(f"/api/photos/{photo.id}/file")
    not_found_response = client.get(f"/api/photos/{uuid.uuid4()}/file")

    assert _SECRET_STORAGE_KEY not in str(ok_response.headers)
    assert _SECRET_STORAGE_KEY.encode() not in ok_response.content
    assert _SECRET_STORAGE_KEY not in str(not_found_response.headers)
    assert _SECRET_STORAGE_KEY not in not_found_response.text
