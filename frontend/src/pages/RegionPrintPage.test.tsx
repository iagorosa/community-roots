import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PlantingFeatureCollection, RegionFeature } from '../types/api'
import RegionPrintPage from './RegionPrintPage'

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
    planting_count: 2,
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
        qr_token: 'tok-planting-1',
        photo_count: 2,
        latest_photo_at: null,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
    {
      type: 'Feature',
      id: '2b3c4d5e-6f78-90ab-cdef-1234567890ab',
      geometry: { type: 'Point', coordinates: [-43.313, -21.8844] },
      properties: {
        region_id: '0f1c1234-5678-90ab-cdef-1234567890ab',
        species: 'Jacarandá',
        nickname: null,
        planted_by: null,
        planted_at: null,
        status: 'active',
        qr_token: 'tok-planting-2',
        photo_count: 0,
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

function renderRegionPrintPage(slug = 'canteiro-do-ipe') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/regions/${slug}/print`]}>
        <Routes>
          <Route path="/regions/:slug/print" element={<RegionPrintPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RegionPrintPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state while the region is being fetched', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    renderRegionPrintPage()

    expect(screen.getByRole('status')).toHaveTextContent(/carregando/i)
  })

  it('renders NotFoundPage, not a generic error, when the region does not exist', async () => {
    stubFetch({
      region: {
        body: { detail: 'Nenhum canteiro encontrado para "inexistente".', code: 'region_not_found' },
        status: 404,
      },
    })

    renderRegionPrintPage('inexistente')

    await waitFor(() => expect(screen.getByRole('heading', { name: /página não encontrada/i })).toBeInTheDocument())
  })

  it('shows a generic error state for a non-404 failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    renderRegionPrintPage()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })

  it('renders the region name and a print button', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE }, plantings: { body: SAMPLE_PLANTINGS } })

    renderRegionPrintPage()

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /imprimir/i })).toBeInTheDocument()
  })

  it('calls window.print when the print button is clicked', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE }, plantings: { body: SAMPLE_PLANTINGS } })
    const printSpy = vi.fn()
    vi.stubGlobal('print', printSpy)

    renderRegionPrintPage()

    const button = await screen.findByRole('button', { name: /imprimir/i })
    button.click()

    expect(printSpy).toHaveBeenCalledTimes(1)
  })

  it("renders the region's own QR code as an entrance-sign card", async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE }, plantings: { body: SAMPLE_PLANTINGS } })

    renderRegionPrintPage()

    const image = await screen.findByRole('img', { name: /qr code.*canteiro do ipê/i })
    expect(image).toHaveAttribute('src', '/api/regions/canteiro-do-ipe/qr-code')
  })

  it('renders one card per active planting, with its QR code and nickname', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE }, plantings: { body: SAMPLE_PLANTINGS } })

    renderRegionPrintPage()

    const image = await screen.findByRole('img', { name: /qr code.*a árvore da ana/i })
    expect(image).toHaveAttribute('src', '/api/plantings/1a2b3c4d-5e6f-7890-abcd-ef1234567890/qr-code')
    expect(screen.getByText('A árvore da Ana')).toBeInTheDocument()
  })

  it('falls back to the species name when a planting has no nickname', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE }, plantings: { body: SAMPLE_PLANTINGS } })

    renderRegionPrintPage()

    await screen.findByText('Jacarandá')
    expect(screen.getByRole('img', { name: /qr code.*jacarandá/i })).toHaveAttribute(
      'src',
      '/api/plantings/2b3c4d5e-6f78-90ab-cdef-1234567890ab/qr-code',
    )
  })

  it('shows an empty state when the region has no active plantings', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE }, plantings: { body: { type: 'FeatureCollection', features: [] } } })

    renderRegionPrintPage()

    expect(await screen.findByText(/ainda não tem muda/i)).toBeInTheDocument()
  })

  it('shows an error state when the plantings request fails independently of the region', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.startsWith('/api/plantings')) {
        return Promise.reject(new TypeError('Failed to fetch'))
      }
      return Promise.resolve(jsonResponse(SAMPLE_FEATURE))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderRegionPrintPage()

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/não foi possível carregar as mudas/i))
  })
})
