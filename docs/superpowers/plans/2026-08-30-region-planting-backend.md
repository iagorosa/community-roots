# Region/Planting Backend Pivot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the backend's single `Region` entity into `Region` (a large grouping, e.g. "AAMA — Matias Barbosa") and a new `Planting` entity (an individual seedling), moving photos and QR codes onto `Planting`, while introducing a shared `QrCode` entity so both `Region` and `Planting` can carry a QR code.

**Architecture:** `Planting` mirrors `Region`'s existing shape (flexible PostGIS geometry, GeoJSON `Feature`/`FeatureCollection` responses, admin-token-gated writes) and gets its own service/schema/route module, following the file-per-entity pattern already in this codebase. `QrCode` replaces the `qr_token` column that used to live directly on `Region`, with two nullable FKs (`region_id`/`planting_id`) and a CHECK constraint enforcing exactly one is set. `Photo` moves from `region_id` to `planting_id`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, GeoAlchemy2/PostGIS, Alembic, Pydantic, pytest.

## Global Constraints

- Code, identifiers, comments, and docstrings in English; error messages shown to end users in Brazilian Portuguese (matches every existing service/route module).
- No real data exists in any environment today — every migration in this plan may be destructive (drop/recreate columns) without a data-preservation path. Confirmed with the user in the brainstorm that produced `docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md`.
- Every new migration is hand-edited after `alembic revision -m "..."` generates the file — never raw autogenerate output — matching the existing three migrations in `backend/alembic/versions/`.
- Run backend commands from `backend/` with the virtualenv activated (`source .venv/bin/activate`), per `README.md`.
- Migrations apply to `DATABASE_URL` by default (`backend/app/alembic/env.py` reads `settings.database_url`). To apply the same migration to the test database, override the env var for that one command:
  ```bash
  DATABASE_URL="$(grep '^TEST_DATABASE_URL=' .env | cut -d= -f2-)" alembic upgrade head
  ```
  Every task below that adds a migration includes this as an explicit step — do not skip it, or the test suite will fail with "relation does not exist".
- Every task that changes a model/schema/route must also fix any existing test file that breaks as a direct result (listed explicitly per task) — the suite must stay green at the end of every task, not just at the end of the plan.

---

## Task 1: `Planting` model + migration

**Files:**
- Create: `backend/app/models/planting.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<generated>_planting_model.py` (filename assigned by `alembic revision`)
- Test: `backend/tests/test_planting_model.py`

**Interfaces:**
- Produces: `app.models.planting.Planting` — columns `id: uuid.UUID`, `region_id: uuid.UUID`, `geom: WKBElement`, `centroid: WKBElement` (computed), `species: str | None`, `nickname: str | None`, `planted_by: str | None`, `planted_at: datetime | None`, `status: str`, `created_at: datetime`, `updated_at: datetime`. Table name `plantings`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_planting_model.py`:

```python
"""Tests for the `Planting` model and its migration (backend/app/models/planting.py).

`Planting` mirrors `Region`'s geometry design (a permissive
`geometry(Geometry, 4326)` column narrowed by a CHECK constraint, plus a
generated `centroid`) — see
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.region import Region

_POINT_WKT = "POINT(-43.3130 -21.8845)"


def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"regiao-{uuid.uuid4().hex[:8]}",
        "name": "Região de teste",
        "geom": WKTElement(_POINT_WKT, srid=4326),
    }
    defaults.update(overrides)
    return Region(**defaults)


def _make_planting(region_id: uuid.UUID, **overrides: object) -> Planting:
    defaults: dict[str, object] = {
        "region_id": region_id,
        "geom": WKTElement(_POINT_WKT, srid=4326),
    }
    defaults.update(overrides)
    return Planting(**defaults)


def test_centroid_is_computed_automatically_on_insert(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    planting = _make_planting(region.id)
    db_session.add(planting)
    db_session.commit()

    centroid_matches_postgis_computation = db_session.execute(
        select(func.ST_Equals(Planting.centroid, func.ST_Centroid(Planting.geom))).where(
            Planting.id == planting.id
        )
    ).scalar_one()

    assert centroid_matches_postgis_computation is True


def test_linestring_geometry_is_rejected_by_check_constraint(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    planting = _make_planting(
        region.id, geom=WKTElement("LINESTRING(-43.313 -21.884, -43.312 -21.883)", srid=4326)
    )
    db_session.add(planting)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()  # required after a failed flush before the session is usable again


def test_invalid_status_is_rejected_by_check_constraint(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    planting = _make_planting(region.id, status="deleted")
    db_session.add(planting)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_optional_fields_default_to_none(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    planting = _make_planting(region.id)
    db_session.add(planting)
    db_session.commit()

    stored = db_session.execute(select(Planting).where(Planting.id == planting.id)).scalar_one()
    assert stored.species is None
    assert stored.nickname is None
    assert stored.planted_by is None
    assert stored.planted_at is None
    assert stored.status == "active"  # server_default, not passed explicitly


def test_deleting_region_cascades_to_its_plantings_at_the_database_level(
    db_session: Session,
) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    planting = _make_planting(region.id)
    db_session.add(planting)
    db_session.commit()
    planting_id = planting.id

    # Deleted via the Core `DELETE` the ORM issues for `db_session.delete`, not
    # via any ORM-side `cascade=` — proves `ON DELETE CASCADE` is enforced by
    # Postgres itself.
    db_session.delete(region)
    db_session.commit()

    remaining = db_session.execute(
        select(Planting).where(Planting.id == planting_id)
    ).scalar_one_or_none()
    assert remaining is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_planting_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.planting'`

- [ ] **Step 3: Write the model**

Create `backend/app/models/planting.py`:

```python
"""`Planting` — an individual seedling planted by someone, inside a `Region`.
See docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Planting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plantings"
    __table_args__ = (
        # Same three shapes `Region.geom` allows — a Planting starts as a
        # point today but may become a small polygon later without a schema
        # change (see the spec's geometry decision).
        CheckConstraint(
            "GeometryType(geom) IN ('POINT', 'POLYGON', 'MULTIPOLYGON')",
            name="ck_plantings_geom_type",
        ),
        CheckConstraint(
            "status IN ('active', 'draft', 'archived')",
            name="ck_plantings_status",
        ),
        Index("ix_plantings_geom", "geom", postgresql_using="gist"),
        Index("ix_plantings_centroid", "centroid", postgresql_using="gist"),
    )

    region_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
        nullable=False,
    )
    centroid: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        Computed("ST_Centroid(geom)", persisted=True),
    )

    species: Mapped[str | None] = mapped_column(Text)
    nickname: Mapped[str | None] = mapped_column(Text)
    planted_by: Mapped[str | None] = mapped_column(Text)
    planted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
```

- [ ] **Step 4: Register the model**

Edit `backend/app/models/__init__.py`:

```python
"""Domain models. Imported here so `Base.metadata` — and Alembic autogenerate — sees them."""

from app.models.photo import Photo
from app.models.planting import Planting
from app.models.region import Region

__all__ = ["Photo", "Planting", "Region"]
```

- [ ] **Step 5: Generate and hand-edit the migration**

Run: `alembic revision -m "planting model"`

This creates `backend/alembic/versions/<hash>_planting_model.py` with an auto-filled `revision`/`down_revision` (pointing at `c60d27ca71eb`, today's head). Replace its `upgrade()`/`downgrade()` bodies — keep the auto-generated header as-is:

```python
def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "plantings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("region_id", sa.UUID(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "centroid",
            geoalchemy2.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            sa.Computed("ST_Centroid(geom)", persisted=True),
            nullable=False,
        ),
        sa.Column("species", sa.Text(), nullable=True),
        sa.Column("nickname", sa.Text(), nullable=True),
        sa.Column("planted_by", sa.Text(), nullable=True),
        sa.Column("planted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "GeometryType(geom) IN ('POINT', 'POLYGON', 'MULTIPOLYGON')",
            name="ck_plantings_geom_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'draft', 'archived')",
            name="ck_plantings_status",
        ),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_plantings_region_id", "plantings", ["region_id"], unique=False)
    op.create_index(
        "ix_plantings_geom", "plantings", ["geom"], unique=False, postgresql_using="gist"
    )
    op.create_index(
        "ix_plantings_centroid", "plantings", ["centroid"], unique=False, postgresql_using="gist"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_plantings_centroid", table_name="plantings", postgresql_using="gist")
    op.drop_index("ix_plantings_geom", table_name="plantings", postgresql_using="gist")
    op.drop_index("ix_plantings_region_id", table_name="plantings")
    op.drop_table("plantings")
```

Add the two imports the existing migrations use at the top of the file, right below the docstring, if `alembic revision` didn't already include them:

```python
import geoalchemy2
import sqlalchemy as sa

from alembic import op
```

- [ ] **Step 6: Apply the migration to both databases**

Run:
```bash
alembic upgrade head
DATABASE_URL="$(grep '^TEST_DATABASE_URL=' .env | cut -d= -f2-)" alembic upgrade head
```
Expected: both commands print the new revision as applied, no errors.

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_planting_model.py -v`
Expected: PASS (5 tests)

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/planting.py backend/app/models/__init__.py \
  backend/alembic/versions backend/tests/test_planting_model.py
git commit -m "feat: adiciona model Planting e migration"
```

---

## Task 2: `QrCode` entity, `qr_code_service`, and Region wiring

**Files:**
- Create: `backend/app/models/qr_code.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/region.py`
- Create: `backend/alembic/versions/<generated>_qr_code_model.py`
- Create: `backend/app/services/qr_code_service.py`
- Modify: `backend/app/services/region_service.py`
- Modify: `backend/scripts/seed.py` (minimal fix so it keeps working — full rewrite is Task 8)
- Modify: `backend/tests/test_region_model.py`
- Modify: `backend/tests/test_region_service.py`
- Modify: `backend/tests/test_region_qr_route.py`
- Modify: `backend/tests/test_photo_model.py` (only drops the now-invalid `qr_token` kwarg from its `_make_region` helper)
- Test: `backend/tests/test_qr_code_model.py`
- Test: `backend/tests/test_qr_code_service.py`

**Interfaces:**
- Consumes: `app.models.region.Region` (Task 1's sibling, already exists), `app.models.planting.Planting` (Task 1).
- Produces:
  - `app.models.qr_code.QrCode` — `id`, `token: str` (unique), `region_id: uuid.UUID | None` (unique when set), `planting_id: uuid.UUID | None` (unique when set). Table `qr_codes`.
  - `app.services.qr_code_service.create_region_qr_code(db: Session, region_id: uuid.UUID) -> str`
  - `app.services.qr_code_service.create_planting_qr_code(db: Session, planting_id: uuid.UUID) -> str`
  - `app.services.qr_code_service.resolve_qr_token(db: Session, token: str) -> QrCodeTarget`
  - `app.services.qr_code_service.QrCodeTarget` — `@dataclass(frozen=True)` with `kind: Literal["region", "planting"]` and `identifier: str` (region's `slug`, or planting's `str(id)`).
  - `app.services.qr_code_service.QrTokenNotFound(NotFoundError)`.
  - `region_service.RegionFeature`/`RegionFeatureCollection` still expose `properties.qr_token: str`, now sourced from a join instead of a column — no consumer of `region_service` needs to change.

- [ ] **Step 1: Write the failing model test**

Create `backend/tests/test_qr_code_model.py`:

```python
"""Tests for the `QrCode` model and its migration
(backend/app/models/qr_code.py). See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md for why
this replaces the `qr_token` column that used to live directly on `Region`:
a QrCode row belongs to exactly one of a Region or a Planting, never both,
never neither.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region

_POINT_WKT = "POINT(-43.3130 -21.8845)"


def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"regiao-{uuid.uuid4().hex[:8]}",
        "name": "Região de teste",
        "geom": WKTElement(_POINT_WKT, srid=4326),
    }
    defaults.update(overrides)
    return Region(**defaults)


def test_qr_code_for_a_region_is_accepted(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()

    db_session.add(QrCode(token="tok-region", region_id=region.id))
    db_session.commit()

    stored = db_session.execute(select(QrCode).where(QrCode.token == "tok-region")).scalar_one()
    assert stored.region_id == region.id
    assert stored.planting_id is None


def test_qr_code_for_a_planting_is_accepted(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    planting = Planting(region_id=region.id, geom=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(planting)
    db_session.flush()

    db_session.add(QrCode(token="tok-planting", planting_id=planting.id))
    db_session.commit()

    stored = db_session.execute(select(QrCode).where(QrCode.token == "tok-planting")).scalar_one()
    assert stored.planting_id == planting.id
    assert stored.region_id is None


def test_qr_code_with_neither_target_is_rejected(db_session: Session) -> None:
    db_session.add(QrCode(token="tok-neither"))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_qr_code_with_both_targets_is_rejected(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    planting = Planting(region_id=region.id, geom=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(planting)
    db_session.flush()

    db_session.add(QrCode(token="tok-both", region_id=region.id, planting_id=planting.id))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_a_region_cannot_have_two_qr_codes(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(token="tok-first", region_id=region.id))
    db_session.commit()

    db_session.add(QrCode(token="tok-second", region_id=region.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_region_cascades_to_its_qr_code(db_session: Session) -> None:
    region = _make_region()
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(token="tok-cascade", region_id=region.id))
    db_session.commit()

    db_session.delete(region)
    db_session.commit()

    remaining = db_session.execute(
        select(QrCode).where(QrCode.token == "tok-cascade")
    ).scalar_one_or_none()
    assert remaining is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qr_code_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.qr_code'`

- [ ] **Step 3: Write the `QrCode` model**

Create `backend/app/models/qr_code.py`:

```python
"""`QrCode` — a printable token pointing at exactly one `Region` or one
`Planting`, never both. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.

Two nullable FKs + a CHECK, not a polymorphic `target_type`/`target_id` pair:
keeps real Postgres foreign-key integrity (a dangling QR code is impossible
by construction) at the cost of a new column if a third QR-able entity ever
shows up — the spec's documented trade-off.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class QrCode(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "qr_codes"
    __table_args__ = (
        CheckConstraint(
            "(region_id IS NOT NULL) != (planting_id IS NOT NULL)",
            name="ck_qr_codes_exactly_one_target",
        ),
    )

    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # `unique=True` on both: at most one QrCode per Region/Planting — the
    # create flows (region_service.create_region,
    # planting_service.create_planting) only ever insert one.
    region_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regions.id", ondelete="CASCADE"), unique=True
    )
    planting_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plantings.id", ondelete="CASCADE"), unique=True
    )
