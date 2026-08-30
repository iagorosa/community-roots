import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Photo, PhotoPage } from '../types/api'
import { fetchRegionPhotos } from './photos'

const SAMPLE_PHOTO: Photo = {
  id: '0f1c1234-5678-90ab-cdef-1234567890ab',
  description: 'Primeira muda plantada.',
  contributor_name: 'Ana',
  captured_at: '2026-08-24T14:00:00Z',
  uploaded_at: '2026-08-24T14:05:00Z',
  latitude: -21.8843,
  longitude: -43.3129,
  width: 1080,
  height: 1350,
  photo_url: '/api/photos/0f1c1234-5678-90ab-cdef-1234567890ab/file',
}

const SAMPLE_PAGE: PhotoPage = { items: [SAMPLE_PHOTO], next_cursor: null }

function stubFetchResolving(body: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status < 400,
    status,
    json: () => Promise.resolve(body),
  } as Response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('fetchRegionPhotos', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests GET /api/regions/{identifier}/photos with no query params by default', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PAGE)

    const result = await fetchRegionPhotos('canteiro-do-ipe')

    expect(fetchMock).toHaveBeenCalledWith('/api/regions/canteiro-do-ipe/photos', undefined)
    expect(result).toEqual(SAMPLE_PAGE)
  })

  it('includes cursor and limit as query params when given', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PAGE)

    await fetchRegionPhotos('canteiro-do-ipe', { cursor: 'abc123', limit: 5 })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/regions/canteiro-do-ipe/photos?cursor=abc123&limit=5',
      undefined,
    )
  })

  it('omits a param from the query string when it is not given', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PAGE)

    await fetchRegionPhotos('canteiro-do-ipe', { limit: 5 })

    expect(fetchMock).toHaveBeenCalledWith('/api/regions/canteiro-do-ipe/photos?limit=5', undefined)
  })
})
