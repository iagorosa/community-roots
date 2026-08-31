"""Tests for the `Region` model and its migration (backend/app/models/region.py).

See docs/architecture.md §4.1/§4.2 for the geometry decision this model
implements: a permissive `geometry(Geometry, 4326)` column narrowed by a CHECK
constraint, plus a generated `centroid` column PostGIS fills in on insert.
"""

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.region import Region

_POLYGON_WKT = (
    "POLYGON((-43.3130 -21.8845, -43.3125 -21.8845, "
    "-43.3125 -21.8840, -43.3130 -21.8840, -43.3130 -21.8845))"
)


def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": "canteiro-1",
        "name": "Canteiro 1",
        "geom": WKTElement(_POLYGON_WKT, srid=4326),
    }
    defaults.update(overrides)
    return Region(**defaults)


def test_centroid_is_computed_automatically_on_insert(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.commit()

    centroid_matches_postgis_computation = db_session.execute(
        select(func.ST_Equals(Region.centroid, func.ST_Centroid(Region.geom))).where(
            Region.id == region.id
        )
    ).scalar_one()

    assert centroid_matches_postgis_computation is True


def test_linestring_geometry_is_rejected_by_check_constraint(db_session: Session) -> None:
    region = _make_region(
        geom=WKTElement("LINESTRING(-43.313 -21.884, -43.312 -21.883)", srid=4326)
    )
    db_session.add(region)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()  # required after a failed flush before the session is usable again


def test_invalid_status_is_rejected_by_check_constraint(db_session: Session) -> None:
    region = _make_region(status="deleted")
    db_session.add(region)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()  # required after a failed flush before the session is usable again
