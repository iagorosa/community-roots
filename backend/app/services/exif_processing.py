"""EXIF extraction and metadata-free re-encoding: turns a decoded
`Image.Image` (already validated by `app.services.image_processing`) into
`ExtractedPhotoMetadata` — timeline/location fields for the database, plus
the re-encoded bytes that actually get stored.

Policy, decided in docs/architecture.md §6.2 and only implemented here:

- `DateTimeOriginal` -> `captured_at`. Always extracted; nothing gates it.
- GPS tags -> `latitude`/`longitude`/`location_source`. Read from the EXIF
  unconditionally (so this module can decide whether to keep them), but
  only ever returned when the caller passes `share_location=True`. Anyone
  can contribute here, including children, so silently recording the exact
  coordinate of where a minor was standing is not acceptable — with
  `share_location=False` (the form's default), GPS is read and discarded,
  never written.
- The stored file is always rewritten with `ImageOps.exif_transpose` baked
  in and no EXIF block at all — this is unconditional, independent of
  `share_location`, so a photo that leaks through any other path still
  carries no hidden location either.
"""

import io
import math
from dataclasses import dataclass
from datetime import UTC, datetime

from PIL import Image, ImageOps

# EXIF tag/IFD ids used below (Pillow exposes these as plain ints, not named
# constants) — see the EXIF 2.3 spec. Orientation (0x0112) itself is never
# read directly here: `ImageOps.exif_transpose` below reads it from the
# image's own EXIF internally.
_IFD_EXIF = 0x8769
_TAG_DATE_TIME_ORIGINAL = 0x9003
_IFD_GPS = 0x8825
_TAG_GPS_LATITUDE_REF = 1
_TAG_GPS_LATITUDE = 2
_TAG_GPS_LONGITUDE_REF = 3
_TAG_GPS_LONGITUDE = 4

# EXIF's DateTimeOriginal has no timezone field at all (EXIF 2.3 §4.6.4) —
# it's whatever the camera clock happened to show. Treating it as UTC is a
# deliberate choice, not a discovery of the "real" zone: it's the only
# reading that doesn't fabricate an offset, it's stable/reproducible
# (doesn't depend on the server's local zone or guesswork about where the
# photo was taken), and `captured_at` only needs to order photos on a
# timeline — a few hours of skew from the camera's real local time doesn't
# change that ordering for a single community garden's timeline.
_EXIF_DATE_TIME_FORMAT = "%Y:%m:%d %H:%M:%S"

# Covers `settings.allowed_image_formats`'s current default
# (app/core/config.py) — kept as an explicit local mapping rather than
# `PIL.Image.MIME` (Pillow's own format->MIME registry) because that
# registry is only populated once the relevant plugin module has been
# imported/registered, an import-order side effect this module shouldn't
# depend on. `_content_type_for` below falls back to a generic
# `image/<format>` for any format an operator adds to the allowlist later
# without updating this dict, rather than raising.
_CONTENT_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def _content_type_for(image_format: str) -> str:
    return _CONTENT_TYPES.get(image_format, f"image/{image_format.lower()}")


@dataclass
class ExtractedPhotoMetadata:
    captured_at: datetime | None
    latitude: float | None
    longitude: float | None
    location_source: str | None
    image_bytes: bytes
    content_type: str


def _extract_captured_at(exif: Image.Exif) -> datetime | None:
    """Read `DateTimeOriginal` from the Exif SubIFD, or `None`.

    Never raises: a photo with no EXIF, no `DateTimeOriginal` tag, or a
    malformed one must still be processable — just without `captured_at`.
    """
    raw_value = exif.get_ifd(_IFD_EXIF).get(_TAG_DATE_TIME_ORIGINAL)
    if not raw_value:
        return None

    try:
        # `%z` isn't in `_EXIF_DATE_TIME_FORMAT` (EXIF carries no offset at
        # all — see the module docstring), so `strptime` necessarily builds
        # a naive datetime; `.replace(tzinfo=UTC)` right after is the
        # deliberate, documented attachment of our own UTC assumption, not
        # an omission. ruff's `DTZ007` flags naive-`strptime` calls in
        # general and can't see that the very next line resolves it.
        naive = datetime.strptime(raw_value, _EXIF_DATE_TIME_FORMAT)  # noqa: DTZ007
    except (ValueError, TypeError):
        return None

    return naive.replace(tzinfo=UTC)