```

- [ ] **Step 4: Remove `qr_token` from the `Region` model**

Edit `backend/app/models/region.py` — remove the `qr_token` line:

```python
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    qr_token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
```

becomes:

```python
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
```

Update the module docstring's first line to note the QR code now lives in `QrCode`:

```python
"""`Region` — a large planting-area grouping (e.g. "AAMA — Matias
Barbosa"). QR codes live in `app.models.qr_code.QrCode`, not on this model.
See docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""
```

- [ ] **Step 5: Register the model**

Edit `backend/app/models/__init__.py`:

```python
"""Domain models. Imported here so `Base.metadata` — and Alembic autogenerate — sees them."""

from app.models.photo import Photo
from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region

__all__ = ["Photo", "Planting", "QrCode", "Region"]
```

- [ ] **Step 6: Generate and hand-edit the migration**

Run: `alembic revision -m "qr code model"`

Replace `upgrade()`/`downgrade()` (keep the generated header/imports):

```python
def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "qr_codes",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("region_id", sa.UUID(), nullable=True),
        sa.Column("planting_id", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(region_id IS NOT NULL) != (planting_id IS NOT NULL)",
            name="ck_qr_codes_exactly_one_target",
        ),
        sa.UniqueConstraint("token", name="uq_qr_codes_token"),
        sa.UniqueConstraint("region_id", name="uq_qr_codes_region_id"),
        sa.UniqueConstraint("planting_id", name="uq_qr_codes_planting_id"),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["planting_id"], ["plantings.id"], ondelete="CASCADE"),
    )

    # `regions.qr_token` is superseded by `qr_codes` — no production data
    # exists yet (confirmed in the pivot brainstorm), so this drops the
    # column outright rather than migrating values.
    op.drop_constraint("uq_regions_qr_token", "regions", type_="unique")
    op.drop_column("regions", "qr_token")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("regions", sa.Column("qr_token", sa.Text(), nullable=True))
    op.execute("UPDATE regions SET qr_token = 'restored-' || id::text WHERE qr_token IS NULL")
    op.alter_column("regions", "qr_token", nullable=False)
    op.create_unique_constraint("uq_regions_qr_token", "regions", ["qr_token"])

    op.drop_table("qr_codes")
```

- [ ] **Step 7: Apply the migration to both databases**

Run:
```bash
alembic upgrade head
DATABASE_URL="$(grep '^TEST_DATABASE_URL=' .env | cut -d= -f2-)" alembic upgrade head
```
Expected: both commands apply cleanly.

- [ ] **Step 8: Run the model test to verify it passes**

Run: `pytest tests/test_qr_code_model.py -v`
Expected: PASS (6 tests)

- [ ] **Step 9: Write the failing service test**

Create `backend/tests/test_qr_code_service.py`:

```python
"""Tests for `app/services/qr_code_service.py`: creating and resolving
QR codes for Regions and Plantings. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region
from app.services import qr_code_service
from app.services.qr_code_service import QrTokenNotFound

_POINT_WKT = "POINT(-43.3130 -21.8845)"


