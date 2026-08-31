"""Tests for `app/storage/keys.py`: the `storage_key` format for a newly
uploaded photo — `plantings/{planting_id}/{ano}/{uuid4}.{ext}`, collision-free,
never derived from user input, cheap to list by muda.
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.storage.keys import generate_storage_key


def test_generate_storage_key_follows_the_documented_format() -> None:
    planting_id = uuid.uuid4()

    key = generate_storage_key(planting_id, extension="jpg", now=datetime(2026, 8, 30, tzinfo=UTC))

    prefix, key_planting_id, year, filename = key.split("/")
    assert prefix == "plantings"
    assert key_planting_id == str(planting_id)
    assert year == "2026"
    name, ext = filename.rsplit(".", 1)
    assert ext == "jpg"
    assert uuid.UUID(name)  # the filename stem is a valid uuid4


def test_generate_storage_key_is_scoped_to_the_given_planting() -> None:
    planting_id = uuid.uuid4()

    key = generate_storage_key(planting_id, extension="png", now=datetime(2026, 1, 1, tzinfo=UTC))

    assert key.startswith(f"plantings/{planting_id}/")


def test_generate_storage_key_is_never_derived_from_user_input() -> None:
    """Nothing about the key depends on a caller-supplied filename — only
    `planting_id` (server-resolved) and `extension` (from the decoded image
    format, never the client's filename)."""
    planting_id = uuid.uuid4()

    first = generate_storage_key(
        planting_id, extension="jpg", now=datetime(2026, 8, 30, tzinfo=UTC)
    )
    second = generate_storage_key(
        planting_id, extension="jpg", now=datetime(2026, 8, 30, tzinfo=UTC)
    )

    assert first != second  # collision-free per call, not memoized on input


@pytest.mark.parametrize("bad_extension", ["", ".jpg", "jpg.", "jp/g"])
def test_generate_storage_key_rejects_a_malformed_extension(bad_extension: str) -> None:
    """`extension` must come from the Pillow-decoded image format, never
    client input — but a future caller bug in that format-to-extension
    mapping (a stray leading dot, an empty string) should fail loudly here
    instead of writing a malformed `storage_key` to the database.
    """
    with pytest.raises(ValueError, match="extension"):
        generate_storage_key(uuid.uuid4(), extension=bad_extension)
