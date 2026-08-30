import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import PlantingMap from './PlantingMap.tsx'

// react-leaflet needs real layout/canvas APIs jsdom doesn't provide well, so
// this test checks *wiring* (env-driven props reaching MapContainer/
// TileLayer) rather than Leaflet's own rendering — the "no gray band" and
// "no Strict Mode double-init" checks in issue #16's critério de pronto are
// validated manually in a real browser instead (docs/architecture.md §10:
// map tests stay shallow).
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children, ...props }: Record<string, unknown> & { children?: ReactNode }) => (
    <div data-testid="map-container" data-props={JSON.stringify(props)}>
      {children}
    </div>
  ),
  TileLayer: (props: Record<string, unknown>) => (
    <div data-testid="tile-layer" data-props={JSON.stringify(props)} />
  ),
}))

describe('PlantingMap', () => {
  it('configures the tile layer from VITE_MAP_* env vars', () => {
    render(<PlantingMap className="h-full" />)

    const props = JSON.parse(screen.getByTestId('tile-layer').dataset.props ?? '{}')
    expect(props.url).toBe(import.meta.env.VITE_MAP_TILE_URL)
    expect(props.attribution).toBe(import.meta.env.VITE_MAP_TILE_ATTRIBUTION)
  })

  it('passes the className through to the map container, for the parent to size', () => {
    render(<PlantingMap className="h-[500px]" />)

    const props = JSON.parse(screen.getByTestId('map-container').dataset.props ?? '{}')
    expect(props.className).toBe('h-[500px]')
  })

  it('defaults the center/zoom from VITE_MAP_DEFAULT_* env vars', () => {
    render(<PlantingMap className="h-full" />)

    const props = JSON.parse(screen.getByTestId('map-container').dataset.props ?? '{}')
    expect(props.center).toEqual([
      Number(import.meta.env.VITE_MAP_DEFAULT_LAT),
      Number(import.meta.env.VITE_MAP_DEFAULT_LON),
    ])
    expect(props.zoom).toBe(Number(import.meta.env.VITE_MAP_DEFAULT_ZOOM))
  })

  it('accepts an explicit center/zoom override', () => {
    render(<PlantingMap className="h-full" center={[1, 2]} zoom={10} />)

    const props = JSON.parse(screen.getByTestId('map-container').dataset.props ?? '{}')
    expect(props.center).toEqual([1, 2])
    expect(props.zoom).toBe(10)
  })

  it('renders children inside the map, for RegionLayer (issue #17)', () => {
    render(
      <PlantingMap className="h-full">
        <div data-testid="child" />
      </PlantingMap>,
    )

    expect(screen.getByTestId('child')).toBeInTheDocument()
  })
})