def _add_region(db_session: Session, **overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"regiao-{uuid.uuid4().hex[:8]}",
        "name": "Região de teste",
        "geom": WKTElement(_POINT_WKT, srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID) -> Planting:
    planting = Planting(region_id=region_id, geom=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(planting)
    db_session.flush()
    return planting


def test_create_region_qr_code_persists_a_unique_token(db_session: Session) -> None:
    region = _add_region(db_session)

    token = qr_code_service.create_region_qr_code(db_session, region.id)
    db_session.commit()

    stored = db_session.execute(select(QrCode).where(QrCode.region_id == region.id)).scalar_one()
    assert stored.token == token


def test_create_planting_qr_code_persists_a_unique_token(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    token = qr_code_service.create_planting_qr_code(db_session, planting.id)
    db_session.commit()

    stored = db_session.execute(
        select(QrCode).where(QrCode.planting_id == planting.id)
    ).scalar_one()
    assert stored.token == token


def test_create_region_qr_code_generates_distinct_tokens(db_session: Session) -> None:
    region_a = _add_region(db_session)
    region_b = _add_region(db_session)

    token_a = qr_code_service.create_region_qr_code(db_session, region_a.id)
    token_b = qr_code_service.create_region_qr_code(db_session, region_b.id)

    assert token_a != token_b


def test_resolve_qr_token_finds_a_region(db_session: Session) -> None:
    region = _add_region(db_session)
    token = qr_code_service.create_region_qr_code(db_session, region.id)
    db_session.commit()

    target = qr_code_service.resolve_qr_token(db_session, token)

    assert target.kind == "region"
    assert target.identifier == region.slug


def test_resolve_qr_token_finds_a_planting(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    token = qr_code_service.create_planting_qr_code(db_session, planting.id)
    db_session.commit()

    target = qr_code_service.resolve_qr_token(db_session, token)

    assert target.kind == "planting"
    assert target.identifier == str(planting.id)


def test_resolve_qr_token_raises_for_an_unknown_token(db_session: Session) -> None:
    with pytest.raises(QrTokenNotFound):
        qr_code_service.resolve_qr_token(db_session, "does-not-exist")
```

- [ ] **Step 10: Run test to verify it fails**

Run: `pytest tests/test_qr_code_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.qr_code_service'`

- [ ] **Step 11: Write `qr_code_service.py`**

Create `backend/app/services/qr_code_service.py`:

```python
"""Create and resolve `QrCode` rows for `Region`/`Planting`. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.

Kept separate from `qr_service.py`, which stays a pure image-generation
function (token in, image bytes out) untouched by this pivot — this module
is the only place that reads/writes the `qr_codes` table.
"""

import secrets
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.qr_code import QrCode
from app.models.region import Region


class QrTokenNotFound(NotFoundError):
    code = "qr_token_not_found"

    def __init__(self, token: str) -> None:
        super().__init__(f'Nenhum QR code encontrado para o token "{token}".')


@dataclass(frozen=True)
class QrCodeTarget:
    """What a scanned token resolves to: a region (by `slug`) or a planting
    (by `id`) — a planting has no slug, see
    docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md."""

    kind: Literal["region", "planting"]
    identifier: str


def create_region_qr_code(db: Session, region_id: uuid.UUID) -> str:
    """Insert a new `QrCode` row for `region_id` and return its token.

    Does not commit — the caller (`region_service.create_region`) controls
    the transaction, same as every other write in this codebase.
    """
    token = secrets.token_urlsafe(9)
    db.add(QrCode(region_id=region_id, token=token))
    return token


def create_planting_qr_code(db: Session, planting_id: uuid.UUID) -> str:
    """Insert a new `QrCode` row for `planting_id` and return its token."""
    token = secrets.token_urlsafe(9)
    db.add(QrCode(planting_id=planting_id, token=token))
    return token


def resolve_qr_token(db: Session, token: str) -> QrCodeTarget:
    """Resolve a scanned `token` to the region or planting it points at.

    Raises `QrTokenNotFound` for an unknown token.
    """
    qr_code = db.execute(select(QrCode).where(QrCode.token == token)).scalar_one_or_none()
    if qr_code is None:
        raise QrTokenNotFound(token)

    if qr_code.region_id is not None:
        slug = db.execute(select(Region.slug).where(Region.id == qr_code.region_id)).scalar_one()
        return QrCodeTarget(kind="region", identifier=slug)

    return QrCodeTarget(kind="planting", identifier=str(qr_code.planting_id))
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pytest tests/test_qr_code_service.py -v`
Expected: PASS (6 tests)

- [ ] **Step 13: Wire `region_service.py` to source `qr_token` from `QrCode`**

Edit `backend/app/services/region_service.py`. Add imports:

```python
from app.models.qr_code import QrCode
from app.services import qr_code_service
```

Replace `_region_feature_columns()`:

```python
def _region_feature_columns() -> tuple[ColumnElement[Any], ...]:
    """Columns shared by the listing and single-region queries.

    `geom` is serialized to GeoJSON by PostGIS's `ST_AsGeoJSON`, never in
    Python. `qr_token` comes from an INNER JOIN on `qr_codes` — every region
    gets exactly one QrCode row at creation time
    (`qr_code_service.create_region_qr_code`), so a region missing one would
    be a data-integrity bug, not a valid "no QR yet" state; the INNER JOIN
    makes that invariant visible (such a region silently drops out of every
    listing) instead of surfacing as a 500 from a `NULL` where `qr_token`
    must be a `str`.

    `photo_count`/`latest_photo_at` are literals — see Task 4 of this plan,
    which replaces them with a real `planting_count`.
    """
    return (
        Region.id,
        Region.slug,
        Region.name,
        Region.description,
        Region.status,
        QrCode.token.label("qr_token"),
        Region.created_at,
        Region.updated_at,
        func.ST_AsGeoJSON(Region.geom).label("geometry_geojson"),
        literal(0).label("photo_count"),
        literal(None).label("latest_photo_at"),
    )


def _region_query() -> Any:
    return select(*_region_feature_columns()).join(QrCode, QrCode.region_id == Region.id)
```

(Leave `create_region`'s old `import secrets` usage in place for now — Step 14 below rewrites `create_region` to drop it, and only then should the import be removed. Removing it here first would leave the not-yet-rewritten `create_region` referencing a missing name.)

Update every function that built its own `select(*_region_feature_columns())...` to start from `_region_query()` instead:

```python
def list_regions(db: Session) -> RegionFeatureCollection:
    rows = db.execute(_region_query().where(_PUBLICLY_VISIBLE).order_by(Region.name, Region.id)).all()
    return RegionFeatureCollection(features=[_row_to_feature(row) for row in rows])


def get_region(db: Session, identifier: str) -> RegionFeature:
    row = db.execute(
        _region_query().where(_identifier_filter(identifier), _PUBLICLY_VISIBLE)
    ).first()
    if row is None:
        raise RegionNotFound(identifier)
    return _row_to_feature(row)
```

```python
def _fetch_feature_by_id(db: Session, region_id: uuid.UUID) -> RegionFeature:
    row = db.execute(_region_query().where(Region.id == region_id)).first()
    if row is None:
        raise RegionNotFound(str(region_id))
    return _row_to_feature(row)
```

- [ ] **Step 14: Update `create_region` to create the `QrCode` row**

Replace `create_region`:

```python
def create_region(db: Session, payload: RegionCreate) -> RegionFeature:
    region = Region(
        slug=_generate_unique_slug(db, payload.name),
        name=payload.name,
        description=payload.description,
        geom=_geometry_to_geom_expression(payload.geometry),
        status=payload.status,
    )
    db.add(region)
    db.flush()  # assigns region.id (server-side gen_random_uuid()) before the QrCode FK needs it
    qr_code_service.create_region_qr_code(db, region.id)
    db.commit()
    return _fetch_feature_by_id(db, region.id)
```

Now that `create_region` no longer calls `secrets.token_urlsafe(...)`, remove the file's `import secrets` line — confirm nothing else in the file still uses `secrets` first: `grep secrets backend/app/services/region_service.py` should only show the import line itself before you delete it.

- [ ] **Step 15: Fix the three region tests broken by the model change**

Edit `backend/tests/test_region_model.py` — `_make_region`'s defaults no longer include `qr_token` (the column doesn't exist anymore):

```python
def _make_region(**overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": "canteiro-1",
        "name": "Canteiro 1",
        "geom": WKTElement(_POLYGON_WKT, srid=4326),
    }
    defaults.update(overrides)
    return Region(**defaults)
```

Edit `backend/tests/test_photo_model.py` — same fix, drop `"qr_token": f"token-{uuid.uuid4().hex[:8]}",` from its `_make_region` defaults.

Edit `backend/tests/test_region_service.py` — every test that builds a `Region` directly now also needs a matching `QrCode` row, since `list_regions`/`get_region` INNER JOIN on it. Replace the `_make_region` helper and every direct `db_session.add(_make_region(...))` call:

```python
import uuid

from app.models.qr_code import QrCode
from app.models.region import Region
from app.services import region_service
from app.services.region_service import RegionNotFound

_POINT_A = "POINT(-43.3130 -21.8845)"
_POINT_B = "POINT(-43.3200 -21.8900)"


def _add_region(db_session: Session, **overrides: object) -> Region:
    """Insert a `Region` plus the `QrCode` row every real region gets at
    creation time (`region_service.create_region`) — the listing/read
    queries INNER JOIN on it, so a region without one wouldn't be a
    realistic fixture.
    """
    defaults: dict[str, object] = {
        "slug": "canteiro-a",
        "name": "Canteiro A",
        "geom": WKTElement(_POINT_A, srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return region
```

Then replace every `db_session.add(_make_region(...))` / `db_session.add(_make_region())` call in that file with `_add_region(db_session, ...)` (drop the now-redundant `db_session.commit()` right after only where a test previously relied on `_make_region` + a separate `db_session.add`/`commit()` pair — `_add_region` already flushes; keep the existing `db_session.commit()` calls that follow, since tests still commit before querying). For example:

```python
def test_list_regions_returns_a_valid_feature_collection(db_session: Session) -> None:
    _add_region(db_session)
    _add_region(db_session, slug="canteiro-b", name="Canteiro B", geom=WKTElement(_POINT_B, srid=4326))
    db_session.commit()

    collection = region_service.list_regions(db_session)

    assert collection.type == "FeatureCollection"
    names = [feature.properties.name for feature in collection.features]
    assert names == ["Canteiro A", "Canteiro B"]  # ordered by name
```

Apply the same `_make_region(...)` → `_add_region(db_session, ...)` substitution to the rest of that file's tests (`test_list_regions_serializes_geometry_and_default_photo_fields`, `test_list_regions_excludes_draft_and_archived_regions`, `test_get_region_resolves_by_slug`, `test_get_region_resolves_by_uuid`, `test_get_region_raises_not_found_for_an_archived_region`) — the two "not found" tests (`test_get_region_raises_not_found_for_unknown_slug`/`_uuid`) create no region and need no change.

`test_list_regions_runs_a_single_query` still expects exactly one `SELECT` — the join doesn't change that (it's one query with a `JOIN`, not two queries), so its assertion is unaffected; only update its `_make_region` calls to `_add_region(db_session, ...)` the same way.

Edit `backend/tests/test_region_qr_route.py` similarly — replace `_make_region` (which passed `qr_token=...` directly) with an `_add_region` helper matching the one above, and update every call site (`db_session.add(_make_region())` → `_add_region(db_session)`, with the specific token/slug/status kwargs each test passed today preserved as `_add_region(db_session, ...)` kwargs, and `token=` renamed to match `_add_region`'s `QrCode(token=...)` insertion — e.g. `_add_region(db_session, slug="canteiro-draft", status="draft", token="token-draft")`, with `_add_region` accepting an explicit `token` kwarg defaulting to a random one:

```python
def _add_region(db_session: Session, *, token: str | None = None, **overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": "canteiro-qr",
        "name": "Canteiro QR",
        "geom": WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=token or f"token-{uuid.uuid4().hex[:8]}"))
    return region
```

Update every test in that file to call `_add_region(db_session, token="token-qr-abc")` (for the base case) or with the specific `slug`/`status`/`token` combination it used before, then keep `db_session.commit()` as the next line, unchanged. Add `import uuid` and `from app.models.qr_code import QrCode` at the top of the file.

- [ ] **Step 16: Fix `scripts/seed.py`'s `qr_token=` call**

Edit `backend/scripts/seed.py` — `seed()` currently passes `qr_token=secrets.token_urlsafe(9)` straight to `Region(...)`, which no longer accepts that kwarg. Minimal fix (the full plantings rewrite is Task 8):

```python
from app.services.qr_code_service import create_region_qr_code
```

Replace the `if region is None:` branch:

```python
        if region is None:
            new_region = Region(
                slug=slug,
                name=name,
                description=_PLACEHOLDER_DESCRIPTION,
                geom=geom,
            )
            db.add(new_region)
            db.flush()
            create_region_qr_code(db, new_region.id)
            created += 1
```

(`region.id` after `flush()` is what `create_region_qr_code` needs — same pattern as `region_service.create_region`.) Remove the now-unused `import secrets` from `scripts/seed.py` only if nothing else in that file uses it — check with `grep secrets backend/scripts/seed.py` first.

Edit `backend/tests/test_seed_script.py`'s `test_seed_preserves_qr_token_across_reruns` — `Region.qr_token` no longer exists as a column, so `select(Region.qr_token)` breaks. Replace it with a query through `QrCode`:

```python
from app.models.qr_code import QrCode


def test_seed_preserves_qr_token_across_reruns(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)
    first_region_id = db_session.execute(
        select(Region.id).order_by(Region.slug).limit(1)
    ).scalar_one()
    original_token = db_session.execute(
        select(QrCode.token).where(QrCode.region_id == first_region_id)
    ).scalar_one()

    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)
    token_after_rerun = db_session.execute(
        select(QrCode.token).where(QrCode.region_id == first_region_id)
    ).scalar_one()

    assert original_token == token_after_rerun
```

- [ ] **Step 17: Run the full backend suite to verify nothing else broke**

Run: `pytest -v`
Expected: PASS — every test, including the ones just edited.

- [ ] **Step 18: Commit**

```bash
git add backend/app/models/qr_code.py backend/app/models/region.py backend/app/models/__init__.py \
  backend/alembic/versions backend/app/services/qr_code_service.py backend/app/services/region_service.py \
  backend/scripts/seed.py backend/tests/test_qr_code_model.py backend/tests/test_qr_code_service.py \
  backend/tests/test_region_model.py backend/tests/test_region_service.py backend/tests/test_region_qr_route.py \
  backend/tests/test_photo_model.py backend/tests/test_seed_script.py
git commit -m "feat: adiciona entidade QrCode compartilhada e migra Region para usá-la"
```

---

## Task 3: `planting_service`, `planting` schemas, and `/api/plantings` routes

**Files:**
- Create: `backend/app/schemas/planting.py`
- Create: `backend/app/services/planting_service.py`
- Create: `backend/app/api/routes/plantings.py`
- Modify: `backend/app/api/routes/__init__.py`
- Test: `backend/tests/test_planting_service.py`
- Test: `backend/tests/test_planting_routes.py`
- Test: `backend/tests/test_planting_admin_routes.py`
- Test: `backend/tests/test_planting_qr_route.py`

**Interfaces:**
- Consumes: `app.models.planting.Planting` (Task 1), `app.models.qr_code.QrCode`/`qr_code_service.create_planting_qr_code` (Task 2), `app.schemas.geojson.{Feature,FeatureCollection,Point,Polygon,MultiPolygon}`, `app.core.security.require_admin_token`, `app.services.qr_service.generate_qr_code`/`MAX_BOX_SIZE`.
- Produces:
  - `app.schemas.planting.{PlantingStatus, PlantingGeometry, PlantingProperties, PlantingFeature, PlantingFeatureCollection, PlantingCreate, PlantingUpdate}`.
  - `app.services.planting_service.PlantingNotFound(NotFoundError)`.
  - `app.services.planting_service.list_plantings(db: Session, *, region_id: uuid.UUID | None = None) -> PlantingFeatureCollection`
  - `app.services.planting_service.get_planting(db: Session, planting_id: uuid.UUID) -> PlantingFeature`
  - `app.services.planting_service.create_planting(db: Session, payload: PlantingCreate) -> PlantingFeature`
  - `app.services.planting_service.update_planting(db: Session, planting_id: uuid.UUID, payload: PlantingUpdate) -> PlantingFeature`
  - Routes: `GET /api/plantings` (optional `?region_id=`), `GET /api/plantings/{planting_id}`, `GET /api/plantings/{planting_id}/qr-code`, `POST /api/plantings` (admin), `PATCH /api/plantings/{planting_id}` (admin).

- [ ] **Step 1: Write the failing schema/service test**

Create `backend/tests/test_planting_service.py`:

```python
"""Tests for `app/services/planting_service.py`: listing, resolution, and
admin create/update of Plantings. Mirrors
`backend/tests/test_region_service.py` — see
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region
from app.schemas.planting import PlantingCreate, PlantingUpdate
from app.services import planting_service, qr_code_service
from app.services.planting_service import PlantingNotFound

_POINT_A = "POINT(-43.3130 -21.8845)"
_POINT_B = "POINT(-43.3200 -21.8900)"


def _add_region(db_session: Session, **overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"regiao-{uuid.uuid4().hex[:8]}",
        "name": "Região de teste",
        "geom": WKTElement(_POINT_A, srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID, **overrides: object) -> Planting:
    defaults: dict[str, object] = {
        "region_id": region_id,
        "geom": WKTElement(_POINT_A, srid=4326),
    }
    defaults.update(overrides)
    planting = Planting(**defaults)
    db_session.add(planting)
    db_session.flush()
    db_session.add(QrCode(planting_id=planting.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return planting


def test_list_plantings_returns_a_valid_feature_collection(db_session: Session) -> None:
    region = _add_region(db_session)
    _add_planting(db_session, region.id)
    _add_planting(db_session, region.id, geom=WKTElement(_POINT_B, srid=4326))
    db_session.commit()

    collection = planting_service.list_plantings(db_session)

    assert collection.type == "FeatureCollection"
    assert len(collection.features) == 2


def test_list_plantings_filters_by_region_id(db_session: Session) -> None:
    region_a = _add_region(db_session)
    region_b = _add_region(db_session)
    _add_planting(db_session, region_a.id)
    _add_planting(db_session, region_b.id)
    db_session.commit()

    collection = planting_service.list_plantings(db_session, region_id=region_a.id)

    assert len(collection.features) == 1
    assert collection.features[0].properties.region_id == region_a.id


def test_list_plantings_excludes_draft_and_archived(db_session: Session) -> None:
    region = _add_region(db_session)
    _add_planting(db_session, region.id)
    _add_planting(db_session, region.id, status="draft")
    _add_planting(db_session, region.id, status="archived")
    db_session.commit()

    collection = planting_service.list_plantings(db_session)

    assert len(collection.features) == 1


def test_get_planting_returns_the_feature(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id, species="Ipê-amarelo", nickname="Muda da Ana")
    db_session.commit()

    feature = planting_service.get_planting(db_session, planting.id)

    assert feature.properties.species == "Ipê-amarelo"
    assert feature.properties.nickname == "Muda da Ana"
    assert feature.properties.region_id == region.id
    assert feature.properties.qr_token


def test_get_planting_raises_not_found_for_unknown_id(db_session: Session) -> None:
    with pytest.raises(PlantingNotFound):
        planting_service.get_planting(db_session, uuid.uuid4())


def test_get_planting_raises_not_found_for_an_archived_planting(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id, status="archived")
    db_session.commit()

    with pytest.raises(PlantingNotFound):
        planting_service.get_planting(db_session, planting.id)


def test_create_planting_persists_fields_and_creates_a_qr_code(db_session: Session) -> None:
    region = _add_region(db_session)
    db_session.commit()

    payload = PlantingCreate(
        region_id=region.id,
        geometry={"type": "Point", "coordinates": (-43.3130, -21.8845)},
        species="Jacarandá",
        nickname="A árvore da Ana",
        planted_by="Ana",
    )

    feature = planting_service.create_planting(db_session, payload)

    assert feature.properties.species == "Jacarandá"
    assert feature.properties.nickname == "A árvore da Ana"
    assert feature.properties.planted_by == "Ana"
    assert feature.properties.qr_token
    qr_code_count = (
        db_session.query(QrCode).filter(QrCode.planting_id == uuid.UUID(feature.id)).count()
    )
    assert qr_code_count == 1


def test_update_planting_changes_only_given_fields(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id, species="Ipê-amarelo")
    db_session.commit()

    feature = planting_service.update_planting(
        db_session, planting.id, PlantingUpdate(nickname="Nova muda")
    )

    assert feature.properties.nickname == "Nova muda"
    assert feature.properties.species == "Ipê-amarelo"  # untouched
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_planting_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.planting'`

- [ ] **Step 3: Write `app/schemas/planting.py`**

```python
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
```

- [ ] **Step 4: Write `app/services/planting_service.py`**

```python
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

from app.core.errors import NotFoundError
from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.schemas.planting import (
    PlantingCreate,
    PlantingFeature,
    PlantingFeatureCollection,
    PlantingProperties,
    PlantingUpdate,
)
from app.services import qr_code_service


class PlantingNotFound(NotFoundError):
    code = "planting_not_found"

    def __init__(self, identifier: uuid.UUID) -> None:
        super().__init__(f'Nenhuma muda encontrada para "{identifier}".')


_PUBLICLY_VISIBLE: ColumnElement[bool] = Planting.status == "active"


def _planting_feature_columns() -> tuple[ColumnElement[Any], ...]:
    """`qr_token` via INNER JOIN — every planting gets exactly one QrCode at
    creation time (`qr_code_service.create_planting_qr_code`), same
    invariant `region_service._region_feature_columns` documents.

    `photo_count`/`latest_photo_at` are literal placeholders until Task 6 of
    this plan wires them to real `photos` data (that table doesn't
    reference `planting_id` yet at this point in the plan).
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
    row = db.execute(
        _planting_query().where(Planting.id == planting_id, _PUBLICLY_VISIBLE)
    ).first()
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


def update_planting(db: Session, planting_id: uuid.UUID, payload: PlantingUpdate) -> PlantingFeature:
    planting = db.get(Planting, planting_id)
    if planting is None:
        raise PlantingNotFound(planting_id)

    changed_fields = payload.model_dump(exclude_unset=True, exclude={"geometry"})
    for field, value in changed_fields.items():
        setattr(planting, field, value)
    if payload.geometry is not None:
        planting.geom = _geometry_to_geom_expression(payload.geometry)

    db.commit()
    return _fetch_feature_by_id(db, planting.id)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_planting_service.py -v`
Expected: PASS (9 tests). If `db.get(Planting, planting_id)` in `update_planting` raises an `IntegrityError` due to an FK on `region_id` you didn't touch, ignore — that path isn't exercised in this test file.

- [ ] **Step 6: Write the failing route tests**

Create `backend/tests/test_planting_routes.py`:

```python
"""Tests for `GET /api/plantings` and `GET /api/plantings/{planting_id}`.
Mirrors `backend/tests/test_region_routes.py` shape."""

import uuid

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region

_POINT = "POINT(-43.3130 -21.8845)"


def _add_region(db_session: Session, **overrides: object) -> Region:
    defaults: dict[str, object] = {
        "slug": f"regiao-{uuid.uuid4().hex[:8]}",
        "name": "Região de teste",
        "geom": WKTElement(_POINT, srid=4326),
    }
    defaults.update(overrides)
    region = Region(**defaults)
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID, **overrides: object) -> Planting:
    defaults: dict[str, object] = {"region_id": region_id, "geom": WKTElement(_POINT, srid=4326)}
    defaults.update(overrides)
    planting = Planting(**defaults)
    db_session.add(planting)
    db_session.flush()
    db_session.add(QrCode(planting_id=planting.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return planting


def test_list_plantings_returns_200(client: TestClient, db_session: Session) -> None:
    region = _add_region(db_session)
    _add_planting(db_session, region.id)
    db_session.commit()

    response = client.get("/api/plantings")

    assert response.status_code == 200
    assert response.json()["type"] == "FeatureCollection"
    assert len(response.json()["features"]) == 1


def test_list_plantings_filters_by_region_id_query_param(
    client: TestClient, db_session: Session
) -> None:
    region_a = _add_region(db_session)
    region_b = _add_region(db_session)
    _add_planting(db_session, region_a.id)
    _add_planting(db_session, region_b.id)
    db_session.commit()

    response = client.get(f"/api/plantings?region_id={region_a.id}")

    assert response.status_code == 200
    assert len(response.json()["features"]) == 1


def test_get_planting_returns_200(client: TestClient, db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id, species="Ipê-amarelo")
    db_session.commit()

    response = client.get(f"/api/plantings/{planting.id}")

    assert response.status_code == 200
    assert response.json()["properties"]["species"] == "Ipê-amarelo"


def test_get_planting_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get(f"/api/plantings/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["code"] == "planting_not_found"


def test_get_planting_returns_422_for_a_malformed_id(client: TestClient) -> None:
    response = client.get("/api/plantings/not-a-uuid")

    assert response.status_code == 422
```

Create `backend/tests/test_planting_admin_routes.py`:

```python
"""Tests for `POST /api/plantings` and `PATCH /api/plantings/{planting_id}`.
Mirrors `backend/tests/test_region_admin_routes.py`."""

import uuid

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.qr_code import QrCode
from app.models.region import Region

_VALID_HEADERS = {"X-Admin-Token": settings.admin_api_token}


def _add_region(db_session: Session) -> Region:
    region = Region(
        slug=f"regiao-{uuid.uuid4().hex[:8]}",
        name="Região de teste",
        geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    db_session.commit()
    return region


def _create_payload(region_id: uuid.UUID) -> dict[str, object]:
    return {
        "region_id": str(region_id),
        "geometry": {"type": "Point", "coordinates": [-43.3130, -21.8845]},
        "species": "Ipê-amarelo",
        "nickname": "A árvore da Ana",
    }


def test_create_planting_without_header_returns_401(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)

    response = client.post("/api/plantings", json=_create_payload(region.id))

    assert response.status_code == 401


def test_create_planting_with_valid_header_returns_201(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)

    response = client.post(
        "/api/plantings", json=_create_payload(region.id), headers=_VALID_HEADERS
    )

    assert response.status_code == 201
    body = response.json()
    assert body["properties"]["species"] == "Ipê-amarelo"
    assert body["properties"]["qr_token"]


def test_update_planting_without_header_returns_401(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)
    created = client.post(
        "/api/plantings", json=_create_payload(region.id), headers=_VALID_HEADERS
    ).json()

    response = client.patch(f"/api/plantings/{created['id']}", json={"nickname": "Novo apelido"})

    assert response.status_code == 401


def test_update_planting_with_valid_header_returns_200(
    client: TestClient, db_session: Session
) -> None:
    region = _add_region(db_session)
    created = client.post(
        "/api/plantings", json=_create_payload(region.id), headers=_VALID_HEADERS
    ).json()

    response = client.patch(
        f"/api/plantings/{created['id']}",
        json={"nickname": "Novo apelido"},
        headers=_VALID_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["properties"]["nickname"] == "Novo apelido"
```

Create `backend/tests/test_planting_qr_route.py`:

```python
"""Tests for `GET /api/plantings/{planting_id}/qr-code`. Mirrors
`backend/tests/test_region_qr_route.py`."""

import io
import uuid

import zxingcpp
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region


def _add_region(db_session: Session) -> Region:
    region = Region(
        slug=f"regiao-{uuid.uuid4().hex[:8]}",
        name="Região de teste",
        geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=f"token-{uuid.uuid4().hex[:8]}"))
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID, token: str) -> Planting:
    planting = Planting(region_id=region_id, geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326))
    db_session.add(planting)
    db_session.flush()
    db_session.add(QrCode(planting_id=planting.id, token=token))
    return planting


def _expected_url(token: str) -> str:
    return f"{str(settings.public_web_base_url).rstrip('/')}/r/{token}"


def _decode_png(png_bytes: bytes) -> str:
    [result] = zxingcpp.read_barcodes(Image.open(io.BytesIO(png_bytes)))
    return result.text


def test_get_planting_qr_code_defaults_to_png(client: TestClient, db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id, "token-planting-abc")
    db_session.commit()

    response = client.get(f"/api/plantings/{planting.id}/qr-code")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert _decode_png(response.content) == _expected_url("token-planting-abc")


def test_get_planting_qr_code_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get(f"/api/plantings/{uuid.uuid4()}/qr-code")

    assert response.status_code == 404
    assert response.json()["code"] == "planting_not_found"
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `pytest tests/test_planting_routes.py tests/test_planting_admin_routes.py tests/test_planting_qr_route.py -v`
Expected: FAIL — `404 Not Found` on every request (no `/api/plantings` route registered yet).

- [ ] **Step 8: Write `app/api/routes/plantings.py`**

```python
"""`GET`/`POST`/`PATCH /api/plantings` and `GET /api/plantings/{id}/qr-code`.
Mirrors `app/api/routes/regions.py`. Writes are admin-only (`X-Admin-Token`),
same rule as regions.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.schemas.planting import (
    PlantingCreate,
    PlantingFeature,
    PlantingFeatureCollection,
    PlantingUpdate,
)
from app.services import planting_service, qr_service

router = APIRouter(prefix="/api/plantings", tags=["plantings"])


@router.get("", response_model=PlantingFeatureCollection)
def list_plantings(
    region_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
) -> PlantingFeatureCollection:
    return planting_service.list_plantings(db, region_id=region_id)


@router.get("/{planting_id}", response_model=PlantingFeature)
def get_planting(
    planting_id: uuid.UUID,
    db: Session = Depends(get_db),  # noqa: B008
) -> PlantingFeature:
    return planting_service.get_planting(db, planting_id)


@router.get("/{planting_id}/qr-code")
def get_planting_qr_code(
    planting_id: uuid.UUID,
    format: Literal["png", "svg"] = Query(default="png"),
    size: int | None = Query(default=None, gt=0, le=qr_service.MAX_BOX_SIZE),
    db: Session = Depends(get_db),  # noqa: B008
) -> Response:
    """Public (no admin token) — same visibility rule as
    `GET /{planting_id}` (`planting_service.get_planting` 404s for a
    `draft`/`archived` planting here too, same rationale as the region
    QR route)."""
    feature = planting_service.get_planting(db, planting_id)
    image_bytes, content_type = qr_service.generate_qr_code(
        feature.properties.qr_token, format=format, size=size
    )
    return Response(content=image_bytes, media_type=content_type)


@router.post(
    "",
    response_model=PlantingFeature,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_token)],
)
def create_planting(
    payload: PlantingCreate,
    db: Session = Depends(get_db),  # noqa: B008
) -> PlantingFeature:
    return planting_service.create_planting(db, payload)


@router.patch(
    "/{planting_id}",
    response_model=PlantingFeature,
    dependencies=[Depends(require_admin_token)],
)
def update_planting(
    planting_id: uuid.UUID,
    payload: PlantingUpdate,
    db: Session = Depends(get_db),  # noqa: B008
) -> PlantingFeature:
    return planting_service.update_planting(db, planting_id, payload)
```

- [ ] **Step 9: Register the router**

Edit `backend/app/api/routes/__init__.py`:

```python
"""Single mount point for all route modules.

Route modules (health, regions, plantings, photos, ...) register themselves
on this router as they are implemented; `app.main` only ever imports
`api_router`, so it never needs to know which route modules currently exist.
"""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.photos import file_router as photo_files_router
from app.api.routes.photos import router as photos_router
from app.api.routes.plantings import router as plantings_router
from app.api.routes.regions import router as regions_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(regions_router)
api_router.include_router(plantings_router)
api_router.include_router(photos_router)
api_router.include_router(photo_files_router)
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `pytest tests/test_planting_routes.py tests/test_planting_admin_routes.py tests/test_planting_qr_route.py -v`
Expected: PASS (11 tests)

- [ ] **Step 11: Run the full backend suite**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 12: Commit**

```bash
git add backend/app/schemas/planting.py backend/app/services/planting_service.py \
  backend/app/api/routes/plantings.py backend/app/api/routes/__init__.py \
  backend/tests/test_planting_service.py backend/tests/test_planting_routes.py \
  backend/tests/test_planting_admin_routes.py backend/tests/test_planting_qr_route.py
git commit -m "feat: adiciona CRUD e rotas de Planting"
```

---

## Task 4: Region exposes `planting_count` instead of `photo_count`/`latest_photo_at`

**Files:**
- Modify: `backend/app/schemas/region.py`
- Modify: `backend/app/services/region_service.py`
- Modify: `backend/tests/test_region_service.py`

**Interfaces:**
- Consumes: `app.models.planting.Planting` (Task 1).
- Produces: `RegionProperties.planting_count: int` replaces `RegionProperties.photo_count`/`RegionProperties.latest_photo_at`.

- [ ] **Step 1: Write the failing test**

Edit `backend/tests/test_region_service.py`, replace `test_list_regions_serializes_geometry_and_default_photo_fields`:

```python
def test_list_regions_serializes_geometry_and_planting_count(db_session: Session) -> None:
    region = _add_region(db_session)
    db_session.commit()
    _add_planting(db_session, region.id)
    _add_planting(db_session, region.id, geom=WKTElement(_POINT_B, srid=4326))
    db_session.commit()

    [feature] = region_service.list_regions(db_session).features

    assert feature.geometry.type == "Point"
    assert feature.geometry.coordinates == pytest.approx((-43.3130, -21.8845))
    assert feature.properties.planting_count == 2
```

Add a `_add_planting` helper right below `_add_region` in the same file:

```python
from app.models.planting import Planting


def _add_planting(db_session: Session, region_id: uuid.UUID, **overrides: object) -> Planting:
    defaults: dict[str, object] = {"region_id": region_id, "geom": WKTElement(_POINT_A, srid=4326)}
    defaults.update(overrides)
    planting = Planting(**defaults)
    db_session.add(planting)
    db_session.flush()
    return planting
```

Also add a test proving `planting_count` only counts `active` plantings:

```python
def test_list_regions_planting_count_excludes_draft_and_archived(db_session: Session) -> None:
    region = _add_region(db_session)
    db_session.commit()
    _add_planting(db_session, region.id)
    _add_planting(db_session, region.id, status="draft")
    _add_planting(db_session, region.id, status="archived")
    db_session.commit()

    [feature] = region_service.list_regions(db_session).features

    assert feature.properties.planting_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_region_service.py -v -k planting_count`
Expected: FAIL with `AttributeError: 'RegionProperties' object has no attribute 'planting_count'` (or a Pydantic validation error, since `photo_count`/`latest_photo_at` are still what the schema defines).

- [ ] **Step 3: Update `RegionProperties`**

Edit `backend/app/schemas/region.py`:

```python
class RegionProperties(BaseModel):
    """The `properties` object of a region `Feature`."""

    slug: str
    name: str
    description: str | None
    status: RegionStatus
    qr_token: str
    planting_count: int
    created_at: datetime
    updated_at: datetime
```

(removes `photo_count: int` and `latest_photo_at: datetime | None`).

- [ ] **Step 4: Update `region_service.py`**

Add the import:

```python
from app.models.planting import Planting
```

Replace `_region_feature_columns()`'s tail:

```python
def _region_feature_columns() -> tuple[ColumnElement[Any], ...]:
    """... (docstring as edited in Task 2, plus:)

    `planting_count` is a correlated scalar subquery, not a `GROUP BY` —
    keeps this a flat per-row column list (matching the existing query
    shape) instead of forcing every other column into a `GROUP BY` clause.
    """
    planting_count = (
        select(func.count())
        .select_from(Planting)
        .where(Planting.region_id == Region.id, Planting.status == "active")
        .scalar_subquery()
    )
    return (
        Region.id,
        Region.slug,
        Region.name,
        Region.description,
        Region.status,
        QrCode.token.label("qr_token"),
        Region.created_at,
        Region.updated_at,
        func.ST_AsGeoJSON(Region.geom).label("geometry_geojson"),
        planting_count.label("planting_count"),
    )
```

Update `_row_to_feature`:

```python
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
            planting_count=row.planting_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        ),
    )
```

Remove the now-unused `literal` import if nothing else in the file uses it — check with `grep literal backend/app/services/region_service.py` first.

- [ ] **Step 5: Fix the other test broken by the schema change**

Edit `backend/tests/test_region_service.py`'s `test_list_regions_runs_a_single_query` — unaffected by the column change (still one `SELECT`), but confirm the scalar subquery doesn't add a second top-level `SELECT` statement to `executed_statements` by rerunning it (it shouldn't — a scalar subquery is part of the same statement).

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_region_service.py -v`
Expected: PASS

- [ ] **Step 7: Run the full backend suite**

Run: `pytest -v`
Expected: PASS — this touches `RegionProperties`, which `test_region_admin_routes.py` also asserts on (`body["properties"]["qr_token"]`/`slug`/`status`, none of which changed) and `test_region_routes.py` if it exists; confirm both stay green. If either asserts `photo_count`/`latest_photo_at` directly, update that assertion to `planting_count` (expected `0` for a freshly created region with no plantings).

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/region.py backend/app/services/region_service.py backend/tests/test_region_service.py
git commit -m "feat: substitui photo_count/latest_photo_at por planting_count em Region"
```

---

## Task 5: `GET /api/qr/{token}` resolution route

**Files:**
- Create: `backend/app/api/routes/qr.py`
- Modify: `backend/app/api/routes/__init__.py`
- Test: `backend/tests/test_qr_resolve_route.py`

**Interfaces:**
- Consumes: `app.services.qr_code_service.{resolve_qr_token, QrTokenNotFound}` (Task 2).
- Produces: `GET /api/qr/{token}` → `{"type": "region" | "planting", "identifier": str}` (region's `slug`, or planting's `id`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_qr_resolve_route.py`:

```python
"""Tests for `GET /api/qr/{token}` — resolves a scanned QR token to the
region or planting it points at (the frontend's `/r/:qrToken` redirect
depends on this)."""

import uuid

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region


def _add_region(db_session: Session, token: str) -> Region:
    region = Region(
        slug="canteiro-alvo",
        name="Canteiro Alvo",
        geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    db_session.add(QrCode(region_id=region.id, token=token))
    return region


def test_resolve_region_token(client: TestClient, db_session: Session) -> None:
    _add_region(db_session, "token-region-abc")
    db_session.commit()

    response = client.get("/api/qr/token-region-abc")

    assert response.status_code == 200
    assert response.json() == {"type": "region", "identifier": "canteiro-alvo"}


def test_resolve_planting_token(client: TestClient, db_session: Session) -> None:
    region = _add_region(db_session, "token-region-owner")
    planting = Planting(region_id=region.id, geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326))
    db_session.add(planting)
    db_session.flush()
    db_session.add(QrCode(planting_id=planting.id, token="token-planting-xyz"))
    db_session.commit()

    response = client.get("/api/qr/token-planting-xyz")

    assert response.status_code == 200
    assert response.json() == {"type": "planting", "identifier": str(planting.id)}


def test_resolve_unknown_token_returns_404(client: TestClient) -> None:
    response = client.get("/api/qr/does-not-exist")

    assert response.status_code == 404
    assert response.json()["code"] == "qr_token_not_found"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qr_resolve_route.py -v`
Expected: FAIL with `404 Not Found` (no route registered).

- [ ] **Step 3: Write `app/api/routes/qr.py`**

```python
"""`GET /api/qr/{token}` — resolves a scanned QR token to the region or
planting it points at. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md.
"""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import qr_code_service

router = APIRouter(prefix="/api/qr", tags=["qr"])


class QrResolution(BaseModel):
    """Where a scanned token points. The frontend builds the destination
    path itself: `/regions/{identifier}` for a region, `/plantings/{identifier}`
    for a planting — this endpoint only tells it which."""

    type: Literal["region", "planting"]
    identifier: str


@router.get("/{token}", response_model=QrResolution)
def resolve_qr_token(
    token: str,
    db: Session = Depends(get_db),  # noqa: B008
) -> QrResolution:
    target = qr_code_service.resolve_qr_token(db, token)
    return QrResolution(type=target.kind, identifier=target.identifier)
```

- [ ] **Step 4: Register the router**

Edit `backend/app/api/routes/__init__.py`, add:

```python
from app.api.routes.qr import router as qr_router
```

and register it:

```python
api_router.include_router(qr_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_qr_resolve_route.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/qr.py backend/app/api/routes/__init__.py backend/tests/test_qr_resolve_route.py
git commit -m "feat: adiciona resolução de token de QR code via GET /api/qr/{token}"
```

---

## Task 6: `Photo` moves from `region_id` to `planting_id`

**Files:**
- Modify: `backend/app/models/photo.py`
- Create: `backend/alembic/versions/<generated>_photo_planting_id.py`
- Modify: `backend/app/schemas/photo.py`
- Modify: `backend/app/services/photo_service.py`
- Modify: `backend/app/services/planting_service.py` (real `photo_count`/`latest_photo_at`)
- Modify: `backend/app/api/routes/photos.py`
- Modify: `backend/tests/test_photo_model.py`
- Modify: `backend/tests/test_photo_service.py`
- Modify: `backend/tests/test_photo_routes.py`
- Modify: `backend/tests/test_photo_file_route.py`
- Modify: `backend/tests/test_planting_service.py` (adds photo-count coverage)

**Interfaces:**
- Consumes: `app.models.planting.Planting`/`app.services.planting_service.{get_planting, PlantingNotFound}` (Tasks 1 and 3).
- Produces: `app.models.photo.Photo.planting_id` (replaces `region_id`). `photo_service.list_planting_photos(db, planting_id: uuid.UUID, *, cursor=None, limit=...) -> PhotoPage` (renamed from `list_region_photos`, its identifier parameter is now a plain `uuid.UUID`, not a slug-or-UUID string — a Planting has no slug). Route path `GET/POST /api/plantings/{planting_id}/photos` (replaces `/api/regions/{region}/photos`).

- [ ] **Step 1: Write the failing model test**

Rewrite `backend/tests/test_photo_model.py`:

```python
"""Tests for the `Photo` model and its migration (backend/app/models/photo.py).

`Photo.planting_id` replaces `region_id` — see
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md: fotos
belong to an individual Planting, never directly to a Region.
"""

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.photo import Photo
from app.models.planting import Planting
from app.models.region import Region

_POINT_WKT = "POINT(-43.3127 -21.8843)"


def _add_region(db_session: Session) -> Region:
    region = Region(
        slug=f"regiao-{uuid.uuid4().hex[:8]}",
        name="Região de teste",
        geom=WKTElement(_POINT_WKT, srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID) -> Planting:
    planting = Planting(region_id=region_id, geom=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(planting)
    db_session.flush()
    return planting


def _make_photo(planting_id: uuid.UUID, **overrides: object) -> Photo:
    defaults: dict[str, object] = {
        "planting_id": planting_id,
        "storage_key": f"photos/{uuid.uuid4().hex}.jpg",
        "content_type": "image/jpeg",
        "byte_size": 123_456,
        "width": 1080,
        "height": 1350,
    }
    defaults.update(overrides)
    return Photo(**defaults)


def test_photo_is_created_with_location_null(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    photo = _make_photo(planting.id)
    db_session.add(photo)
    db_session.commit()

    stored = db_session.execute(select(Photo).where(Photo.id == photo.id)).scalar_one()
    assert stored.location is None
    assert stored.status == "published"


def test_photo_accepts_a_valid_point_location(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    photo = _make_photo(planting.id, location=WKTElement(_POINT_WKT, srid=4326))
    db_session.add(photo)
    db_session.commit()

    stored = db_session.execute(select(Photo).where(Photo.id == photo.id)).scalar_one()
    assert stored.location is not None


def test_invalid_status_is_rejected_by_check_constraint(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    photo = _make_photo(planting.id, status="deleted")
    db_session.add(photo)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_hidden_status_is_accepted_by_check_constraint(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    photo = _make_photo(planting.id, status="hidden")
    db_session.add(photo)
    db_session.commit()

    stored = db_session.execute(select(Photo).where(Photo.id == photo.id)).scalar_one()
    assert stored.status == "hidden"


def test_deleting_planting_cascades_to_its_photos_at_the_database_level(
    db_session: Session,
) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)

    photo = _make_photo(planting.id)
    db_session.add(photo)
    db_session.commit()
    photo_id = photo.id

    db_session.delete(planting)
    db_session.commit()

    remaining = db_session.execute(select(Photo).where(Photo.id == photo_id)).scalar_one_or_none()
    assert remaining is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_photo_model.py -v`
Expected: FAIL — `TypeError: 'planting_id' is an invalid keyword argument for Photo` (model still uses `region_id`).

- [ ] **Step 3: Update `app/models/photo.py`**

Replace the `region_id` column and its index references:

```python
    planting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plantings.id", ondelete="CASCADE"),
        nullable=False,
    )
```

Update `__table_args__`'s index:

```python
        Index("ix_photos_planting_id_uploaded_at", planting_id, uploaded_at.desc()),
```

Update the module docstring's first line to say "a Planting's photo timeline" instead of "a region's".

- [ ] **Step 4: Generate and hand-edit the migration**

Run: `alembic revision -m "photo planting id"`

```python
def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("photos_region_id_fkey", "photos", type_="foreignkey")
    op.drop_index("ix_photos_region_id_uploaded_at", table_name="photos")
    op.alter_column("photos", "region_id", new_column_name="planting_id")
    op.create_foreign_key(
        "photos_planting_id_fkey", "photos", "plantings", ["planting_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(
        "ix_photos_planting_id_uploaded_at",
        "photos",
        ["planting_id", sa.text("uploaded_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_photos_planting_id_uploaded_at", table_name="photos")
    op.drop_constraint("photos_planting_id_fkey", "photos", type_="foreignkey")
    op.alter_column("photos", "planting_id", new_column_name="region_id")
    op.create_foreign_key(
        "photos_region_id_fkey", "photos", "regions", ["region_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(
        "ix_photos_region_id_uploaded_at",
        "photos",
        ["region_id", sa.text("uploaded_at DESC")],
        unique=False,
    )
```

If `alembic revision --autogenerate` (not plain `revision`) would have detected the FK constraint's auto-generated name differently, confirm the real name first: `psql "$DATABASE_URL" -c "\d photos"` and use whatever `photos_region_id_fkey`-equivalent name Postgres actually assigned when the Task-2-era `c60d27ca71eb_photo_model.py` migration ran (Alembic/SQLAlchemy's default FK-naming convention produces `photos_region_id_fkey` for an unnamed `ForeignKeyConstraint`, which is what `c60d27ca71eb` declares — this should match, but verify rather than assume).

- [ ] **Step 5: Apply the migration to both databases**

```bash
alembic upgrade head
DATABASE_URL="$(grep '^TEST_DATABASE_URL=' .env | cut -d= -f2-)" alembic upgrade head
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_photo_model.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Write the failing service test**

Rewrite `backend/tests/test_photo_service.py` — read the current file first (`backend/tests/test_photo_service.py`) to preserve any keyset-pagination edge-case tests it already has, then apply this transformation throughout: every `region.id`/`region_identifier` becomes `planting.id`/`planting_id: uuid.UUID`, `region_service.get_region` mentions become `planting_service.get_planting`, `RegionNotFound` becomes `PlantingNotFound`, and `Photo.region_id ==` becomes `Photo.planting_id ==`. `list_region_photos` calls become `list_planting_photos`, and its `identifier` argument switches from a slug/UUID string to `planting.id` (a `uuid.UUID`), since Planting has no slug. Add fixtures:

```python
def _add_region(db_session: Session) -> Region:
    region = Region(
        slug=f"regiao-{uuid.uuid4().hex[:8]}",
        name="Região de teste",
        geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326),
    )
    db_session.add(region)
    db_session.flush()
    return region


def _add_planting(db_session: Session, region_id: uuid.UUID) -> Planting:
    planting = Planting(region_id=region_id, geom=WKTElement("POINT(-43.3130 -21.8845)", srid=4326))
    db_session.add(planting)
    db_session.flush()
    return planting
```

and replace every call site that built a region-only fixture with `region = _add_region(db_session)` followed by `planting = _add_planting(db_session, region.id)`, passing `planting.id` wherever a photo needs its owner.

- [ ] **Step 8: Run test to verify it fails**

Run: `pytest tests/test_photo_service.py -v`
Expected: FAIL — `ImportError`/`AttributeError` referencing `list_region_photos`/`region_id`, which no longer exist as written.

- [ ] **Step 9: Update `app/services/photo_service.py`**

Add the import, remove the `region_service` one:

```python
from app.services import planting_service
```

Replace every `Photo.region_id` with `Photo.planting_id`, `_PUBLICLY_VISIBLE` filter unchanged. Rename and update `list_region_photos`:

```python
def list_planting_photos(
    db: Session,
    planting_id: uuid.UUID,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> PhotoPage:
    """List `published` photos of `planting_id`, most-recently-uploaded first.

    Raises `planting_service.PlantingNotFound` if `planting_id` doesn't
    resolve to a visible planting.
    """
    planting_service.get_planting(db, planting_id)  # raises PlantingNotFound if missing

    page_size = min(max(limit, 1), MAX_PAGE_SIZE)

    query = (
        select(
            Photo.id,
            Photo.description,
            Photo.contributor_name,
            Photo.captured_at,
            Photo.uploaded_at,
            Photo.width,
            Photo.height,
            func.ST_Y(Photo.location).label("latitude"),
            func.ST_X(Photo.location).label("longitude"),
        )
        .where(Photo.planting_id == planting_id, _PUBLICLY_VISIBLE)
        .order_by(Photo.uploaded_at.desc(), Photo.id.desc())
        .limit(page_size + 1)
    )

    if cursor is not None:
        cursor_uploaded_at, cursor_id = _decode_cursor(cursor)
        query = query.where(
            tuple_(Photo.uploaded_at, Photo.id) < tuple_(cursor_uploaded_at, cursor_id)
        )

    rows = db.execute(query).all()

    has_more = len(rows) > page_size
    page_rows = rows[:page_size]
    next_cursor = _encode_cursor(page_rows[-1].uploaded_at, page_rows[-1].id) if has_more else None

    return PhotoPage(
        items=[
            PhotoOut(
                id=row.id,
                description=row.description,
                contributor_name=row.contributor_name,
                captured_at=row.captured_at,
                uploaded_at=row.uploaded_at,
                latitude=row.latitude,
                longitude=row.longitude,
                width=row.width,
                height=row.height,
            )
            for row in page_rows
        ],
        next_cursor=next_cursor,
    )
```

(`open_photo_file` is untouched — it only ever looked up by `photo_id`, never `region_id`.)

- [ ] **Step 10: Update `app/schemas/photo.py`**

Only the module docstring and the `photo_url`/module-level comments reference "region" — update the top docstring's first line to mention `GET /api/plantings/{planting_id}/photos` instead of `GET /api/regions/{region}/photos`. No field changes needed (`PhotoOut`/`PhotoPage` never referenced `region_id` directly).

- [ ] **Step 11: Update `app/api/routes/photos.py`**

```python
router = APIRouter(prefix="/api/plantings", tags=["photos"])
```

```python
@router.get("/{planting_id}/photos", response_model=PhotoPage)
def list_planting_photos(
    planting_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(
        default=photo_service.DEFAULT_PAGE_SIZE,
        ge=1,
        le=photo_service.MAX_PAGE_SIZE,
    ),
    db: Session = Depends(get_db),  # noqa: B008
) -> PhotoPage:
    return photo_service.list_planting_photos(db, planting_id, cursor=cursor, limit=limit)
```

Rename the route function `upload_photo`'s `region: str` parameter to `planting_id: uuid.UUID`, and its route decorator to `@router.post("/{planting_id}/photos", ...)`. Update the call:

```python
    return photo_upload_service.upload_photo(
        db,
        storage,
        planting_id,
        file=file,
        description=description,
        contributor_name=contributor_name,
        share_location=share_location,
    )
```

Add `import uuid` at the top of this file if not already present (it isn't — check with `grep "^import uuid" backend/app/api/routes/photos.py`).

- [ ] **Step 12: Add real `photo_count`/`latest_photo_at` to `planting_service.py`**

Now that `Photo.planting_id` exists, replace the literal placeholders in `_planting_feature_columns()`:

```python
from app.models.photo import Photo
```

```python
def _planting_feature_columns() -> tuple[ColumnElement[Any], ...]:
    """..."""
    photo_count = (
        select(func.count())
        .select_from(Photo)
        .where(Photo.planting_id == Planting.id, Photo.status == "published")
        .scalar_subquery()
    )
    latest_photo_at = (
        select(func.max(Photo.uploaded_at))
        .select_from(Photo)
        .where(Photo.planting_id == Planting.id, Photo.status == "published")
        .scalar_subquery()
    )
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
        photo_count.label("photo_count"),
        latest_photo_at.label("latest_photo_at"),
    )
```

Remove the now-unused `literal` import from `planting_service.py` if nothing else in the file uses it.

- [ ] **Step 13: Add a photo-count regression test to `test_planting_service.py`**

Append to `backend/tests/test_planting_service.py`:

```python
from app.models.photo import Photo


def _add_photo(db_session: Session, planting_id: uuid.UUID, **overrides: object) -> Photo:
    defaults: dict[str, object] = {
        "planting_id": planting_id,
        "storage_key": f"photos/{uuid.uuid4().hex}.jpg",
        "content_type": "image/jpeg",
        "byte_size": 1000,
        "width": 100,
        "height": 100,
    }
    defaults.update(overrides)
    photo = Photo(**defaults)
    db_session.add(photo)
    return photo


def test_get_planting_reports_real_photo_count(db_session: Session) -> None:
    region = _add_region(db_session)
    planting = _add_planting(db_session, region.id)
    _add_photo(db_session, planting.id)
    _add_photo(db_session, planting.id, status="hidden")
    db_session.commit()

    feature = planting_service.get_planting(db_session, planting.id)

    assert feature.properties.photo_count == 1  # `hidden` excluded
```

- [ ] **Step 14: Run tests to verify they pass**

Run: `pytest tests/test_photo_model.py tests/test_photo_service.py tests/test_planting_service.py -v`
Expected: PASS

- [ ] **Step 15: Fix `test_photo_routes.py` and `test_photo_file_route.py`**

Read both files first (`backend/tests/test_photo_routes.py`, `backend/tests/test_photo_file_route.py`) and apply the same transformation as Step 7: region-only fixtures become region + planting, `/api/regions/{region}/photos` URLs become `/api/plantings/{planting.id}/photos`, and any `region_id`/`Photo.region_id` reference becomes `planting_id`/`Photo.planting_id`.

- [ ] **Step 16: Run the full backend suite**

Run: `pytest -v`
Expected: FAIL only on `test_photo_upload_route.py`/`test_photo_upload_service.py`/`test_storage_keys.py` — those are fixed in Task 7. Confirm every other file passes.

- [ ] **Step 17: Commit**

```bash
git add backend/app/models/photo.py backend/alembic/versions backend/app/schemas/photo.py \
  backend/app/services/photo_service.py backend/app/services/planting_service.py \
  backend/app/api/routes/photos.py backend/tests/test_photo_model.py backend/tests/test_photo_service.py \
  backend/tests/test_photo_routes.py backend/tests/test_photo_file_route.py backend/tests/test_planting_service.py
git commit -m "feat: migra Photo de region_id para planting_id"
```

---

## Task 7: Photo upload moves to `planting_id`

**Files:**
- Modify: `backend/app/storage/keys.py`
- Modify: `backend/app/services/photo_upload_service.py`
- Modify: `backend/tests/test_storage_keys.py`
- Modify: `backend/tests/test_photo_upload_service.py`
- Modify: `backend/tests/test_photo_upload_route.py`

**Interfaces:**
- Consumes: `app.services.planting_service.{get_planting, PlantingNotFound}` (Task 3).
- Produces: `app.storage.keys.generate_storage_key(planting_id: uuid.UUID, *, extension: str, now: datetime | None = None) -> str` (parameter renamed, key prefix changes from `regions/` to `plantings/`). `app.services.photo_upload_service.upload_photo(db, storage, planting_identifier: uuid.UUID, *, file, description, contributor_name, share_location) -> PhotoOut`.

- [ ] **Step 1: Write the failing storage-key test**

Edit `backend/tests/test_storage_keys.py` — replace every `region_id` with `planting_id` and the expected prefix `"regions"` with `"plantings"`:

```python
"""Tests for `app/storage/keys.py`: the `storage_key` format for a newly
uploaded photo — `plantings/{planting_id}/{ano}/{uuid4}.{ext}`, collision-free,
never derived from user input, cheap to list by muda."""

import uuid
from datetime import UTC, datetime

import pytest

from app.storage.keys import generate_storage_key


def test_generate_storage_key_follows_the_documented_format() -> None:
    planting_id = uuid.uuid4()

    key = generate_storage_key(planting_id, extension="jpg", now=datetime(2026, 8, 30, tzinfo=UTC))

    prefix, key_planting_id, year, filename = key.split("/")
    assert prefix == "plantings"
    assert key_planting_id == str(planting_id)
    assert year == "2026"
    name, ext = filename.rsplit(".", 1)
    assert ext == "jpg"
    assert uuid.UUID(name)


def test_generate_storage_key_is_scoped_to_the_given_planting() -> None:
    planting_id = uuid.uuid4()

    key = generate_storage_key(planting_id, extension="png", now=datetime(2026, 1, 1, tzinfo=UTC))

    assert key.startswith(f"plantings/{planting_id}/")


def test_generate_storage_key_is_never_derived_from_user_input() -> None:
    planting_id = uuid.uuid4()

    first = generate_storage_key(planting_id, extension="jpg", now=datetime(2026, 8, 30, tzinfo=UTC))
    second = generate_storage_key(planting_id, extension="jpg", now=datetime(2026, 8, 30, tzinfo=UTC))

    assert first != second


@pytest.mark.parametrize("bad_extension", ["", ".jpg", "jpg.", "jp/g"])
def test_generate_storage_key_rejects_a_malformed_extension(bad_extension: str) -> None:
    with pytest.raises(ValueError, match="extension"):
        generate_storage_key(uuid.uuid4(), extension=bad_extension)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_keys.py -v`
Expected: FAIL — assertions on `"plantings"`/`"planting_id"` fail against the current `"regions/"` prefix.

- [ ] **Step 3: Update `app/storage/keys.py`**

```python
"""`storage_key` generation for a newly uploaded photo:
`plantings/{planting_id}/{ano}/{uuid4}.{ext}` — collision-free, cheap to
list by muda, never derived from anything a client sends."""

import uuid
from datetime import UTC, datetime


def generate_storage_key(
    planting_id: uuid.UUID, *, extension: str, now: datetime | None = None
) -> str:
    """Build the `storage_key` for a new photo of `planting_id`.

    `extension` must come from the image format decoded server-side, never
    the client's filename. `now` defaults to the current UTC time.

    Raises `ValueError` for a malformed `extension`.
    """
    if not extension or extension.startswith(".") or extension.endswith(".") or "/" in extension:
        raise ValueError(f"extension inválida para storage_key: {extension!r}")

    year = (now or datetime.now(UTC)).year
    return f"plantings/{planting_id}/{year}/{uuid.uuid4()}.{extension}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_keys.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Write the failing upload-service test**

Read `backend/tests/test_photo_upload_service.py` — it currently only tests `_extension_for_content_type`, which doesn't reference `region_id`/`planting_id` at all, so it needs no change. Confirm this by running it now:

Run: `pytest tests/test_photo_upload_service.py -v`
Expected: PASS already (no change needed — this file is unaffected by the rename).

- [ ] **Step 6: Update `app/services/photo_upload_service.py`**

Replace the `region_service` import and every reference:

```python
from app.services import planting_service
```

```python
def upload_photo(
    db: Session,
    storage: StorageBackend,
    planting_id: uuid.UUID,
    *,
    file: UploadFile,
    description: str | None,
    contributor_name: str | None,
    share_location: bool,
) -> PhotoOut:
    """Validate, store and record a new photo for `planting_id`.

    Propagates `planting_service.PlantingNotFound`, `image_processing.
    ImageTooLarge` and `image_processing.InvalidImage` unchanged."""
    planting_service.get_planting(db, planting_id)  # raises PlantingNotFound if missing

    image = validate_upload(file.file, max_bytes=settings.max_upload_bytes)
    metadata = process_photo_metadata(image, share_location=share_location)

    extension = _extension_for_content_type(metadata.content_type)
    storage_key = generate_storage_key(planting_id, extension=extension)
    storage.save(storage_key, io.BytesIO(metadata.image_bytes), metadata.content_type)

    location = None
    if metadata.latitude is not None and metadata.longitude is not None:
        location = WKTElement(f"POINT({metadata.longitude} {metadata.latitude})", srid=4326)

    photo = Photo(
        planting_id=planting_id,
        storage_key=storage_key,
        original_filename=file.filename,
        content_type=metadata.content_type,
        byte_size=len(metadata.image_bytes),
        width=metadata.width,
        height=metadata.height,
        description=description,
        contributor_name=contributor_name,
        captured_at=metadata.captured_at,
        location=location,
        location_source=metadata.location_source,
    )
    db.add(photo)
    db.commit()

    return PhotoOut(
        id=photo.id,
        description=photo.description,
        contributor_name=photo.contributor_name,
        captured_at=photo.captured_at,
        uploaded_at=photo.uploaded_at,
        latitude=metadata.latitude,
        longitude=metadata.longitude,
        width=photo.width,
        height=photo.height,
    )
```

Note `region_id = uuid.UUID(region.id)` is gone — `planting_id` arrives already typed as `uuid.UUID` from the route (Task 6, Step 11 changed the route parameter to `planting_id: uuid.UUID`), so no string-to-UUID conversion is needed here anymore.

- [ ] **Step 7: Fix `test_photo_upload_route.py`**

Read `backend/tests/test_photo_upload_route.py` first, then apply the same transformation as Task 6 Step 15: build a region + planting fixture, POST to `/api/plantings/{planting.id}/photos` instead of `/api/regions/{region}/photos`, and update any `Photo.region_id`/`region_id` assertion to `Photo.planting_id`/`planting_id`.

- [ ] **Step 8: Run the full backend suite**

Run: `pytest -v`
Expected: PASS — every test in the suite, no exceptions.

- [ ] **Step 9: Commit**

```bash
git add backend/app/storage/keys.py backend/app/services/photo_upload_service.py \
  backend/tests/test_storage_keys.py backend/tests/test_photo_upload_route.py
git commit -m "feat: migra upload de fotos e storage_key de region_id para planting_id"
```

---

## Task 8: `scripts/seed.py` creates Regions with nested Plantings

**Files:**
- Modify: `backend/scripts/seed.py`
- Modify: `backend/tests/test_seed_script.py`

**Interfaces:**
- Consumes: `app.services.planting_service.create_planting`/`app.schemas.planting.PlantingCreate` (Task 3), `app.services.qr_code_service.create_region_qr_code` (Task 2, already wired in from Task 2 Step 16).
- Produces: `scripts.seed.seed(db, *, center_lat=..., center_lon=..., region_count=..., plantings_per_region=...) -> tuple[int, int]` — return value gains a documented meaning (`created`/`updated` now count Regions only, same as before; Plantings are seeded idempotently per Region alongside them).

- [ ] **Step 1: Write the failing test**

Rewrite `backend/tests/test_seed_script.py`:

```python
"""Tests for `scripts/seed.py`: idempotent development seed data — Regions
with nested Plantings. See
docs/superpowers/specs/2026-08-30-region-planting-pivot-design.md."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.planting import Planting
from app.models.qr_code import QrCode
from app.models.region import Region
from scripts.seed import _grid_cell_centers, seed

_CENTER_LAT = -21.883859
_CENTER_LON = -43.312459


def _region_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Region)).scalar_one()


def _planting_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Planting)).scalar_one()


