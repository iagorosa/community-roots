"""Photo response schemas: the timeline listing at
`GET /api/regions/{region}/photos`. See docs/architecture.md §4.3/§4.4 for
the columns this derives from and §5.2 for why `storage_key` never leaves the
backend.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, computed_field


class PhotoOut(BaseModel):
    """A single photo in a region's timeline.

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def photo_url(self) -> str:
        """Where the actual image bytes live (architecture.md §5.2).

        `GET /api/photos/{photo_id}/file` is issue #22, not built yet —
        this only points at the URL by convention so the frontend has a
        stable field to render from once that route exists.
        """
        return f"/api/photos/{self.id}/file"


class PhotoPage(BaseModel):
    """Paginated response for `GET /api/regions/{region}/photos`.

    Keyset (not offset) pagination — see
    `app.services.photo_service.list_region_photos` for why. `next_cursor`
    is `None` once there is nothing more to fetch; callers should stop on
    that, not on `len(items) < limit`, since a full page can still be the
    last one.
    """

    items: list[PhotoOut]
    next_cursor: str | None
