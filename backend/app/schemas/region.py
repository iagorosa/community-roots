"""Region schemas: the GeoJSON `properties` shape and the admin request
bodies for create/update. See docs/architecture.md §4.2/§5.1.
"""

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.geojson import Feature, FeatureCollection, MultiPolygon, Point, Polygon

RegionStatus = Literal["active", "draft", "archived"]

# The three geometry shapes the `ck_regions_geom_type` CHECK constraint
# allows (app/models/region.py). `discriminator="type"` makes FastAPI render
# this as an explicit `oneOf` in `/docs`, matched on the GeoJSON `type` field
# PostGIS's `ST_AsGeoJSON` always includes.
RegionGeometry = Annotated[Point | Polygon | MultiPolygon, Field(discriminator="type")]

# The shape every slug `region_service.slugify` produces: lowercase ASCII
# words joined by single hyphens, no leading/trailing/doubled hyphen. Used to
# validate a client-supplied slug in `RegionImportProperties`, the one place
# a slug arrives from outside the app instead of being derived from `name`.
_SLUG_SHAPE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


class RegionProperties(BaseModel):
    """The `properties` object of a region `Feature` — architecture.md §5.1."""

    slug: str
    name: str
    description: str | None
    status: RegionStatus
    qr_token: str
    planting_count: int
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


class RegionImportProperties(BaseModel):
    """A feature's `properties` in a `POST /api/regions/import` payload
    (architecture.md §12, issue #33).

    `extra="ignore"`, unlike `RegionCreate`/`RegionUpdate`'s `extra="forbid"`:
    the expected workflow re-uploads an edited export of `GET /api/regions`,
    which carries `qr_token`/`planting_count`/timestamps this endpoint has no
    use for — rejecting those would make that round trip needlessly brittle.
    """

    model_config = ConfigDict(extra="ignore")

    slug: str
    name: str | None = None
    description: str | None = None
    status: RegionStatus | None = None

    @field_validator("slug")
    @classmethod
    def _slug_must_match_generated_shape(cls, slug: str) -> str:
        """Every server-generated slug (`region_service.slugify`) is
        lowercase ASCII, hyphen-separated. Import is the one path where a
        client supplies a slug directly rather than it being derived from
        `name` — reject anything outside that shape here, rather than
        storing an unusable URL segment or a byte-for-byte-different
        "duplicate" of a region a human would call the same slug.
        """
        if not _SLUG_SHAPE.fullmatch(slug):
            raise ValueError(
                'slug deve ser minúsculo, ASCII, com palavras separadas por hífen (ex.: "canteiro-do-ipe").'
            )
        return slug


class RegionImportFeature(BaseModel):
    """One feature of a `POST /api/regions/import` payload.

    Deliberately not `Feature[...]` (unlike `RegionFeature`): matching is by
    `properties.slug`, not `id` — a region this import is about to create
    doesn't have an `id` yet.
    """

    type: Literal["Feature"] = "Feature"
    geometry: RegionGeometry
    properties: RegionImportProperties


class RegionImportFeatureCollection(BaseModel):
    """Request body for `POST /api/regions/import`."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[RegionImportFeature]


class RegionImportSummary(BaseModel):
    """Response body for `POST /api/regions/import` — architecture.md §5 table."""

    created: int
    updated: int
    ignored: int
