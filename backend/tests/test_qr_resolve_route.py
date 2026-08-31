"""Tests for `GET /api/qr/{token}` — resolves a scanned QR token to the
region or planting it points at (the frontend's `/r/:qrToken` redirect
depends on this)."""

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region


def _add_region(db_session: Session, token: str) -> Region:
    region = Region(
        slug="canteiro-alvo",
        name="Canteiro Alvo",
        geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=token))
    return region


def test_resolve_region_token(client: TestClient, db_session: Session) -> None:
    _add_region(db_session, "token-region-abc")
    db_session.commit()

    response = client.get("/api/qr/token-region-abc")

    assert response.status_code == 200
    assert response.json() == {"type": "region", "identifier": "canteiro-alvo"}


def test_resolve_planting_token(client: TestClient, db_session: Session) -> None:
    region = _add_region(db_session, "token-region-owner")
    planting = Planting(region_id=region.id, geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326))
    db_session.add(planting)
    db_session.flush()
    db_session.add(QrCode(planting_id=planting.id, token="token-planting-xyz"))
    db_session.commit()

    response = client.get("/api/qr/token-planting-xyz")

    assert response.status_code == 200
    assert response.json() == {"type": "planting", "identifier": str(planting.id)}


def test_resolve_unknown_token_returns_404(client: TestClient) -> None:
    response = client.get("/api/qr/does-not-exist")

    assert response.status_code == 404
    assert response.json()["code"] == "qr_token_not_found"
