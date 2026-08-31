"""Tests for the `QrCode` model and its migration
(backend/app/models/qr_code.py). See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md for why
this replaces the `qr_token` column that used to live directly on `Region`:
a QrCode row belongs to exactly one of a Region or a Planting, never both,
never neither.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region

_POINT_WKT = "POINT(-43.3130 -21.8845)"


def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"regiao-{uuid.uuid4().hex[:8]}",
        "name": "Região de teste",
        "geom": WKTElement(_POINT_WKT, srid=4326),
    }
    defaults.update(overrides)
    return Region(**defaults)


def test_qr_code_for_a_region_is_accepted(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    db_session.add(QrCode(token="tok-region", region_id=region.id))
    db_session.commit()

    stored = db_session.execute(select(QrCode).where(QrCode.token == "tok-region")).scalar_one()
    assert stored.region_id == region.id
    assert stored.planting_id is None


def test_qr_code_for_a_planting_is_accepted(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    planting = Planting(region_id=region.id, geom=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(planting)
    db_session.flush()

    db_session.add(QrCode(token="tok-planting", planting_id=planting.id))
    db_session.commit()

    stored = db_session.execute(select(QrCode).where(QrCode.token == "tok-planting")).scalar_one()
    assert stored.planting_id == planting.id
    assert stored.region_id is None


def test_qr_code_with_neither_target_is_rejected(db_session: Session) -> None:
    db_session.add(QrCode(token="tok-neither"))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_qr_code_with_both_targets_is_rejected(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    planting = Planting(region_id=region.id, geom=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(planting)
    db_session.flush()

    db_session.add(QrCode(token="tok-both", region_id=region.id, planting_id=planting.id))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_a_region_cannot_have_two_qr_codes(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(token="tok-first", region_id=region.id))
    db_session.commit()

    db_session.add(QrCode(token="tok-second", region_id=region.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_region_cascades_to_its_qr_code(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(token="tok-cascade", region_id=region.id))
    db_session.commit()

    db_session.delete(region)
    db_session.commit()

    remaining = db_session.execute(
        select(QrCode).where(QrCode.token == "tok-cascade")
    ).scalar_one_or_none()
    assert remaining is None
