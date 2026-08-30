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
  photo_count: 3,
  latest_photo_at: null,
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
}

describe('RegionPopup', () => {
  it('shows the region name', () => {
    render(<RegionPopup properties={PROPERTIES} />)

    expect(screen.getByText('Canteiro do Ipê')).toBeInTheDocument()
  })

  it('shows the photo count, pluralized', () => {
    render(<RegionPopup properties={PROPERTIES} />)

    expect(screen.getByText('3 fotos')).toBeInTheDocument()
  })

  it('shows "1 foto" in the singular for exactly one photo', () => {
    render(<RegionPopup properties={{ ...PROPERTIES, photo_count: 1 }} />)

    expect(screen.getByText('1 foto')).toBeInTheDocument()
  })

  it('links to the region page', () => {
    render(<RegionPopup properties={PROPERTIES} />)

    expect(screen.getByRole('link', { name: /ver canteiro/i })).toHaveAttribute(
      'href',
      '/regions/canteiro-do-ipe',
    )
  })
})
