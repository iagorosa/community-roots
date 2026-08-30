"""Tests for `app/services/image_processing.py`: upload byte validation.

See docs/architecture.md §6.1 for the order of checks these tests exercise —
size while streaming, real (decoded) format, decompression-bomb ceiling.

No `client`/`db_session` fixture is used anywhere here: this module never
touches the database or an HTTP request, only raw bytes, so these tests stay
as cheap and isolated as `tests/test_storage_local.py`.
"""

import io

import pytest
from PIL import Image

from app.services import image_processing
from app.services.image_processing import ImageTooLarge, InvalidImage, validate_upload


def _encode(*, format: str, width: int = 32, height: int = 32) -> bytes:
    """Build real, decodable image bytes in `format` — never a mock."""
    image = Image.new("RGB", (width, height), color=(10, 20, 30))
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


class _StreamThatFailsIfReadUnboundedOrTooFar:
    """A fake stream that proves `_read_within_limit` never buffers more than
    `max_bytes` plus one chunk, no matter how much data is behind it.

    Two invariants are enforced on every `.read()` call, and either one
    failing means the size limit isn't really applied during streaming:

    1. The caller must always pass a bounded `size` — a call with no size
       (or a falsy one) would mean "read everything at once", which is
       exactly the whole-file-buffering bug this test exists to catch.
    2. `.read()` must never be called again once the running total has
       already crossed `max_bytes` — that would mean the implementation
       kept pulling bytes from an oversized upload instead of aborting the
       moment it knew the limit was exceeded.

    The stream never runs out on its own (every call returns `size` bytes of
    filler) — an attacker-controlled upload has no natural end either, so
    the only thing that can stop the read loop is the limit check itself.
    """

    def __init__(self, *, max_bytes: int) -> None:
        self._max_bytes = max_bytes
        self._served = 0

    def read(self, size: int | None = None) -> bytes:
        if not size or size <= 0:
            raise AssertionError(
                "read() was called without a bounded size — this would try "
                "to buffer the whole (attacker-controlled) stream at once."
            )
        if self._served > self._max_bytes:
            raise AssertionError(
                "read() was called again after the running total already "
                "exceeded max_bytes — the limit isn't aborting early."
            )
        self._served += size
        return b"\xff" * size


def test_valid_jpeg_is_accepted_and_decoded() -> None:
    stream = io.BytesIO(_encode(format="JPEG"))

    image = validate_upload(stream)

    assert image.format == "JPEG"


def test_valid_png_is_accepted_and_decoded() -> None:
    stream = io.BytesIO(_encode(format="PNG"))

    image = validate_upload(stream)

    assert image.format == "PNG"


def test_valid_webp_is_accepted_and_decoded() -> None:
    stream = io.BytesIO(_encode(format="WEBP"))

    image = validate_upload(stream)

    assert image.format == "WEBP"


def test_bytes_that_are_not_an_image_are_rejected_even_with_a_jpg_name() -> None:
    # The file's name/extension is never even passed to `validate_upload` —
    # only bytes go in, which is itself the proof that the extension can't
    # influence the decision. The `.jpg`-flavored variable name documents
    # the scenario the "critério de pronto" describes.
    fake_dot_jpg_bytes = b"this is definitely not image data, just text"

    with pytest.raises(InvalidImage):
        validate_upload(io.BytesIO(fake_dot_jpg_bytes))


def test_image_format_outside_the_allow_list_is_rejected() -> None:
    # GIF is a real, Pillow-decodable format — just not one of
    # settings.allowed_image_formats (JPEG/PNG/WEBP) — so this proves the
    # allow-list is enforced, not just "did Pillow decode it".
    stream = io.BytesIO(_encode(format="GIF"))

    with pytest.raises(InvalidImage):
        validate_upload(stream)


