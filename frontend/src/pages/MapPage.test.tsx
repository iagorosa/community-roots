import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { RegionFeatureCollection } from '../types/api'
import MapPage from './MapPage'

// `MapPage` renders `PlantingMap` (which renders `RegionLayer` once data
// arrives), so react-leaflet is faked the same shallow way its own test
// files do (docs/architecture.md §10) — real Leaflet needs layout/canvas
// APIs jsdom doesn't provide.
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children, ...props }: Record<string, unknown> & { children?: React.ReactNode }) => (
    <div data-testid="map-container" data-props={JSON.stringify(props)}>
      {children}
    </div>
  ),
  TileLayer: () => null,
  GeoJSON: (props: { data: RegionFeatureCollection }) => (
    <div data-testid="region-layer" data-feature-count={props.data.features.length} />
  ),
  useMap: () => ({ fitBounds: vi.fn() }),
}))

const SAMPLE_COLLECTION: RegionFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: '0f1c1234-5678-90ab-cdef-1234567890ab',
      geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
      properties: {
        slug: 'canteiro-do-ipe',
        name: 'Canteiro do Ipê',
        description: null,
        status: 'active',
        qr_token: 'k3Zq8xR2mNvA',
        photo_count: 0,
        latest_photo_at: null,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: () => Promise.resolve(body) } as Response
}

function renderMapPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <MapPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('MapPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state while the regions are being fetched', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise(() => {})),
    )

    renderMapPage()

    expect(screen.getByRole('status')).toHaveTextContent(/carregando/i)
  })

  it('shows an error state instead of a blank page when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    renderMapPage()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.queryByTestId('map-container')).not.toBeInTheDocument()
  })

  it('shows an empty state when there are no canteiros to display', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ type: 'FeatureCollection', features: [] })),
    )

    renderMapPage()

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/nenhum canteiro/i))
  })

  it('renders the map with the fetched canteiros', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(SAMPLE_COLLECTION)))

    renderMapPage()

    await waitFor(() => expect(screen.getByTestId('map-container')).toBeInTheDocument())
    expect(screen.getByTestId('region-layer')).toHaveAttribute('data-feature-count', '1')
  })

  it('keeps the page heading visible in every state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(SAMPLE_COLLECTION)))

    renderMapPage()

    expect(screen.getByRole('heading', { name: /mapa/i })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('map-container')).toBeInTheDocument())
    expect(screen.getByRole('heading', { name: /mapa/i })).toBeInTheDocument()
  })
})
