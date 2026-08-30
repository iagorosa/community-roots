import { geoJSON, type LatLngBounds } from 'leaflet'
import type { RegionFeature, RegionFeatureCollection } from '../types/api'

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

/**
 * Center point for a single region, for `PlantingMap`'s `center` prop on
 * the region detail page's mini-map (issue #23). There's no centroid
 * column in the API response — only the raw geometry — so, like
 * `regionsBounds` above, this reuses Leaflet's own GeoJSON bounds
 * calculation (its bounding-box center) instead of hand-rolling a walk
 * over the three possible `RegionGeometry` shapes. For a `Point` geometry
 * this is just that point; for a `Polygon`/`MultiPolygon` it's the
 * bounding-box center, not a true area centroid — close enough to frame
 * the canteiro in a mini-map.
 */
export function regionCenter(feature: RegionFeature): [number, number] {
  const center = geoJSON(feature).getBounds().getCenter()
  return [center.lat, center.lng]
}
