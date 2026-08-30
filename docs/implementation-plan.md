# Community Roots — Implementation Plan

Companion to [architecture.md](./architecture.md), which holds the reasoning
behind every decision referenced here. Scope comes from
[../PROJECT_BOOTSTRAP.md](../PROJECT_BOOTSTRAP.md).

Each phase ends with a validation step. A phase is not finished until its
validation passes and the result is reported honestly.

| Phase | Outcome | Status |
|---|---|---|
| 0 | Planning, documentation, decisions | done |
| 1 | Project foundation: skeleton, database, health endpoint | not started |
| 2 | Regions: model, migration, seed, GeoJSON API | not started |
| 3 | Interactive map | not started |
| 4 | Region pages and photo timeline (read-only) | not started |
| 5 | Photo uploads | not started |
| 6 | QR codes | not started |
| 7 | Polish, accessibility, security review | not started |

---

## Confirmed decisions

Resolved with the project owner during planning:

1. **Reference location.** The planting area is in **Matias Barbosa, Minas
   Gerais** (approximately `-21.883859, -43.312459`). The centre is configured
   through `SEED_CENTER_LAT` / `SEED_CENTER_LON`, never hardcoded.
2. **Seed data.** 10 fictional regions, generated as a grid around the configured
   centre. These are development placeholders, not surveyed geography, and every
   record is labelled as such.
3. **Region geometry.** `geometry(Geometry, 4326)` with a check constraint on the
   geometry type, plus a generated `centroid` — see architecture §4.1.
4. **EXIF.** Capture date and GPS are both extracted; GPS is persisted only when
   the contributor opts in via an explicit unchecked-by-default checkbox. The
   stored image file is always stripped of metadata — see architecture §6.2.
5. **Frontend language.** TypeScript.

Decisions taken by the implementer, open to reversal: local venv rather than a
containerized backend; admin write endpoints behind a shared token;
`postgis/postgis:16-3.4`; a configurable database port to avoid the other
Postgres instances already running on this machine.

---

## Phase 1 — Project foundation

**Goal:** `docker compose up -d`, one backend command, one frontend command, and
both respond. No domain logic yet.

### Deliverables

**Infrastructure**
- `docker-compose.yml` with a single `db` service on `postgis/postgis:16-3.4`,
  a named volume, a `pg_isready` healthcheck, and the port from `POSTGRES_PORT`.
- `infrastructure/postgres/init/01-init.sql`: `CREATE EXTENSION postgis`, plus
  creation of the `community_roots_test` database.
- Root `.env.example`.

**Backend**
- `pyproject.toml` pinning fastapi, uvicorn, sqlalchemy, geoalchemy2, psycopg,
  alembic, pydantic-settings, pillow, qrcode, python-multipart; dev extras
  pytest, httpx, ruff.
- `.python-version` (3.11.10) and `backend/.env.example`.
- `app/core/config.py` — `Settings`, validated at import, failing with a message
  that names the missing variable.
- `app/db/session.py` — engine, session factory, `get_db` dependency.
- `app/db/base.py` — `DeclarativeBase` with shared `id` / timestamp mixins.
- `app/main.py` — app factory, CORS from settings, exception handlers, router
  mounting.
- `app/api/routes/health.py` — `GET /health` returning `{"status": "ok",
  "database": "ok"}`, where `database` reflects an actual `SELECT 1`.
- Alembic initialized against the app's metadata, with an empty baseline revision.
- `tests/conftest.py` and `tests/test_health.py`.

**Frontend**
- `npm create vite@latest` (react-ts), Node pinned by `.nvmrc` (22.22.1).
- Tailwind v4 through `@tailwindcss/vite` — no `init` command, no
  `tailwind.config.js`, no `postcss.config.js`.
- `react-router`, TanStack Query, `leaflet` + `react-leaflet` installed but not
  yet wired into pages.
- Vite dev proxy from `/api` to the backend, so the browser sees one origin in
  development.
