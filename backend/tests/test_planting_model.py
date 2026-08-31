"""Tests for the `Planting` model and its migration (backend/app/models/planting.py).

`Planting` mirrors `Region`'s geometry design (a permissive
`geometry(Geometry, 4326)` column narrowed by a CHECK constraint, plus a
generated `centroid`) — see
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.region import Region

_POINT_WKT = "POINT(-43.3130 -21.8845)"


def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"regiao-{uuid.uuid4().hex[:8]}",
        "name": "Região de teste",
        "geom": WKTElement(_POINT_WKT, srid=4326),
        # `Region.qr_token` is still a required, unique column pre-Task-2
        # (it only moves to the standalone `QrCode` entity there), so this
        # helper — unlike the plan's Task 1 listing — must supply one.
        "qr_token": f"token-{uuid.uuid4().hex[:8]}",
    }
    defaults.update(overrides)
    return Region(**defaults)


def _make_planting(region_id: uuid.UUID, **overrides: object) -> Planting:
    defaults: dict[str, object] = {
        "region_id": region_id,
        "geom": WKTElement(_POINT_WKT, srid=4326),
    }
    defaults.update(overrides)
    return Planting(**defaults)


def test_centroid_is_computed_automatically_on_insert(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    planting = _make_planting(region.id)
    db_session.add(planting)
    db_session.commit()

    centroid_matches_postgis_computation = db_session.execute(
        select(func.ST_Equals(Planting.centroid, func.ST_Centroid(Planting.geom))).where(
            Planting.id == planting.id
        )
    ).scalar_one()

    assert centroid_matches_postgis_computation is True


def test_linestring_geometry_is_rejected_by_check_constraint(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    planting = _make_planting(
        region.id, geom=WKTElement("LINESTRING(-43.313 -21.884, -43.312 -21.883)", srid=4326)
    )
    db_session.add(planting)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()  # required after a failed flush before the session is usable again


def test_invalid_status_is_rejected_by_check_constraint(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    planting = _make_planting(region.id, status="deleted")
    db_session.add(planting)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_optional_fields_default_to_none(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    planting = _make_planting(region.id)
    db_session.add(planting)
    db_session.commit()

    stored = db_session.execute(select(Planting).where(Planting.id == planting.id)).scalar_one()
    assert stored.species is None
    assert stored.nickname is None
    assert stored.planted_by is None
    assert stored.planted_at is None
    assert stored.status == "active"  # server_default, not passed explicitly


def test_deleting_region_cascades_to_its_plantings_at_the_database_level(
    db_session: Session,
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    planting = _make_planting(region.id)
    db_session.add(planting)
    db_session.commit()
    planting_id = planting.id

    # Deleted via the Core `DELETE` the ORM issues for `db_session.delete`, not
    # via any ORM-side `cascade=` — proves `ON DELETE CASCADE` is enforced by
    # Postgres itself.
    db_session.delete(region)
    db_session.commit()

    remaining = db_session.execute(
        select(Planting).where(Planting.id == planting_id)
    ).scalar_one_or_none()
    assert remaining is None
