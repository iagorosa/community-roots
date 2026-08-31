"""Tests for `GET /api/plantings/{planting_id}/qr-code`. Mirrors
`backend/tests/test_region_qr_route.py`."""

import io
import uuid

import zxingcpp
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region


def _add_region(db_session: Session) -> Region:
    region = Region(
        slug=f"regiao-{uuid.uuid4().hex[:8]}",
        name="Região de teste",
        geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID, token: str) -> Planting:
    planting = Planting(region_id=region_id, geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326))
    db_session.add(planting)
    db_session.flush()
    db_session.add(QrCode(planting_id=planting.id, token=token))
    return planting


def _expected_url(token: str) -> str:
    return f"{str(settings.public_web_base_url).rstrip('/')}/r/{token}"


def _decode_png(png_bytes: bytes) -> str:
    [result] = zxingcpp.read_barcodes(Image.open(io.BytesIO(png_bytes)))
    return result.text


def test_get_planting_qr_code_defaults_to_png(client: TestClient, db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id, "token-planting-abc")
    db_session.commit()

    response = client.get(f"/api/plantings/{planting.id}/qr-code")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert _decode_png(response.content) == _expected_url("token-planting-abc")


def test_get_planting_qr_code_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get(f"/api/plantings/{uuid.uuid4()}/qr-code")

    assert response.status_code == 404
    assert response.json()["code"] == "planting_not_found"
