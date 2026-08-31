"""Photo response schemas: the timeline listing at
`GET /api/plantings/{planting_id}/photos`. See docs/architecture.md §4.3/§4.4
for the columns this derives from and §5.2 for why `storage_key` never leaves
the backend.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, computed_field


class PhotoOut(BaseModel):
    """A single photo in a planting's timeline.

    `latitude`/`longitude` are derived from the `location` PostGIS column at
    query time (architecture.md §4.4) — never the raw geometry, and never
    `storage_key`, which is opaque to callers (architecture.md §5.2).
    """

    id: uuid.UUID
    description: str | None
    contributor_name: str | None
    captured_at: datetime | None
    uploaded_at: datetime
    latitude: float | None
    longitude: float | None
    # Recorded on upload (issue #20), never re-derived here — this is what
    # lets the frontend timeline (issue #24) set the `<img>` `width`/`height`
    # attributes up front, so the browser reserves the image's layout space
    # before it loads instead of reflowing the page once it does.
    width: int
    height: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def photo_url(self) -> str:
        """Where the actual image bytes live (architecture.md §5.2).

        Served by `GET /api/photos/{photo_id}/file` (issue #22,
        `app/api/routes/photos.py`).
        """
        return f"/api/photos/{self.id}/file"


class PhotoPage(BaseModel):
    """Paginated response for `GET /api/plantings/{planting_id}/photos`.

    Keyset (not offset) pagination — see
    `app.services.photo_service.list_planting_photos` for why. `next_cursor`
    is `None` once there is nothing more to fetch; callers should stop on
    that, not on `len(items) < limit`, since a full page can still be the
    last one.
    """

    items: list[PhotoOut]
    next_cursor: str | None
