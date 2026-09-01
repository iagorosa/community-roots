import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { RegionProperties } from '../../types/api'
import RegionPopup from './RegionPopup.tsx'

const PROPERTIES: RegionProperties = {
  slug: 'canteiro-do-ipe',
  name: 'Canteiro do Ipê',
  description: null,
  status: 'active',
  qr_token: 'k3Zq8xR2mNvA',
  planting_count: 3,
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
}

describe('RegionPopup', () => {
  it('shows the region name', () => {
    render(<RegionPopup properties={PROPERTIES} />)

    expect(screen.getByText('Canteiro do Ipê')).toBeInTheDocument()
  })

  it('shows the planting count, pluralized', () => {
    render(<RegionPopup properties={PROPERTIES} />)

    expect(screen.getByText('3 mudas')).toBeInTheDocument()
  })

  it('shows "1 muda" in the singular for exactly one planting', () => {
    render(<RegionPopup properties={{ ...PROPERTIES, planting_count: 1 }} />)

    expect(screen.getByText('1 muda')).toBeInTheDocument()
  })

  it('links to the region page', () => {
    render(<RegionPopup properties={PROPERTIES} />)

    expect(screen.getByRole('link', { name: /ver canteiro/i })).toHaveAttribute(
      'href',
      '/regions/canteiro-do-ipe',
    )
  })
})
