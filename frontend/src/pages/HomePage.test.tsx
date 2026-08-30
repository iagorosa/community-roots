import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import HomePage from './HomePage'

// Smoke test: mocks `fetch` directly (rather than pulling in MSW) since
// this HomePage is provisional and a single request — see issue #7.
describe('HomePage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the loading state and then the backend health status on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ status: 'ok', database: 'ok' }),
      } as Response),
    )

    render(<HomePage />)

    expect(screen.getByText(/verificando status do servidor/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText(/status do servidor/i)).toBeInTheDocument()
    })

    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('ok')
    expect(status).toHaveTextContent('banco de dados')
  })

  it('shows a readable error message when the request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: () => Promise.resolve({}),
      } as Response),
    )

    render(<HomePage />)

    await waitFor(() => {
      expect(screen.getByText(/não foi possível carregar o status do servidor/i)).toBeInTheDocument()
    })
  })
})
