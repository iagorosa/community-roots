"""Idempotent development seed: placeholder canteiros around
`SEED_CENTER_LAT`/`SEED_CENTER_LON`. See docs/architecture.md §4.1 — this
geometry is a development placeholder, replaced by the geographer's real
survey in Phase 6 (docs/implementation-plan.md).

Upserts by slug: re-running never duplicates, and repositions existing
canteiros when the configured center changes. `qr_token` is only assigned
on first creation and left untouched on later reruns.
"""

import math
import secrets
import sys
from pathlib import Path

# `python scripts/seed.py` puts `scripts/` on `sys.path`, not `backend/`
# (the directory containing this file, not the cwd) — without this, `app`
# isn't importable when run the way the README documents.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.region import Region
from app.services.region_service import slugify

_METERS_PER_DEGREE_LATITUDE = 111_320
_CELL_SIDE_METERS = 50
_CELL_SPACING_METERS = 60  # 50m plot + 10m gap, so neighboring squares don't touch
_GRID_ROWS = 2

_PLACEHOLDER_DESCRIPTION = (
    "Geometria placeholder de desenvolvimento, gerada por scripts/seed.py — "
    "será substituída pelo levantamento do geógrafo (Fase 6)."
)

# Fictional names for development data — no relation to the area's real
# vegetation, which the geographer's survey (Phase 6) will establish.
_REGION_NAMES = [
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


def _square_wkt(center_lat: float, center_lon: float, side_meters: float) -> str:
    """A `side_meters`-wide square centered on `(center_lat, center_lon)`, as WKT.

    Longitude degrees shrink toward the poles (`cos(latitude)`), so the
    conversion has to account for it or the square would stretch east-west
    away from the equator.
    """
    half_lat_deg = (side_meters / 2) / _METERS_PER_DEGREE_LATITUDE
    half_lon_deg = (side_meters / 2) / (
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


def _grid_cell_centers(
    count: int, rows: int, center_lat: float, center_lon: float
) -> list[tuple[float, float]]:
    """`count` cell centers arranged in `rows` rows around `(center_lat, center_lon)`."""
    columns = math.ceil(count / rows)
    spacing_lat_deg = _CELL_SPACING_METERS / _METERS_PER_DEGREE_LATITUDE
    spacing_lon_deg = _CELL_SPACING_METERS / (
        _METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(center_lat))
    )

    cell_centers = []
    for index in range(count):
        row, column = divmod(index, columns)
        row_offset = row - (rows - 1) / 2
        column_offset = column - (columns - 1) / 2
        cell_centers.append(
            (
                center_lat + row_offset * spacing_lat_deg,
                center_lon + column_offset * spacing_lon_deg,
            )
        )
    return cell_centers


def seed(
    db: Session,
    *,
    center_lat: float = settings.seed_center_lat,
    center_lon: float = settings.seed_center_lon,
    region_count: int = settings.seed_region_count,
) -> tuple[int, int]:
    """Upsert `region_count` placeholder canteiros by slug. Returns `(created, updated)`."""
    if region_count > len(_REGION_NAMES):
        raise ValueError(
            f"SEED_REGION_COUNT={region_count} excede o pool de "
            f"{len(_REGION_NAMES)} nomes fictícios em _REGION_NAMES."
        )
    names = _REGION_NAMES[:region_count]
    cell_centers = _grid_cell_centers(len(names), _GRID_ROWS, center_lat, center_lon)

    created = updated = 0
    for name, (cell_lat, cell_lon) in zip(names, cell_centers, strict=True):
        slug = slugify(name)
        geom = WKTElement(_square_wkt(cell_lat, cell_lon, _CELL_SIDE_METERS), srid=4326)

        region = db.execute(select(Region).where(Region.slug == slug)).scalar_one_or_none()
        if region is None:
            db.add(
                Region(
                    slug=slug,
                    name=name,
                    description=_PLACEHOLDER_DESCRIPTION,
                    geom=geom,
                    qr_token=secrets.token_urlsafe(9),
                )
            )
            created += 1
        else:
            region.name = name
            region.description = _PLACEHOLDER_DESCRIPTION
            region.geom = geom
            updated += 1

    db.commit()
    return created, updated


def main() -> None:
    with SessionLocal() as db:
        created, updated = seed(db)
    print(f"Seed concluído: {created} canteiro(s) criado(s), {updated} atualizado(s).")


if __name__ == "__main__":
    main()
