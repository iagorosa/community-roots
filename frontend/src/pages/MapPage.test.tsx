import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PlantingFeatureCollection, RegionFeatureCollection } from '../types/api'
import MapPage from './MapPage'

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
  Marker: () => null,
  // `getContainer` backs `PlantingClusterLayer`'s cluster-bubble-labeling
  // `MutationObserver` (see that component's own comment) — a real,
  // detached `<div>` since `MutationObserver.observe` needs an actual DOM
  // node, not just a stub.
  useMap: () => ({ fitBounds: vi.fn(), getContainer: () => document.createElement('div') }),
}))

vi.mock('react-leaflet-cluster', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="planting-layer">{children}</div>,
}))

const SAMPLE_REGIONS: RegionFeatureCollection = {
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
        planting_count: 1,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

const SAMPLE_PLANTINGS: PlantingFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: '1a2b3c4d-5e6f-7890-abcd-ef1234567890',
      geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
      properties: {
        region_id: '0f1c1234-5678-90ab-cdef-1234567890ab',
        species: 'Ipê-amarelo',
        nickname: null,
        planted_by: null,
        planted_at: null,
        status: 'active',
        qr_token: 'tok-planting',
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

function stubFetch(options: { regions: unknown; plantings?: unknown; planting?: unknown }) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.startsWith('/api/plantings/')) return Promise.resolve(jsonResponse(options.planting))
      if (url.startsWith('/api/plantings')) {
        return Promise.resolve(jsonResponse(options.plantings ?? { type: 'FeatureCollection', features: [] }))
      }
      return Promise.resolve(jsonResponse(options.regions))
    }),
  )
}

function renderMapPage(initialEntry = '/mapa') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
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
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

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
    stubFetch({ regions: { type: 'FeatureCollection', features: [] } })

    renderMapPage()

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/nenhum canteiro/i))
  })

  it('renders the region layer and the planting cluster layer with the fetched data', async () => {
    stubFetch({ regions: SAMPLE_REGIONS, plantings: SAMPLE_PLANTINGS })

    renderMapPage()

    await waitFor(() => expect(screen.getByTestId('map-container')).toBeInTheDocument())
    expect(screen.getByTestId('region-layer')).toHaveAttribute('data-feature-count', '1')
    await waitFor(() => expect(screen.getByTestId('planting-layer')).toBeInTheDocument())
  })

  it('opens the planting drawer when ?planting= is present on load', async () => {
    stubFetch({ regions: SAMPLE_REGIONS, plantings: SAMPLE_PLANTINGS, planting: SAMPLE_PLANTINGS.features[0] })

    renderMapPage('/mapa?planting=1a2b3c4d-5e6f-7890-abcd-ef1234567890')

    await waitFor(() => expect(screen.getByText('Ipê-amarelo')).toBeInTheDocument())
  })

  it('renders the region sidebar alongside the map', async () => {
    stubFetch({ regions: SAMPLE_REGIONS, plantings: SAMPLE_PLANTINGS })

    renderMapPage()

    await waitFor(() => expect(screen.getByText('Canteiro do Ipê')).toBeInTheDocument())
  })

  it('keeps the page heading visible in every state', async () => {
    stubFetch({ regions: SAMPLE_REGIONS, plantings: SAMPLE_PLANTINGS })

    renderMapPage()

    expect(screen.getByRole('heading', { name: /mapa/i })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('map-container')).toBeInTheDocument())
    expect(screen.getByRole('heading', { name: /mapa/i })).toBeInTheDocument()
  })
})
