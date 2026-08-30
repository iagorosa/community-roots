"""Tests for `app/services/exif_processing.py`: EXIF extraction, conditional
GPS disclosure, and metadata-free re-encoding.

See docs/architecture.md §6.2 for the policy these tests exercise: the
stored file is always stripped of EXIF, `captured_at` is always extracted,
and `location` is only ever written when the caller passes
`share_location=True`.

No `client`/`db_session` fixture is used anywhere here: this module never
touches the database or an HTTP request, only a decoded `Image.Image` (the
same object `validate_upload` in `app/services/image_processing.py`
already returns), so these tests stay as cheap and isolated as
`tests/test_image_processing.py`.
"""

import io
import math
from datetime import UTC, datetime

import pytest
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from app.services.exif_processing import process_photo_metadata

# Real-world-shaped DMS values, chosen so the decimal conversion isn't a
# round number (a bug that only shows up on non-trivial minutes/seconds
# wouldn't be caught by, say, 40°0'0").
_LATITUDE_DMS = (40.0, 26.0, 46.302)  # degrees, minutes, seconds
_LATITUDE_REF = "N"
_LONGITUDE_DMS = (79.0, 58.0, 55.7027)
_LONGITUDE_REF = "W"

# Same formula `process_photo_metadata` must implement, computed
# independently here so the test proves the conversion rather than
# assuming it: decimal = degrees + minutes/60 + seconds/3600, negated for
# S/W. This is a standalone check of DMS arithmetic, not a mirror of the
# implementation's code path.
_EXPECTED_LATITUDE = _LATITUDE_DMS[0] + _LATITUDE_DMS[1] / 60 + _LATITUDE_DMS[2] / 3600
_EXPECTED_LONGITUDE = -(_LONGITUDE_DMS[0] + _LONGITUDE_DMS[1] / 60 + _LONGITUDE_DMS[2] / 3600)

_DATE_TIME_ORIGINAL = "2024:03:15 10:30:00"
_EXPECTED_CAPTURED_AT = datetime(2024, 3, 15, 10, 30, 0, tzinfo=UTC)

# EXIF Orientation 6 = "rotate 90° CW to display correctly" — chosen because
# it swaps width/height once baked into the pixels, which is an
# unambiguous, easy-to-assert signal that `exif_transpose` actually ran.
_ORIENTATION_ROTATED_90 = 6


def _build_image_with_exif(
    *,
    format: str = "JPEG",
    width: int = 4,
    height: int = 6,
    date_time_original: str | None = None,
    gps: tuple[tuple, str, tuple, str] | None = None,
    orientation: int | None = None,
    icc_profile: bytes | None = None,
) -> Image.Image:
    """Build a real, decodable image carrying real EXIF tags — never a mock.

    Mirrors how a camera/phone actually lays these tags out: `Orientation`
    (0x0112) in the main IFD, `DateTimeOriginal` (0x9003) in the Exif SubIFD
    (0x8769), and the GPS tags in the GPS IFD (0x8825). `icc_profile`, when
    given, is an embedded color profile — a format of metadata Pillow
    handles separately from EXIF (see
    `test_rewritten_png_bytes_carry_no_icc_profile` below).

    `gps` DMS components are typically `float`, but the type is loose
    enough to also accept a `PIL.TiffImagePlugin.IFDRational` — real camera
    EXIF is `IFDRational`-typed, and one malformed-denominator test below
    needs to inject one directly.
    """
    source = Image.new("RGB", (width, height), color=(10, 20, 30))

    exif = Image.Exif()
    if orientation is not None:
        exif[0x0112] = orientation
    if date_time_original is not None:
        exif[0x8769] = {0x9003: date_time_original}
    if gps is not None:
        lat_dms, lat_ref, lon_dms, lon_ref = gps
        exif[0x8825] = {1: lat_ref, 2: lat_dms, 3: lon_ref, 4: lon_dms}

    save_kwargs = {"exif": exif}
    if icc_profile is not None:
        save_kwargs["icc_profile"] = icc_profile

    buffer = io.BytesIO()
    source.save(buffer, format=format, **save_kwargs)
    buffer.seek(0)

    decoded = Image.open(buffer)
    decoded.load()
    return decoded


