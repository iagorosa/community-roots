"""Unit tests for `app/services/photo_upload_service.py` internals that
aren't easily reached through the HTTP route in
`tests/test_photo_upload_route.py` — currently just the storage-key
extension mapping.
"""

import pytest

from app.services.photo_upload_service import _extension_for_content_type


@pytest.mark.parametrize(
    ("content_type", "expected_extension"),
    [
        ("image/jpeg", "jpg"),
        ("image/png", "png"),
        ("image/webp", "webp"),
    ],
)
def test_extension_for_content_type_matches_the_allowed_formats(
    content_type: str, expected_extension: str
) -> None:
    assert _extension_for_content_type(content_type) == expected_extension


def test_extension_for_content_type_raises_loudly_for_an_unmapped_content_type() -> None:
    """`app/storage/keys.py`'s own docstring states the principle this
    enforces: "a future bug in the Pillow-format-to-extension mapping
    should fail loudly ... instead of writing a malformed storage_key to
    the database." A silent fallback (e.g. a generic ".bin" extension)
    would violate that the moment `settings.allowed_image_formats` grows a
    format this mapping doesn't know about yet.
    """
    with pytest.raises(ValueError, match="image/gif"):
        _extension_for_content_type("image/gif")
