"""Tests for `GET /api/regions/{region}/photos` (issue #21)."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.photo import Photo
from app.models.region import Region

_POLYGON_WKT = (
    "POLYGON((-43.3130 -21.8845, -43.3125 -21.8845, "
    "-43.3125 -21.8840, -43.3130 -21.8840, -43.3130 -21.8845))"
)


def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": "canteiro-a",
        "name": "Canteiro A",
        "geom": WKTElement(_POLYGON_WKT, srid=4326),
        "qr_token": "token-a",
    }
    defaults.update(overrides)
    return Region(**defaults)


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 1, hour, minute, tzinfo=UTC)


def _make_photo(region_id: object, **overrides: object) -> Photo:
    defaults: dict[str, object] = {
        "region_id": region_id,
        "storage_key": "photos/whatever.jpg",
        "content_type": "image/jpeg",
        "byte_size": 123_456,
        "width": 1080,
        "height": 1350,
        "uploaded_at": _dt(10),
    }
    defaults.update(overrides)
    return Photo(**defaults)


def test_list_photos_returns_published_photos_most_recent_first(
    client: TestClient, db_session: Session
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    older = _make_photo(region.id, uploaded_at=_dt(9), description="Foto antiga")
    newer = _make_photo(region.id, uploaded_at=_dt(11), description="Foto nova")
    db_session.add_all([older, newer])
    db_session.commit()

    response = client.get("/api/regions/canteiro-a/photos")

    assert response.status_code == 200
    body = response.json()
    assert [item["description"] for item in body["items"]] == ["Foto nova", "Foto antiga"]
    assert body["next_cursor"] is None


def test_list_photos_hides_photos_marked_hidden(client: TestClient, db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    published = _make_photo(region.id, status="published", description="Visível")
    hidden = _make_photo(region.id, status="hidden", uploaded_at=_dt(12), description="Oculta")
    db_session.add_all([published, hidden])
    db_session.commit()

    response = client.get("/api/regions/canteiro-a/photos")

    body = response.json()
    descriptions = [item["description"] for item in body["items"]]
    assert descriptions == ["Visível"]
    assert "Oculta" not in descriptions


def test_list_photos_exposes_latitude_longitude_and_photo_url_not_storage_key(
    client: TestClient, db_session: Session
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    photo = _make_photo(region.id, location=WKTElement("POINT(-43.3127 -21.8843)", srid=4326))
    db_session.add(photo)
    db_session.commit()

    response = client.get("/api/regions/canteiro-a/photos")

    [item] = response.json()["items"]
    assert item["latitude"] == pytest.approx(-21.8843)
    assert item["longitude"] == pytest.approx(-43.3127)
    assert item["photo_url"] == f"/api/photos/{photo.id}/file"
    assert "storage_key" not in item
    assert "location" not in item


def test_list_photos_returns_404_for_unknown_region(client: TestClient) -> None:
    response = client.get("/api/regions/nao-existe/photos")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "region_not_found"
    assert "detail" in body


def test_list_photos_respects_limit_and_returns_a_usable_next_cursor(
    client: TestClient, db_session: Session
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    photos = [_make_photo(region.id, uploaded_at=_dt(10, i)) for i in range(3)]
    db_session.add_all(photos)
    db_session.commit()

    first_response = client.get("/api/regions/canteiro-a/photos", params={"limit": 2})
    first_body = first_response.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"] is not None

    second_response = client.get(
        "/api/regions/canteiro-a/photos",
        params={"limit": 2, "cursor": first_body["next_cursor"]},
    )
    second_body = second_response.json()
    assert len(second_body["items"]) == 1
    assert second_body["next_cursor"] is None

    first_ids = {item["id"] for item in first_body["items"]}
    second_ids = {item["id"] for item in second_body["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_list_photos_returns_422_for_a_malformed_cursor(
    client: TestClient, db_session: Session
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.commit()

    response = client.get("/api/regions/canteiro-a/photos", params={"cursor": "not-a-valid-cursor"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_cursor"
    assert "detail" in body


def test_list_photos_rejects_limit_out_of_bounds(client: TestClient, db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.commit()

    too_low = client.get("/api/regions/canteiro-a/photos", params={"limit": 0})
    too_high = client.get("/api/regions/canteiro-a/photos", params={"limit": 101})

    # FastAPI's own `Query(ge=1, le=100)` validation rejects these before
    # `photo_service.list_region_photos` ever runs — a 422 from request
    # validation, distinct from the `InvalidCursor` domain error above.
    assert too_low.status_code == 422
    assert too_high.status_code == 422


def test_list_photos_resolves_region_by_uuid(client: TestClient, db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    photo = _make_photo(region.id, description="Foto via uuid")
    db_session.add(photo)
    db_session.commit()

    response = client.get(f"/api/regions/{region.id}/photos")

    assert response.status_code == 200
    [item] = response.json()["items"]
    assert item["description"] == "Foto via uuid"
