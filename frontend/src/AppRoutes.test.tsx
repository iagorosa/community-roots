import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import AppRoutes from './AppRoutes'

// `AppRoutes` is `App` without the `BrowserRouter` wrapper, so each route
// can be exercised with `MemoryRouter` — see docs/architecture.md §8 for
// the five routes this covers (issue #14's "critério de pronto").
function renderAtPath(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

describe('AppRoutes', () => {
  it('resolves / to the home page', () => {
    renderAtPath('/')

    expect(screen.getByRole('heading', { name: /community roots/i })).toBeInTheDocument()
  })

  it('resolves /mapa to the map page', () => {
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
    renderAtPath('/mapa')

    expect(screen.getByRole('navigation')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /mapa/i })).toBeInTheDocument()
  })
})
