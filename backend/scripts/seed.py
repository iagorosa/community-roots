"""Idempotent development seed: a single placeholder `Region` — the AAMA,
in Matias Barbosa — with `SEED_PLANTING_COUNT` `Planting`s arranged in a
grid inside it, around `SEED_CENTER_LAT`/`SEED_CENTER_LON`. See
docs/architecture.md §4.1 — this geometry is a development placeholder,
replaced by the geographer's real survey in Phase 6
(docs/implementation-plan.md).

The Region is upserted by slug: re-running never duplicates it, and
repositions it when the configured center changes. Plantings are seeded
alongside it, one per missing ordinal position, so a rerun tops the Region
back up to `SEED_PLANTING_COUNT` without duplicating existing Plantings.
Every Region/Planting's QR code is assigned on first creation and left
untouched on later reruns — except a pre-existing Region missing one (data
seeded before issue #80 introduced `QrCode`), which a rerun backfills
(issue #108).
"""

import math
import sys
from dataclasses import dataclass
from itertools import cycle, islice
from pathlib import Path

# `python scripts/seed.py` puts `scripts/` on `sys.path`, not `backend/`
# (the directory containing this file, not the cwd) — without this, `app`
# isn't importable when run the way the README documents.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.planting import Planting
from app.models.region import Region
from app.services.qr_code_service import (
    create_planting_qr_code,
    create_region_qr_code,
    ensure_region_qr_code,
)
from app.services.region_service import slugify

_METERS_PER_DEGREE_LATITUDE = 111_320

# There's exactly one Region in the seed (the AAMA's own area) — see issue
# #122. Its geometry is a rectangle sized to fit the Planting grid below
# plus this margin, not a real survey boundary.
_REGION_NAME = "AAMA — Matias Barbosa"
_REGION_MARGIN_METERS = 25

_PLANTING_GRID_ROWS = 5
_PLANTING_SPACING_METERS = 15

_PLACEHOLDER_DESCRIPTION = (
    "Geometria placeholder de desenvolvimento, gerada por scripts/seed.py — "
    "será substituída pelo levantamento do geógrafo (Fase 6)."
)

# Fictional names for development data — no relation to the area's real
# vegetation, which the geographer's survey (Phase 6) will establish. Used
# as `Planting.nickname`, cycling if `SEED_PLANTING_COUNT` exceeds the pool.
_PLANTING_NICKNAMES = [
    "Canteiro do Ipê-Amarelo",
    "Canteiro do Ipê-Roxo",
    "Canteiro do Jacarandá",
    "Canteiro do Pau-Brasil",
    "Canteiro do Jequitibá",
    "Canteiro da Aroeira",
    "Canteiro do Jatobá",
    "Canteiro do Angico",
    "Canteiro do Cedro-Rosa",
    "Canteiro da Canela-Preta",
]


@dataclass(frozen=True)
class SeedResult:
    """Outcome of one `seed()` call — `plantings_created` never includes
    Plantings that already existed from a previous run."""

    region_created: bool
    plantings_created: int


def _rectangle_wkt(
    center_lat: float, center_lon: float, width_meters: float, height_meters: float
) -> str:
    """A `width_meters` x `height_meters` rectangle centered on
    `(center_lat, center_lon)`, as WKT.

    Longitude degrees shrink toward the poles (`cos(latitude)`), so the
    conversion has to account for it or the rectangle would stretch
    east-west away from the equator.
    """
    half_lat_deg = (height_meters / 2) / _METERS_PER_DEGREE_LATITUDE
    half_lon_deg = (width_meters / 2) / (
        _METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(center_lat))
    )

    corners = [
        (center_lon - half_lon_deg, center_lat - half_lat_deg),
        (center_lon + half_lon_deg, center_lat - half_lat_deg),
        (center_lon + half_lon_deg, center_lat + half_lat_deg),
        (center_lon - half_lon_deg, center_lat + half_lat_deg),
        (center_lon - half_lon_deg, center_lat - half_lat_deg),  # closed ring
    ]
    coordinates = ", ".join(f"{lon} {lat}" for lon, lat in corners)
    return f"POLYGON(({coordinates}))"


