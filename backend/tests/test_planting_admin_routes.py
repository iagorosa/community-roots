"""Tests for `POST /api/plantings` and `PATCH /api/plantings/{planting_id}`.
Mirrors `backend/tests/test_region_admin_routes.py`."""

import uuid

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.qr_code import QrCode
from app.models.region import Region

_VALID_HEADERS = {"X-Admin-Token": settings.admin_api_token}


def _add_region(db_session: Session) -> Region:
    region = Region(
        slug=f"regiao-{uuid.uuid4().hex[:8]}",
        name="Região de teste",
        geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    db_session.commit()
    return region


def _create_payload(region_id: uuid.UUID) -> dict[str, object]:
    return {
        "region_id": str(region_id),
        "geometry": {"type": "Point", "coordinates": [-43.3130, -21.8845]},
        "species": "Ipê-amarelo",
        "nickname": "A árvore da Ana",
    }


def test_create_planting_without_header_returns_401(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)

    response = client.post("/api/plantings", json=_create_payload(region.id))

    assert response.status_code == 401


def test_create_planting_with_valid_header_returns_201(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)

    response = client.post(
        "/api/plantings", json=_create_payload(region.id), headers=_VALID_HEADERS
    )

    assert response.status_code == 201
    body = response.json()
    assert body["properties"]["species"] == "Ipê-amarelo"
    assert body["properties"]["qr_token"]


def test_update_planting_without_header_returns_401(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)
    created = client.post(
        "/api/plantings", json=_create_payload(region.id), headers=_VALID_HEADERS
    ).json()

    response = client.patch(f"/api/plantings/{created['id']}", json={"nickname": "Novo apelido"})

    assert response.status_code == 401


def test_update_planting_with_valid_header_returns_200(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)
    created = client.post(
        "/api/plantings", json=_create_payload(region.id), headers=_VALID_HEADERS
    ).json()

    response = client.patch(
        f"/api/plantings/{created['id']}",
        json={"nickname": "Novo apelido"},
        headers=_VALID_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["properties"]["nickname"] == "Novo apelido"


def test_create_planting_with_unknown_region_id_returns_404(
    client: TestClient, db_session: Session
) -> None:
    response = client.post(
        "/api/plantings", json=_create_payload(uuid.uuid4()), headers=_VALID_HEADERS
    )

    assert response.status_code == 404
    assert response.json()["code"] == "region_not_found"


def test_update_planting_rejects_an_explicit_null_status(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)
    created = client.post(
        "/api/plantings", json=_create_payload(region.id), headers=_VALID_HEADERS
    ).json()

    response = client.patch(
        f"/api/plantings/{created['id']}", json={"status": None}, headers=_VALID_HEADERS
    )

    assert response.status_code == 422