def test_seed_creates_the_configured_number_of_regions(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)

    assert _region_count(db_session) == 10


def test_seed_creates_plantings_inside_each_region(db_session: Session) -> None:
    seed(
        db_session,
        center_lat=_CENTER_LAT,
        center_lon=_CENTER_LON,
        region_count=10,
        plantings_per_region=3,
    )

    assert _planting_count(db_session) == 30
    first_region_id = db_session.execute(
        select(Region.id).order_by(Region.slug).limit(1)
    ).scalar_one()
    plantings_in_first_region = db_session.execute(
        select(func.count()).select_from(Planting).where(Planting.region_id == first_region_id)
    ).scalar_one()
    assert plantings_in_first_region == 3


def test_seed_gives_every_region_and_planting_a_qr_code(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)

    region_qr_count = db_session.execute(
        select(func.count()).select_from(QrCode).where(QrCode.region_id.is_not(None))
    ).scalar_one()
    planting_qr_count = db_session.execute(
        select(func.count()).select_from(QrCode).where(QrCode.planting_id.is_not(None))
    ).scalar_one()
    assert region_qr_count == 10
    assert planting_qr_count == _planting_count(db_session)


def test_seed_is_idempotent(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)

    assert _region_count(db_session) == 10
    assert _planting_count(db_session) == 10 * 4  # default plantings_per_region — no duplicates


