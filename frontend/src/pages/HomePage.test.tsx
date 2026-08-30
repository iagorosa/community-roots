import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import HomePage from './HomePage'

// Words the reader (child or parent, per docs/architecture.md §8's
// vocabulary rule) must never see, however the copy gets rewritten.
const FORBIDDEN_JARGON = [/região/i, /regiões/i, /polígono/i, /geojson/i, /\btoken\b/i]

function renderHomePage() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  )
}

describe('HomePage', () => {
  it('shows the project name as the main heading', () => {
    renderHomePage()

    expect(screen.getByRole('heading', { level: 1, name: /community roots/i })).toBeInTheDocument()
  })

  it('explains what the project is and its environmental purpose', () => {
    const { container } = renderHomePage()

    expect(container.textContent).toMatch(/plant|verde|natureza|meio ambiente/i)
  })

  it('explains how to participate by mentioning canteiros', () => {
    const { container } = renderHomePage()

    expect(container.textContent).toMatch(/canteiro/i)
  })

  it('has an accessible call-to-action link to the map', () => {
    // `HomePage` renders standalone here, without `Header` (see
    // `renderHomePage`), so the CTA is the only link matching /mapa/i.
    renderHomePage()

    expect(screen.getByRole('link', { name: /mapa/i })).toHaveAttribute('href', '/mapa')
  })

  it('never shows technical jargon to the user', () => {
    const { container } = renderHomePage()

    for (const pattern of FORBIDDEN_JARGON) {
      expect(container.textContent).not.toMatch(pattern)
    }
  })
})
