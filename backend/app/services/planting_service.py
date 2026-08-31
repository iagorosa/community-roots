"""Planting read and admin-write operations. Mirrors
`app/services/region_service.py` — see
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.

Unlike `Region`, a `Planting` has no slug: it's resolved by UUID only, since
its URL/QR target is `/plantings/{id}`, never a human-typed path.
"""

import json
import uuid
from typing import Any

from sqlalchemy import ColumnElement, Row, func, literal, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region
from app.schemas.planting import (
    PlantingCreate,
    PlantingFeature,
    PlantingFeatureCollection,
    PlantingProperties,
    PlantingUpdate,
)
from app.services import qr_code_service
from app.services.region_service import RegionNotFound


class PlantingNotFound(NotFoundError):
    code = "planting_not_found"

    def __init__(self, identifier: uuid.UUID) -> None:
        super().__init__(f'Nenhuma muda encontrada para "{identifier}".')


_PUBLICLY_VISIBLE: ColumnElement[bool] = Planting.status == "active"


def _planting_feature_columns() -> tuple[ColumnElement[Any], ...]:
    """`qr_token` via INNER JOIN — every planting gets exactly one QrCode at
    creation time (`qr_code_service.create_planting_qr_code`), same
    invariant `region_service._region_feature_columns` documents.

    `photo_count`/`latest_photo_at` are literal placeholders until a later
    task wires them to real `photos` data (that table doesn't reference
    `planting_id` yet at this point in the plan).
    """
    return (
        Planting.id,
        Planting.region_id,
        Planting.species,
        Planting.nickname,
        Planting.planted_by,
        Planting.planted_at,
        Planting.status,
        Planting.created_at,
        Planting.updated_at,
        QrCode.token.label("qr_token"),
        func.ST_AsGeoJSON(Planting.geom).label("geometry_geojson"),
        literal(0).label("photo_count"),
        literal(None).label("latest_photo_at"),
    )


def _planting_query() -> Any:
    return select(*_planting_feature_columns()).join(QrCode, QrCode.planting_id == Planting.id)


def _row_to_feature(row: Row[Any]) -> PlantingFeature:
    return PlantingFeature(
        id=str(row.id),
        geometry=json.loads(row.geometry_geojson),
        properties=PlantingProperties(
            region_id=row.region_id,
            species=row.species,
            nickname=row.nickname,
            planted_by=row.planted_by,
            planted_at=row.planted_at,
            status=row.status,
            qr_token=row.qr_token,
            photo_count=row.photo_count,
            latest_photo_at=row.latest_photo_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        ),
    )


def list_plantings(db: Session, *, region_id: uuid.UUID | None = None) -> PlantingFeatureCollection:
    query = _planting_query().where(_PUBLICLY_VISIBLE)
    if region_id is not None:
        query = query.where(Planting.region_id == region_id)
    rows = db.execute(query.order_by(Planting.created_at, Planting.id)).all()
    return PlantingFeatureCollection(features=[_row_to_feature(row) for row in rows])


def get_planting(db: Session, planting_id: uuid.UUID) -> PlantingFeature:
    row = db.execute(_planting_query().where(Planting.id == planting_id, _PUBLICLY_VISIBLE)).first()
    if row is None:
        raise PlantingNotFound(planting_id)
    return _row_to_feature(row)


def _fetch_feature_by_id(db: Session, planting_id: uuid.UUID) -> PlantingFeature:
    """Fetch a planting by id regardless of `status` — used after an admin
    create/update, same as `region_service._fetch_feature_by_id`.
    """
    row = db.execute(_planting_query().where(Planting.id == planting_id)).first()
    if row is None:
        raise PlantingNotFound(planting_id)
    return _row_to_feature(row)


def _geometry_to_geom_expression(geometry: Any) -> ColumnElement[Any]:
    geometry_json = json.dumps(geometry.model_dump())
    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(geometry_json), 4326)


def create_planting(db: Session, payload: PlantingCreate) -> PlantingFeature:
    # Validated here, not left to the FK: an unknown `region_id` would
    # otherwise surface as a raw `ForeignKeyViolation` (500) instead of the
    # domain 404 every other parent-lookup in this codebase raises (see
    # `photo_service.list_region_photos`'s `region_service.get_region` call).
    if db.get(Region, payload.region_id) is None:
        raise RegionNotFound(str(payload.region_id))

    planting = Planting(
        region_id=payload.region_id,
        geom=_geometry_to_geom_expression(payload.geometry),
        species=payload.species,
        nickname=payload.nickname,
        planted_by=payload.planted_by,
        planted_at=payload.planted_at,
        status=payload.status,
    )
    db.add(planting)
    db.flush()  # assigns planting.id before the QrCode FK needs it
    qr_code_service.create_planting_qr_code(db, planting.id)
    db.commit()
    return _fetch_feature_by_id(db, planting.id)


# `PlantingUpdate.status` is `X | None = None` only so `None` can mean
# "field omitted" (via `exclude_unset`) — the column is NOT NULL, so a
# payload that explicitly sends `null` must be rejected here, same rule
# `region_service._NOT_NULLABLE_UPDATE_FIELDS` applies for `Region`. Left
# unchecked, it reaches Postgres as a `NotNullViolation` (500) instead of a 422.
_NOT_NULLABLE_UPDATE_FIELDS = ("status",)


def update_planting(
    db: Session, planting_id: uuid.UUID, payload: PlantingUpdate
) -> PlantingFeature:
    planting = db.get(Planting, planting_id)
    if planting is None:
        raise PlantingNotFound(planting_id)

    changed_fields = payload.model_dump(exclude_unset=True, exclude={"geometry"})
    for field in _NOT_NULLABLE_UPDATE_FIELDS:
        if field in changed_fields and changed_fields[field] is None:
            raise ValidationFailedError(
                f'O campo "{field}" não pode ser removido, apenas alterado.'
            )

    for field, value in changed_fields.items():
        setattr(planting, field, value)
    if payload.geometry is not None:
        planting.geom = _geometry_to_geom_expression(payload.geometry)

    db.commit()
    return _fetch_feature_by_id(db, planting.id)
