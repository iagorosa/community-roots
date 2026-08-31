"""Tests for `POST /api/regions` and `PATCH /api/regions/{region}` (issue #12).

architecture.md §9: write routes require a valid `X-Admin-Token` header.
"""

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.qr_code import QrCode
from app.models.region import Region

_VALID_HEADERS = {"X-Admin-Token": settings.admin_api_token}

_CREATE_PAYLOAD = {
    "name": "Canteiro do Ipê",
    "description": "Perto da entrada principal.",
    "geometry": {"type": "Point", "coordinates": [-43.3130, -21.8845]},
}


def test_create_region_without_header_returns_401(client: TestClient) -> None:
    response = client.post("/api/regions", json=_CREATE_PAYLOAD)

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_create_region_with_wrong_header_returns_401(client: TestClient) -> None:
    response = client.post(
        "/api/regions", json=_CREATE_PAYLOAD, headers={"X-Admin-Token": "not-the-token"}
    )

    assert response.status_code == 401


def test_create_region_with_valid_header_returns_201(client: TestClient) -> None:
    response = client.post("/api/regions", json=_CREATE_PAYLOAD, headers=_VALID_HEADERS)

    assert response.status_code == 201
    body = response.json()
    assert body["properties"]["name"] == "Canteiro do Ipê"
    assert body["properties"]["slug"] == "canteiro-do-ipe"
    assert body["properties"]["qr_token"]
    assert body["properties"]["status"] == "active"
    assert body["geometry"] == {"type": "Point", "coordinates": [-43.3130, -21.8845]}


def test_create_region_generates_a_distinct_slug_on_name_collision(client: TestClient) -> None:
    client.post("/api/regions", json=_CREATE_PAYLOAD, headers=_VALID_HEADERS)

    response = client.post("/api/regions", json=_CREATE_PAYLOAD, headers=_VALID_HEADERS)

    assert response.status_code == 201
    assert response.json()["properties"]["slug"] == "canteiro-do-ipe-2"


def test_create_region_rejects_a_linestring_geometry(client: TestClient) -> None:
    payload = {
        **_CREATE_PAYLOAD,
        "geometry": {"type": "LineString", "coordinates": [[-43.31, -21.88], [-43.30, -21.87]]},
    }

    response = client.post("/api/regions", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 422


def test_update_region_without_header_returns_401(client: TestClient, db_session: Session) -> None:
    region = _seed_region(db_session)

    response = client.patch(f"/api/regions/{region.slug}", json={"name": "Novo nome"})

    assert response.status_code == 401


def test_update_region_with_valid_header_returns_200(
    client: TestClient, db_session: Session
) -> None:
    region = _seed_region(db_session)

    response = client.patch(
        f"/api/regions/{region.slug}",
        json={"description": "Descrição nova"},
        headers=_VALID_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["properties"]["description"] == "Descrição nova"
    assert body["properties"]["slug"] == region.slug  # unchanged: name wasn't updated


def test_update_region_renaming_regenerates_the_slug(
    client: TestClient, db_session: Session
) -> None:
    region = _seed_region(db_session)

    response = client.patch(
        f"/api/regions/{region.slug}", json={"name": "Canteiro Renomeado"}, headers=_VALID_HEADERS
    )

    assert response.status_code == 200
    assert response.json()["properties"]["slug"] == "canteiro-renomeado"


def test_update_region_can_archive_a_region(client: TestClient, db_session: Session) -> None:
    region = _seed_region(db_session)

    response = client.patch(
        f"/api/regions/{region.slug}", json={"status": "archived"}, headers=_VALID_HEADERS
    )

    assert response.status_code == 200
    assert response.json()["properties"]["status"] == "archived"
    # architecture.md §4.5: the admin who just archived it must still see it
    # in the response, even though it's now excluded from public reads.
    assert client.get(f"/api/regions/{region.slug}").status_code == 404


def test_update_region_rejects_an_explicit_null_name(
    client: TestClient, db_session: Session
) -> None:
    region = _seed_region(db_session)

    response = client.patch(
        f"/api/regions/{region.slug}", json={"name": None}, headers=_VALID_HEADERS
    )

    assert response.status_code == 422


def test_update_region_rejects_an_explicit_null_status(
    client: TestClient, db_session: Session
) -> None:
    region = _seed_region(db_session)

    response = client.patch(
        f"/api/regions/{region.slug}", json={"status": None}, headers=_VALID_HEADERS
    )

    assert response.status_code == 422


def _seed_region(db_session: Session) -> Region:
    region = Region(
        slug="canteiro-existente",
        name="Canteiro Existente",
        geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token="existing-token"))
    db_session.commit()
    return region