def test_bmp_format_outside_the_allow_list_is_rejected() -> None:
    stream = io.BytesIO(_encode(format="BMP"))

    with pytest.raises(InvalidImage):
        validate_upload(stream)


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_image_exceeding_max_image_pixels_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    # A tiny image in bytes, but with a pixel count forced over a
    # deliberately lowered ceiling — proves the check is against decoded
    # dimensions, not file size, without needing a real multi-gigapixel file.
    #
    # Pillow itself warns (DecompressionBombWarning) for this ratio — expected
    # and silenced here, since asserting on `InvalidImage` below is the real
    # proof; `image_processing` already silences this warning at import time
    # for production, but pytest's own warning capture re-arms it per test.
    #
    # 144 pixels against a ceiling of 100 is only a 1.44x overshoot —
    # deliberately *inside* Pillow's own "warn but don't raise" band (it
    # only raises past 2x the ceiling on its own). That's the point: this
    # ratio can only be caught by `validate_upload`'s own explicit
    # width*height check, so this test fails if that check is ever removed
    # — unlike a >2x overshoot, which Pillow's internal guard would catch
    # on its own and give a false sense that this module's check matters.
    monkeypatch.setattr(image_processing, "MAX_IMAGE_PIXELS", 100)
    stream = io.BytesIO(_encode(format="PNG", width=12, height=12))  # 144 pixels > 100, < 200

    with pytest.raises(InvalidImage):
        validate_upload(stream)


def test_file_above_the_byte_limit_is_rejected() -> None:
    oversized_bytes = _encode(format="PNG", width=200, height=200)
    stream = io.BytesIO(oversized_bytes)

    with pytest.raises(ImageTooLarge):
        validate_upload(stream, max_bytes=10)


def test_image_too_large_message_reads_in_whole_megabytes_for_a_round_limit() -> None:
    """The "critério de pronto" of issue #28 requires that this message be
    actionable for a non-technical user — raw byte counts (e.g. "10485760
    bytes") don't clear that bar, a rounded MB figure does. 10_485_760 is
    exactly 10 MiB (the shipped `settings.max_upload_bytes` default), so it
    must read as a clean "10 MB", not "10.0 MB".
    """
    error = ImageTooLarge(10_485_760)

    assert error.detail == "O arquivo excede o limite de 10 MB."


def test_image_too_large_message_rounds_a_fractional_limit_to_one_decimal() -> None:
    """1_572_864 bytes is exactly 1.5 MiB — proves the conversion isn't just
    truncating to whole megabytes for a limit that doesn't land on one.
    """
    error = ImageTooLarge(1_572_864)

    assert error.detail == "O arquivo excede o limite de 1.5 MB."


def test_image_too_large_message_never_contains_a_raw_byte_count() -> None:
    error = ImageTooLarge(10_485_760)

    assert "10485760" not in error.detail
    assert "bytes" not in error.detail


def test_file_above_the_byte_limit_is_rejected_after_several_chunks() -> None:
    # Unlike `test_file_above_the_byte_limit_is_rejected` (which trips on the
    # very first 64 KiB chunk), this picks a limit several chunks in, so the
    # running-total accumulation across loop iterations — not just the
    # first-chunk check — is what `_read_within_limit` is proven against.
    # Content doesn't need to decode as an image: the size check runs, and
    # must raise, before any bytes ever reach Pillow.
    chunk_size = image_processing._READ_CHUNK_SIZE
    max_bytes = chunk_size * 2 + 100
    oversized_bytes = b"\x00" * (chunk_size * 3)
    stream = io.BytesIO(oversized_bytes)

    with pytest.raises(ImageTooLarge):
        validate_upload(stream, max_bytes=max_bytes)


def test_oversized_upload_is_rejected_without_buffering_the_whole_stream() -> None:
    """The critical proof for this issue's "security" label: rejecting an
    over-limit upload must not first read/buffer an amount of data
    proportional to the (potentially huge) upload size.

    `_StreamThatFailsIfReadUnboundedOrTooFar` stands in for an attacker
    sending unbounded data — it never ends on its own — and raises
    `AssertionError` itself if `validate_upload` ever reads unboundedly or
    keeps reading after the limit is already exceeded. If the
    `ImageTooLarge` below is raised, it can only be because the streaming
    limit aborted the read loop early; if the implementation instead tried
    to drain the stream (e.g. `stream.read()` with no size, or a loop that
    doesn't check the running total until after accumulating everything),
    the fake stream raises `AssertionError` first, which fails this test
    with a different, unambiguous error — not `ImageTooLarge`.
    """
    max_bytes = 1_000
    stream = _StreamThatFailsIfReadUnboundedOrTooFar(max_bytes=max_bytes)

    with pytest.raises(ImageTooLarge):
        validate_upload(stream, max_bytes=max_bytes)
