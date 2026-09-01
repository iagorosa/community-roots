import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Photo, PhotoPage } from '../types/api'
import { fetchPlantingPhotos, uploadPhoto } from './photos'

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

describe('fetchPlantingPhotos', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests GET /api/plantings/{identifier}/photos with no query params by default', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PAGE)

    const result = await fetchPlantingPhotos('canteiro-do-ipe')

    expect(fetchMock).toHaveBeenCalledWith('/api/plantings/canteiro-do-ipe/photos', undefined)
    expect(result).toEqual(SAMPLE_PAGE)
  })

  it('includes cursor and limit as query params when given', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PAGE)

    await fetchPlantingPhotos('canteiro-do-ipe', { cursor: 'abc123', limit: 5 })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/plantings/canteiro-do-ipe/photos?cursor=abc123&limit=5',
      undefined,
    )
  })

  it('omits a param from the query string when it is not given', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PAGE)

    await fetchPlantingPhotos('canteiro-do-ipe', { limit: 5 })

    expect(fetchMock).toHaveBeenCalledWith('/api/plantings/canteiro-do-ipe/photos?limit=5', undefined)
  })
})

describe('uploadPhoto', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs a FormData body with the file to /api/plantings/{identifier}/photos', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PHOTO, 201)
    const file = new File(['fake-image-bytes'], 'canteiro.jpg', { type: 'image/jpeg' })

    const result = await uploadPhoto('canteiro-do-ipe', { file })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe('/api/plantings/canteiro-do-ipe/photos')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    const body = init.body as FormData
    expect(body.get('file')).toBe(file)
    expect(result).toEqual(SAMPLE_PHOTO)
  })

  it('does not set a Content-Type header, so the browser sets the multipart boundary itself', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PHOTO, 201)
    const file = new File(['fake-image-bytes'], 'canteiro.jpg', { type: 'image/jpeg' })

    await uploadPhoto('canteiro-do-ipe', { file })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.headers).toBeUndefined()
  })

  it('includes description, contributor name, and share_location when given', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PHOTO, 201)
    const file = new File(['fake-image-bytes'], 'canteiro.jpg', { type: 'image/jpeg' })

    await uploadPhoto('canteiro-do-ipe', {
      file,
      description: 'Primeira muda plantada.',
      contributorName: 'Ana',
      shareLocation: true,
    })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const body = init.body as FormData
    expect(body.get('description')).toBe('Primeira muda plantada.')
    expect(body.get('contributor_name')).toBe('Ana')
    expect(body.get('share_location')).toBe('true')
  })

  it('omits description and contributor name, and sends share_location=false, when not given', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PHOTO, 201)
    const file = new File(['fake-image-bytes'], 'canteiro.jpg', { type: 'image/jpeg' })

    await uploadPhoto('canteiro-do-ipe', { file })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const body = init.body as FormData
    expect(body.get('description')).toBeNull()
    expect(body.get('contributor_name')).toBeNull()
    expect(body.get('share_location')).toBe('false')
  })

  // Issue #38 (LGPD): mirrors `share_location`'s own opt-in-by-default test
  // above — both consent fields must default to `false` explicitly, not be
  // omitted, since the backend form fields they map to also default to
  // `False` only when present-but-false, never when the key is missing from
  // a manually-built request.
  it('sends both identifiable-person consent fields as false when not given', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PHOTO, 201)
    const file = new File(['fake-image-bytes'], 'canteiro.jpg', { type: 'image/jpeg' })

    await uploadPhoto('canteiro-do-ipe', { file })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const body = init.body as FormData
    expect(body.get('includes_identifiable_person')).toBe('false')
    expect(body.get('identifiable_person_consent_confirmed')).toBe('false')
  })

  it('sends both identifiable-person consent fields as true when both are given', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_PHOTO, 201)
    const file = new File(['fake-image-bytes'], 'canteiro.jpg', { type: 'image/jpeg' })

    await uploadPhoto('canteiro-do-ipe', {
      file,
      includesIdentifiablePerson: true,
      identifiablePersonConsentConfirmed: true,
    })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const body = init.body as FormData
    expect(body.get('includes_identifiable_person')).toBe('true')
    expect(body.get('identifiable_person_consent_confirmed')).toBe('true')
  })
})