- `src/services/apiClient.ts` and a placeholder `HomePage` that renders the
  backend's health response, proving the whole path end to end.
- Vitest configured with one passing smoke test.
- `frontend/.env.example`.

**Documentation**
- README with real setup steps, verified by following them from a clean state.

### Validation
- `docker compose up -d` reaches a healthy container; `SELECT postgis_version()`
  succeeds.
- `alembic upgrade head` runs clean; `alembic downgrade base` then `upgrade head`
  also runs clean.
- `GET /health` returns `database: "ok"`; stopping the database changes that
  field rather than crashing the process.
- `pytest` passes.
- `npm run dev` serves a page that displays the health response fetched through
  the proxy.
- `npm run build` and `npm run test` pass.

---

## Phase 2 — Geographic regions

**Goal:** regions exist in PostGIS and are readable as GeoJSON.

### Deliverables
- `app/models/region.py` per architecture §4.2, using GeoAlchemy2 `Geometry`.
- Alembic migration: extension guard, table, check constraints, generated
  centroid, GiST indexes, unique constraints. Hand-reviewed, not raw autogenerate.
- `app/schemas/geojson.py` — `Feature` / `FeatureCollection` models, so OpenAPI
  documents the real response shape instead of a bare `dict`.
- `app/services/region_service.py` — list, resolve by slug or UUID, create,
  update. Slug generation and `qr_token` generation live here.
- `GET /api/regions`, `GET /api/regions/{region}`, `POST /api/regions`,
  `PATCH /api/regions/{region}`.
- `app/core/security.py` — admin token dependency on the write routes.
- `scripts/seed.py` — idempotent (upsert by slug), generating 10 regions on a
  5 × 2 grid of roughly 50 m squares around the configured centre, with
  Portuguese names taken from Brazilian native trees. Reads the centre from
  settings; running it twice changes nothing.
- Tests: GeoJSON shape, geometry round-trip through the database, slug/UUID
  resolution, 404 handling, admin token enforcement, seed idempotency.

### Validation
- Seed produces 10 regions; running it again still produces 10.
- `GET /api/regions` returns a valid `FeatureCollection` that passes a GeoJSON
  schema check.
- The geometry check constraint rejects a `LINESTRING`.
- `photo_count` is present and zero, resolved in a single query (verified by
  logging the SQL, not assumed).
- `pytest` passes.

---

## Phase 3 — Interactive map

**Goal:** the map shows real regions from the backend and navigates to them.

### Deliverables
- `App.tsx` with the router; `Layout` and `Header`.
- `types/api.ts` mirroring the backend schemas.
- `services/regions.ts`, `hooks/useRegions.ts`.
- `components/map/PlantingMap.tsx` — `MapContainer`, OSM tiles and attribution
  from environment variables, height supplied by the parent.
- `components/map/RegionLayer.tsx` — renders the `FeatureCollection`, handles
  click and keyboard activation, applies hover and focus styling.
- `components/map/RegionPopup.tsx` — name, photo count, link to the region.
- `MapPage` — full-height layout, fits bounds to the returned features.
- `feedback/LoadingState`, `ErrorState`, `EmptyState`.
- `HomePage` with real content: what the project is, how to take part, call to
  action to the map.
- Tests for `RegionLayer` with `react-leaflet` mocked.

### Validation
- Regions render; there is no hardcoded geography in the frontend.
- Tapping a region opens its page.
- The map fills its container on a 360 px-wide viewport with no grey area and no
  horizontal page scroll.
- Strict Mode causes no double initialization and no console errors.
- Stopping the backend produces the error state, not a blank screen.

---

## Phase 4 — Region pages

**Goal:** a region page reachable by URL, with its (still empty) timeline.

### Deliverables
- `app/models/photo.py` and its migration, per architecture §4.3.
- `app/services/photo_service.py` — listing with pagination.
- `GET /api/regions/{region}/photos`.
- `GET /api/photos/{photo_id}/file` — streams from the storage backend, correct
  content type, `Cache-Control` for immutable content.
