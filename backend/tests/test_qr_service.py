"""Tests for `app/services/qr_service.py` — QR code image generation for a
region's `qr_token` (issue #30). See docs/architecture.md §7.

The "content is exactly the token URL" criterion is proven by real QR
decoding, not by inspecting bytes: PNG output is decoded directly with
`zxing-cpp` (a pure-wheel binding, no system `libzbar` needed — that's why
`zxing-cpp` was chosen over `pyzbar`, which requires a system library this
environment doesn't have installed). SVG output can't be decoded directly
(no barcode reader accepts SVG), so it's rasterized to PNG with `cairosvg`
first, then decoded the same way. Both are dev-only dependencies
(`pyproject.toml`), never imported by application code.
"""

import io

import cairosvg
import pytest
import zxingcpp
from PIL import Image

from app.core.config import settings
from app.services import qr_service
from app.services.qr_service import MAX_BOX_SIZE, InvalidQrCodeSize

_QR_TOKEN = "tok_abc123XYZ"


def _expected_url(qr_token: str) -> str:
    # Mirrors qr_service's own URL assembly, against the real configured
    # `PUBLIC_WEB_BASE_URL` (backend/.env) rather than a hardcoded host —
    # this test suite doesn't override that setting per-test.
    return f"{str(settings.public_web_base_url).rstrip('/')}/r/{qr_token}"


def _decode_png(png_bytes: bytes) -> str:
    [result] = zxingcpp.read_barcodes(Image.open(io.BytesIO(png_bytes)))
    return result.text


def _decode_svg(svg_bytes: bytes) -> str:
    # `SvgPathImage` draws only the dark modules' `<path>` — no background
    # `<rect>` — so `cairosvg` rasterizes everything else as transparent,
    # not white (RGBA (0, 0, 0, 0), same R/G/B as a dark module). That's
    # fine on paper/a white page, which is this SVG's real target, but a
    # decoder reading the raw RGBA can't tell a transparent pixel from a
    # black one. Flattening onto white here reproduces that real target
    # instead of reading the never-intended "on black" composite.
    rgba_image = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg_bytes))).convert("RGBA")
    white_background = Image.new("RGBA", rgba_image.size, "white")
    flattened = Image.alpha_composite(white_background, rgba_image).convert("RGB")

    buffer = io.BytesIO()
    flattened.save(buffer, format="PNG")
    return _decode_png(buffer.getvalue())


def test_generate_qr_code_png_encodes_the_token_url() -> None:
    image_bytes, content_type = qr_service.generate_qr_code(_QR_TOKEN, format="png")

    assert content_type == "image/png"
    assert _decode_png(image_bytes) == _expected_url(_QR_TOKEN)


def test_generate_qr_code_svg_encodes_the_token_url() -> None:
    image_bytes, content_type = qr_service.generate_qr_code(_QR_TOKEN, format="svg")

    assert content_type == "image/svg+xml"
    assert _decode_svg(image_bytes) == _expected_url(_QR_TOKEN)


def test_generate_qr_code_svg_is_xml_bytes() -> None:
    image_bytes, _content_type = qr_service.generate_qr_code(_QR_TOKEN, format="svg")

    assert image_bytes.lstrip().startswith(b"<?xml")


def test_generate_qr_code_size_controls_box_size() -> None:
    """`?size=` is passed through as `qrcode`'s `box_size` (pixels per QR
    module), not a total-pixel target — see qr_service.py's module docstring
    for why. A bigger box_size must produce a visibly bigger PNG.
    """
    small_bytes, _ = qr_service.generate_qr_code(_QR_TOKEN, format="png", size=4)
    large_bytes, _ = qr_service.generate_qr_code(_QR_TOKEN, format="png", size=20)

    small_image = Image.open(io.BytesIO(small_bytes))
    large_image = Image.open(io.BytesIO(large_bytes))

    assert large_image.width > small_image.width
    assert large_image.width == small_image.width * 5  # 20 / 4


def test_generate_qr_code_without_size_uses_a_sensible_default() -> None:
    image_bytes, _content_type = qr_service.generate_qr_code(_QR_TOKEN, format="png")

    image = Image.open(io.BytesIO(image_bytes))
    assert image.width > 0
    assert _decode_png(image_bytes) == _expected_url(_QR_TOKEN)


@pytest.mark.parametrize("size", [0, -1, -100])
def test_generate_qr_code_rejects_non_positive_size(size: int) -> None:
    with pytest.raises(InvalidQrCodeSize):
        qr_service.generate_qr_code(_QR_TOKEN, format="png", size=size)


@pytest.mark.parametrize("size", [MAX_BOX_SIZE + 1, MAX_BOX_SIZE + 1000, 10_000])
def test_generate_qr_code_rejects_size_above_the_cap(size: int) -> None:
    """Regression test: an unbounded `size` maps straight to `qrcode`'s
    `box_size`, which scales the rendered pixel buffer large enough to OOM
    a worker from a single unauthenticated request — see
    `qr_service.MAX_BOX_SIZE`'s comment for the measurements that set this
    cap. `size=10_000` specifically reproduces the case that was observed to
    kill the process outright before this cap existed.
    """
    with pytest.raises(InvalidQrCodeSize):
        qr_service.generate_qr_code(_QR_TOKEN, format="png", size=size)


def test_generate_qr_code_accepts_size_at_the_cap() -> None:
    image_bytes, _content_type = qr_service.generate_qr_code(
        _QR_TOKEN, format="png", size=MAX_BOX_SIZE
    )

    assert _decode_png(image_bytes) == _expected_url(_QR_TOKEN)


def test_generate_qr_code_different_tokens_encode_different_urls() -> None:
    first_bytes, _ = qr_service.generate_qr_code("token-one", format="png")
    second_bytes, _ = qr_service.generate_qr_code("token-two", format="png")

    assert _decode_png(first_bytes) == _expected_url("token-one")
    assert _decode_png(second_bytes) == _expected_url("token-two")
