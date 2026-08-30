import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Photo, PhotoPage, RegionFeature } from '../types/api'
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

const SAMPLE_PHOTO: Photo = {
  id: '1a2b3c4d-5e6f-7890-abcd-ef1234567890',
  description: 'Primeira muda plantada.',
  contributor_name: 'Ana',
  captured_at: '2026-08-24T14:00:00Z',
  uploaded_at: '2026-08-24T14:05:00Z',
  latitude: -21.8843,
  longitude: -43.3129,
  width: 1080,
  height: 1350,
  photo_url: '/api/photos/1a2b3c4d-5e6f-7890-abcd-ef1234567890/file',
}

const EMPTY_PHOTO_PAGE: PhotoPage = { items: [], next_cursor: null }

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response
}

// `RegionPage` fetches both the region (`GET /api/regions/{slug}`) and its
// photos (`GET /api/regions/{slug}/photos`) — this routes a single `fetch`
// mock to the right canned response for each, by URL, instead of every
// test needing to know both endpoints exist. Defaults the photos response
// to an empty page so tests that only care about the region don't have to
// think about photos at all.
function stubFetch(options: {
  region: { body: unknown; status?: number }
  photos?: { body: unknown; status?: number }
}) {
  const fetchMock = vi.fn((url: string) => {
    if (url.includes('/photos')) {
      const photos = options.photos ?? { body: EMPTY_PHOTO_PAGE }
      return Promise.resolve(jsonResponse(photos.body, photos.status))
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
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise(() => {})),
    )

    renderRegionPage()

    expect(screen.getByRole('status')).toHaveTextContent(/carregando/i)
  })

  it('shows the name, description, and photo count on success', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE } })

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
    stubFetch({ region: { body: featureWithoutDescription } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
    expect(screen.queryByTestId('region-description')).not.toBeInTheDocument()
  })

  it('uses the singular "1 foto" when the photo count is exactly one', async () => {
    const featureWithOnePhoto: RegionFeature = {
      ...SAMPLE_FEATURE,
      properties: { ...SAMPLE_FEATURE.properties, photo_count: 1 },
    }
    stubFetch({ region: { body: featureWithOnePhoto } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByText('1 foto')).toBeInTheDocument())
    expect(screen.queryByText('1 fotos')).not.toBeInTheDocument()
  })

  it('renders the mini-map centered on the canteiro', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByTestId('map-container')).toBeInTheDocument())
    const props = JSON.parse(screen.getByTestId('map-container').dataset.props ?? '{}')
    expect(props.center[0]).toBeCloseTo(-21.8843)
    expect(props.center[1]).toBeCloseTo(-43.3129)
  })

  it('renders the photo upload form, with submit disabled until a file is chosen', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE } })

    renderRegionPage()

    const button = await screen.findByRole('button', { name: /enviar foto/i })
    expect(button).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: /compartilhar/i })).not.toBeChecked()
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

  describe('photo timeline', () => {
    it('shows an empty state explaining how to contribute when the canteiro has no photos', async () => {
      stubFetch({ region: { body: SAMPLE_FEATURE }, photos: { body: EMPTY_PHOTO_PAGE } })

      renderRegionPage()

      await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
      expect(await screen.findByText(/ainda não tem foto/i)).toBeInTheDocument()
    })

    it('renders a PhotoCard for each photo once photos load', async () => {
      const photoPage: PhotoPage = { items: [SAMPLE_PHOTO], next_cursor: null }
      stubFetch({ region: { body: SAMPLE_FEATURE }, photos: { body: photoPage } })

      renderRegionPage()

      const image = await screen.findByRole('img')
      expect(image).toHaveAttribute('src', SAMPLE_PHOTO.photo_url)
      expect(image).toHaveAttribute('width', '1080')
      expect(image).toHaveAttribute('height', '1350')
      expect(screen.getByText('Ana')).toBeInTheDocument()
      expect(screen.getByText('Primeira muda plantada.')).toBeInTheDocument()
    })

    it('shows a scoped error state for the photo section when photos fail to load, without hiding the rest of the page', async () => {
      stubFetch({
        region: { body: SAMPLE_FEATURE },
        photos: { body: { detail: 'erro' }, status: 500 },
      })

      renderRegionPage()

      await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
      expect(await screen.findByText(/não foi possível carregar as fotos/i)).toBeInTheDocument()
    })
  })
})
