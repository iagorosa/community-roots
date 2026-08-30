// Imported here, and only here — the one place in the codebase that pulls
// in Leaflet's CSS, satisfying issue #16's "importado uma única vez"
// (ES modules only execute a given import's top-level code once anyway,
// but a single import site keeps that guarantee obvious).
import 'leaflet/dist/leaflet.css'

import type { LatLngBoundsExpression } from 'leaflet'
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { MapContainer, TileLayer, useMap } from 'react-leaflet'

function requiredEnvVar(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Variável de ambiente ${name} não configurada — veja frontend/.env.example.`)
  }
  return value
}

const TILE_URL = requiredEnvVar('VITE_MAP_TILE_URL', import.meta.env.VITE_MAP_TILE_URL)
const TILE_ATTRIBUTION = requiredEnvVar(
  'VITE_MAP_TILE_ATTRIBUTION',
  import.meta.env.VITE_MAP_TILE_ATTRIBUTION,
)
const DEFAULT_CENTER: [number, number] = [
  Number(requiredEnvVar('VITE_MAP_DEFAULT_LAT', import.meta.env.VITE_MAP_DEFAULT_LAT)),
  Number(requiredEnvVar('VITE_MAP_DEFAULT_LON', import.meta.env.VITE_MAP_DEFAULT_LON)),
]
const DEFAULT_ZOOM = Number(requiredEnvVar('VITE_MAP_DEFAULT_ZOOM', import.meta.env.VITE_MAP_DEFAULT_ZOOM))

interface PlantingMapProps {
  /**
   * Required, not optional: the parent decides height by CSS
   * (docs/architecture.md §2.2) — an unsized ancestor is the actual cause
   * of the classic "half-gray map", so this can't quietly default to
   * nothing.
   *
   * Inside a `flex-col` parent, pass `flex-1`, not `h-full`: a percentage
   * height doesn't reliably resolve against a flex-grown ancestor, so the
   * map silently gets zero height (confirmed live in a browser — see
   * `pages/MapPage.tsx`). `h-full` only works when the immediate parent
   * has a genuinely fixed height (e.g. a `aspect-ratio` box).
   */
  className: string
  /** Defaults to the pre-survey placement (VITE_MAP_DEFAULT_*); the region
   * detail page's mini-map (issue #23) overrides this to its own canteiro. */
  center?: [number, number]
  zoom?: number
  /**
   * When given, the map fits itself to these bounds (issue #18) instead of
   * sitting at `center`/`zoom`. Applied imperatively via `useMap`, not
   * `MapContainer`'s own `bounds` prop: that prop is skipped whenever
   * `center`/`zoom` are also set (see react-leaflet's `MapContainer.js`),
   * and this component always supplies a `center`/`zoom` default above.
   */
  bounds?: LatLngBoundsExpression
  children?: ReactNode
}

/** Imperative `fitBounds` call, reacting to `bounds` changes — a plain
 * `MapContainer` prop can't do this past the initial mount (see the
 * `bounds` doc comment on `PlantingMapProps` above). Rendered only when
 * `bounds` is given, so `PlantingMap` stays usable without ever pulling in
 * `useMap` (the region detail page's mini-map, issue #23, has fixed
 * center/zoom and no bounds to fit). */
function FitBounds({ bounds }: { bounds: LatLngBoundsExpression }) {
  const map = useMap()

  useEffect(() => {
    map.fitBounds(bounds)
  }, [map, bounds])

  return null
}

function PlantingMap({
  className,
  center = DEFAULT_CENTER,
  zoom = DEFAULT_ZOOM,
  bounds,
  children,
}: PlantingMapProps) {
  return (
    <MapContainer center={center} zoom={zoom} scrollWheelZoom className={className}>
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
      {bounds && <FitBounds bounds={bounds} />}
      {children}
    </MapContainer>
  )
}

export default PlantingMap
