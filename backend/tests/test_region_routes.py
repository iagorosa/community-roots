"""Tests for `GET /api/regions` and `GET /api/regions/{region}` (issue #11)."""

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.qr_code import QrCode
from app.models.region import Region


def _add_region(db_session: Session, **overrides: object) -> Region:
    """Insert a `Region` plus the `QrCode` row every real region gets at
    creation time (`region_service.create_region`) — the listing/read
    queries INNER JOIN on it, so a region without one wouldn't be a
    realistic fixture.
    """
    defaults: dict[str, object] = {
        "slug": "canteiro-a",
        "name": "Canteiro A",
        "geom": WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token="token-a"))
    return region


def test_list_regions_returns_a_feature_collection(client: TestClient, db_session: Session) -> None:
    _add_region(db_session)
    db_session.commit()

    response = client.get("/api/regions")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    [feature] = body["features"]
    assert feature["type"] == "Feature"
    assert feature["properties"]["slug"] == "canteiro-a"
    assert feature["geometry"]["type"] == "Point"


def test_get_region_by_slug_returns_a_feature(client: TestClient, db_session: Session) -> None:
    _add_region(db_session)
    db_session.commit()

    response = client.get("/api/regions/canteiro-a")

    assert response.status_code == 200
    assert response.json()["properties"]["slug"] == "canteiro-a"


def test_get_region_by_uuid_returns_a_feature(client: TestClient, db_session: Session) -> None:
    region = _add_region(db_session)
    db_session.commit()

    response = client.get(f"/api/regions/{region.id}")

    assert response.status_code == 200
    assert response.json()["properties"]["slug"] == "canteiro-a"


def test_get_region_returns_404_for_unknown_region(client: TestClient) -> None:
    response = client.get("/api/regions/nao-existe")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "region_not_found"
    assert "detail" in body
