import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PhotoPage, PlantingFeature } from '../../types/api'
import PlantingDetailPanel from './PlantingDetailPanel.tsx'

const SAMPLE_PLANTING: PlantingFeature = {
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
    qr_token: 'k3Zq8xR2mNvA',
    photo_count: 0,
    latest_photo_at: null,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
}

const EMPTY_PHOTO_PAGE: PhotoPage = { items: [], next_cursor: null }

function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: () => Promise.resolve(body) } as Response
}

function stubFetch(planting: unknown, photos: unknown = EMPTY_PHOTO_PAGE) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => Promise.resolve(jsonResponse(url.includes('/photos') ? photos : planting))),
  )
}

function renderPanel(plantingId = SAMPLE_PLANTING.id) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <PlantingDetailPanel plantingId={plantingId} />
    </QueryClientProvider>,
  )
}

describe('PlantingDetailPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the nickname as the title, and the species below it', async () => {
    stubFetch(SAMPLE_PLANTING)

    renderPanel()

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'A árvore da Ana' })).toBeInTheDocument(),
    )
    expect(screen.getByText('Ipê-amarelo')).toBeInTheDocument()
  })

  it('falls back to species as the title when there is no nickname', async () => {
    stubFetch({ ...SAMPLE_PLANTING, properties: { ...SAMPLE_PLANTING.properties, nickname: null } })

    renderPanel()

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Ipê-amarelo' })).toBeInTheDocument(),
    )
  })

  it('shows who planted it, when known', async () => {
    stubFetch(SAMPLE_PLANTING)

    renderPanel()

    await waitFor(() => expect(screen.getByText('Plantada por Ana')).toBeInTheDocument())
  })

  it('renders the photo upload form scoped to this planting', async () => {
    stubFetch(SAMPLE_PLANTING)

    renderPanel()

    expect(await screen.findByRole('button', { name: /enviar foto/i })).toBeDisabled()
  })

  it('shows an empty state for the photo timeline when there are no photos', async () => {
    stubFetch(SAMPLE_PLANTING, EMPTY_PHOTO_PAGE)

    renderPanel()

    expect(await screen.findByText(/ainda não tem foto/i)).toBeInTheDocument()
  })
})
