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
