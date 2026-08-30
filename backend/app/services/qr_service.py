"""QR code image generation for a region's `qr_token` — issue #30, see
docs/architecture.md §7.

`generate_qr_code` is deliberately pure: it takes a `qr_token` string and
returns image bytes, nothing else. It never resolves a region, never touches
`Session` — that resolution (slug-or-UUID → `qr_token`) belongs to the route/
`region_service`, same split as the other pure, easily-unit-tested functions
`app/services/image_processing.py` and `app/services/exif_processing.py` built
for issues #25-#27. Keeping this function free of the DB and FastAPI makes it
trivial to test in isolation (see `tests/test_qr_service.py`) and reusable
later by the Fase 6 print-sheet endpoint the architecture doc mentions.

The token, not the slug, is what gets encoded — a physical QR code, once
printed and installed on a bed, is expensive to reprint, so the URL it
carries must survive the region being renamed (see docs/architecture.md §7
and `region_service.slugify`/`_generate_unique_slug`).

Nothing here ever touches disk: both formats are built entirely in memory
(`io.BytesIO`) and handed back as bytes, so "regenerate is cheap, no stale
file ever exists" holds by construction, not by a cleanup job.
"""

import io
from typing import Literal

import qrcode
import qrcode.image.svg

from app.core.config import settings
from app.core.errors import ValidationFailedError

# Matches `qrcode.QRCode`'s own default box_size (pixels per QR module) —
# unremarkable, legible at normal screen/print sizes, and the same value a
# caller gets by not passing `?size=` to `qrcode.make()` directly.
_DEFAULT_BOX_SIZE = 10

# `box_size` scales the rendered pixel buffer roughly quadratically (both
# width and height grow with it), and this endpoint takes `size` from an
# unauthenticated public request with no rate limiting anywhere in the app
# (architecture.md doesn't call for any yet). Measured directly against this
# function: box_size=200 stays under ~100 MB RSS and ~0.6s, but box_size=1000
# already costs ~1.4 GB RSS and ~3s, and box_size=10000 OOM-kills the
# process outright — so an ungated `?size=` is a one-request DoS. 100 is
# comfortably inside the safe range measured above (~60 MB RSS) while still
# producing an image far larger than any real print/screen use needs (100
# px/module on even a small QR version is already thousands of pixels per
# side). Enforced both here and in the route's `Query(le=MAX_BOX_SIZE)`, so
# a direct caller (a future print-sheet endpoint, a script) can't bypass it
# just by skipping the route.
MAX_BOX_SIZE = 100

# The QR spec's "quiet zone": a border of at least 4 modules around the
# code is what keeps scanners reliable. Not exposed via `?size=` — that
# query param controls box_size only (see `generate_qr_code`'s docstring)
# — because shrinking the quiet zone is a scan-reliability risk, not a
# cosmetic size choice a caller should casually override.
_BORDER_MODULES = 4

# `SvgPathImage` renders every dark module as segments of a *single* SVG
# `<path>`, instead of `SvgImage`/`SvgFragmentImage`'s one `<rect>` per
# module. Measured on a same-content QR code (see the implementation notes
# in tests/test_qr_service.py's module docstring for how this was checked):
# ~4.9 KB vs ~17.3 KB — the path form is the "cleanest/most compact" option
# the issue asks for, and it's still a real, standalone SVG document (not a
# `<svg>`-less fragment), same as what a browser or print pipeline expects.
_SVG_IMAGE_FACTORY = qrcode.image.svg.SvgPathImage

_CONTENT_TYPES: dict[str, str] = {
    "png": "image/png",
    "svg": "image/svg+xml",
}


class InvalidQrCodeSize(ValidationFailedError):
    code = "invalid_qr_code_size"

    def __init__(self, size: int) -> None:
        super().__init__(
            f'O parâmetro "size" precisa estar entre 1 e {MAX_BOX_SIZE} (recebido: {size}).'
        )


def generate_qr_code(
    qr_token: str,
    *,
    format: Literal["png", "svg"],
    size: int | None = None,
) -> tuple[bytes, str]:
    """Encode `{PUBLIC_WEB_BASE_URL}/r/{qr_token}` as a QR code image.

    Returns `(image_bytes, content_type)`. Raises `InvalidQrCodeSize` if
    `size` is given and falls outside `1..MAX_BOX_SIZE` (see that
    constant's comment for why the upper bound exists).

    `size`, when given, is passed straight through as `qrcode`'s `box_size`
    (pixels *per module*), not a total-pixel target for the whole image.
    Hitting an exact total pixel count isn't possible in one pass: the
    QR version (and therefore the module count the total depends on) is only
    known after encoding, since it's driven by the URL's length — which
    varies with `qr_token`'s length. A second, corrective encode pass would
    be needed to hit an exact total, which isn't worth the complexity for
    what is effectively an internal/print tool. A caller after a specific
    pixel size can scale the output client-side instead — losslessly for
    SVG, or via a standard image resize for PNG.
    """
    if size is not None and not (1 <= size <= MAX_BOX_SIZE):
        raise InvalidQrCodeSize(size)
    box_size = size if size is not None else _DEFAULT_BOX_SIZE

    token_url = f"{str(settings.public_web_base_url).rstrip('/')}/r/{qr_token}"

    if format == "png":
        image = qrcode.make(token_url, box_size=box_size, border=_BORDER_MODULES)
    elif format == "svg":
        image = qrcode.make(
            token_url,
            box_size=box_size,
            border=_BORDER_MODULES,
            image_factory=_SVG_IMAGE_FACTORY,
        )
    else:
        # Unreachable through the route, which restricts `format` to
        # `Literal["png", "svg"]` at the FastAPI/Pydantic layer before this
        # function is ever called — but Python doesn't enforce `Literal` at
        # runtime, so a direct caller (another service, a future script)
        # that passes anything else must fail loudly, not silently produce
        # one format while claiming another.
        raise ValueError(f'Formato de QR code não suportado: "{format}".')

    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue(), _CONTENT_TYPES[format]
