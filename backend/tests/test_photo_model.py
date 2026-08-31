"""Tests for the `Photo` model and its migration (backend/app/models/photo.py).

`Photo.planting_id` replaces `region_id` — see
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md: fotos
belong to an individual Planting, never directly to a Region.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.photo import Photo
from app.models.planting import Planting
from app.models.region import Region

_POINT_WKT = "POINT(-43.3127 -21.8843)"


def _add_region(db_session: Session) -> Region:
    region = Region(
        slug=f"regiao-{uuid.uuid4().hex[:8]}",
        name="Região de teste",
        geom=WKTElement(_POINT_WKT, srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID) -> Planting:
    planting = Planting(region_id=region_id, geom=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(planting)
    db_session.flush()
    return planting


def _make_photo(planting_id: uuid.UUID, **overrides: object) -> Photo:
    defaults: dict[str, object] = {
        "planting_id": planting_id,
        "storage_key": f"photos/{uuid.uuid4().hex}.jpg",
        "content_type": "image/jpeg",
        "byte_size": 123_456,
        "width": 1080,
        "height": 1350,
    }
    defaults.update(overrides)
    return Photo(**defaults)


def test_photo_is_created_with_location_null(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    photo = _make_photo(planting.id)
    db_session.add(photo)
    db_session.commit()

    stored = db_session.execute(select(Photo).where(Photo.id == photo.id)).scalar_one()
    assert stored.location is None
    assert stored.status == "published"  # server_default, not passed explicitly


def test_photo_accepts_a_valid_point_location(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    photo = _make_photo(planting.id, location=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(photo)
    db_session.commit()

    stored = db_session.execute(select(Photo).where(Photo.id == photo.id)).scalar_one()
    assert stored.location is not None


def test_invalid_status_is_rejected_by_check_constraint(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    photo = _make_photo(planting.id, status="deleted")
    db_session.add(photo)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()  # required after a failed flush before the session is usable again


def test_hidden_status_is_accepted_by_check_constraint(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    photo = _make_photo(planting.id, status="hidden")
    db_session.add(photo)
    db_session.commit()

    stored = db_session.execute(select(Photo).where(Photo.id == photo.id)).scalar_one()
    assert stored.status == "hidden"


def test_deleting_planting_cascades_to_its_photos_at_the_database_level(
    db_session: Session,
) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    photo = _make_photo(planting.id)
    db_session.add(photo)
    db_session.commit()
    photo_id = photo.id

    # Deleted via the Core `DELETE` the ORM issues for `db_session.delete`,
    # not via any ORM-side `cascade=` — this proves the `ON DELETE CASCADE`
    # is enforced by Postgres itself, not just by SQLAlchemy bookkeeping.
    db_session.delete(planting)
    db_session.commit()

    remaining = db_session.execute(select(Photo).where(Photo.id == photo_id)).scalar_one_or_none()
    assert remaining is None
