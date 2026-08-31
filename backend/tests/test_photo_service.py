"""Tests for `app/services/photo_service.py`: the region photo timeline and
its keyset pagination (issue #21), plus resolving a photo's file for
`GET /api/photos/{photo_id}/file` (issue #22).
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.photo import Photo
from app.models.qr_code import QrCode
from app.models.region import Region
from app.services import photo_service
from app.services.photo_service import InvalidCursor, PhotoNotFound
from app.services.region_service import RegionNotFound
from app.storage.local import LocalFilesystemStorage

_POLYGON_WKT = (
    "POLYGON((-43.3130 -21.8845, -43.3125 -21.8845, "
    "-43.3125 -21.8840, -43.3130 -21.8840, -43.3130 -21.8845))"
)
_POINT_WKT = "POINT(-43.3127 -21.8843)"


def _add_region(db_session: Session, **overrides: object) -> Region:
    """Insert a `Region` plus the `QrCode` row every real region gets at
    creation time (`region_service.create_region`) — `region_service.
    get_region` (which `photo_service.list_region_photos` reuses to resolve
    the `{region}` path parameter) INNER JOINs on it, so a region without one
    wouldn't be a realistic fixture.
    """
    defaults: dict[str, object] = {
        "slug": "canteiro-a",
        "name": "Canteiro A",
        "geom": WKTElement(_POLYGON_WKT, srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return region


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
    region = _add_region(db_session)

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
    region = _add_region(db_session)

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


def test_list_region_photos_exposes_width_and_height(db_session: Session) -> None:
    """The frontend timeline (issue #24) reserves layout space for each
    image via its `width`/`height` HTML attributes before it loads — it can
    only do that if `PhotoOut` carries the columns already recorded on
    upload (issue #20), rather than only the derived `latitude`/`longitude`.
    """
    region = _add_region(db_session)

    photo = _make_photo(region.id, width=800, height=600)
    db_session.add(photo)
    db_session.commit()

    page = photo_service.list_region_photos(db_session, "canteiro-a")

    [item] = page.items
    assert item.width == 800
    assert item.height == 600


def test_list_region_photos_excludes_hidden_photos(db_session: Session) -> None:
    region = _add_region(db_session)

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
    region = _add_region(db_session)

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
    region = _add_region(db_session)

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
    _add_region(db_session)
    db_session.commit()

    with pytest.raises(InvalidCursor):
        photo_service.list_region_photos(db_session, "canteiro-a", cursor="not-a-valid-cursor")


def test_open_photo_file_returns_readable_bytes_and_the_stored_content_type(
    db_session: Session, tmp_path: Path
) -> None:
    region = _add_region(db_session)

    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "a.png").write_bytes(b"fake-png-bytes")
    photo = _make_photo(region.id, storage_key="photos/a.png", content_type="image/png")
    db_session.add(photo)
    db_session.commit()

    storage = LocalFilesystemStorage(tmp_path)
    file, content_type = photo_service.open_photo_file(db_session, photo.id, storage)

    with file:
        assert file.read() == b"fake-png-bytes"
    assert content_type == "image/png"


def test_open_photo_file_raises_photo_not_found_for_an_unknown_id(
    db_session: Session, tmp_path: Path
) -> None:
    storage = LocalFilesystemStorage(tmp_path)

    with pytest.raises(PhotoNotFound):
        photo_service.open_photo_file(db_session, uuid.uuid4(), storage)


def test_open_photo_file_raises_photo_not_found_for_a_hidden_photo(
    db_session: Session, tmp_path: Path
) -> None:
    """`hidden` fully hides a photo's file too, not just the timeline listing
    — see the docstring of `photo_service.open_photo_file` for why.
    """
    region = _add_region(db_session)

    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "a.png").write_bytes(b"fake-png-bytes")
    photo = _make_photo(region.id, storage_key="photos/a.png", status="hidden")
    db_session.add(photo)
    db_session.commit()

    storage = LocalFilesystemStorage(tmp_path)
    with pytest.raises(PhotoNotFound):
        photo_service.open_photo_file(db_session, photo.id, storage)


def test_open_photo_file_raises_photo_not_found_when_the_file_is_missing_from_storage(
    db_session: Session, tmp_path: Path
) -> None:
    """A `Photo` row can outlive its file (storage wiped out-of-band, e.g. by
    hand during an incident) — this must surface as the same clean 404 as an
    unknown id, never as a 500 leaking a filesystem `FileNotFoundError`.
    """
    region = _add_region(db_session)

    photo = _make_photo(region.id, storage_key="photos/never-written.png")
    db_session.add(photo)
    db_session.commit()

    storage = LocalFilesystemStorage(tmp_path)
    with pytest.raises(PhotoNotFound):
        photo_service.open_photo_file(db_session, photo.id, storage)
