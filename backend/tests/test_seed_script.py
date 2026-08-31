"""Tests for `scripts/seed.py`: idempotent development seed data — Regions
with nested Plantings. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region
from scripts.seed import _grid_cell_centers, seed

_CENTER_LAT = -21.883859
_CENTER_LON = -43.312459


def _region_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Region)).scalar_one()


def _planting_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Planting)).scalar_one()


def test_seed_creates_the_configured_number_of_regions(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)

    assert _region_count(db_session) == 10


def test_seed_creates_plantings_inside_each_region(db_session: Session) -> None:
    seed(
        db_session,
        center_lat=_CENTER_LAT,
        center_lon=_CENTER_LON,
        region_count=10,
        plantings_per_region=3,
    )

    assert _planting_count(db_session) == 30
    first_region_id = db_session.execute(
        select(Region.id).order_by(Region.slug).limit(1)
    ).scalar_one()
    plantings_in_first_region = db_session.execute(
        select(func.count()).select_from(Planting).where(Planting.region_id == first_region_id)
    ).scalar_one()
    assert plantings_in_first_region == 3


def test_seed_gives_every_region_and_planting_a_qr_code(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)

    region_qr_count = db_session.execute(
        select(func.count()).select_from(QrCode).where(QrCode.region_id.is_not(None))
    ).scalar_one()
    planting_qr_count = db_session.execute(
        select(func.count()).select_from(QrCode).where(QrCode.planting_id.is_not(None))
    ).scalar_one()
    assert region_qr_count == 10
    assert planting_qr_count == _planting_count(db_session)


def test_seed_is_idempotent(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)

    assert _region_count(db_session) == 10
    assert _planting_count(db_session) == 10 * 4  # default plantings_per_region — no duplicates


def test_seed_documents_the_placeholder_geometry_in_the_description(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)

    region = db_session.execute(select(Region)).scalars().first()

    assert region is not None
    assert "placeholder" in (region.description or "").lower()


def test_seed_repositions_existing_regions_when_center_changes(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)
    original_centroid = db_session.execute(
        select(func.ST_AsText(Region.centroid)).order_by(Region.slug).limit(1)
    ).scalar_one()

    seed(db_session, center_lat=_CENTER_LAT + 1.0, center_lon=_CENTER_LON + 1.0, region_count=10)
    moved_centroid = db_session.execute(
        select(func.ST_AsText(Region.centroid)).order_by(Region.slug).limit(1)
    ).scalar_one()

    assert _region_count(db_session) == 10  # still no duplicates
    assert original_centroid != moved_centroid


def test_seed_preserves_qr_token_across_reruns(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)
    first_region_id = db_session.execute(
        select(Region.id).order_by(Region.slug).limit(1)
    ).scalar_one()
    original_token = db_session.execute(
        select(QrCode.token).where(QrCode.region_id == first_region_id)
    ).scalar_one()

    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)
    token_after_rerun = db_session.execute(
        select(QrCode.token).where(QrCode.region_id == first_region_id)
    ).scalar_one()

    assert original_token == token_after_rerun


def test_grid_cell_centers_forms_a_5x2_grid_for_the_default_count() -> None:
    cell_centers = _grid_cell_centers(10, rows=2, center_lat=_CENTER_LAT, center_lon=_CENTER_LON)

    distinct_lats = {lat for lat, _lon in cell_centers}
    distinct_lons = {lon for _lat, lon in cell_centers}
    assert len(distinct_lats) == 2
    assert len(distinct_lons) == 5


def test_seed_rejects_a_region_count_beyond_the_fictional_name_pool(db_session: Session) -> None:
    # `_REGION_NAMES` has 10 entries — silently truncating a higher
    # `SEED_REGION_COUNT` would contradict the issue's own requirement that
    # the script reads and honors that setting.
    with pytest.raises(ValueError, match="10"):
        seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=15)
