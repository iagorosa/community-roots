import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PlantingFeature, PlantingFeatureCollection } from '../types/api'
import { fetchPlanting, fetchPlantings } from './plantings'

const SAMPLE_FEATURE: PlantingFeature = {
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

const SAMPLE_COLLECTION: PlantingFeatureCollection = { type: 'FeatureCollection', features: [SAMPLE_FEATURE] }

function stubFetchResolving(body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('fetchPlantings', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests GET /api/plantings with no query params by default', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_COLLECTION)

    const result = await fetchPlantings()

    expect(fetchMock).toHaveBeenCalledWith('/api/plantings', undefined)
    expect(result).toEqual(SAMPLE_COLLECTION)
  })

  it('includes region_id as a query param when given', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_COLLECTION)

    await fetchPlantings({ regionId: '0f1c1234-5678-90ab-cdef-1234567890ab' })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/plantings?region_id=0f1c1234-5678-90ab-cdef-1234567890ab',
      undefined,
    )
  })
})

describe('fetchPlanting', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests GET /api/plantings/{id} and returns the typed feature', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_FEATURE)

    const result = await fetchPlanting('1a2b3c4d-5e6f-7890-abcd-ef1234567890')

    expect(fetchMock).toHaveBeenCalledWith('/api/plantings/1a2b3c4d-5e6f-7890-abcd-ef1234567890', undefined)
    expect(result).toEqual(SAMPLE_FEATURE)
  })
})