def test_full_exif_with_share_location_true_extracts_everything() -> None:
    image = _build_image_with_exif(
        date_time_original=_DATE_TIME_ORIGINAL,
        gps=(_LATITUDE_DMS, _LATITUDE_REF, _LONGITUDE_DMS, _LONGITUDE_REF),
    )

    result = process_photo_metadata(image, share_location=True)

    assert result.captured_at == _EXPECTED_CAPTURED_AT
    assert result.latitude == pytest.approx(_EXPECTED_LATITUDE)
    assert result.longitude == pytest.approx(_EXPECTED_LONGITUDE)
    assert result.location_source == "exif"


def test_full_exif_with_share_location_false_discards_gps() -> None:
    """The central privacy requirement of issue #27: GPS is present in the
    source EXIF, but `share_location=False` must mean it never reaches the
    output — not partially, not in a side channel, not at all.
    """
    image = _build_image_with_exif(
        date_time_original=_DATE_TIME_ORIGINAL,
        gps=(_LATITUDE_DMS, _LATITUDE_REF, _LONGITUDE_DMS, _LONGITUDE_REF),
    )

    result = process_photo_metadata(image, share_location=False)

    assert result.latitude is None
    assert result.longitude is None
    assert result.location_source is None
    # captured_at is unrelated to location consent and must still come through.
    assert result.captured_at == _EXPECTED_CAPTURED_AT


def test_image_without_any_exif_yields_no_metadata_and_does_not_raise() -> None:
    image = _build_image_with_exif()

    result = process_photo_metadata(image, share_location=True)

    assert result.captured_at is None
    assert result.latitude is None
    assert result.longitude is None
    assert result.location_source is None


def test_date_time_original_without_gps_yields_no_location_regardless_of_share_location() -> None:
    for share_location in (True, False):
        image = _build_image_with_exif(date_time_original=_DATE_TIME_ORIGINAL)

        result = process_photo_metadata(image, share_location=share_location)

        assert result.captured_at == _EXPECTED_CAPTURED_AT
        assert result.latitude is None
        assert result.longitude is None
        assert result.location_source is None


def test_rewritten_image_bytes_carry_no_exif_block() -> None:
    """The other central requirement: reopening the saved bytes must find no
    EXIF block at all — proven literally, not inferred from "no error".
    """
    image = _build_image_with_exif(
        date_time_original=_DATE_TIME_ORIGINAL,
        gps=(_LATITUDE_DMS, _LATITUDE_REF, _LONGITUDE_DMS, _LONGITUDE_REF),
        orientation=_ORIENTATION_ROTATED_90,
    )

    result = process_photo_metadata(image, share_location=True)

    reopened_exif = Image.open(io.BytesIO(result.image_bytes)).getexif()
    assert dict(reopened_exif) == {}


def test_orientation_is_baked_into_pixels_before_exif_is_dropped() -> None:
    """Orientation 6 (rotate 90° CW) swaps width/height once applied — the
    only way to prove `exif_transpose` ran, since the EXIF that a naive
    viewer would otherwise use to rotate the image is gone afterwards.
    """
    image = _build_image_with_exif(width=4, height=6, orientation=_ORIENTATION_ROTATED_90)
    assert image.size == (4, 6)  # sanity: orientation not yet applied

    result = process_photo_metadata(image, share_location=True)

    reopened = Image.open(io.BytesIO(result.image_bytes))
    assert reopened.size == (6, 4)


def test_width_and_height_reflect_the_source_image_when_not_rotated() -> None:
    image = _build_image_with_exif(width=4, height=6)

    result = process_photo_metadata(image, share_location=True)

    assert (result.width, result.height) == (4, 6)