- `RegionPage` — name, description, a small map centred on the region, photo
  count, timeline, and a disabled upload button until Phase 5.
- `PhotoTimeline` and `PhotoCard`, grouped by date, newest first.
- `NotFoundPage`, plus a real 404 for an unknown slug.

### Validation
- A region URL loads directly, without visiting the map first.
- The empty state explains how to contribute instead of showing a blank area.
- The small map renders correctly next to page content, at a fixed aspect ratio.
- An unknown slug produces the 404 page, not an error state.

---

## Phase 5 — Photo uploads

**Goal:** the QR contribution flow works end to end.

### Deliverables
- `app/storage/base.py` — the `StorageBackend` protocol.
- `app/storage/local.py` — `LocalFilesystemStorage`, injected as a dependency.
- `app/services/image_processing.py` — size limit, real-format detection through
  Pillow, decompression-bomb guard, EXIF extraction, orientation applied,
  re-encode with metadata stripped.
- `POST /api/regions/{region}/photos` — multipart: `file`, `description`,
  `contributor_name`, `share_location`.
- Domain exceptions mapped to Portuguese, user-safe messages with stable codes.
- `PhotoUploadForm` — file picker with immediate preview, optional name and
  observation, unchecked `share_location` checkbox with plain-language text
  explaining what it does, progress state, disabled submit while in flight.
- The timeline refreshes on success through query invalidation.
- Tests: happy path; oversized file; wrong format; corrupt bytes; a `.jpg`
  filename holding non-image bytes; EXIF absent from the stored file, verified by
  re-reading it; GPS written only when opted in.

### Validation
- A photo uploaded from a phone appears in the timeline.
- Every rejection path returns a message a non-technical user can act on.
- The stored file, re-opened, has no EXIF block.
- With the checkbox unchecked, a photo carrying GPS produces `location IS NULL`.
- Two uploads of identically named files do not collide.

---

## Phase 6 — QR codes

**Goal:** an organizer can print codes and place them in the field.

### Deliverables
- `app/services/qr_service.py`, `GET /api/regions/{region}/qr-code`
  (`?format=png|svg`, `?size=`), encoding `{PUBLIC_WEB_BASE_URL}/r/{qr_token}`.
- `GET /api/qr/{qr_token}` and the `/r/:qrToken` frontend route that redirects to
  the region.
- A printable sheet: one card per region with its QR code and name, laid out for
  A4 with print CSS.
- `POST /api/regions/import` accepting a GeoJSON `FeatureCollection`, matching by
  slug, reporting created/updated/skipped counts.
- Tests: encoded URL contents, content types, unknown token 404, import matching
  and idempotency.

### Validation
- A code scanned with a phone camera opens the correct region.
- Renaming a region and changing its slug does not invalidate the printed code.
- Importing a GeoJSON file replaces placeholder geometry while preserving each
  region's `qr_token`.

---

## Phase 7 — Polish

### Deliverables
- Mobile pass on every page at 360 px; touch targets at least 44 px.
- Accessibility: keyboard navigation over map regions, visible focus, alt text on
  photos, labelled form fields, contrast checked, one `h1` per page.
- Error handling review: no raw stack traces, no English strings reaching users.
- Security review against architecture §9; decide on rate limiting for the upload
  endpoint.
- Backend `Dockerfile` and a deployment note.
- Documentation: manual test scripts for each flow in spec §15, an organizer
  guide, and a coverage gap review.

---

## Working agreement

- One phase at a time; validation reported with real command output, not claimed.
- Conventional Commits with Portuguese subjects, per the repository conventions.
- Architectural changes are recorded in `docs/architecture.md` as they are made,
  not at the end.
- Anything touching the privacy model, authentication, paid services, or an
  irreversible data-model change stops for confirmation.
