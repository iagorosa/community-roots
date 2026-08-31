import { afterEach, describe, expect, it, vi } from 'vitest'
import type { RegionFeature, RegionFeatureCollection } from '../types/api'
import { fetchRegion, fetchRegions } from './regions'

const SAMPLE_FEATURE: RegionFeature = {
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

const SAMPLE_COLLECTION: RegionFeatureCollection = {
  type: 'FeatureCollection',
  features: [SAMPLE_FEATURE],
}

describe('fetchRegions', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests GET /api/regions and returns the typed feature collection', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SAMPLE_COLLECTION),
    } as Response)
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchRegions()

    expect(fetchMock).toHaveBeenCalledWith('/api/regions', undefined)
    expect(result).toEqual(SAMPLE_COLLECTION)
  })
})

describe('fetchRegion', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests GET /api/regions/{identifier} and returns the typed feature', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SAMPLE_FEATURE),
    } as Response)
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchRegion('canteiro-do-ipe')

    expect(fetchMock).toHaveBeenCalledWith('/api/regions/canteiro-do-ipe', undefined)
    expect(result).toEqual(SAMPLE_FEATURE)
  })
})