def test_seed_documents_the_placeholder_geometry_in_the_description(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)

    region = db_session.execute(select(Region)).scalars().first()

    assert region is not None
    assert "placeholder" in (region.description or "").lower()


def test_seed_repositions_existing_regions_when_center_changes(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)
    original_centroid = db_session.execute(
        select(func.ST_AsText(Region.centroid)).order_by(Region.slug).limit(1)
    ).scalar_one()

    seed(db_session, center_lat=_CENTER_LAT + 1.0, center_lon=_CENTER_LON + 1.0, region_count=10)
    moved_centroid = db_session.execute(
        select(func.ST_AsText(Region.centroid)).order_by(Region.slug).limit(1)
    ).scalar_one()

    assert _region_count(db_session) == 10  # still no duplicates
    assert original_centroid != moved_centroid


def test_seed_preserves_qr_token_across_reruns(db_session: Session) -> None:
    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)
    first_region_id = db_session.execute(
        select(Region.id).order_by(Region.slug).limit(1)
    ).scalar_one()
    original_token = db_session.execute(
        select(QrCode.token).where(QrCode.region_id == first_region_id)
    ).scalar_one()

    seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=10)
    token_after_rerun = db_session.execute(
        select(QrCode.token).where(QrCode.region_id == first_region_id)
    ).scalar_one()

    assert original_token == token_after_rerun


