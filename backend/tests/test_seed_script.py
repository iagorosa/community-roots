"""Tests for `scripts/seed.py`: idempotent development seed data — a single
`Region` (the AAMA, in Matias Barbosa) with nested `Planting`s. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md and
issue #122 (the seed used to create one `Region` per fictional "canteiro",
which contradicted the domain model as soon as `Planting` existed)."""

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region
from scripts.seed import _PLANTING_NICKNAMES, _grid_positions, seed

_CENTER_LAT = -21.883859
_CENTER_LON = -43.312459


def _region_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Region)).scalar_one()


def _planting_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Planting)).scalar_one()


def test_seed_creates_exactly_one_region(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=15)

    assert _region_count(db_session) == 1


def test_seed_names_the_region_after_the_real_association(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=15)

    region = db_session.execute(select(Region)).scalar_one()

    assert region.name == "AAMA — Matias Barbosa"


def test_seed_creates_the_configured_number_of_plantings_inside_the_region(
    db_session: Session,
) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=15)

    region_id = db_session.execute(select(Region.id)).scalar_one()
    plantings_in_region = db_session.execute(
        select(func.count()).select_from(Planting).where(Planting.region_id == region_id)
    ).scalar_one()

    assert _planting_count(db_session) == 15
    assert plantings_in_region == 15


def test_seed_assigns_every_planting_a_nickname_from_the_fictional_pool(
    db_session: Session,
) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=8)

    nicknames = db_session.execute(select(Planting.nickname)).scalars().all()

    assert len(nicknames) == 8
    assert all(nickname in _PLANTING_NICKNAMES for nickname in nicknames)


def test_seed_cycles_nicknames_when_planting_count_exceeds_the_pool(
    db_session: Session,
) -> None:
    # `_PLANTING_NICKNAMES` has 10 entries — a `planting_count` beyond that
    # must still succeed by repeating names, rather than raising like the
    # old per-Region name pool used to (there's no such limit anymore: a
    # nickname is flavor text on a Planting, not a unique Region name).
    planting_count = len(_PLANTING_NICKNAMES) + 3
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=planting_count)

    nicknames = db_session.execute(select(Planting.nickname)).scalars().all()

    # Row order isn't guaranteed without an ORDER BY, so this checks the
    # multiset of nicknames (each pool name used once, plus 3 repeats),
    # not positional order.
    expected_counts = Counter(_PLANTING_NICKNAMES) + Counter(_PLANTING_NICKNAMES[:3])
    assert len(nicknames) == planting_count
    assert Counter(nicknames) == expected_counts


def test_seed_gives_the_region_and_every_planting_a_qr_code(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=8)

    region_qr_count = db_session.execute(
        select(func.count()).select_from(QrCode).where(QrCode.region_id.is_not(None))
    ).scalar_one()
    planting_qr_count = db_session.execute(
        select(func.count()).select_from(QrCode).where(QrCode.planting_id.is_not(None))
    ).scalar_one()

    assert region_qr_count == 1
    assert planting_qr_count == 8


def test_seed_is_idempotent(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=12)
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=12)

    assert _region_count(db_session) == 1
    assert _planting_count(db_session) == 12  # no duplicates on rerun


def test_seed_documents_the_placeholder_geometry_in_the_description(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=8)

    region = db_session.execute(select(Region)).scalar_one()

    assert "placeholder" in (region.description or "").lower()


def test_seed_repositions_the_region_when_center_changes(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=8)
    original_centroid = db_session.execute(select(func.ST_AsText(Region.centroid))).scalar_one()

    seed(db_session, center_lat=_CENTER_LAT + 1.0, center_lon=_CENTER_LON + 1.0, planting_count=8)
    moved_centroid = db_session.execute(select(func.ST_AsText(Region.centroid))).scalar_one()

    assert _region_count(db_session) == 1  # still no duplicates
    assert original_centroid != moved_centroid


def test_seed_preserves_qr_token_across_reruns(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=8)
    region_id = db_session.execute(select(Region.id)).scalar_one()
    original_token = db_session.execute(
        select(QrCode.token).where(QrCode.region_id == region_id)
    ).scalar_one()

    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, planting_count=8)
    token_after_rerun = db_session.execute(
        select(QrCode.token).where(QrCode.region_id == region_id)
    ).scalar_one()

    assert original_token == token_after_rerun


def test_grid_positions_forms_a_5x2_grid_for_the_default_count() -> None:
    positions = _grid_positions(10, rows=2, center_lat=_CENTER_LAT, center_lon=_CENTER_LON)

    distinct_lats = {lat for lat, _lon in positions}
    distinct_lons = {lon for _lat, lon in positions}
    assert len(distinct_lats) == 2
    assert len(distinct_lons) == 5
