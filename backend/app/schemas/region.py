"""Region schemas: the GeoJSON `properties` shape and the admin request
bodies for create/update. See docs/architecture.md §4.2/§5.1.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.geojson import Feature, FeatureCollection, MultiPolygon, Point, Polygon

RegionStatus = Literal["active", "draft", "archived"]

# The three geometry shapes the `ck_regions_geom_type` CHECK constraint
# allows (app/models/region.py). `discriminator="type"` makes FastAPI render
# this as an explicit `oneOf` in `/docs`, matched on the GeoJSON `type` field
# PostGIS's `ST_AsGeoJSON` always includes.
RegionGeometry = Annotated[Point | Polygon | MultiPolygon, Field(discriminator="type")]


class RegionProperties(BaseModel):
    """The `properties` object of a region `Feature` — architecture.md §5.1."""

    slug: str
    name: str
    description: str | None
    status: RegionStatus
    qr_token: str
    photo_count: int
    latest_photo_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RegionFeature(Feature[RegionGeometry, RegionProperties]):
    """A single region, as returned by `GET /api/regions/{region}`."""


class RegionFeatureCollection(FeatureCollection[RegionGeometry, RegionProperties]):
    """The region list, as returned by `GET /api/regions`."""

    # Overrides the inherited generic field so `/docs` reuses the named
    # `RegionFeature` schema here instead of synthesizing an unnamed
    # duplicate from the parametrized generic base.
    features: list[RegionFeature]


class RegionCreate(BaseModel):
    """Admin request body for `POST /api/regions`.

    `extra="forbid"`: `slug`/`qr_token` are server-generated
    (`region_service.py`, issue #12), so a client payload that includes them
    must error loudly instead of having them silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    geometry: RegionGeometry
    status: RegionStatus = "active"


class RegionUpdate(BaseModel):
    """Admin request body for `PATCH /api/regions/{region}` — every field optional."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    geometry: RegionGeometry | None = None
    status: RegionStatus | None = None
