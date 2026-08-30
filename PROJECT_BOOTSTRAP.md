# Community Roots — Project Bootstrap

You are working on a new full-stack application called **Community Roots**.

Before writing application code, you must first understand the product, review the architecture requirements, identify important technical decisions, and create a clear implementation plan.

Do not blindly implement everything at once.

Work iteratively, validate each phase, and keep the project architecture clean enough for future evolution.

---

# 1. Product Vision

Community Roots is a community project focused on environmental education and collective participation.

Children and teenagers will plant seeds in a specific physical area of the city.

The application will allow them and other community members to follow the development of the planted seeds over time.

The central idea is to create a digital representation of the physical planting area.

Users should be able to:

- Explore the planting area through an interactive map.
- View the different planting regions.
- Identify a specific region in the real world.
- Access the corresponding region through a QR Code.
- Upload photos documenting the development of the seed or plant.
- View the historical timeline of photos for a region.
- Follow the growth and evolution of the planted area over time.

The application should create a strong connection between:

Physical space → QR Code → Digital region → Photo history → Plant development.

The initial users may include children and teenagers, but other community members should also be able to contribute photos.

The product should be designed with a simple, accessible, mobile-friendly user experience.

---

# 2. Core Product Concept

The physical planting area will eventually be mapped by a geographer.

The geographer may provide geographic data representing multiple regions inside the planting area.

Each region may be represented by a geographic polygon.

Example:

Planting Area
├── Region A
│   ├── Polygon
│   ├── QR Code
│   └── Photo history
├── Region B
│   ├── Polygon
│   ├── QR Code
│   └── Photo history
└── Region C
    ├── Polygon
    ├── QR Code
    └── Photo history

The final application should support geographic polygons.

However, the MVP must not depend on the geographic data already being available.

The application should initially support manually created regions with simple geometry or placeholder locations.

When the official geographic polygons become available, the architecture should allow importing or updating them without requiring a redesign of the application.

Possible future formats may include:

- GeoJSON
- Shapefile
- Other GIS-compatible formats

Prefer an architecture that can evolve naturally toward importing GeoJSON.

---

# 3. Important MVP Decision

For the MVP, we will combine two interaction methods.

## Method A: Interactive map

Users can:

- Open the map.
- See the planting regions.
- Click or tap a region.
- View information about the region.
- Access its photo history.
- Upload a new photo.

This provides the visual exploration experience.

## Method B: QR Code

Each physical region should have a unique identifier and associated QR Code.

The QR Code should point directly to a region page or photo upload flow.

Example:

/regions/region-a

or:

/regions/{region_id}

The QR Code is important because a person standing in the physical planting area should not need to manually find the correct location on the map.

The intended physical interaction is:

1. Person visits the planting area.
2. Person finds the region identification.
3. Person scans the QR Code.
4. Application opens directly on the correct region.
5. Person can view the region history.
6. Person can upload a new photo.

The map and QR Code should complement each other.

---

# 4. Product Scope for the First MVP

The first working version should include:

## Public landing page

A simple introduction explaining:

- What Community Roots is.
- The environmental/community purpose.
- How people can participate.
- A call to action to explore the planting map.

## Interactive map page

The map should:

- Display a real map base layer.
- Display planting regions.
- Allow clicking or tapping a region.
- Work well on desktop and mobile.
- Eventually support polygons.

## Region page

Each region should have a dedicated URL.

Example:

/regions/{region_id}

The page should display:

- Region name.
- Optional description.
- Region location on the map.
- Photo timeline.
- Number of contributions.
- Button to upload a new photo.

## Photo upload

Users should initially be able to upload:

- Image file.
- Optional description or observation.
- Optional contributor name.

The MVP should keep authentication optional.

Do not make authentication a blocker for the first usable version.

Design the architecture so authentication can be added later.

## Photo timeline

Photos associated with a region should be displayed chronologically.

Each photo should include, when available:

- Image.
- Upload date.
- Contributor name.
- Description.
- Original capture timestamp if available in metadata.

## Region administration

For the MVP, region creation and administration does not need a full admin interface.

It is acceptable to manage regions through:

- API endpoints.
- Database scripts.
- Seed data.

However, the architecture should make a future admin interface possible.

---

# 5. Technology Direction

The previous prototype started with:

Frontend:
- React
- Vite
- Tailwind CSS
- Leaflet

Backend:
- Python
- FastAPI

