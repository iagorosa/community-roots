"""Tests for `app/services/photo_service.py`: the region photo timeline and
its keyset pagination. See docs/architecture.md §4.3/§4.4 and issue #21.
"""

from datetime import UTC, datetime

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.photo import Photo
from app.models.region import Region
from app.services import photo_service
from app.services.photo_service import InvalidCursor
from app.services.region_service import RegionNotFound

_POLYGON_WKT = (
    "POLYGON((-43.3130 -21.8845, -43.3125 -21.8845, "
    "-43.3125 -21.8840, -43.3130 -21.8840, -43.3130 -21.8845))"
)
_POINT_WKT = "POINT(-43.3127 -21.8843)"


def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": "canteiro-a",
        "name": "Canteiro A",
        "geom": WKTElement(_POLYGON_WKT, srid=4326),
        "qr_token": "token-a",
    }
    defaults.update(overrides)
    return Region(**defaults)


def _dt(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 1, 1, hour, minute, second, tzinfo=UTC)


def _make_photo(region_id: object, **overrides: object) -> Photo:
    defaults: dict[str, object] = {
        "region_id": region_id,
        "storage_key": "photos/whatever.jpg",
        "content_type": "image/jpeg",
        "byte_size": 123_456,
        "width": 1080,
        "height": 1350,
        "uploaded_at": _dt(10, 0),
    }
    defaults.update(overrides)
    return Photo(**defaults)


def test_list_region_photos_returns_published_photos_most_recent_first(
    db_session: Session,
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    older = _make_photo(region.id, uploaded_at=_dt(9, 0))
    newer = _make_photo(region.id, uploaded_at=_dt(11, 0))
    db_session.add_all([older, newer])
    db_session.commit()

    page = photo_service.list_region_photos(db_session, "canteiro-a")

    assert [photo.id for photo in page.items] == [newer.id, older.id]
    assert page.next_cursor is None


def test_list_region_photos_derives_latitude_and_longitude_from_location(
    db_session: Session,
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    with_location = _make_photo(region.id, location=WKTElement(_POINT_WKT, srid=4326))
    without_location = _make_photo(region.id, uploaded_at=_dt(8, 0))
    db_session.add_all([with_location, without_location])
    db_session.commit()

    page = photo_service.list_region_photos(db_session, "canteiro-a")

    by_id = {photo.id: photo for photo in page.items}
    located = by_id[with_location.id]
    assert located.latitude == pytest.approx(-21.8843)
    assert located.longitude == pytest.approx(-43.3127)
    assert by_id[without_location.id].latitude is None
    assert by_id[without_location.id].longitude is None


def test_list_region_photos_excludes_hidden_photos(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    published = _make_photo(region.id, status="published")
    hidden = _make_photo(region.id, status="hidden", uploaded_at=_dt(12, 0))
    db_session.add_all([published, hidden])
    db_session.commit()

    page = photo_service.list_region_photos(db_session, "canteiro-a")

    assert [photo.id for photo in page.items] == [published.id]


def test_list_region_photos_raises_not_found_for_unknown_region(db_session: Session) -> None:
    with pytest.raises(RegionNotFound):
        photo_service.list_region_photos(db_session, "nao-existe")


def test_list_region_photos_paginates_by_limit(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    photos = [_make_photo(region.id, uploaded_at=_dt(10, i)) for i in range(3)]
    db_session.add_all(photos)
    db_session.commit()

    page = photo_service.list_region_photos(db_session, "canteiro-a", limit=2)

    assert [photo.id for photo in page.items] == [photos[2].id, photos[1].id]
    assert page.next_cursor is not None


def test_list_region_photos_pagination_is_stable_against_concurrent_inserts(
    db_session: Session,
) -> None:
    """The critério de pronto requires stable pagination: since the listing
    orders by `uploaded_at DESC` on a table that receives constant inserts,
    offset/page-number pagination would shift every row between two
    requests. This test proves keyset pagination doesn't: a photo inserted
    *after* the first page was fetched, newer than everything already seen,
    must not appear on the second page, and the item that belongs there
    must appear exactly once — not duplicated, not skipped.
    """
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    photos = [_make_photo(region.id, uploaded_at=_dt(10, i)) for i in range(3)]
    db_session.add_all(photos)
    db_session.commit()

    first_page = photo_service.list_region_photos(db_session, "canteiro-a", limit=2)
    assert [photo.id for photo in first_page.items] == [photos[2].id, photos[1].id]
    assert first_page.next_cursor is not None

    # Arrives between the two page requests, newer than every photo already
    # fetched — with offset pagination this would push `photos[0]` to a
    # different page or duplicate `photos[1]`.
    newest = _make_photo(region.id, uploaded_at=_dt(11, 0))
    db_session.add(newest)
    db_session.commit()

    second_page = photo_service.list_region_photos(
        db_session, "canteiro-a", cursor=first_page.next_cursor, limit=2
    )

    assert [photo.id for photo in second_page.items] == [photos[0].id]
    assert second_page.next_cursor is None


def test_list_region_photos_rejects_a_malformed_cursor(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.commit()

    with pytest.raises(InvalidCursor):
        photo_service.list_region_photos(db_session, "canteiro-a", cursor="not-a-valid-cursor")
