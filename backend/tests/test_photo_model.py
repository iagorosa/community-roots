"""Tests for the `Photo` model and its migration (backend/app/models/photo.py).

See docs/architecture.md §4.3/§4.4 for the columns this model implements: a
single `geometry(Point, 4326)` `location` column (not loose `latitude`/
`longitude` floats) so "which region contains this photo?" can reuse the same
GiST index the regions already use, plus a `status` CHECK that lets an
organizer pull a photo offline with a single `UPDATE`.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.photo import Photo
from app.models.region import Region

_POLYGON_WKT = (
    "POLYGON((-43.3130 -21.8845, -43.3125 -21.8845, "
    "-43.3125 -21.8840, -43.3130 -21.8840, -43.3130 -21.8845))"
)
_POINT_WKT = "POINT(-43.3127 -21.8843)"


def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"canteiro-{uuid.uuid4().hex[:8]}",
        "name": "Canteiro de teste",
        "geom": WKTElement(_POLYGON_WKT, srid=4326),
    }
    defaults.update(overrides)
    return Region(**defaults)


def _make_photo(region_id: uuid.UUID, **overrides: object) -> Photo:
    defaults: dict[str, object] = {
        "region_id": region_id,
        "storage_key": f"photos/{uuid.uuid4().hex}.jpg",
        "content_type": "image/jpeg",
        "byte_size": 123_456,
        "width": 1080,
        "height": 1350,
    }
    defaults.update(overrides)
    return Photo(**defaults)


def test_photo_is_created_with_location_null(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    photo = _make_photo(region.id)
    db_session.add(photo)
    db_session.commit()

    stored = db_session.execute(select(Photo).where(Photo.id == photo.id)).scalar_one()
    assert stored.location is None
    assert stored.status == "published"  # server_default, not passed explicitly


def test_photo_accepts_a_valid_point_location(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    photo = _make_photo(region.id, location=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(photo)
    db_session.commit()

    stored = db_session.execute(select(Photo).where(Photo.id == photo.id)).scalar_one()
    assert stored.location is not None


def test_invalid_status_is_rejected_by_check_constraint(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    photo = _make_photo(region.id, status="deleted")
    db_session.add(photo)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()  # required after a failed flush before the session is usable again


def test_hidden_status_is_accepted_by_check_constraint(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    photo = _make_photo(region.id, status="hidden")
    db_session.add(photo)
    db_session.commit()

    stored = db_session.execute(select(Photo).where(Photo.id == photo.id)).scalar_one()
    assert stored.status == "hidden"


def test_deleting_region_cascades_to_its_photos_at_the_database_level(
    db_session: Session,
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    photo = _make_photo(region.id)
    db_session.add(photo)
    db_session.commit()
    photo_id = photo.id

    # Deleted via the Core `DELETE` the ORM issues for `db_session.delete`,
    # not via any ORM-side `cascade=` — this proves the `ON DELETE CASCADE`
    # is enforced by Postgres itself, not just by SQLAlchemy bookkeeping.
    db_session.delete(region)
    db_session.commit()

    remaining = db_session.execute(select(Photo).where(Photo.id == photo_id)).scalar_one_or_none()
    assert remaining is None