This stack should be evaluated and used as the default direction unless there is a strong technical reason to change it.

The expected stack is:

## Frontend

- React
- Vite
- JavaScript or TypeScript
- Tailwind CSS
- Leaflet or React Leaflet

Prefer React Leaflet if it results in cleaner React integration.

Avoid manually managing Leaflet DOM instances if React Leaflet provides a cleaner architecture.

The frontend should be componentized and easy for a backend-oriented developer to understand.

## Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic

Use a clean project structure.

Avoid placing all application logic in a single file.

Separate:

- API routes
- Models
- Schemas
- Services
- Database configuration
- Storage logic
- Configuration

## Database

Use PostgreSQL with PostGIS from the beginning.

Reason:

The project is fundamentally geographic and will eventually work with polygons and spatial queries.

Do not use SQLite as the primary production-oriented architecture if PostGIS can reasonably be included from the start.

The system should support:

- Geographic points.
- Geographic polygons.
- Spatial relationships.
- Future spatial queries.

Examples of possible future queries:

- Which region contains a specific point?
- Which region is closest to a location?
- Which photo belongs to which region?
- Which regions intersect with a geographic boundary?

Use an architecture that makes these future features possible.

For the MVP, the PostGIS complexity should remain manageable.

## Database migrations

Use Alembic.

Do not rely exclusively on automatic table creation for the long-term architecture.

## Local infrastructure

Prefer Docker Compose for services that benefit from isolation.

At minimum, evaluate using Docker Compose for:

- PostgreSQL
- PostGIS

The Python backend may either run locally inside a virtual environment or inside Docker.

Choose the simplest developer experience for a single developer while keeping the architecture reproducible.

Document all setup steps.

---

# 6. Geographic Data Model

The geographic model is a central part of the application.

Think carefully about the Region entity.

A region should conceptually contain:

- Unique ID
- Name
- Description
- Geographic geometry
- Creation date
- Update date
- Optional status
- QR Code identifier or token

The geometry should support future polygons.

Avoid designing the database around only latitude and longitude fields if PostGIS geometry can represent the requirement better.

Evaluate whether to use:

- geometry
- geography

and document the decision.

Prefer a practical and conventional PostGIS design.

The application should eventually support a GeoJSON representation of each region.

---

# 7. Suggested Initial Data Model

This is a starting point, not a rigid final schema.

## Region

Possible fields:

- id
- slug
- name
- description
- geometry
- qr_token
- created_at
- updated_at

## Photo

Possible fields:

- id
- region_id
- storage_key
- original_filename
- content_type
- description
- contributor_name
- captured_at
- uploaded_at
- latitude
- longitude

Photo coordinates are optional.

Do not assume every uploaded photo will contain GPS metadata.

## Future entities

Do not implement unnecessarily yet, but consider future compatibility with:

- User
- Contributor
- Planting event
- Seed or plant
- Organization
- Region metadata
- Moderation status

---

# 8. Photo Storage Architecture

Do not store large image binaries directly inside PostgreSQL unless there is a strong reason.

Create an abstraction for image storage.

For local development, use a simple local storage implementation.

The architecture should allow a future migration to object storage such as:

- Amazon S3
- Cloudflare R2
- Google Cloud Storage
- Another S3-compatible provider

The API should not expose storage implementation details unnecessarily.

Think about:

- Unique filenames.
- File validation.
- File size limits.
- Allowed image formats.
- Image metadata.
- Future thumbnail generation.
- Future image optimization.

For the MVP, implement the simplest safe working approach.

---

# 9. QR Code Architecture

Every region should be identifiable through a stable public URL.

Do not make the QR Code itself the source of truth.

The source of truth should be the region identifier or stable public token.

Example:

https://example.com/regions/{slug}

or:

https://example.com/r/{qr_token}

The QR Code should encode a stable URL.

Design this so QR Codes do not need to be regenerated if the internal database implementation changes.

The system should eventually support generating a printable QR Code for each region.

For the MVP, implement QR Code generation through an API endpoint or utility.

---

# 10. API Design

Use a REST API for the MVP.

Suggested resources:

## Regions

GET /api/regions

GET /api/regions/{region_id}

GET /api/regions/{region_id}/photos

POST /api/regions

PATCH /api/regions/{region_id}

POST /api/regions/{region_id}/photos

GET /api/regions/{region_id}/qr-code

## Health

GET /health

