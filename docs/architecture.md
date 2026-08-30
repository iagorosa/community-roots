# Community Roots — Architecture

Status: **planning phase**. This document describes the target architecture and
the reasoning behind each decision. It is the reference for all implementation
phases described in [implementation-plan.md](./implementation-plan.md).

Product specification: [../PROJECT_BOOTSTRAP.md](../PROJECT_BOOTSTRAP.md).

---

## 1. System overview

Community Roots is a well-structured monolith split into two deployable units
plus one database:

```
Browser (mobile-first)
      |
      |  HTTPS / JSON + multipart
      v
React SPA (Vite)  ---- static build, served by any static host
      |
      |  REST /api/*
      v
FastAPI backend  ----> StorageBackend (local filesystem today, S3-compatible later)
      |
      |  SQLAlchemy + GeoAlchemy2
      v
PostgreSQL 16 + PostGIS 3.4
```

There are no microservices, no message broker, and no background workers in the
MVP. Every request is handled synchronously.

The physical-to-digital chain the product depends on:

```
Physical marker -> QR code -> /r/{qr_token} -> /regions/{slug} -> photo timeline
```

---

## 2. Technology decisions

| Layer | Choice | Why |
|---|---|---|
| Frontend framework | React 19 + Vite 7 | Matches the prior prototype's direction; Vite gives fast HMR and a trivial static build. |
| Frontend language | TypeScript | The developer is backend-strong; types on `Region`/`Photo` mirror the Pydantic schemas and catch API shape errors at edit time. |
| Styling | Tailwind CSS v4 via `@tailwindcss/vite` | See [§2.1](#21-tailwind-v4-decision). |
| Map | `react-leaflet` v5 + `leaflet` 1.9 | See [§2.2](#22-map-decision). |
| Routing | `react-router` v7 (declarative mode) | Standard, small, no framework lock-in. |
| Server state | TanStack Query v5 | Loading/error/refetch states are the bulk of this app's UI logic. Writing that by hand in every page is the larger complexity. |
| Backend | FastAPI + Pydantic v2 | Automatic OpenAPI docs, request validation, multipart support. |
| ORM | SQLAlchemy 2.0 (typed `Mapped[...]`) + GeoAlchemy2 | GeoAlchemy2 maps PostGIS geometry columns to real Python types and exposes `ST_*` functions through SQLAlchemy. |
| Migrations | Alembic | Required by the spec. Autogenerate is used as a starting point only; every migration is reviewed by hand. |
| Database | PostgreSQL 16 + PostGIS 3.4 (`postgis/postgis:16-3.4`) | The product is geographic by nature; polygons and spatial predicates are core, not future extras. |
| Local infra | Docker Compose (database only) | See [§2.3](#23-runtime-topology-decision). |
| Python env | pyenv 3.11.10 + `uv` virtualenv | pyenv is already the developer's tool; `uv` gives fast, reproducible installs with a lockfile. Plain `venv` + `pip` is documented as a fallback. |
| Backend tests | pytest + FastAPI `TestClient` | Synchronous stack, so no async test harness is needed. |
| Frontend tests | Vitest + Testing Library + MSW | Same transform pipeline as Vite; MSW mocks the API at the network layer. |
| QR codes | `qrcode` + `Pillow` | Pure Python, no external service, no API key. |

### 2.1 Tailwind v4 decision

The previous prototype broke on Tailwind setup, specifically around
`npx tailwindcss init -p`. Tailwind v4 removes that failure mode entirely:

- There is no `init` command and no required `tailwind.config.js`.
- There is no PostCSS config to maintain — the official `@tailwindcss/vite`
  plugin handles the pipeline.
- Setup is two lines: the plugin in `vite.config.ts`, and `@import "tailwindcss";`
  at the top of `src/styles/index.css`.
- Theme customization, when needed, lives in CSS via `@theme { ... }`.

The exact pinned versions are recorded in `frontend/package.json` and repeated in
the README so the working combination is never guessed at again.

### 2.2 Map decision

Leaflet is used through `react-leaflet`, never through direct `L.map(...)` calls.
This removes the three failure modes hit by the prior prototype:

- **Double initialization.** `react-leaflet` owns the map instance lifecycle, so
  there is no `L.map("map")` bound to a global DOM id that can be initialized
  twice under React Strict Mode.
- **Container sizing.** The map container is given an explicit height by CSS
  (a flex-sized wrapper on the map page, a fixed `aspect-ratio` box on the region
  page). This is the actual cause of the classic "grey half-rendered map"; it is
  fixed by layout, not by sprinkling `invalidateSize()`.
- **Manual lifecycle.** No `useEffect` wiring for map creation or teardown.

`invalidateSize()` is used in exactly one place, if needed: a small hook reacting
to a container resize on the region page. If layout alone proves sufficient, that
hook is not written.

Tiles come from OpenStreetMap, with the tile URL and attribution read from
environment variables so a different provider can be swapped in without a code
change. No paid API key is required.

### 2.3 Runtime topology decision

Only PostgreSQL/PostGIS runs in Docker Compose. The backend and frontend run
directly on the host.

Rationale: for a single developer, container-mounted Python with a reload watcher
is measurably slower to iterate on and adds a debugging layer for no benefit here.
The database, by contrast, genuinely benefits from isolation — PostGIS is
tedious to install natively, and the developer already runs other Postgres
instances on this machine that must not be disturbed.

The database port is exposed through the `POSTGRES_PORT` variable (default
`5432`) precisely because other Postgres containers already occupy `5433` and
`54322` on this machine.

A backend `Dockerfile` is added in Phase 7 for deployment, not for local
development.

---

## 3. Repository structure

```
community_roots/
├── README.md
├── PROJECT_BOOTSTRAP.md          # product spec (source of truth for scope)
├── docker-compose.yml
├── .env.example                  # variables consumed by docker-compose
├── docs/
│   ├── architecture.md
│   └── implementation-plan.md
├── infrastructure/
│   └── postgres/init/            # runs once on first container start
│       └── 01-init.sql           # CREATE EXTENSION postgis; create test database
├── backend/
│   ├── .python-version           # 3.11.10
│   ├── .env.example
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py               # app factory, router mounting, CORS, error handlers
│   │   ├── core/
│   │   │   ├── config.py         # Settings (pydantic-settings)
│   │   │   ├── security.py       # admin token dependency
│   │   │   └── errors.py         # domain exceptions -> HTTP responses
│   │   ├── db/
│   │   │   ├── base.py           # DeclarativeBase
│   │   │   └── session.py        # engine, session factory, get_db dependency
│   │   ├── models/               # SQLAlchemy models (region.py, photo.py)
│   │   ├── schemas/              # Pydantic request/response models
│   │   ├── services/             # business logic, no FastAPI imports
│   │   ├── storage/              # StorageBackend protocol + local implementation
│   │   └── api/routes/           # health.py, regions.py, photos.py
│   ├── scripts/seed.py
│   ├── storage/                  # local uploads (gitignored)
│   └── tests/
└── frontend/
    ├── .nvmrc                    # 22.22.1
    ├── .env.example
    ├── vite.config.ts
    └── src/
        ├── pages/                # HomePage, MapPage, RegionPage, QrRedirectPage, NotFoundPage
        ├── components/
        │   ├── layout/           # Header, Layout
        │   ├── map/              # PlantingMap, RegionLayer, RegionPopup
        │   ├── photos/           # PhotoTimeline, PhotoCard, PhotoUploadForm
        │   └── feedback/         # LoadingState, ErrorState, EmptyState
        ├── services/             # apiClient, regions, photos — the only fetch callers
        ├── hooks/                # useRegions, useRegion, useRegionPhotos, useUploadPhoto
        ├── types/                # API type definitions
        ├── utils/
        └── styles/index.css
```

**Layering rule for the backend:** routes parse and authorize, services decide,
models and storage persist. Services never import from `app.api`; routes never
build SQL. This is what makes a future admin interface or CLI reuse the same
service functions.

**Layering rule for the frontend:** components never call `fetch`. All network
access goes through `src/services/`, wrapped by hooks in `src/hooks/`. This keeps
components testable with plain props.

---

## 4. Data model

### 4.1 Geometry decision: `geometry(Geometry, 4326)`

The `regions.geom` column is declared as `geometry(Geometry, 4326)` with a check
constraint restricting it to `POINT`, `POLYGON`, and `MULTIPOLYGON`.

**Why a generic geometry type.** The MVP must work before the geographer delivers
official data (spec §2). A permissive type lets a region start as a placeholder
point or a rough hand-drawn polygon and later be replaced by a surveyed
`MultiPolygon` with a plain `UPDATE` — no column type migration, no data
rewrite, no application redesign. The check constraint keeps that permissiveness
bounded so the column can never hold something the map cannot render.

**Why `geometry` and not `geography`.** SRID 4326 `geometry` is the conventional
PostGIS choice and has the complete function surface, including everything
`ST_AsGeoJSON` and Leaflet need. `geography` buys accurate metre-based distances
without projection, but the planting area spans a few hundred metres; over that
extent, casting `geom::geography` for the rare distance query is exact enough and
costs nothing. The `geography` type also supports a smaller set of functions,
which would constrain the spatial queries listed in spec §5.

**Why a separate centroid.** `centroid` is a `geometry(Point, 4326)` column
generated as `ST_Centroid(geom)` (stored, `ST_Centroid` is `IMMUTABLE`). It gives
the map a stable marker anchor and makes "nearest region to this point" a simple
indexed query, without recomputing a centroid on every request.

### 4.2 `regions`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()` |
| `slug` | `text` unique, not null | URL segment, human-readable, may be renamed |
| `name` | `text` not null | Displayed to users |
| `description` | `text` null | Optional short text |
| `geom` | `geometry(Geometry, 4326)` not null | CHECK on `GeometryType(geom)`; GiST index |
| `centroid` | `geometry(Point, 4326)` generated stored | GiST index |
| `status` | `text` not null, default `'active'` | CHECK in (`active`, `draft`, `archived`) |
| `qr_token` | `text` unique, not null | Opaque, URL-safe, stable for the region's lifetime |
| `created_at` | `timestamptz` not null | |
| `updated_at` | `timestamptz` not null | |

### 4.3 `photos`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `region_id` | `uuid` FK -> `regions.id` | `ON DELETE CASCADE`, indexed |
| `storage_key` | `text` not null | Opaque key, meaningful only to the storage backend |
| `original_filename` | `text` null | Kept for display; never used to build a path |
| `content_type` | `text` not null | Determined by decoding the image, not by the client header |
| `byte_size` | `integer` not null | |
| `width`, `height` | `integer` not null | Lets the frontend reserve layout space and avoids reflow |
| `description` | `text` null | |
| `contributor_name` | `text` null | |
| `captured_at` | `timestamptz` null | From EXIF `DateTimeOriginal` when present |
| `uploaded_at` | `timestamptz` not null | Server clock |
| `location` | `geometry(Point, 4326)` null | See [§4.4](#44-photo-location-decision) |
| `location_source` | `text` null | `exif` today; `manual` / `browser` are future values |
| `status` | `text` not null, default `'published'` | CHECK in (`published`, `hidden`) |

Index on `(region_id, uploaded_at DESC)` — the timeline query is the hot path.

### 4.4 Photo location decision

The spec suggests `latitude` / `longitude` columns. We store a single
`geometry(Point, 4326)` instead, and expose `latitude` / `longitude` in the API
response. Two loose float columns cannot answer "which region contains this
photo?" without ad-hoc construction on every query; a real point can, through the
same GiST index the regions use. The API contract is unaffected.

### 4.5 The `status` columns

Neither `regions.status` nor `photos.status` has a UI in the MVP. They exist
because the product involves public uploads by and about children, and an
organizer needs a way to take a photo down immediately — a one-line `UPDATE` on
day one instead of an emergency migration. This is the only forward-looking
column in the schema; every other future entity from spec §7 (User, Contributor,
Planting event, Seed, Organization) is deliberately absent.

### 4.6 Future entities

`User`, `Contributor`, `PlantingEvent`, `Seed`, and `Organization` are not
modelled. The paths that would need them are already isolated: `contributor_name`
is a plain nullable text column that a future `contributor_id` FK can supersede,
and every write endpoint already goes through a service function where an
authenticated identity can be threaded in.

---

## 5. API design

REST, JSON, documented automatically at `/docs` (OpenAPI).

`{region}` in the paths below accepts either the UUID or the slug. Resolution is
handled once, in a shared FastAPI dependency.

| Method | Path | Auth | Response |
|---|---|---|---|
| `GET` | `/health` | public | `{status, database}` |
| `GET` | `/api/regions` | public | GeoJSON `FeatureCollection` |
| `GET` | `/api/regions/{region}` | public | GeoJSON `Feature` |
| `POST` | `/api/regions` | admin | GeoJSON `Feature` (201) |
| `PATCH` | `/api/regions/{region}` | admin | GeoJSON `Feature` |
| `POST` | `/api/regions/import` | admin | Import summary — Phase 6 |
| `GET` | `/api/regions/{region}/photos` | public | Paginated photo list |
| `POST` | `/api/regions/{region}/photos` | public | Created photo (201), `multipart/form-data` |
| `GET` | `/api/regions/{region}/qr-code` | public | `image/png` or `image/svg+xml` |
| `GET` | `/api/photos/{photo_id}/file` | public | Image bytes |
| `GET` | `/api/qr/{qr_token}` | public | Resolves a token to its region |

### 5.1 GeoJSON as the region representation

Region collections are returned as a GeoJSON `FeatureCollection`, which
`react-leaflet`'s `<GeoJSON>` component consumes directly with no transformation
step. Region attributes travel in `properties`:

```json
{
  "type": "Feature",
  "id": "0f1c...",
  "geometry": { "type": "Polygon", "coordinates": [[[-43.3129, -21.8843], "..."]] },
  "properties": {
    "slug": "canteiro-do-ipe",
    "name": "Canteiro do Ipê",
    "description": "...",
    "status": "active",
    "qr_token": "k3Zq8xR2mNvA",
    "photo_count": 12,
    "latest_photo_at": "2026-08-24T14:03:11Z",
    "created_at": "2026-08-01T10:00:00Z",
    "updated_at": "2026-08-24T14:03:11Z"
  }
}
```

The geometry is produced by `ST_AsGeoJSON` in the database rather than serialized
in Python, so the coordinate output has exactly one implementation.

`photo_count` and `latest_photo_at` are computed with a `LEFT JOIN LATERAL`
aggregate in the same query — the map needs them for every region and an N+1
would be immediate.

### 5.2 Photo file serving

Images are always served through `GET /api/photos/{photo_id}/file`, never through
a direct storage path. The URL therefore stays valid when the storage backend
changes: today the endpoint streams from disk, tomorrow it returns a 302 to a
presigned S3 URL. Storage keys are never exposed in API responses.

### 5.3 Errors

Domain exceptions (`RegionNotFound`, `InvalidImage`, `ImageTooLarge`) are raised
by services and mapped to HTTP responses by exception handlers in `app/main.py`.
Response body:

```json
{ "detail": "Não foi possível ler esta imagem.", "code": "invalid_image" }
```

`detail` is user-facing Brazilian Portuguese, safe to display directly. `code` is
a stable English identifier for the frontend to branch on.

---

## 6. Photo storage

```python
class StorageBackend(Protocol):
    def save(self, key: str, data: BinaryIO, content_type: str) -> None: ...
    def open(self, key: str) -> BinaryIO: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
```

`LocalFilesystemStorage` is the only implementation in the MVP, writing under
`backend/storage/` (gitignored). It is selected by `STORAGE_BACKEND=local` and
injected as a FastAPI dependency, so tests substitute a temp-directory instance
without touching service code.

Keys follow `regions/{region_id}/{yyyy}/{uuid4}.{ext}` — collision-free, never
derived from user input, and cheap to prefix-list per region.

### 6.1 Upload validation

Applied in order; the first failure rejects the request:

1. **Size.** `MAX_UPLOAD_BYTES` (default 10 MB), enforced while streaming, before
   the file is fully buffered.
2. **Real format.** The bytes are decoded with Pillow and the format read from the
   decoded image. The client's `Content-Type` header and the filename extension
   are both ignored for this decision. Allowed: JPEG, PNG, WebP.
3. **Decompression bomb.** `Image.MAX_IMAGE_PIXELS` is set to a bounded value so a
   small crafted file cannot exhaust memory.
4. **Re-encode.** The image is re-encoded before being written. This normalizes
   the format, applies EXIF orientation, and — critically — produces a stored file
   that carries no metadata (see below).

### 6.2 EXIF and privacy

The stored image file always has its EXIF block stripped. Metadata is extracted
into database columns first, and only what the contributor agreed to share is
kept:

- `DateTimeOriginal` -> `captured_at`. Always extracted; it is what makes the
  timeline meaningful.
- GPS tags -> `location`. **Only** persisted when the upload includes
  `share_location=true`.

`share_location` is an explicit opt-in checkbox in the upload form, **unchecked by
default**, with plain-language text stating that the photo's location will be
recorded. Anyone can contribute — including children — so silently harvesting the
precise coordinates of where a minor was standing is not acceptable. When the box
is left unchecked, GPS tags are read and discarded, never written to the database.

Because the stored file is stripped regardless, a photo that leaks by any other
route still carries no hidden location.

### 6.3 Deferred

Thumbnail generation and responsive variants are not in the MVP. The hook is in
place: `width`/`height` are recorded at upload time, and the file-serving endpoint
is the single place a `?size=` parameter would later be handled.

---

## 7. QR codes

The stable identifier is `regions.qr_token`: an opaque, URL-safe random string
assigned once and never changed. The QR image encodes:

```
{PUBLIC_WEB_BASE_URL}/r/{qr_token}
```

The token, not the slug, is encoded on purpose. A printed and physically installed
QR code cannot be reprinted cheaply, so the URL it carries must survive a region
being renamed, re-slugged, or re-keyed internally. `/r/{qr_token}` resolves
through `GET /api/qr/{qr_token}` and redirects to `/regions/{slug}`.

`GET /api/regions/{region}/qr-code` renders the image on demand (`?format=png|svg`,
`?size=`). Nothing is cached to disk — regeneration is cheap and there is no
stale-file problem. A print-oriented sheet with the region name below each code is
Phase 6 work, produced from the same endpoint.

---

## 8. Frontend architecture

| Route | Page | Purpose |
|---|---|---|
| `/` | `HomePage` | What the project is, how to take part, call to action |
| `/mapa` | `MapPage` | Full-height interactive map of all regions |
| `/regions/:slug` | `RegionPage` | Region detail, timeline, upload |
| `/r/:qrToken` | `QrRedirectPage` | Resolves a scanned token, redirects |
| `*` | `NotFoundPage` | |

The region path stays `/regions/:slug` (English, as specified in spec §3) so
printed QR codes and the spec agree. Other user-facing paths are Portuguese.

**Data flow.** `services/apiClient.ts` owns `fetch`, the base URL, and error
normalization. `services/regions.ts` and `services/photos.ts` expose typed
functions. Hooks wrap those in TanStack Query. Pages call hooks and render
components; components receive plain props and never fetch.

**Map components.** `PlantingMap` owns the `MapContainer` and tile layer;
`RegionLayer` renders the `FeatureCollection` and handles click and keyboard
activation; `RegionPopup` renders the summary shown on selection. `PlantingMap`
takes an explicit `height` from its parent's layout, never `100%` of an
unsized ancestor.

**Vocabulary.** The user-facing word for a region is **"canteiro"**. Users never
see "region", "polygon", "GeoJSON", or "QR token". Per spec §14, all UI text is
Brazilian Portuguese while identifiers, comments, and these documents are English.

---

## 9. Security and moderation

Implemented in the MVP:

- Upload size limit, real-format validation, decompression-bomb guard (§6.1).
- EXIF stripped from every stored file; GPS persisted only on explicit opt-in (§6.2).
- Admin write endpoints (`POST`/`PATCH /api/regions`) require an
  `X-Admin-Token` header matching `ADMIN_API_TOKEN`, compared with
  `secrets.compare_digest`. The backend refuses to start with a default or empty
  token when `ENVIRONMENT=production`.
- CORS restricted to `CORS_ALLOWED_ORIGINS`, not `*`.
- Storage keys and filesystem paths never appear in responses.
- `photos.status` lets an organizer hide content immediately.

Documented and deliberately deferred:

- **Rate limiting.** No limit on photo uploads in the MVP; the endpoint is public
  and this is the clearest abuse vector. Phase 7 evaluates a per-IP limit.
- **Image moderation.** No automated or human moderation queue. `photos.status`
  is the manual escape hatch.
- **Consent.** No recorded consent flow for images of identifiable people. If the
  project photographs children rather than only plants, this needs a real policy
  decision before any public launch — it is a legal question (LGPD), not a
  technical one.
- **Authentication.** No user accounts. The admin token is a stopgap, not an
  authentication system; the write paths are already isolated behind one
  dependency, so replacing it is a contained change.
- **Contributor name.** Free text, unvalidated, publicly displayed. The UI asks
  for a first name only.

---

## 10. Testing strategy

**Backend** (`pytest`): tests run against a real PostGIS database — `postgis`
behaviour is the thing most worth testing, so it is never mocked. The
`community_roots_test` database is created by the Compose init script; each test
runs inside a transaction that is rolled back afterwards.

Coverage: health endpoint; region list/detail/create/patch including GeoJSON
output shape; slug and UUID resolution; admin token enforcement; photo upload
happy path; each rejection path (oversized, wrong format, corrupt bytes); EXIF
stripping verified by re-reading the stored file; GPS persisted only with opt-in;
QR endpoint content type and encoded URL.

**Frontend** (Vitest + Testing Library + MSW): upload form validation and states;
`RegionPage` loading/error/empty/populated; `PhotoTimeline` ordering. Map tests
stay shallow — `react-leaflet` in jsdom is high-friction for low value, so
`RegionLayer` is tested for the props and handlers it passes down, with
`react-leaflet` mocked.

Manual test scripts live in the README, one per user flow from spec §15.

---

## 11. Configuration

No secrets in the repository. Every service reads a `.env` created from its
`.env.example`.

| File | Consumed by |
|---|---|
| `.env` (root) | `docker-compose.yml` |
| `backend/.env` | FastAPI (`pydantic-settings`) |
| `frontend/.env` | Vite (only `VITE_`-prefixed variables reach the browser) |

`backend/app/core/config.py` fails fast at startup on a missing or invalid
required variable, with a message naming the variable.

---

## 12. Evolution paths

The design deliberately leaves these doors open:

- **Real polygons arrive.** `POST /api/regions/import` accepts a GeoJSON
  `FeatureCollection` and matches features to existing regions by slug,
  `UPDATE`-ing `geom`. QR codes stay valid because they encode `qr_token`.
  Shapefiles are converted with `ogr2ogr` before import rather than parsed in the
  application.
- **Object storage.** Implement `S3Storage` against the same protocol, flip
  `STORAGE_BACKEND`. The file endpoint switches from streaming to a redirect.
- **Authentication.** Replace the admin token dependency; add `contributor_id` to
  `photos` alongside the existing `contributor_name`.
- **Admin interface.** Services already contain the logic; an admin UI is new
  routes plus a frontend area, with no changes below the route layer.
- **Spatial features.** "Which region contains this point?", "nearest region",
  and boundary intersection are all direct `ST_*` queries against the existing
  GiST-indexed columns.
