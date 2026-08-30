import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { RegionFeature } from '../types/api'
import RegionPage from './RegionPage'

// Same shallow react-leaflet fake `MapPage.test.tsx` uses (docs/architecture.md
// §10): `RegionPage` renders `PlantingMap` on success, and real Leaflet
// needs layout/canvas APIs jsdom doesn't provide.
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
    photo_count: 3,
    latest_photo_at: null,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
}

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response
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
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise(() => {})),
    )

    renderRegionPage()

    expect(screen.getByRole('status')).toHaveTextContent(/carregando/i)
  })

  it('shows the name, description, and photo count on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(SAMPLE_FEATURE)))

    renderRegionPage()

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
    expect(screen.getByText('Um canteiro cheio de ipês amarelos.')).toBeInTheDocument()
    expect(screen.getByText('3 fotos')).toBeInTheDocument()
  })

  it('omits the description paragraph when the API returns a null description', async () => {
    const featureWithoutDescription: RegionFeature = {
      ...SAMPLE_FEATURE,
      properties: { ...SAMPLE_FEATURE.properties, description: null },
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(featureWithoutDescription)))

    renderRegionPage()

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
    expect(screen.queryByTestId('region-description')).not.toBeInTheDocument()
  })

  it('uses the singular "1 foto" when the photo count is exactly one', async () => {
    const featureWithOnePhoto: RegionFeature = {
      ...SAMPLE_FEATURE,
      properties: { ...SAMPLE_FEATURE.properties, photo_count: 1 },
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(featureWithOnePhoto)))

    renderRegionPage()

    await waitFor(() => expect(screen.getByText('1 foto')).toBeInTheDocument())
    expect(screen.queryByText('1 fotos')).not.toBeInTheDocument()
  })

  it('renders the mini-map centered on the canteiro', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(SAMPLE_FEATURE)))

    renderRegionPage()

    await waitFor(() => expect(screen.getByTestId('map-container')).toBeInTheDocument())
    const props = JSON.parse(screen.getByTestId('map-container').dataset.props ?? '{}')
    expect(props.center[0]).toBeCloseTo(-21.8843)
    expect(props.center[1]).toBeCloseTo(-43.3129)
  })

  it('shows a disabled photo-upload button with a plain-language explanation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(SAMPLE_FEATURE)))

    renderRegionPage()

    const button = await screen.findByRole('button', { name: /enviar foto/i })
    expect(button).toBeDisabled()
    expect(screen.getByText(/em breve você vai poder enviar fotos/i)).toBeInTheDocument()
  })

  it('renders NotFoundPage, not a generic error, when the region does not exist', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: 'Nenhum canteiro encontrado para "inexistente".', code: 'region_not_found' }, 404),
      ),
    )

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
})