Use clear request and response schemas.

Use appropriate HTTP status codes.

Document the API automatically through FastAPI's OpenAPI support.

---

# 11. Frontend Architecture

The frontend should not be a single App.jsx with all application logic.

Create a clear structure.

For example:

src/
  components/
  pages/
  services/
  hooks/
  utils/
  types/
  styles/

The exact structure may change if you have a better approach.

Important principles:

- Keep pages separate from reusable components.
- Keep API calls outside UI components when practical.
- Avoid excessive abstraction.
- Keep the project understandable for a developer who is stronger in backend than frontend.

Suggested pages:

- HomePage
- MapPage
- RegionPage
- NotFoundPage

Suggested components:

- Map
- RegionLayer
- RegionPopup
- PhotoTimeline
- PhotoCard
- PhotoUploadForm
- Header
- LoadingState
- ErrorState

Use React Router or another appropriate routing solution.

---

# 12. Map Requirements

The map is one of the main experiences of the application.

Requirements:

- Use OpenStreetMap-compatible tiles initially.
- Avoid requiring paid API keys for the MVP.
- Display regions as polygons when geographic data is available.
- Display placeholder regions before official polygons are available.
- Allow clicking/tapping a region.
- Navigate to the region page.
- Support mobile interactions.
- Fit the map to the available region boundaries when possible.

When receiving geographic data from the API, prefer a GeoJSON-compatible response.

The frontend map implementation should not contain hardcoded geographic data except for development seed data.

The backend/database should be the source of truth.

---

# 13. Initial Development Data

The first MVP should include seed data.

Create a small development dataset with approximately 3 to 5 fictional regions.

Use the same city/area only if a real location is explicitly configured.

Do not invent a production location.

The seed data should demonstrate:

- Multiple regions.
- Polygon support.
- Different region names.
- Some sample photos or placeholders if useful.

The application should be testable without waiting for the geographer's final data.

---

# 14. UX Principles

The application may be used by:

- Children.
- Teenagers.
- Parents.
- Teachers.
- Community members.
- Project organizers.

Therefore:

- Keep navigation simple.
- Use clear language.
- Avoid technical terminology in user-facing interfaces.
- Make important actions visually obvious.
- Make mobile usage a first-class experience.
- Keep the upload flow short.
- Do not require users to understand geographic concepts.

User-facing text should initially be in Brazilian Portuguese.

Code, variable names, API names, comments, file names, and technical documentation should be in English.

---

# 15. MVP User Flows

## Flow A — Explore map

1. User opens the website.
2. User understands the project.
3. User opens the map.
4. User sees planting regions.
5. User taps a region.
6. User opens the region page.
7. User sees the photo history.

## Flow B — QR Code contribution

1. User visits the physical planting area.
2. User scans the region QR Code.
3. User is taken directly to the region page.
4. User sees previous photos.
5. User taps "Enviar uma foto".
6. User selects a photo.
7. User optionally writes an observation.
8. User submits.
9. The photo appears in the region history.

## Flow C — Organizer

1. Organizer creates or imports regions.
2. Organizer obtains a QR Code for each region.
3. Organizer places QR Codes in the physical area.

---

# 16. Security and Moderation Considerations

The MVP should remain simple, but because the project involves public image uploads and potentially children and teenagers, the architecture should consider safety.

Do not overbuild the MVP.

However, identify and document future considerations such as:

- Upload abuse.
- File validation.
- Rate limiting.
- Image moderation.
- EXIF privacy.
- Personal data.
- Consent.
- Authentication for administrators.

For the initial MVP, implement reasonable file validation and size limits.

Do not silently expose unnecessary EXIF data.

---

# 17. Testing Requirements

Do not postpone all validation until the end.

Implement an appropriate level of tests.

At minimum:

Backend:
- Health endpoint test.
- Region API tests.
- Photo upload validation tests.
- Basic database integration tests.

Frontend:
- At least basic component or integration tests for important flows if the chosen tooling is straightforward.

Also provide manual testing instructions.

Every major implementation phase should be validated before moving to the next one.

---

# 18. Developer Experience

This project is being built by a developer with strong backend and data experience but less frontend experience.

Therefore, optimize for clarity.

Requirements:

- Clear README.
- Simple setup commands.
- Environment variable examples.
- One-command or low-friction local startup where possible.
- Useful error messages.
- Avoid unnecessary microservices.
- Avoid enterprise architecture for its own sake.

