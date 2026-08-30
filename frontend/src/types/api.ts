// Mirrors backend/app/schemas/geojson.py and region.py. Kept in sync by
// hand until the backend grows an OpenAPI-generated client (see
// types/health.ts for the same note).

export interface Point {
  type: 'Point'
  coordinates: [number, number]
}

export interface Polygon {
  type: 'Polygon'
  coordinates: number[][][]
}

export interface MultiPolygon {
  type: 'MultiPolygon'
  coordinates: number[][][][]
}

// The three geometry shapes `ck_regions_geom_type` allows
// (backend/app/models/region.py).
export type RegionGeometry = Point | Polygon | MultiPolygon

export type RegionStatus = 'active' | 'draft' | 'archived'

// The `properties` object of a region `Feature` (architecture.md §5.1).
// `latest_photo_at`/`created_at`/`updated_at` are ISO 8601 strings over the
// wire — parse with `new Date(...)` at the point of use, not here.
export interface RegionProperties {
  slug: string
  name: string
  description: string | null
  status: RegionStatus
  qr_token: string
  photo_count: number
  latest_photo_at: string | null
  created_at: string
  updated_at: string
}

export interface Feature<Geometry, Properties> {
  type: 'Feature'
  id: string
  geometry: Geometry
  properties: Properties
}

export interface FeatureCollection<Geometry, Properties> {
  type: 'FeatureCollection'
  features: Feature<Geometry, Properties>[]
}

export type RegionFeature = Feature<RegionGeometry, RegionProperties>
export type RegionFeatureCollection = FeatureCollection<RegionGeometry, RegionProperties>

// Mirrors backend/app/schemas/photo.py::PhotoOut. `width`/`height` are the
// dimensions recorded on upload (issue #20) — the frontend timeline
// (issue #24) sets them as the `<img>` element's native `width`/`height`
// attributes so the browser reserves the image's layout space before it
// loads, instead of reflowing the page once it does.
export interface Photo {
  id: string
  description: string | null
  contributor_name: string | null
  captured_at: string | null
  uploaded_at: string
  latitude: number | null
  longitude: number | null
  width: number
  height: number
  photo_url: string
}

// Mirrors backend/app/schemas/photo.py::PhotoPage — the response of
// `GET /api/regions/{region}/photos` (keyset-paginated, see
// backend/app/services/photo_service.py for why).
export interface PhotoPage {
  items: Photo[]
  next_cursor: string | null
}
