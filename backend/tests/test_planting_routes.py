"""Tests for `GET /api/plantings` and `GET /api/plantings/{planting_id}`.
Mirrors `backend/tests/test_region_routes.py` shape."""

import uuid

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region

_POINT = "POINT(-43.3130 -21.8845)"


def _add_region(db_session: Session, **overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"regiao-{uuid.uuid4().hex[:8]}",
        "name": "Região de teste",
        "geom": WKTElement(_POINT, srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID, **overrides: object) -> Planting:
    defaults: dict[str, object] = {"region_id": region_id, "geom": WKTElement(_POINT, srid=4326)}
    defaults.update(overrides)
    planting = Planting(**defaults)
    db_session.add(planting)
    db_session.flush()
    db_session.add(QrCode(planting_id=planting.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return planting


def test_list_plantings_returns_200(client: TestClient, db_session: Session) -> None:
    region = _add_region(db_session)
    _add_planting(db_session, region.id)
    db_session.commit()

    response = client.get("/api/plantings")

    assert response.status_code == 200
    assert response.json()["type"] == "FeatureCollection"
    assert len(response.json()["features"]) == 1


def test_list_plantings_filters_by_region_id_query_param(
    client: TestClient, db_session: Session
) -> None:
    region_a = _add_region(db_session)
    region_b = _add_region(db_session)
    _add_planting(db_session, region_a.id)
    _add_planting(db_session, region_b.id)
    db_session.commit()

    response = client.get(f"/api/plantings?region_id={region_a.id}")

    assert response.status_code == 200
    assert len(response.json()["features"]) == 1


def test_get_planting_returns_200(client: TestClient, db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id, species="Ipê-amarelo")
    db_session.commit()

    response = client.get(f"/api/plantings/{planting.id}")

    assert response.status_code == 200
    assert response.json()["properties"]["species"] == "Ipê-amarelo"


def test_get_planting_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get(f"/api/plantings/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["code"] == "planting_not_found"


def test_get_planting_returns_422_for_a_malformed_id(client: TestClient) -> None:
    response = client.get("/api/plantings/not-a-uuid")

    assert response.status_code == 422
