import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, ApiError } from './apiClient'

function jsonResponse(body: unknown, status: number): Response {
  return { ok: false, status, json: () => Promise.resolve(body) } as Response
}

describe('apiFetch', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses the backend detail/code as the ApiError message/code when the error body is valid JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'O arquivo excede o limite de 10 MB.', code: 'image_too_large' }, 422)),
    )

    await expect(apiFetch('/api/regions/x/photos')).rejects.toMatchObject({
      message: 'O arquivo excede o limite de 10 MB.',
      status: 422,
      code: 'image_too_large',
    })
  })

  it('falls back to a generic message that still says what to do next when the error body is not valid JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.reject(new SyntaxError('Unexpected token < in JSON')),
      } as Response),
    )

    await expect(apiFetch('/api/regions/x/photos')).rejects.toMatchObject({
      message: 'O servidor respondeu com erro (500). Tente novamente mais tarde.',
      status: 500,
    })
  })

  it('falls back to a generic message that still says what to do next when the error body is JSON but has no detail field', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ some: 'other shape' }, 400)))

    await expect(apiFetch('/api/regions/x/photos')).rejects.toMatchObject({
      message: 'O servidor respondeu com erro (400). Tente novamente mais tarde.',
      status: 400,
    })
  })

  it('reports a network failure with a message that says what to do next', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(apiFetch('/api/regions/x/photos')).rejects.toMatchObject({
      message: 'Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.',
    })
  })

  it('rejects with an instance of ApiError in every failure mode', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(apiFetch('/api/regions/x/photos')).rejects.toBeInstanceOf(ApiError)
  })
})
