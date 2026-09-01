"""Tests for `POST /api/regions/import` (issue #33).

architecture.md §12: the geographer's `FeatureCollection` matches existing
regions by `slug` and updates only `geom`, keeping `qr_token` valid. A slug
absent from the database is created when the feature carries a `name`, and
ignored otherwise (docs/implementation-plan.md, Fase 6). See
`test_region_admin_routes.py` for the header/auth conventions this mirrors.
"""

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.qr_code import QrCode
from app.models.region import Region

_VALID_HEADERS = {"X-Admin-Token": settings.admin_api_token}


def _seed_region(db_session: Session, *, slug: str = "canteiro-existente") -> Region:
    region = Region(
        slug=slug,
        name="Canteiro Existente",
        geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token="token-original"))
    db_session.commit()
    return region


def _import_payload(*features: dict) -> dict:
    return {"type": "FeatureCollection", "features": list(features)}


def _feature(
    slug: str,
    geometry: dict,
    *,
    name: str | None = None,
    description: str | None = None,
) -> dict:
    properties: dict = {"slug": slug}
    if name is not None:
        properties["name"] = name
    if description is not None:
        properties["description"] = description
    return {"type": "Feature", "geometry": geometry, "properties": properties}


_NEW_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [-43.3135, -21.8850],
            [-43.3125, -21.8850],
            [-43.3125, -21.8840],
            [-43.3135, -21.8840],
            [-43.3135, -21.8850],
        ]
    ],
}


def test_import_without_header_returns_401(client: TestClient) -> None:
    response = client.post("/api/regions/import", json=_import_payload())

    assert response.status_code == 401


def test_import_with_wrong_header_returns_401(client: TestClient) -> None:
    response = client.post(
        "/api/regions/import",
        json=_import_payload(),
        headers={"X-Admin-Token": "not-the-token"},
    )

    assert response.status_code == 401


def test_import_updates_geometry_of_existing_region_by_slug(
    client: TestClient, db_session: Session
) -> None:
    region = _seed_region(db_session)
    payload = _import_payload(_feature(region.slug, _NEW_POLYGON))

    response = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 200
    updated = client.get(f"/api/regions/{region.slug}").json()
    assert updated["geometry"]["type"] == "Polygon"


def test_import_preserves_qr_token_of_updated_region(
    client: TestClient, db_session: Session
) -> None:
    region = _seed_region(db_session)
    before = client.get(f"/api/regions/{region.slug}").json()["properties"]["qr_token"]
    payload = _import_payload(_feature(region.slug, _NEW_POLYGON))

    response = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 200
    after_body = client.get(f"/api/regions/{region.slug}").json()
    assert after_body["geometry"]["type"] == "Polygon"  # confirms the import actually ran
    assert after_body["properties"]["qr_token"] == before == "token-original"


def test_import_creates_a_new_region_when_slug_is_unknown_and_name_given(
    client: TestClient,
) -> None:
    payload = _import_payload(
        _feature(
            "canteiro-novo", _NEW_POLYGON, name="Canteiro Novo", description="Achado em campo."
        )
    )

    response = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 200
    created = client.get("/api/regions/canteiro-novo")
    assert created.status_code == 200
    assert created.json()["properties"]["name"] == "Canteiro Novo"
    assert created.json()["properties"]["qr_token"]


def test_import_ignores_feature_with_unknown_slug_and_no_name(client: TestClient) -> None:
    payload = _import_payload(_feature("canteiro-fantasma", _NEW_POLYGON))

    response = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"created": 0, "updated": 0, "ignored": 1}
    assert client.get("/api/regions/canteiro-fantasma").status_code == 404


def test_import_returns_summary_counts_for_a_mixed_batch(
    client: TestClient, db_session: Session
) -> None:
    region = _seed_region(db_session)
    payload = _import_payload(
        _feature(region.slug, _NEW_POLYGON),
        _feature("canteiro-novo", _NEW_POLYGON, name="Canteiro Novo"),
        _feature("canteiro-fantasma", _NEW_POLYGON),
    )

    response = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"created": 1, "updated": 1, "ignored": 1}


def test_import_same_file_twice_does_not_duplicate_regions(
    client: TestClient, db_session: Session
) -> None:
    region = _seed_region(db_session)
    payload = _import_payload(
        _feature(region.slug, _NEW_POLYGON),
        _feature("canteiro-novo", _NEW_POLYGON, name="Canteiro Novo"),
    )

    first = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)
    second = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert first.json() == {"created": 1, "updated": 1, "ignored": 0}
    assert second.json() == {"created": 0, "updated": 2, "ignored": 0}
    region_count = db_session.execute(select(Region).where(Region.slug == "canteiro-novo")).all()
    assert len(region_count) == 1


def test_import_rejects_a_linestring_geometry(client: TestClient) -> None:
    payload = _import_payload(
        _feature(
            "canteiro-novo",
            {"type": "LineString", "coordinates": [[-43.31, -21.88], [-43.30, -21.87]]},
            name="Canteiro Novo",
        )
    )

    response = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 422


def test_import_rejects_a_malformed_slug_on_a_new_region(client: TestClient) -> None:
    # Every server-generated slug (`region_service.slugify`) is lowercase
    # ASCII with single hyphen separators — a hand-edited import file that
    # drifts from that shape (spaces, uppercase, accents) must be rejected
    # up front rather than silently stored as an unusable URL segment.
    payload = _import_payload(_feature("Canteiro Novo!", _NEW_POLYGON, name="Canteiro Novo"))

    response = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 422


def test_import_rejects_an_empty_slug(client: TestClient) -> None:
    payload = _import_payload(_feature("", _NEW_POLYGON, name="Canteiro Novo"))

    response = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 422


def test_import_updates_an_archived_region_matched_by_slug(
    client: TestClient, db_session: Session
) -> None:
    # `region_service.update_region` deliberately resolves draft/archived
    # regions too (an admin editing a hidden region) — import's slug match
    # follows the same rule: `status` never gates a write path, only reads.
    region = _seed_region(db_session)
    region.status = "archived"
    db_session.commit()
    payload = _import_payload(_feature(region.slug, _NEW_POLYGON))

    response = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"created": 0, "updated": 1, "ignored": 0}


def test_import_treats_a_repeated_slug_within_one_payload_as_a_second_update(
    client: TestClient,
) -> None:
    # Two features sharing a not-yet-existing slug in the same payload: the
    # first creates the region, and since that create is flushed (not just
    # added) before the second feature is matched, the second sees it as an
    # existing region and updates it — no `IntegrityError` on the unique
    # `slug` constraint, no duplicate row.
    payload = _import_payload(
        _feature("canteiro-novo", _NEW_POLYGON, name="Canteiro Novo"),
        _feature("canteiro-novo", _NEW_POLYGON, name="Canteiro Novo"),
    )

    response = client.post("/api/regions/import", json=payload, headers=_VALID_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"created": 1, "updated": 1, "ignored": 0}


def test_import_with_no_features_returns_zeroed_summary(client: TestClient) -> None:
    response = client.post("/api/regions/import", json=_import_payload(), headers=_VALID_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"created": 0, "updated": 0, "ignored": 0}
