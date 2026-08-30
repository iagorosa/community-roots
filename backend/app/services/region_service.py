"""Region read and admin-write operations. See docs/architecture.md §5.1 for
the GeoJSON response shape, §4.2 for the `regions` table, and §9 for why
writes are admin-only (issue #12).
"""

import json
import re
import secrets
import unicodedata
import uuid
from typing import Any

from sqlalchemy import ColumnElement, Row, func, literal, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.region import Region
from app.schemas.region import (
    RegionCreate,
    RegionFeature,
    RegionFeatureCollection,
    RegionProperties,
    RegionUpdate,
)


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


def _fetch_feature_by_id(db: Session, region_id: uuid.UUID) -> RegionFeature:
    """Fetch a region by id regardless of `status`.

    Used after an admin create/update: the caller who just archived a region
    still needs to see the result, even though `_PUBLICLY_VISIBLE` would now
    hide it from everyone else.
    """
    row = db.execute(select(*_region_feature_columns()).where(Region.id == region_id)).first()
    if row is None:
        raise RegionNotFound(str(region_id))
    return _row_to_feature(row)


def _resolve_region_id(db: Session, identifier: str) -> uuid.UUID:
    """Like `_identifier_filter`, but for admin writes: a `draft`/`archived`
    region must still be resolvable so it can be edited.
    """
    region_id = db.execute(
        select(Region.id).where(_identifier_filter(identifier))
    ).scalar_one_or_none()
    if region_id is None:
        raise RegionNotFound(identifier)
    return region_id


def slugify(name: str) -> str:
    """Derive a URL-safe slug from `name`. Public: also used by `scripts/seed.py`."""
    ascii_only = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    return slug or "canteiro"


def _generate_unique_slug(db: Session, name: str, *, exclude_id: uuid.UUID | None = None) -> str:
    """Derive a URL slug from `name`, disambiguated with a numeric suffix on collision.

    Check-then-write: two concurrent admin writes racing for the same slug
    would both pass this check and hit `uq_regions_slug` at commit time,
    surfacing as an unhandled `IntegrityError` (500). Accepted for the MVP's
    low-concurrency admin usage rather than adding a retry loop.
    """
    base_slug = slugify(name)

    query = select(Region.slug).where(Region.slug.like(f"{base_slug}%"))
    if exclude_id is not None:
        query = query.where(Region.id != exclude_id)
    taken_slugs = set(db.execute(query).scalars())

    if base_slug not in taken_slugs:
        return base_slug

    suffix = 2
    while f"{base_slug}-{suffix}" in taken_slugs:
        suffix += 1
    return f"{base_slug}-{suffix}"


def _geometry_to_geom_expression(geometry: Any) -> ColumnElement[Any]:
    """Build the geometry the same way reads produce it: through PostGIS, not Python.

    `ST_GeomFromGeoJSON` doesn't set an SRID on its own, so it's pinned to
    4326 explicitly — the CHECK/typmod on `regions.geom` requires it.
    """
    geometry_json = json.dumps(geometry.model_dump())
    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(geometry_json), 4326)


def create_region(db: Session, payload: RegionCreate) -> RegionFeature:
    region = Region(
        slug=_generate_unique_slug(db, payload.name),
        name=payload.name,
        description=payload.description,
        geom=_geometry_to_geom_expression(payload.geometry),
        status=payload.status,
        qr_token=secrets.token_urlsafe(9),
    )
    db.add(region)
    db.commit()
    return _fetch_feature_by_id(db, region.id)


# `RegionUpdate.name`/`.status` are `X | None = None` only so `None` can mean
# "field omitted" (via `exclude_unset`) — both columns are NOT NULL, unlike
# `description`, so a payload that explicitly sends `null` for either must be
# rejected here. Left unchecked, it reaches Postgres as a `NotNullViolation`
# (500) instead of a 422.
_NOT_NULLABLE_UPDATE_FIELDS = ("name", "status")


def update_region(db: Session, identifier: str, payload: RegionUpdate) -> RegionFeature:
    region_id = _resolve_region_id(db, identifier)
    region = db.get(Region, region_id)
    assert region is not None  # `_resolve_region_id` just confirmed this row exists

    changed_fields = payload.model_dump(exclude_unset=True, exclude={"geometry"})
    for field in _NOT_NULLABLE_UPDATE_FIELDS:
        if field in changed_fields and changed_fields[field] is None:
            raise ValidationFailedError(
                f'O campo "{field}" não pode ser removido, apenas alterado.'
            )

    if "name" in changed_fields and changed_fields["name"] != region.name:
        region.slug = _generate_unique_slug(db, changed_fields["name"], exclude_id=region.id)
    for field, value in changed_fields.items():
        setattr(region, field, value)
    if payload.geometry is not None:
        region.geom = _geometry_to_geom_expression(payload.geometry)

    db.commit()
    return _fetch_feature_by_id(db, region.id)
