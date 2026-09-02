"""Tests for `app/services/planting_service.py`: listing, resolution, and
admin create/update of Plantings. Mirrors
`backend/tests/test_region_service.py` — see
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.models.photo import Photo
from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region
from app.schemas.planting import PlantingCreate, PlantingUpdate
from app.services import planting_service
from app.services.planting_service import PlantingNotFound
from app.services.region_service import RegionNotFound

_POINT_A = "POINT(-43.3130 -21.8845)"
_POINT_B = "POINT(-43.3200 -21.8900)"


def _add_region(db_session: Session, **overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"regiao-{uuid.uuid4().hex[:8]}",
        "name": "Região de teste",
        "geom": WKTElement(_POINT_A, srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID, **overrides: object) -> Planting:
    defaults: dict[str, object] = {
        "region_id": region_id,
        "geom": WKTElement(_POINT_A, srid=4326),
    }
    defaults.update(overrides)
    planting = Planting(**defaults)
    db_session.add(planting)
    db_session.flush()
    db_session.add(QrCode(planting_id=planting.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return planting


def test_list_plantings_returns_a_valid_feature_collection(db_session: Session) -> None:
    region = _add_region(db_session)
    _add_planting(db_session, region.id)
    _add_planting(db_session, region.id, geom=WKTElement(_POINT_B, srid=4326))
    db_session.commit()

    collection = planting_service.list_plantings(db_session)

    assert collection.type == "FeatureCollection"
    assert len(collection.features) == 2


def test_list_plantings_filters_by_region_id(db_session: Session) -> None:
    region_a = _add_region(db_session)
    region_b = _add_region(db_session)
    _add_planting(db_session, region_a.id)
    _add_planting(db_session, region_b.id)
    db_session.commit()

    collection = planting_service.list_plantings(db_session, region_id=region_a.id)

    assert len(collection.features) == 1
    assert collection.features[0].properties.region_id == region_a.id


def test_list_plantings_excludes_draft_and_archived(db_session: Session) -> None:
    region = _add_region(db_session)
    _add_planting(db_session, region.id)
    _add_planting(db_session, region.id, status="draft")
    _add_planting(db_session, region.id, status="archived")
    db_session.commit()

    collection = planting_service.list_plantings(db_session)

    assert len(collection.features) == 1


def test_get_planting_returns_the_feature(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id, species="Ipê-amarelo", nickname="Muda da Ana")
    db_session.commit()

    feature = planting_service.get_planting(db_session, planting.id)

    assert feature.properties.species == "Ipê-amarelo"
    assert feature.properties.nickname == "Muda da Ana"
    assert feature.properties.region_id == region.id
    assert feature.properties.qr_token


def test_get_planting_raises_not_found_for_unknown_id(db_session: Session) -> None:
    with pytest.raises(PlantingNotFound):
        planting_service.get_planting(db_session, uuid.uuid4())


def test_get_planting_raises_not_found_for_an_archived_planting(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id, status="archived")
    db_session.commit()

    with pytest.raises(PlantingNotFound):
        planting_service.get_planting(db_session, planting.id)


def test_list_plantings_excludes_active_planting_in_an_archived_region(
    db_session: Session,
) -> None:
    region = _add_region(db_session, status="archived")
    _add_planting(db_session, region.id)
    db_session.commit()

    collection = planting_service.list_plantings(db_session)

    assert len(collection.features) == 0


def test_list_plantings_excludes_active_planting_in_a_draft_region(db_session: Session) -> None:
    region = _add_region(db_session, status="draft")
    _add_planting(db_session, region.id)
    db_session.commit()

    collection = planting_service.list_plantings(db_session)

    assert len(collection.features) == 0


def test_list_plantings_includes_active_planting_in_an_active_region(
    db_session: Session,
) -> None:
    region = _add_region(db_session, status="active")
    _add_planting(db_session, region.id)
    db_session.commit()

    collection = planting_service.list_plantings(db_session)

    assert len(collection.features) == 1


def test_get_planting_raises_not_found_for_an_active_planting_in_an_archived_region(
    db_session: Session,
) -> None:
    region = _add_region(db_session, status="archived")
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    with pytest.raises(PlantingNotFound):
        planting_service.get_planting(db_session, planting.id)


def test_create_planting_persists_fields_and_creates_a_qr_code(db_session: Session) -> None:
    region = _add_region(db_session)
    db_session.commit()

    payload = PlantingCreate(
        region_id=region.id,
        geometry={"type": "Point", "coordinates": (-43.3130, -21.8845)},
        species="Jacarandá",
        nickname="A árvore da Ana",
        planted_by="Ana",
    )

    feature = planting_service.create_planting(db_session, payload)

    assert feature.properties.species == "Jacarandá"
    assert feature.properties.nickname == "A árvore da Ana"
    assert feature.properties.planted_by == "Ana"
    assert feature.properties.qr_token
    qr_code_count = db_session.execute(
        select(func.count()).select_from(QrCode).where(QrCode.planting_id == uuid.UUID(feature.id))
    ).scalar_one()
    assert qr_code_count == 1


def test_create_planting_in_an_archived_region_still_returns_the_feature(
    db_session: Session,
) -> None:
    """Admin create/update goes through `_fetch_feature_by_id`, which must stay
    independent of the parent Region's status — same rule
    `region_service._fetch_feature_by_id` documents for `Region` itself.
    """
    region = _add_region(db_session, status="archived")
    db_session.commit()

    payload = PlantingCreate(
        region_id=region.id,
        geometry={"type": "Point", "coordinates": (-43.3130, -21.8845)},
        species="Jacarandá",
    )

    feature = planting_service.create_planting(db_session, payload)

    assert feature.properties.species == "Jacarandá"


def test_update_planting_changes_only_given_fields(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id, species="Ipê-amarelo")
    db_session.commit()

    feature = planting_service.update_planting(
        db_session, planting.id, PlantingUpdate(nickname="Nova muda")
    )

    assert feature.properties.nickname == "Nova muda"
    assert feature.properties.species == "Ipê-amarelo"  # untouched


def test_create_planting_raises_region_not_found_for_unknown_region_id(
    db_session: Session,
) -> None:
    payload = PlantingCreate(
        region_id=uuid.uuid4(),
        geometry={"type": "Point", "coordinates": (-43.3130, -21.8845)},
    )

    with pytest.raises(RegionNotFound):
        planting_service.create_planting(db_session, payload)


def test_update_planting_rejects_an_explicit_null_status(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    db_session.commit()

    with pytest.raises(ValidationFailedError):
        planting_service.update_planting(db_session, planting.id, PlantingUpdate(status=None))


def _add_photo(db_session: Session, planting_id: uuid.UUID, **overrides: object) -> Photo:
    defaults: dict[str, object] = {
        "planting_id": planting_id,
        "storage_key": f"photos/{uuid.uuid4().hex}.jpg",
        "content_type": "image/jpeg",
        "byte_size": 1000,
        "width": 100,
        "height": 100,
    }
    defaults.update(overrides)
    photo = Photo(**defaults)
    db_session.add(photo)
    return photo


def test_get_planting_reports_real_photo_count(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    _add_photo(db_session, planting.id)
    _add_photo(db_session, planting.id, status="hidden")
    db_session.commit()

    feature = planting_service.get_planting(db_session, planting.id)

    assert feature.properties.photo_count == 1  # `hidden` excluded