def test_grid_cell_centers_forms_a_5x2_grid_for_the_default_count() -> None:
    cell_centers = _grid_cell_centers(10, rows=2, center_lat=_CENTER_LAT, center_lon=_CENTER_LON)

    distinct_lats = {lat for lat, _lon in cell_centers}
    distinct_lons = {lon for _lat, lon in cell_centers}
    assert len(distinct_lats) == 2
    assert len(distinct_lons) == 5


def test_seed_rejects_a_region_count_beyond_the_fictional_name_pool(db_session: Session) -> None:
    with pytest.raises(ValueError, match="10"):
        seed(db_session, center_lat=_CENTER_LAT, center_lon=_CENTER_LON, region_count=15)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_script.py -v`
Expected: FAIL — `TypeError: seed() got an unexpected keyword argument 'plantings_per_region'` and the planting-count assertions fail (0 plantings created today).

- [ ] **Step 3: Rewrite `scripts/seed.py`**

Add imports:

```python
from app.models.planting import Planting
from app.services.qr_code_service import create_planting_qr_code, create_region_qr_code
```

Add a settings-backed default and the per-region planting placement helper, right below `_GRID_ROWS`:

```python
_DEFAULT_PLANTINGS_PER_REGION = 4
_PLANTING_SPACING_METERS = 8  # inside a 50m plot, well clear of its edges