Prefer a well-structured monolith.

Suggested repository structure:

community-roots/
  backend/
  frontend/
  infrastructure/
  docs/
  docker-compose.yml
  README.md

The exact structure can be refined if necessary.

---

# 19. Environment Isolation

The previous development environment was Linux-based and Python was managed using pyenv.

The previous project had a structure similar to:

community-roots/
  backend/
  frontend/

The backend should continue using an isolated Python environment.

Document the recommended Python version.

If pyenv is used, provide setup instructions.

The frontend should use a clearly documented Node.js version.

Consider adding:

- .python-version
- .nvmrc or equivalent
- .env.example files

Do not require global npm package installation.

Avoid reproducing the previous Tailwind setup problem.

Use a Tailwind version and setup compatible with the chosen Vite version and document it correctly.

---

# 20. Previous Prototype Lessons

A previous prototype encountered issues with:

- Tailwind CSS version compatibility.
- Running `npx tailwindcss init -p`.
- Leaflet rendering incorrectly in React.
- Map container sizing.
- Manual Leaflet lifecycle management.

Do not blindly reproduce those issues.

Evaluate whether React Leaflet provides a cleaner implementation than manually using:

L.map(...)
useEffect(...)
map.invalidateSize()

Prefer the solution that is idiomatic, stable, and easier to maintain.

If Leaflet is used directly, use React refs instead of relying on a global DOM id such as:

L.map("map")

Avoid multiple map initialization issues.

---

# 21. Required Planning Phase

Before implementing the application:

1. Inspect the current repository.
2. Determine what already exists.
3. Do not overwrite useful files.
4. Create or update:
   - README.md
   - docs/architecture.md
   - docs/implementation-plan.md
   - .env.example files where appropriate
5. Explain the proposed architecture.
6. Identify any important decisions requiring confirmation.

After planning, present a concise summary of:

- Proposed stack.
- Repository structure.
- Database/PostGIS approach.
- Map approach.
- Image storage approach.
- Main entities.
- Implementation phases.

Do not start a massive implementation until the plan is internally coherent.

---

# 22. Implementation Phases

After the planning phase, implement incrementally.

## Phase 1 — Project foundation

- Repository structure.
- Backend setup.
- Frontend setup.
- Environment configuration.
- Docker Compose for PostgreSQL/PostGIS.
- Database connection.
- Alembic.
- Health endpoint.
- Basic README.

Validate everything.

## Phase 2 — Geographic regions

- Region database model.
- PostGIS geometry.
- Migrations.
- Seed data.
- Region API.
- GeoJSON-compatible responses.

Validate everything.

## Phase 3 — Interactive map

- React application structure.
- Routing.
- Map implementation.
- Fetch regions from backend.
- Display development polygons.
- Region interactions.
- Responsive behavior.

Validate everything.

## Phase 4 — Region pages

- Region details.
- Photo timeline.
- Empty states.
- Loading and error states.

Validate everything.

## Phase 5 — Photo uploads

- Backend file validation.
- Local storage abstraction.
- Upload API.
- Frontend upload form.
- Photo persistence.
- Photo timeline refresh.

Validate everything.

## Phase 6 — QR Codes

- Stable region URLs.
- QR Code generation.
- Printable/downloadable representation if practical.

Validate everything.

## Phase 7 — Polish

- Improve mobile UX.
- Improve accessibility.
- Improve error handling.
- Review security basics.
- Improve documentation.
- Add missing tests.

---

# 23. Working Style

When working on this repository:

- Do not make unnecessary assumptions.
- Inspect existing code before modifying it.
- Prefer small coherent changes.
- Run relevant tests after changes.
- Fix errors you introduce.
- Keep code readable.
- Do not create abstractions without a clear reason.
- Do not over-engineer the MVP.
- Document important architectural decisions.
- When a decision has meaningful long-term consequences, explain it.

Do not repeatedly ask for confirmation for minor implementation details.

Use reasonable engineering judgment.

However, stop and request confirmation when a decision would significantly affect:

- Core architecture.
- Paid services.
- Cloud provider lock-in.
- Public authentication strategy.
- Privacy model.
- Irreversible data model decisions.

---

# 24. Immediate Task

Start by inspecting the current repository and determining its current state.

Then perform the Required Planning Phase.

Do not immediately implement all phases.

First provide the proposed architecture and implementation plan.

After that, begin Phase 1.