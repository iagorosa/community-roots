import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AppRoutes from './AppRoutes'

// `AppRoutes` is `App` without the `BrowserRouter`/`QueryClientProvider`
// wrappers, so each route can be exercised with `MemoryRouter` and a
// throwaway `QueryClient` — see docs/architecture.md §8 for the five
// routes this covers (issue #14's "critério de pronto"). `/mapa` renders
// `MapPage`, which calls `useRegions` (issue #17), hence both wrappers and
// the `fetch` stub below.
function renderAtPath(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AppRoutes', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('resolves / to the home page', () => {
    renderAtPath('/')

    expect(screen.getByRole('heading', { name: /community roots/i })).toBeInTheDocument()
  })

  it('resolves /mapa to the map page', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ type: 'FeatureCollection', features: [] }),
      } as Response),
    )

    renderAtPath('/mapa')

    expect(screen.getByRole('heading', { name: /mapa/i })).toBeInTheDocument()
  })

  it('resolves /regions/:slug to the region page with the slug from the URL', () => {
    renderAtPath('/regions/canteiro-do-ipe')

    expect(screen.getByText('canteiro-do-ipe')).toBeInTheDocument()
  })

  it('resolves /r/:qrToken to the QR redirect page with the token from the URL', () => {
    renderAtPath('/r/k3Zq8xR2mNvA')

    expect(screen.getByText('k3Zq8xR2mNvA')).toBeInTheDocument()
  })

  it('resolves an unknown path to the not-found page', () => {
    renderAtPath('/isso-nao-existe')

    expect(screen.getByRole('heading', { name: /não encontrada/i })).toBeInTheDocument()
  })

  it('renders the header navigation alongside a page', () => {
    renderAtPath('/regions/canteiro-do-ipe')

    expect(screen.getByRole('navigation')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /mapa/i })).toBeInTheDocument()
  })
})