def test_width_and_height_reflect_the_post_rotation_size_not_the_source_size() -> None:
    """Orientation 6 (rotate 90° CW) swaps width/height once applied — the
    stored `width`/`height` must be the *final* (post-rotation) size, the
    same one `image_bytes` actually decodes to, not the pre-rotation size
    read straight off the source image.
    """
    image = _build_image_with_exif(width=4, height=6, orientation=_ORIENTATION_ROTATED_90)

    result = process_photo_metadata(image, share_location=True)

    assert (result.width, result.height) == (6, 4)
    reopened = Image.open(io.BytesIO(result.image_bytes))
    assert reopened.size == (result.width, result.height)


def test_content_type_matches_the_images_format() -> None:
    image = _build_image_with_exif(format="PNG")

    result = process_photo_metadata(image, share_location=True)

    assert result.content_type == "image/png"
    assert Image.open(io.BytesIO(result.image_bytes)).format == "PNG"


def test_content_type_matches_webp_format() -> None:
    image = _build_image_with_exif(format="WEBP")

    result = process_photo_metadata(image, share_location=True)

    assert result.content_type == "image/webp"
    assert Image.open(io.BytesIO(result.image_bytes)).format == "WEBP"


def test_rewritten_png_bytes_carry_no_icc_profile() -> None:
    """PNG's ICC-profile write path is not the same code path as EXIF's —
    Pillow's PNG saver falls back to the *source* image's `.info["icc_profile"]`
    when `save()` isn't given an explicit `icc_profile=` kwarg, unlike EXIF
    (which only PNG/JPEG/WEBP savers read from `encoderinfo`, never `.info`).
    So an embedded color profile on the upload could survive re-encoding even
    though EXIF doesn't — this proves it does not.
    """
    image = _build_image_with_exif(format="PNG", icc_profile=b"fake-icc-profile-bytes")

    result = process_photo_metadata(image, share_location=True)

    reopened = Image.open(io.BytesIO(result.image_bytes))
    reopened.load()
    assert "icc_profile" not in reopened.info


def test_date_time_original_with_garbage_value_yields_none_without_raising() -> None:
    image = _build_image_with_exif(date_time_original="not-a-real-timestamp")

    result = process_photo_metadata(image, share_location=True)

    assert result.captured_at is None


def test_gps_with_missing_longitude_ref_yields_no_location() -> None:
    """A half-written coordinate (latitude present, but the longitude
    reference tag empty) is not a usable location — `_extract_gps`'s
    docstring calls this out as a deliberate all-or-nothing design: no
    guessed default reference, no partially-filled pair. This proves it.
    """
    image = _build_image_with_exif(
        date_time_original=_DATE_TIME_ORIGINAL,
        gps=(_LATITUDE_DMS, _LATITUDE_REF, (0.0, 0.0, 0.0), ""),
    )

    result = process_photo_metadata(image, share_location=True)

    assert result.latitude is None
    assert result.longitude is None
    assert result.location_source is None


def test_gps_with_zero_denominator_rational_yields_no_location() -> None:
    """A malformed EXIF rational (denominator 0) converts to `float('nan')`
    rather than raising — Pillow's `IFDRational.__float__` swallows the
    division. `nan` is not a usable coordinate (it isn't valid JSON, and it
    would silently corrupt a future DB float/geometry column), so this must
    be treated the same as any other malformed GPS data: `None`, never a
    `nan` slipping through as if it were real.
    """
    image = _build_image_with_exif(
        gps=((IFDRational(40, 0), 26.0, 46.302), _LATITUDE_REF, _LONGITUDE_DMS, _LONGITUDE_REF),
    )

    result = process_photo_metadata(image, share_location=True)

    assert result.latitude is None
    assert result.longitude is None
    assert result.location_source is None
    assert not (result.latitude is not None and math.isnan(result.latitude))
