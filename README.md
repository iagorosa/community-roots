# Community Roots

A community project for environmental education. Children, teenagers, and
neighbours plant seeds in a shared area of the city and follow how those plants
grow over time.

The application is the digital twin of that physical area: an interactive map of
the planting beds, a QR code on each bed in the field, and a photo timeline
showing each bed's development.

```
Physical marker  ->  QR code  ->  digital region  ->  photo timeline
```

Reference area: **Matias Barbosa, Minas Gerais, Brazil**.

---

## Project status

Planning is complete. Implementation has not started.

| Phase | Description | Status |
|---|---|---|
| 0 | Planning and documentation | done |
| 1 | Project foundation | not started |
| 2 | Geographic regions | not started |
| 3 | Interactive map | not started |
| 4 | Region pages | not started |
| 5 | Photo uploads | not started |
| 6 | QR codes | not started |
| 7 | Polish | not started |

The setup instructions below describe the state at the end of Phase 1. They do
not work yet.

Read next:

- [docs/architecture.md](docs/architecture.md) — architecture and the reasoning
  behind each decision.
- [docs/implementation-plan.md](docs/implementation-plan.md) — phases,
  deliverables, and validation criteria.
- [PROJECT_BOOTSTRAP.md](PROJECT_BOOTSTRAP.md) — the product specification.

---

## Stack

**Frontend** — React 19, Vite 7, TypeScript, Tailwind CSS v4, React Leaflet 5,
React Router 7, TanStack Query 5.

**Backend** — Python 3.11, FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Pydantic v2,
Alembic.

**Database** — PostgreSQL 16 with PostGIS 3.4, in Docker.

Map tiles come from OpenStreetMap. No paid service and no API key is required to
run this project.

---

## Requirements

| Tool | Version | Notes |
|---|---|---|
| Docker + Compose | any recent | Runs the database only |
| Python | 3.11.10 | Pinned in `backend/.python-version` |
| Node.js | 22.22.1 | Pinned in `frontend/.nvmrc` |

`pyenv` and `nvm` will pick up those pinned versions automatically.
No global npm package is needed.

---

## Setup

### 1. Database

```bash
cp .env.example .env          # edit POSTGRES_PASSWORD
docker compose up -d
docker compose ps             # wait for "healthy"
```

The container exposes the port set in `POSTGRES_PORT` (default `5432`). Change it
if that port is taken. On first start, the init script enables PostGIS and creates
the `community_roots_test` database used by the test suite.

### 2. Backend

```bash
cd backend
cp .env.example .env           # DATABASE_URL must match the root .env
pyenv install --skip-existing 3.11.10

uv venv && source .venv/bin/activate
uv sync

alembic upgrade head
uvicorn app.main:app --reload
```

Without `uv`, the equivalent is:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

- API: <http://localhost:8000>
- Interactive docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

### 3. Frontend

```bash
cd frontend
cp .env.example .env
nvm use                        # reads .nvmrc
npm install
npm run dev
```

Open <http://localhost:5173>. In development, `/api` is proxied to the backend,
so there is a single origin and no CORS to configure.

### 4. Development data

```bash
cd backend
python scripts/seed.py
```

This creates 10 fictional planting beds arranged around `SEED_CENTER_LAT` /
`SEED_CENTER_LON`. **The geometry is a placeholder** — real polygons will be
imported once the geographer delivers them. Running the script again changes
nothing; it matches on slug.

---

## Common commands

```bash
# Backend
pytest                                   # tests
ruff check . && ruff format .            # lint and format
alembic revision --autogenerate -m "..." # new migration (always review it)
alembic upgrade head                     # apply
python scripts/seed.py                   # development data

# Frontend
npm run dev
npm run build
npm run test
npm run lint

# Database
docker compose up -d
docker compose logs -f db
docker compose down                      # stop, keep data
docker compose down -v                   # stop and erase data
```

---

## Manual testing

**Flow A — explore the map.** Open `/`, follow the call to action, tap a bed,
confirm the region page opens with its timeline.

**Flow B — contribute via QR code.** Fetch a bed's QR code from
`/api/regions/{slug}/qr-code`, scan it with a phone camera, confirm it opens the
right bed, send a photo, confirm it appears in the timeline.

**Flow C — organizer.** Create a bed through the API with the `X-Admin-Token`
header, fetch its QR code, confirm the printable sheet renders.

Test on a 360 px-wide viewport as well. Mobile is the primary experience for
anyone standing in the planting area.

---

## Project conventions

- Code, identifiers, comments, and documentation in **English**.
- All user-facing interface text in **Brazilian Portuguese**, avoiding technical
  vocabulary. A region is a *canteiro*; users never see the words "polygon",
  "GeoJSON", or "token".
- Commit messages in Portuguese, following Conventional Commits.
- Secrets stay in `.env` files, which are never committed.
- Uploaded photos are stored under `backend/storage/` and are never committed.

## Privacy

Photos may be taken by and of children. Every stored image has its metadata
stripped before it is written to disk. GPS coordinates are recorded only when the
contributor explicitly opts in through the upload form. See
[docs/architecture.md §6.2](docs/architecture.md) and §9 for the full policy and
for what is deliberately deferred.
