"""Planting schemas: the GeoJSON `properties` shape and the admin request
bodies for create/update. Mirrors `app/schemas/region.py` — see
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.geojson import Feature, FeatureCollection, MultiPolygon, Point, Polygon

PlantingStatus = Literal["active", "draft", "archived"]

# The three geometry shapes `ck_plantings_geom_type` allows (app/models/planting.py).
PlantingGeometry = Annotated[Point | Polygon | MultiPolygon, Field(discriminator="type")]


class PlantingProperties(BaseModel):
    """The `properties` object of a planting `Feature`."""

    region_id: uuid.UUID
    species: str | None
    nickname: str | None
    planted_by: str | None
    planted_at: datetime | None
    status: PlantingStatus
    qr_token: str
    photo_count: int
    latest_photo_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PlantingFeature(Feature[PlantingGeometry, PlantingProperties]):
    """A single planting, as returned by `GET /api/plantings/{planting_id}`."""


class PlantingFeatureCollection(FeatureCollection[PlantingGeometry, PlantingProperties]):
    """The planting list, as returned by `GET /api/plantings`."""

    features: list[PlantingFeature]


class PlantingCreate(BaseModel):
    """Admin request body for `POST /api/plantings`.

    `extra="forbid"`: `qr_token` is server-generated, so a client payload
    that includes it must error loudly instead of having it silently
    dropped — same rule `RegionCreate` applies.
    """

    model_config = ConfigDict(extra="forbid")

    region_id: uuid.UUID
    geometry: PlantingGeometry
    species: str | None = None
    nickname: str | None = None
    planted_by: str | None = None
    planted_at: datetime | None = None
    status: PlantingStatus = "active"


class PlantingUpdate(BaseModel):
    """Admin request body for `PATCH /api/plantings/{planting_id}` — every field optional."""

    model_config = ConfigDict(extra="forbid")

    geometry: PlantingGeometry | None = None
    species: str | None = None
    nickname: str | None = None
    planted_by: str | None = None
    planted_at: datetime | None = None
    status: PlantingStatus | None = None