def _dms_to_decimal(dms: tuple[float, float, float], ref: str) -> float:
    """Convert (degrees, minutes, seconds) + a N/S/E/W reference to signed
    decimal degrees. `S`/`W` negate; `N`/`E` stay positive.

    Raises `ValueError` if the result isn't finite. Real EXIF rationals are
    `IFDRational(numerator, denominator)`; a malformed one with a zero
    denominator converts to `float("nan")` instead of raising (Pillow's own
    `__float__` swallows the division), so a plain `float(component)` call
    would otherwise let a `nan` slip through silently as if it were a real
    coordinate — `_extract_gps`'s caller relies on this function raising
    instead, so it can fall back to `None` the same as any other malformed
    coordinate.
    """
    degrees, minutes, seconds = (float(component) for component in dms)
    decimal = degrees + minutes / 60 + seconds / 3600

    if not math.isfinite(decimal):
        msg = f"non-finite GPS coordinate: degrees={degrees}, minutes={minutes}, seconds={seconds}"
        raise ValueError(msg)

    if ref in ("S", "W"):
        return -decimal
    return decimal


def _extract_gps(exif: Image.Exif) -> tuple[float, float] | None:
    """Read the GPS IFD and return `(latitude, longitude)`, or `None` if any
    of the four required tags is missing or malformed.

    Deliberately all-or-nothing: a partially-decoded coordinate (e.g. a
    latitude with no matching reference) is not a usable location, and
    guessing a default reference would silently corrupt it — so any failure
    here falls back to `None` rather than a half-filled pair.
    """
    gps_ifd = exif.get_ifd(_IFD_GPS)

    latitude_ref = gps_ifd.get(_TAG_GPS_LATITUDE_REF)
    latitude_dms = gps_ifd.get(_TAG_GPS_LATITUDE)
    longitude_ref = gps_ifd.get(_TAG_GPS_LONGITUDE_REF)
    longitude_dms = gps_ifd.get(_TAG_GPS_LONGITUDE)

    if not (latitude_ref and latitude_dms and longitude_ref and longitude_dms):
        return None

    try:
        latitude = _dms_to_decimal(latitude_dms, latitude_ref)
        longitude = _dms_to_decimal(longitude_dms, longitude_ref)
    except (TypeError, ValueError):
        return None

    return latitude, longitude


def _reencode_without_metadata(image: Image.Image, *, format: str) -> bytes:
    """Bake EXIF orientation into the pixels, then re-save with no metadata
    at all.

    Pillow only writes an EXIF block into `save()`'s output when `exif=` is
    passed explicitly — it never falls back to the source image's own
    `.info["exif"]` on its own (verified for JPEG/PNG/WEBP; see
    `tests/test_exif_processing.py::test_rewritten_image_bytes_carry_no_exif_block`
    for the literal proof), so simply never passing `exif=` is already
    sufficient there.

    ICC color profiles are a *different* code path, though: `ImageOps.
    exif_transpose` copies the source image's `.info` dict onto the
    transposed copy (including `.info["icc_profile"]` when present), and
    unlike EXIF, PNG's saver falls back to `im.info["icc_profile"]` when
    `save()` doesn't pass `icc_profile=` explicitly (JPEG/WEBP don't have
    this fallback, but passing it unconditionally costs nothing and is
    format-agnostic). So `icc_profile=None` below is not a redundant
    no-op — for PNG specifically, it is the one line that actually
    prevents a re-embedded profile from surviving; see
    `tests/test_exif_processing.py::test_rewritten_png_bytes_carry_no_icc_profile`.
    """
    transposed = ImageOps.exif_transpose(image)

    buffer = io.BytesIO()
    transposed.save(buffer, format=format, icc_profile=None)
    return buffer.getvalue()


def process_photo_metadata(image: Image.Image, *, share_location: bool) -> ExtractedPhotoMetadata:
    """Extract timeline/location metadata from `image` and re-encode it with
    no EXIF block, applying the orientation tag to the pixels first.

    `image` is expected to already be `app.services.image_processing.
    validate_upload`'s output: decoded, format-checked, and loaded. GPS is
    read here regardless of `share_location` (so the decision below has
    something to discard), but `latitude`/`longitude`/`location_source` on
    the result are populated only when `share_location=True` — with it
    `False`, they are always `None`, never partially filled.
    """
    # `image.format` is lost on the transposed copy `ImageOps.exif_transpose`
    # returns, so it has to be captured now, from the original.
    original_format = image.format

    exif = image.getexif()
    captured_at = _extract_captured_at(exif)
    gps = _extract_gps(exif)

    should_record_location = share_location and gps is not None
    latitude, longitude = gps if should_record_location else (None, None)
    location_source = "exif" if should_record_location else None

    image_bytes = _reencode_without_metadata(image, format=original_format)

    return ExtractedPhotoMetadata(
        captured_at=captured_at,
        latitude=latitude,
        longitude=longitude,
        location_source=location_source,
        image_bytes=image_bytes,
        content_type=_content_type_for(original_format),
    )
