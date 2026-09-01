import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import QrRedirectPage from './QrRedirectPage'

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response
}

function renderAtToken(token: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/r/${token}`]}>
        <Routes>
          <Route path="/r/:qrToken" element={<QrRedirectPage />} />
          <Route path="/regions/:slug" element={<div>Página da região {`{slug}`}</div>} />
          <Route path="/mapa" element={<div data-testid="mapa-page">Mapa</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('QrRedirectPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state while the token is being resolved', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    renderAtToken('k3Zq8xR2mNvA')

    expect(screen.getByRole('status')).toHaveTextContent(/carregando/i)
  })

  it('navigates to /regions/:slug for a region token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ type: 'region', identifier: 'canteiro-do-ipe' })),
    )

    renderAtToken('k3Zq8xR2mNvA')

    await waitFor(() => expect(screen.getByText('Página da região {slug}')).toBeInTheDocument())
  })

  it('navigates to /mapa?planting=<id> for a planting token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ type: 'planting', identifier: '1a2b3c4d-5e6f-7890-abcd-ef1234567890' }),
      ),
    )

    renderAtToken('tok-planting')

    await waitFor(() => expect(screen.getByTestId('mapa-page')).toBeInTheDocument())
  })

  it('shows an error state, not a navigation, for an unknown token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Nenhum QR code encontrado.', code: 'qr_token_not_found' }, 404)),
    )

    renderAtToken('nao-existe')

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