def _planting_offsets_within_cell(count: int) -> list[tuple[float, float]]:
    """`count` small (lat_offset, lon_offset) pairs, in meters, arranged in a
    tight row inside a region's cell — enough to keep plantings visually
    distinct without leaving the region's placeholder square."""
    return [(0.0, (index - (count - 1) / 2) * _PLANTING_SPACING_METERS) for index in range(count)]
```

Replace `seed()`'s body:

```python
def seed(
    db: Session,
    *,
    center_lat: float = settings.seed_center_lat,
    center_lon: float = settings.seed_center_lon,
    region_count: int = settings.seed_region_count,
    plantings_per_region: int = _DEFAULT_PLANTINGS_PER_REGION,
) -> tuple[int, int]:
    """Upsert `region_count` placeholder Regions, each with
    `plantings_per_region` Plantings inside it. Returns `(created, updated)`
    Region counts — Plantings are seeded idempotently alongside their
    Region and aren't repositioned on rerun (only newly missing ones, by
    ordinal position within the region, are created)."""
    if region_count > len(_REGION_NAMES):
        raise ValueError(
            f"SEED_REGION_COUNT={region_count} excede o pool de "
            f"{len(_REGION_NAMES)} nomes fictícios em _REGION_NAMES."
        )
    names = _REGION_NAMES[:region_count]
    cell_centers = _grid_cell_centers(len(names), _GRID_ROWS, center_lat, center_lon)
    planting_offsets = _planting_offsets_within_cell(plantings_per_region)

    created = updated = 0
    for name, (cell_lat, cell_lon) in zip(names, cell_centers, strict=True):
        slug = slugify(name)
        geom = WKTElement(_square_wkt(cell_lat, cell_lon, _CELL_SIDE_METERS), srid=4326)

        region = db.execute(select(Region).where(Region.slug == slug)).scalar_one_or_none()
        if region is None:
            region = Region(slug=slug, name=name, description=_PLACEHOLDER_DESCRIPTION, geom=geom)
            db.add(region)
            db.flush()
            create_region_qr_code(db, region.id)
            created += 1
        else:
            region.name = name
            region.description = _PLACEHOLDER_DESCRIPTION
            region.geom = geom
            updated += 1

        existing_planting_count = db.execute(
            select(func.count()).select_from(Planting).where(Planting.region_id == region.id)
        ).scalar_one()
        for lat_offset_m, lon_offset_m in planting_offsets[existing_planting_count:]:
            planting_lat = cell_lat + lat_offset_m / _METERS_PER_DEGREE_LATITUDE
            planting_lon = cell_lon + lon_offset_m / (
                _METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(cell_lat))
            )
            planting = Planting(
                region_id=region.id,
                geom=WKTElement(f"POINT({planting_lon} {planting_lat})", srid=4326),
            )
            db.add(planting)
            db.flush()
            create_planting_qr_code(db, planting.id)

    db.commit()
    return created, updated
