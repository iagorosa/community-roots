"""Region read operations: listing and resolving a single region by slug or
UUID. See docs/architecture.md §5.1 for the GeoJSON response shape and §4.2
for the `regions` table this queries.
"""

import json
import uuid
from typing import Any

from sqlalchemy import ColumnElement, Row, func, literal, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.region import Region
from app.schemas.region import RegionFeature, RegionFeatureCollection, RegionProperties


class RegionNotFound(NotFoundError):
    code = "region_not_found"

    def __init__(self, identifier: str) -> None:
        super().__init__(f'Nenhum canteiro encontrado para "{identifier}".')


# architecture.md §4.5: `status` exists so an organizer can pull a region
# from public view immediately, with a plain `UPDATE` — these public read
# endpoints have to honor it, or that escape hatch does nothing.
_PUBLICLY_VISIBLE: ColumnElement[bool] = Region.status == "active"


def _region_feature_columns() -> tuple[ColumnElement[Any], ...]:
    """Columns shared by the listing and single-region queries.

    `geom` is serialized to GeoJSON by PostGIS's `ST_AsGeoJSON`, never in
    Python, so there is exactly one implementation of that conversion
    (architecture.md §5.1).

    `photo_count`/`latest_photo_at` are literals, not the `LEFT JOIN LATERAL`
    the issue describes: the `photos` table doesn't exist yet — the Photo
    model is issue #20, milestone "Fase 4", which lands after this one. This
    query is the natural place to add that join once it does.
    """
    return (
        Region.id,
        Region.slug,
        Region.name,
        Region.description,
        Region.status,
        Region.qr_token,
        Region.created_at,
        Region.updated_at,
        func.ST_AsGeoJSON(Region.geom).label("geometry_geojson"),
        literal(0).label("photo_count"),
        literal(None).label("latest_photo_at"),
    )


def _row_to_feature(row: Row[Any]) -> RegionFeature:
    return RegionFeature(
        id=str(row.id),
        geometry=json.loads(row.geometry_geojson),
        properties=RegionProperties(
            slug=row.slug,
            name=row.name,
            description=row.description,
            status=row.status,
            qr_token=row.qr_token,
            photo_count=row.photo_count,
            latest_photo_at=row.latest_photo_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        ),
    )


def list_regions(db: Session) -> RegionFeatureCollection:
    rows = db.execute(
        select(*_region_feature_columns()).where(_PUBLICLY_VISIBLE).order_by(Region.name, Region.id)
    ).all()
    return RegionFeatureCollection(features=[_row_to_feature(row) for row in rows])


def get_region(db: Session, identifier: str) -> RegionFeature:
    """Resolve `identifier` as a UUID first, falling back to slug.

    The single place architecture.md §5 calls for: every future route that
    takes a `{region}` path parameter resolves it by calling this function.
    """
    row = db.execute(
        select(*_region_feature_columns()).where(_identifier_filter(identifier), _PUBLICLY_VISIBLE)
    ).first()
    if row is None:
        raise RegionNotFound(identifier)
    return _row_to_feature(row)


def _identifier_filter(identifier: str) -> ColumnElement[bool]:
    try:
        region_id = uuid.UUID(identifier)
    except ValueError:
        return Region.slug == identifier
    return Region.id == region_id
