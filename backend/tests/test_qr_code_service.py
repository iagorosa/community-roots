"""Tests for `app/services/qr_code_service.py`: creating and resolving
QR codes for Regions and Plantings. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region
from app.services import qr_code_service
from app.services.qr_code_service import QrTokenNotFound

_POINT_WKT = "POINT(-43.3130 -21.8845)"


def _add_region(db_session: Session, **overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"regiao-{uuid.uuid4().hex[:8]}",
        "name": "Região de teste",
        "geom": WKTElement(_POINT_WKT, srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID) -> Planting:
    planting = Planting(region_id=region_id, geom=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(planting)
    db_session.flush()
    return planting


def test_create_region_qr_code_persists_a_unique_token(db_session: Session) -> None:
    region = _add_region(db_session)

    token = qr_code_service.create_region_qr_code(db_session, region.id)
    db_session.commit()

    stored = db_session.execute(select(QrCode).where(QrCode.region_id == region.id)).scalar_one()
    assert stored.token == token


def test_create_planting_qr_code_persists_a_unique_token(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    token = qr_code_service.create_planting_qr_code(db_session, planting.id)
    db_session.commit()

    stored = db_session.execute(
        select(QrCode).where(QrCode.planting_id == planting.id)
    ).scalar_one()
    assert stored.token == token


def test_create_region_qr_code_generates_distinct_tokens(db_session: Session) -> None:
    region_a = _add_region(db_session)
    region_b = _add_region(db_session)

    token_a = qr_code_service.create_region_qr_code(db_session, region_a.id)
    token_b = qr_code_service.create_region_qr_code(db_session, region_b.id)

    assert token_a != token_b


def test_resolve_qr_token_finds_a_region(db_session: Session) -> None:
    region = _add_region(db_session)
    token = qr_code_service.create_region_qr_code(db_session, region.id)
    db_session.commit()

    target = qr_code_service.resolve_qr_token(db_session, token)

    assert target.kind == "region"
    assert target.identifier == region.slug


def test_resolve_qr_token_finds_a_planting(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    token = qr_code_service.create_planting_qr_code(db_session, planting.id)
    db_session.commit()

    target = qr_code_service.resolve_qr_token(db_session, token)

    assert target.kind == "planting"
    assert target.identifier == str(planting.id)


def test_resolve_qr_token_raises_for_an_unknown_token(db_session: Session) -> None:
    with pytest.raises(QrTokenNotFound):
        qr_code_service.resolve_qr_token(db_session, "does-not-exist")


def test_ensure_region_qr_code_creates_one_for_a_region_missing_it(db_session: Session) -> None:
    region = _add_region(db_session)  # no QrCode — simulates data seeded before issue #80

    token = qr_code_service.ensure_region_qr_code(db_session, region.id)
    db_session.commit()

    assert token is not None
    stored = db_session.execute(select(QrCode).where(QrCode.region_id == region.id)).scalar_one()
    assert stored.token == token


def test_ensure_region_qr_code_leaves_an_existing_one_untouched(db_session: Session) -> None:
    region = _add_region(db_session)
    original_token = qr_code_service.create_region_qr_code(db_session, region.id)
    db_session.commit()

    result = qr_code_service.ensure_region_qr_code(db_session, region.id)
    db_session.commit()

    assert result is None
    stored = db_session.execute(select(QrCode).where(QrCode.region_id == region.id)).scalar_one()
    assert stored.token == original_token


def test_backfill_missing_region_qr_codes_only_creates_missing_ones(db_session: Session) -> None:
    region_without_qr_code = _add_region(db_session)
    region_with_qr_code = _add_region(db_session, slug="regiao-com-qr")
    original_token = qr_code_service.create_region_qr_code(db_session, region_with_qr_code.id)
    db_session.commit()

    created_count = qr_code_service.backfill_missing_region_qr_codes(db_session)
    db_session.commit()

    assert created_count == 1
    backfilled_token = db_session.execute(
        select(QrCode.token).where(QrCode.region_id == region_without_qr_code.id)
    ).scalar_one()
    assert backfilled_token is not None
    untouched_token = db_session.execute(
        select(QrCode.token).where(QrCode.region_id == region_with_qr_code.id)
    ).scalar_one()
    assert untouched_token == original_token


def test_backfill_missing_region_qr_codes_is_a_no_op_when_every_region_has_one(
    db_session: Session,
) -> None:
    region = _add_region(db_session)
    qr_code_service.create_region_qr_code(db_session, region.id)
    db_session.commit()

    created_count = qr_code_service.backfill_missing_region_qr_codes(db_session)

    assert created_count == 0