```

Add `from sqlalchemy import func, select` if `func` isn't already imported (it currently imports only `select` — check with `grep "^from sqlalchemy import" backend/scripts/seed.py` first and extend that line).

Update `main()`'s print statement to mention plantings too:

```python
def main() -> None:
    with SessionLocal() as db:
        created, updated = seed(db)
    print(
        f"Seed concluído: {created} região(ões) criada(s), {updated} atualizada(s), "
        f"com mudas geradas dentro de cada uma."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_script.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Run the full backend suite**

Run: `pytest -v`
Expected: PASS — every test in the entire `backend/tests/` directory.

- [ ] **Step 6: Manually verify the seed script end-to-end**

Run:
```bash
python scripts/seed.py
python scripts/seed.py
```
Expected: first run prints "10 região(ões) criada(s), 0 atualizada(s)"; second run prints "0 região(ões) criada(s), 10 atualizada(s)" — no duplicate regions or plantings on rerun (confirmed by the idempotency test, but worth a manual sanity check against a real running Postgres too).

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/seed.py backend/tests/test_seed_script.py
git commit -m "feat: seed cria mudas dentro de cada região"
```

---

## Plan-Level Verification

After Task 8, run the complete suite one more time and confirm the OpenAPI schema reflects every route change:

```bash
pytest -v
uvicorn app.main:app --reload &
curl -s http://localhost:8000/openapi.json | python -m json.tool | grep -E '"/api/(regions|plantings|photos|qr)'
kill %1
```

Expected: `pytest` reports 0 failures; the `openapi.json` grep shows `/api/regions`, `/api/regions/{region}`, `/api/regions/{region}/qr-code`, `/api/plantings`, `/api/plantings/{planting_id}`, `/api/plantings/{planting_id}/qr-code`, `/api/plantings/{planting_id}/photos`, `/api/photos/{photo_id}/file`, and `/api/qr/{token}` — and no lingering `/api/regions/{region}/photos`.
