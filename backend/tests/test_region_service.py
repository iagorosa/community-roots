"""Tests for `app/services/region_service.py`: listing and single-region
resolution by slug or UUID. See docs/architecture.md §5.1 and issue #11.
"""

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.region import Region
from app.services import region_service
from app.services.region_service import RegionNotFound

_POINT_A = "POINT(-43.3130 -21.8845)"
_POINT_B = "POINT(-43.3200 -21.8900)"


def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": "canteiro-a",
        "name": "Canteiro A",
        "geom": WKTElement(_POINT_A, srid=4326),
        "qr_token": "token-a",
    }
    defaults.update(overrides)
    return Region(**defaults)


def test_list_regions_returns_a_valid_feature_collection(db_session: Session) -> None:
    db_session.add(_make_region())
    db_session.add(
        _make_region(
            slug="canteiro-b",
            name="Canteiro B",
            geom=WKTElement(_POINT_B, srid=4326),
            qr_token="token-b",
        )
    )
    db_session.commit()

    collection = region_service.list_regions(db_session)

    assert collection.type == "FeatureCollection"
    names = [feature.properties.name for feature in collection.features]
    assert names == ["Canteiro A", "Canteiro B"]  # ordered by name


def test_list_regions_serializes_geometry_and_default_photo_fields(db_session: Session) -> None:
    db_session.add(_make_region())
    db_session.commit()

    [feature] = region_service.list_regions(db_session).features

    assert feature.geometry.type == "Point"
    assert feature.geometry.coordinates == pytest.approx((-43.3130, -21.8845))
    # `photos` doesn't exist until issue #20 (milestone "Fase 4") — literal
    # placeholders until then, see region_service.py.
    assert feature.properties.photo_count == 0
    assert feature.properties.latest_photo_at is None


def test_list_regions_runs_a_single_query(db_session: Session) -> None:
    db_session.add(_make_region())
    db_session.add(
        _make_region(
            slug="canteiro-b",
            name="Canteiro B",
            geom=WKTElement(_POINT_B, srid=4326),
            qr_token="token-b",
        )
    )
    db_session.commit()

    executed_statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        executed_statements.append(statement)

    connection = db_session.get_bind()
    event.listen(connection, "before_cursor_execute", _capture)
    try:
        region_service.list_regions(db_session)
    finally:
        event.remove(connection, "before_cursor_execute", _capture)

    # Ignore `SAVEPOINT`/`RELEASE` bookkeeping from the test fixture's own
    # transaction isolation (tests/conftest.py) — what matters here is that
    # listing regions issues exactly one data-fetching query, no N+1.
    select_statements = [s for s in executed_statements if s.strip().upper().startswith("SELECT")]
    assert len(select_statements) == 1


def test_list_regions_excludes_draft_and_archived_regions(db_session: Session) -> None:
    # architecture.md §4.5: `status` exists so an organizer can pull a region
    # from public view immediately — the public listing has to honor it.
    db_session.add(_make_region())
    db_session.add(
        _make_region(
            slug="canteiro-draft",
            name="Canteiro Rascunho",
            geom=WKTElement(_POINT_B, srid=4326),
            qr_token="token-draft",
            status="draft",
        )
    )
    db_session.add(
        _make_region(
            slug="canteiro-archived",
            name="Canteiro Arquivado",
            geom=WKTElement(_POINT_B, srid=4326),
            qr_token="token-archived",
            status="archived",
        )
    )
    db_session.commit()

    collection = region_service.list_regions(db_session)

    slugs = [feature.properties.slug for feature in collection.features]
    assert slugs == ["canteiro-a"]


def test_get_region_resolves_by_slug(db_session: Session) -> None:
    db_session.add(_make_region())
    db_session.commit()

    feature = region_service.get_region(db_session, "canteiro-a")

    assert feature.properties.slug == "canteiro-a"


def test_get_region_resolves_by_uuid(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.commit()

    feature = region_service.get_region(db_session, str(region.id))

    assert feature.properties.slug == "canteiro-a"


def test_get_region_raises_not_found_for_unknown_slug(db_session: Session) -> None:
    with pytest.raises(RegionNotFound):
        region_service.get_region(db_session, "nao-existe")


def test_get_region_raises_not_found_for_unknown_uuid(db_session: Session) -> None:
    with pytest.raises(RegionNotFound):
        region_service.get_region(db_session, "00000000-0000-0000-0000-000000000000")


def test_get_region_raises_not_found_for_an_archived_region(db_session: Session) -> None:
    db_session.add(_make_region(status="archived"))
    db_session.commit()

    with pytest.raises(RegionNotFound):
        region_service.get_region(db_session, "canteiro-a")