def _grid_positions(
    count: int, rows: int, center_lat: float, center_lon: float
) -> list[tuple[float, float]]:
    """`count` (lat, lon) points arranged in `rows` rows around
    `(center_lat, center_lon)`, `_PLANTING_SPACING_METERS` apart."""
    columns = math.ceil(count / rows)
    spacing_lat_deg = _PLANTING_SPACING_METERS / _METERS_PER_DEGREE_LATITUDE
    spacing_lon_deg = _PLANTING_SPACING_METERS / (
        _METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(center_lat))
    )

    positions = []
    for index in range(count):
        row, column = divmod(index, columns)
        row_offset = row - (rows - 1) / 2
        column_offset = column - (columns - 1) / 2
        positions.append(
            (
                center_lat + row_offset * spacing_lat_deg,
                center_lon + column_offset * spacing_lon_deg,
            )
        )
    return positions


def _region_rectangle_size(planting_count: int, rows: int) -> tuple[float, float]:
    """The (width, height) in meters of a rectangle that fits a `rows`-row
    grid of `planting_count` points, `_PLANTING_SPACING_METERS` apart, plus
    `_REGION_MARGIN_METERS` of padding on every side."""
    columns = math.ceil(planting_count / rows)
    width_meters = (columns - 1) * _PLANTING_SPACING_METERS + 2 * _REGION_MARGIN_METERS
    height_meters = (rows - 1) * _PLANTING_SPACING_METERS + 2 * _REGION_MARGIN_METERS
    return width_meters, height_meters


def seed(
    db: Session,
    *,
    center_lat: float = settings.seed_center_lat,
    center_lon: float = settings.seed_center_lon,
    planting_count: int = settings.seed_planting_count,
) -> SeedResult:
    """Upsert the single AAMA `Region`, with `planting_count` `Planting`s
    arranged in a grid inside it. Plantings are seeded idempotently
    alongside the Region — a rerun only creates the newly missing ones (by
    ordinal position) and never repositions or renames existing ones. A
    rerun with a smaller `planting_count` than a previous run does not trim
    the surplus — this only ever tops the Region up, never down."""
    slug = slugify(_REGION_NAME)
    width_meters, height_meters = _region_rectangle_size(planting_count, _PLANTING_GRID_ROWS)
    geom = WKTElement(
        _rectangle_wkt(center_lat, center_lon, width_meters, height_meters), srid=4326
    )

    region = db.execute(select(Region).where(Region.slug == slug)).scalar_one_or_none()
    region_created = region is None
    if region is None:
        region = Region(
            slug=slug, name=_REGION_NAME, description=_PLACEHOLDER_DESCRIPTION, geom=geom
        )
        db.add(region)
        db.flush()
        create_region_qr_code(db, region.id)
    else:
        region.name = _REGION_NAME
        region.description = _PLACEHOLDER_DESCRIPTION
        region.geom = geom
        # A region seeded before issue #80 introduced `QrCode` never got one
        # backfilled by a later rerun — this branch only ever touched
        # name/description/geom. See issue #108.
        ensure_region_qr_code(db, region.id)

    existing_planting_count = db.execute(
        select(func.count()).select_from(Planting).where(Planting.region_id == region.id)
    ).scalar_one()

    positions = _grid_positions(planting_count, _PLANTING_GRID_ROWS, center_lat, center_lon)
    nicknames = list(islice(cycle(_PLANTING_NICKNAMES), planting_count))

    plantings_created = 0
    new_positions = positions[existing_planting_count:]
    new_nicknames = nicknames[existing_planting_count:]
    for (planting_lat, planting_lon), nickname in zip(new_positions, new_nicknames, strict=True):
        planting = Planting(
            region_id=region.id,
            nickname=nickname,
            geom=WKTElement(f"POINT({planting_lon} {planting_lat})", srid=4326),
        )
        db.add(planting)
        db.flush()
        create_planting_qr_code(db, planting.id)
        plantings_created += 1

    db.commit()
    return SeedResult(region_created=region_created, plantings_created=plantings_created)


def main() -> None:
    with SessionLocal() as db:
        result = seed(db)
    region_status = "criada" if result.region_created else "já existia"
    print(
        f"Seed concluído: região da AAMA {region_status}, "
        f"{result.plantings_created} muda(s) nova(s) criada(s)."
    )


if __name__ == "__main__":
    main()
