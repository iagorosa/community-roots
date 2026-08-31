import { afterEach, describe, expect, it, vi } from 'vitest'
import type { QrResolution } from '../types/api'
import { resolveQrToken } from './qr'

describe('resolveQrToken', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests GET /api/qr/{token} and returns the typed resolution', async () => {
    const resolution: QrResolution = { type: 'planting', identifier: '1a2b3c4d-5e6f-7890-abcd-ef1234567890' }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(resolution) } as Response)
    vi.stubGlobal('fetch', fetchMock)

    const result = await resolveQrToken('k3Zq8xR2mNvA')

    expect(fetchMock).toHaveBeenCalledWith('/api/qr/k3Zq8xR2mNvA', undefined)
    expect(result).toEqual(resolution)
  })
})
