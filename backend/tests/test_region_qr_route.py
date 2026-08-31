"""Tests for `GET /api/regions/{region}/qr-code` (issue #30). See
docs/architecture.md §7.

Real QR decoding (not byte inspection) proves the "content is exactly the
token URL" criterion — see `tests/test_qr_service.py`'s module docstring for
why `zxing-cpp`/`cairosvg` were chosen over `pyzbar` (unavailable: no system
`libzbar` in this environment).
"""

import io
import uuid

import cairosvg
import zxingcpp
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.qr_code import QrCode
from app.models.region import Region
from app.services.qr_service import MAX_BOX_SIZE


def _add_region(db_session: Session, *, token: str | None = None, **overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": "canteiro-qr",
        "name": "Canteiro QR",
        "geom": WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=token or f"token-{uuid.uuid4().hex[:8]}"))
    return region


def _expected_url(qr_token: str) -> str:
    return f"{str(settings.public_web_base_url).rstrip('/')}/r/{qr_token}"


def _decode_png(png_bytes: bytes) -> str:
    [result] = zxingcpp.read_barcodes(Image.open(io.BytesIO(png_bytes)))
    return result.text


def _decode_svg(svg_bytes: bytes) -> str:
    # See tests/test_qr_service.py::_decode_svg for why the transparent
    # background needs flattening onto white before decoding.
    rgba_image = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg_bytes))).convert("RGBA")
    white_background = Image.new("RGBA", rgba_image.size, "white")
    flattened = Image.alpha_composite(white_background, rgba_image).convert("RGB")

    buffer = io.BytesIO()
    flattened.save(buffer, format="PNG")
    return _decode_png(buffer.getvalue())


def test_get_qr_code_defaults_to_png(client: TestClient, db_session: Session) -> None:
    _add_region(db_session, token="token-qr-abc")
    db_session.commit()

    response = client.get("/api/regions/canteiro-qr/qr-code")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert _decode_png(response.content) == _expected_url("token-qr-abc")


def test_get_qr_code_svg_format(client: TestClient, db_session: Session) -> None:
    _add_region(db_session, token="token-qr-abc")
    db_session.commit()

    response = client.get("/api/regions/canteiro-qr/qr-code?format=svg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert _decode_svg(response.content) == _expected_url("token-qr-abc")


def test_get_qr_code_resolves_by_uuid(client: TestClient, db_session: Session) -> None:
    region = _add_region(db_session, token="token-qr-abc")
    db_session.commit()

    response = client.get(f"/api/regions/{region.id}/qr-code")

    assert response.status_code == 200
    assert _decode_png(response.content) == _expected_url("token-qr-abc")


def test_get_qr_code_respects_size_param(client: TestClient, db_session: Session) -> None:
    _add_region(db_session, token="token-qr-abc")
    db_session.commit()

    small = client.get("/api/regions/canteiro-qr/qr-code?size=4")
    large = client.get("/api/regions/canteiro-qr/qr-code?size=20")

    small_image = Image.open(io.BytesIO(small.content))
    large_image = Image.open(io.BytesIO(large.content))
    assert large_image.width > small_image.width


def test_get_qr_code_rejects_invalid_format(client: TestClient, db_session: Session) -> None:
    _add_region(db_session, token="token-qr-abc")
    db_session.commit()

    response = client.get("/api/regions/canteiro-qr/qr-code?format=jpeg")

    assert response.status_code == 422


def test_get_qr_code_rejects_non_positive_size(client: TestClient, db_session: Session) -> None:
    _add_region(db_session, token="token-qr-abc")
    db_session.commit()

    response = client.get("/api/regions/canteiro-qr/qr-code?size=0")

    assert response.status_code == 422


def test_get_qr_code_rejects_size_above_the_cap(client: TestClient, db_session: Session) -> None:
    """Regression test for the unbounded-`?size=` DoS found in code review:
    `box_size` scales the rendered pixel buffer large enough to OOM a
    worker from a single unauthenticated request — see
    `qr_service.MAX_BOX_SIZE`'s comment for the measurements behind the cap
    `Query(le=...)` enforces here.
    """
    _add_region(db_session, token="token-qr-abc")
    db_session.commit()

    response = client.get(f"/api/regions/canteiro-qr/qr-code?size={MAX_BOX_SIZE + 1}")

    assert response.status_code == 422


def test_get_qr_code_returns_404_for_unknown_region(client: TestClient) -> None:
    response = client.get("/api/regions/nao-existe/qr-code")

    assert response.status_code == 404
    assert response.json()["code"] == "region_not_found"


def test_get_qr_code_returns_404_for_draft_region(client: TestClient, db_session: Session) -> None:
    """Decision (issue #30): a `draft`/`archived` region's QR code is not
    generable through this public, unauthenticated endpoint — same
    visibility rule as `GET /api/regions/{region}` (`region_service.
    _PUBLICLY_VISIBLE`). The QR image encodes a working `/r/{qr_token}`
    link (future issue) regardless of `status`, so exempting this route
    from that rule would let anyone who knows/guesses a draft/archived
    region's slug mint a live, shareable link to a region the `status`
    column exists specifically to keep out of public view
    (docs/architecture.md §4.5). An organizer wanting to preview a draft
    region's QR before publishing is a real but separate need, left for a
    future admin-authenticated variant if one turns out to be needed.
    """
    _add_region(db_session, slug="canteiro-draft", status="draft", token="token-draft")
    db_session.commit()

    response = client.get("/api/regions/canteiro-draft/qr-code")

    assert response.status_code == 404
    assert response.json()["code"] == "region_not_found"


def test_get_qr_code_returns_404_for_archived_region(
    client: TestClient, db_session: Session
) -> None:
    _add_region(db_session, slug="canteiro-archived", status="archived", token="token-archived")
    db_session.commit()

    response = client.get("/api/regions/canteiro-archived/qr-code")

    assert response.status_code == 404
