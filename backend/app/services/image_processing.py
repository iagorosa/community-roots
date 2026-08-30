"""Upload byte validation: turns a raw stream into a decoded, format-checked
`Image.Image`, independent of the future upload endpoint (issue #28/#29) that
will call it. This module only validates — it never rewrites, strips EXIF, or
extracts `captured_at`/GPS (that's issue #27).

Checks run in the order docs/architecture.md §6.1 describes; the first
failure rejects the upload:

1. **Size**, enforced while `stream` is being read (`_read_within_limit`).
   The running total is checked chunk by chunk, so a too-large upload is
   caught after at most one chunk past `max_bytes` — never after the whole
   file (however large) has been buffered. This is the property the
   "security" label on issue #26 cares about most; see
   `tests/test_image_processing.py::test_oversized_upload_is_rejected_without_buffering_the_whole_stream`
   for the proof.
2. **Real format**, read from `Image.format` on the *decoded* image. The
   client's `Content-Type` header and the upload's filename/extension never
   reach this module at all, so neither can influence this decision.
3. **Decompression-bomb ceiling** (`MAX_IMAGE_PIXELS`), checked against the
   dimensions `Image.open` reads from the file header — before the pixel
   buffer itself is decoded — so a small file claiming absurd dimensions is
   rejected without allocating memory proportional to those dimensions.
"""

import io
import warnings
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import ValidationFailedError

# One 64 KiB read per loop iteration: small enough that a rejected upload
# never buffers much past `max_bytes`, large enough to not dominate runtime
# with per-call overhead.
_READ_CHUNK_SIZE = 64 * 1024

# A module constant, not a `Settings` field: this is an internal defense
# against Pillow decoding an absurd pixel grid, not product policy an
# operator would tune per environment the way `max_upload_bytes` or
# `allowed_image_formats` are. 64 megapixels comfortably covers real
# phone-camera photos (a 48 MP main sensor is common; even 108 MP sensors
# typically pixel-bin their default JPEG output down to ~12-27 MP) while
# still refusing a small file that decodes into a multi-gigabyte pixel
# buffer — within the 50-100 MP range docs/architecture.md's issue calls for.
MAX_IMAGE_PIXELS = 64_000_000

# Pillow's own bomb guard only *warns* (never raises) for images between 1x
# and 2x MAX_IMAGE_PIXELS — `validate_upload` enforces the exact boundary
# itself (see the explicit dimension check below), so that warning is pure
# noise here. Silenced once, at import time, rather than per-call with
# `warnings.catch_warnings()`: that context manager mutates a *global*
# filter stack and isn't thread-safe, and this module's sync function may
# run concurrently across FastAPI's threadpool once the upload endpoint
# (issue #28/#29) calls it from multiple requests at once.
warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)


class InvalidImage(ValidationFailedError):
    code = "invalid_image"

    def __init__(self) -> None:
        # Deliberately generic: never echoes the client's bytes, Content-Type
        # or filename back (architecture.md §5.3 — user-facing text must be
        # safe to display, and none of those are safe to repeat here).
        super().__init__("O arquivo enviado não é uma imagem válida.")


def _format_max_size_in_mb(max_bytes: int) -> str:
    """Render `max_bytes` as a MB figure a non-technical user can act on.

    Raw byte counts (e.g. "10485760 bytes") aren't a unit most people
    reason about; MB is. Uses the everyday 1024*1024 reading of "MB" (not
    the strict SI 1_000_000-byte megabyte) since that's how
    `settings.max_upload_bytes`'s shipped default (10_485_760) was actually
    chosen — that convention is what turns it into a clean "10 MB" instead
    of "10.5 MB". Rounded to one decimal place, with a trailing ".0"
    trimmed so a round limit reads as "10 MB", not "10.0 MB".
    """
    megabytes = max_bytes / (1024 * 1024)
    return f"{megabytes:.1f}".rstrip("0").rstrip(".")


class ImageTooLarge(ValidationFailedError):
    code = "image_too_large"

    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"O arquivo excede o limite de {_format_max_size_in_mb(max_bytes)} MB.")


def _read_within_limit(stream: BinaryIO, *, max_bytes: int) -> bytes:
    """Read `stream` in fixed-size chunks, aborting the instant the running
    total passes `max_bytes`.

    The accumulated chunks never total more than `max_bytes + _READ_CHUNK_SIZE`
    bytes: each chunk is only appended after the running total (checked
    *before* appending) is confirmed to still be within bounds, so an
    oversized upload is caught after reading at most one chunk past the
    limit — never after the stream is fully drained.
    """
    chunks: list[bytes] = []
    total_bytes_read = 0

    while True:
        chunk = stream.read(_READ_CHUNK_SIZE)
        if not chunk:
            break

        total_bytes_read += len(chunk)
        if total_bytes_read > max_bytes:
            raise ImageTooLarge(max_bytes)

        chunks.append(chunk)

    return b"".join(chunks)


def validate_upload(stream: BinaryIO, *, max_bytes: int = settings.max_upload_bytes) -> Image.Image:
    """Validate an uploaded photo's bytes and return the decoded image.

    Raises `ImageTooLarge` if `stream` yields more than `max_bytes` bytes,
    and `InvalidImage` if the bytes — once confirmed within the size limit —
    don't decode into one of `settings.allowed_image_formats` with Pillow.
    That covers bytes that aren't an image at all, images in a real but
    disallowed format, and images past `MAX_IMAGE_PIXELS`. A raw Pillow
    exception never escapes this function.
    """
    raw_bytes = _read_within_limit(stream, max_bytes=max_bytes)

    try:
        # `Image.MAX_IMAGE_PIXELS` is a Pillow-global switch, not a
        # parameter — set on every call (one cheap attribute write) so this
        # module's limit always wins regardless of what else in the process
        # may have touched it, and so tests can monkeypatch this module's
        # `MAX_IMAGE_PIXELS` and see it take effect immediately.
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

        # `Image.open` only parses the header at this point — pixel data
        # isn't decoded yet, and `image.format` is already known — so both
        # checks below run before any pixel buffer is allocated. Order
        # matches docs/architecture.md §6.1: format, then the pixel
        # ceiling, so a disallowed-format file (e.g. GIF/BMP) is rejected
        # without ever paying for `image.load()`'s full decode.
        image = Image.open(io.BytesIO(raw_bytes))

        if image.format not in settings.allowed_image_formats:
            raise InvalidImage()

        # (Pillow's own internal guard would still raise past 2x
        # MAX_IMAGE_PIXELS on its own; this check catches the 1x-2x gap it
        # only warns about, per the module-level `filterwarnings` above.)
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise InvalidImage()

        image.load()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        raise InvalidImage() from None

    return image
