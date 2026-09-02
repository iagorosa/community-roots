import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PlantingFeatureCollection, RegionFeature } from '../types/api'
import RegionPage from './RegionPage'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children, ...props }: Record<string, unknown> & { children?: ReactNode }) => (
    <div data-testid="map-container" data-props={JSON.stringify(props)}>
      {children}
    </div>
  ),
  TileLayer: () => null,
  useMap: () => ({ fitBounds: vi.fn() }),
}))

const SAMPLE_FEATURE: RegionFeature = {
  type: 'Feature',
  id: '0f1c1234-5678-90ab-cdef-1234567890ab',
  geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
  properties: {
    slug: 'canteiro-do-ipe',
    name: 'Canteiro do Ipê',
    description: 'Um canteiro cheio de ipês amarelos.',
    status: 'active',
    qr_token: 'k3Zq8xR2mNvA',
    planting_count: 1,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
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
        nickname: 'A árvore da Ana',
        planted_by: 'Ana',
        planted_at: '2026-08-01T10:00:00Z',
        status: 'active',
        qr_token: 'tok-planting',
        photo_count: 2,
        latest_photo_at: null,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response
}

function stubFetch(options: { region: { body: unknown; status?: number }; plantings?: { body: unknown } }) {
  const fetchMock = vi.fn((url: string) => {
    if (url.startsWith('/api/plantings')) {
      const plantings = options.plantings ?? { body: { type: 'FeatureCollection', features: [] } }
      return Promise.resolve(jsonResponse(plantings.body))
    }
    return Promise.resolve(jsonResponse(options.region.body, options.region.status))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderRegionPage(slug = 'canteiro-do-ipe') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/regions/${slug}`]}>
        <Routes>
          <Route path="/regions/:slug" element={<RegionPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RegionPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state while the region is being fetched', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    renderRegionPage()

    expect(screen.getByRole('status')).toHaveTextContent(/carregando/i)
  })

  it('shows the name, description, and planting count on success', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
    expect(screen.getByText('Um canteiro cheio de ipês amarelos.')).toBeInTheDocument()
    expect(screen.getByText('1 muda')).toBeInTheDocument()
  })

  it('omits the description paragraph when the API returns a null description', async () => {
    const featureWithoutDescription: RegionFeature = {
      ...SAMPLE_FEATURE,
      properties: { ...SAMPLE_FEATURE.properties, description: null },
    }
    stubFetch({ region: { body: featureWithoutDescription } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
    expect(screen.queryByTestId('region-description')).not.toBeInTheDocument()
  })

  it('uses the plural "mudas" when the planting count is not exactly one', async () => {
    const featureWithManyPlantings: RegionFeature = {
      ...SAMPLE_FEATURE,
      properties: { ...SAMPLE_FEATURE.properties, planting_count: 4 },
    }
    stubFetch({ region: { body: featureWithManyPlantings } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByText('4 mudas')).toBeInTheDocument())
  })

  it('renders the mini-map centered on the region', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByTestId('map-container')).toBeInTheDocument())
    const props = JSON.parse(screen.getByTestId('map-container').dataset.props ?? '{}')
    expect(props.center[0]).toBeCloseTo(-21.8843)
    expect(props.center[1]).toBeCloseTo(-43.3129)
  })

  it('links to the region\'s QR code image', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE } })

    renderRegionPage()

    const link = await screen.findByRole('link', { name: /baixar qr code da região/i })
    expect(link).toHaveAttribute('href', '/api/regions/canteiro-do-ipe/qr-code')
  })

  it('links to the printable QR sheet page (issue #135)', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE } })

    renderRegionPage()

    const link = await screen.findByRole('link', { name: /folha.*imprimir|imprimir.*folha/i })
    expect(link).toHaveAttribute('href', '/regions/canteiro-do-ipe/print')
  })

  it('renders NotFoundPage, not a generic error, when the region does not exist', async () => {
    stubFetch({
      region: {
        body: { detail: 'Nenhum canteiro encontrado para "inexistente".', code: 'region_not_found' },
        status: 404,
      },
    })

    renderRegionPage('inexistente')

    await waitFor(() => expect(screen.getByRole('heading', { name: /página não encontrada/i })).toBeInTheDocument())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a generic error state for a non-404 failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    renderRegionPage()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.queryByRole('heading', { name: /página não encontrada/i })).not.toBeInTheDocument()
  })

  describe('planting list', () => {
    it('shows an empty state when the region has no plantings yet', async () => {
      stubFetch({ region: { body: SAMPLE_FEATURE }, plantings: { body: { type: 'FeatureCollection', features: [] } } })

      renderRegionPage()

      await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
      expect(await screen.findByText(/ainda não tem muda/i)).toBeInTheDocument()
    })

    it('lists each planting, linking to its pin on the map', async () => {
      stubFetch({ region: { body: SAMPLE_FEATURE }, plantings: { body: SAMPLE_PLANTINGS } })

      renderRegionPage()

      const link = await screen.findByRole('link', { name: /a árvore da ana/i })
      expect(link).toHaveAttribute('href', '/mapa?planting=1a2b3c4d-5e6f-7890-abcd-ef1234567890')
    })
  })
})
