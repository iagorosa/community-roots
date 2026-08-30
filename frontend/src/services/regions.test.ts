import { afterEach, describe, expect, it, vi } from 'vitest'
import type { RegionFeatureCollection } from '../types/api'
import { fetchRegions } from './regions'

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
