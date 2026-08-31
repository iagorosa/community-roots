"""`storage_key` generation for a newly uploaded photo:
`plantings/{planting_id}/{ano}/{uuid4}.{ext}` — collision-free, cheap to
list by muda, never derived from anything a client sends (the `uuid4`
avoids collisions on its own; a client-supplied filename is never part of
the key).
"""

import uuid
from datetime import UTC, datetime


def generate_storage_key(
    planting_id: uuid.UUID, *, extension: str, now: datetime | None = None
) -> str:
    """Build the `storage_key` for a new photo of `planting_id`.

    `extension` must come from the image format decoded server-side, never
    the client's filename. `now` defaults to the current UTC time; a caller
    passes it explicitly only to get a deterministic key in a test.

    Raises `ValueError` for a malformed `extension` (empty, a stray leading/
    trailing dot, or an embedded `/`) — a future bug in the Pillow-format-to-
    extension mapping should fail loudly here instead of writing a malformed
    `storage_key` to the database.
    """
    if not extension or extension.startswith(".") or extension.endswith(".") or "/" in extension:
        raise ValueError(f"extension inválida para storage_key: {extension!r}")

    year = (now or datetime.now(UTC)).year
    return f"plantings/{planting_id}/{year}/{uuid.uuid4()}.{extension}"
