import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AppRoutes from './AppRoutes'
import type { RegionFeature } from './types/api'

// `AppRoutes` is `App` without the `BrowserRouter`/`QueryClientProvider`
// wrappers, so each route can be exercised with `MemoryRouter` and a
// throwaway `QueryClient` — see docs/architecture.md §8 for the five
// routes this covers (issue #14's "critério de pronto"). `/mapa` and
// `/regions/:slug` both fetch data (`useRegions`/`useRegion`), hence both
// wrappers and the `fetch` stub below.
//
// react-leaflet is faked the same shallow way `RegionPage.test.tsx` does
// (docs/architecture.md §10): a successful `/regions/:slug` render reaches
// `RegionPage`'s mini-map (`PlantingMap`), and real Leaflet needs
// layout/canvas APIs jsdom doesn't provide.
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children, ...props }: Record<string, unknown> & { children?: ReactNode }) => (
    <div data-testid="map-container" data-props={JSON.stringify(props)}>
      {children}
    </div>
  ),
  TileLayer: () => null,
  GeoJSON: () => null,
  useMap: () => ({ fitBounds: vi.fn() }),
}))

const SAMPLE_REGION: RegionFeature = {
  type: 'Feature',
  id: '0f1c1234-5678-90ab-cdef-1234567890ab',
  geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
  properties: {
    slug: 'canteiro-do-ipe',
    name: 'Canteiro do Ipê',
    description: null,
    status: 'active',
    qr_token: 'k3Zq8xR2mNvA',
    planting_count: 0,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
}

function renderAtPath(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AppRoutes', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('resolves / to the home page', () => {
    renderAtPath('/')

    expect(screen.getByRole('heading', { name: /community roots/i })).toBeInTheDocument()
  })

  it('resolves /mapa to the map page', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ type: 'FeatureCollection', features: [] }),
      } as Response),
    )

    renderAtPath('/mapa')

    expect(screen.getByRole('heading', { name: /mapa/i })).toBeInTheDocument()
  })

  it('resolves /regions/:slug to the region page with the region matching the slug from the URL', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        const body = url.startsWith('/api/plantings')
          ? { type: 'FeatureCollection', features: [] }
          : SAMPLE_REGION
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response)
      }),
    )

    renderAtPath('/regions/canteiro-do-ipe')

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
  })

  it('resolves /r/:qrToken to a region page after the token resolves', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        let body: unknown
        if (url.startsWith('/api/qr/')) {
          body = { type: 'region', identifier: 'canteiro-do-ipe' }
        } else if (url.startsWith('/api/plantings')) {
          body = { type: 'FeatureCollection', features: [] }
        } else {
          body = SAMPLE_REGION
        }
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response)
      }),
    )

    renderAtPath('/r/k3Zq8xR2mNvA')

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
  })

  it('resolves an unknown path to the not-found page', () => {
    renderAtPath('/isso-nao-existe')

    expect(screen.getByRole('heading', { name: /não encontrada/i })).toBeInTheDocument()
  })

  it('renders the header navigation alongside a page', () => {
    renderAtPath('/isso-nao-existe')

    expect(screen.getByRole('navigation')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /mapa/i })).toBeInTheDocument()
  })
})
