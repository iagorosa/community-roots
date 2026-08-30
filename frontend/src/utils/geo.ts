import { geoJSON, type LatLngBounds } from 'leaflet'
import type { RegionFeatureCollection } from '../types/api'

/**
 * Bounding box covering every feature in the collection, for
 * `PlantingMap`'s `bounds` prop (issue #18's `fitBounds` requirement).
 * Reuses Leaflet's own GeoJSON bounds calculation instead of hand-rolling
 * a min/max walk over the three heterogeneous geometry shapes
 * (`RegionGeometry` — Point/Polygon/MultiPolygon).
 */
export function regionsBounds(data: RegionFeatureCollection): LatLngBounds {
  return geoJSON(data).getBounds()
}
