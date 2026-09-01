import { render, screen } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { RegionFeatureCollection } from '../../types/api'
import RegionSidebar from './RegionSidebar.tsx'

const REGIONS: RegionFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: 'r1',
      geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
      properties: {
        slug: 'canteiro-do-ipe',
        name: 'Canteiro do Ipê',
        description: null,
        status: 'active',
        qr_token: 'tok-1',
        planting_count: 12,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
    {
      type: 'Feature',
      id: 'r2',
      geometry: { type: 'Point', coordinates: [-43.32, -21.9] },
      properties: {
        slug: 'canteiro-do-jacaranda',
        name: 'Canteiro do Jacarandá',
        description: null,
        status: 'active',
        qr_token: 'tok-2',
        planting_count: 5,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

function renderSidebar() {
  return render(
    <MemoryRouter>
      <RegionSidebar regions={REGIONS} />
    </MemoryRouter>,
  )
}

describe('RegionSidebar', () => {
  it('lists every region with its planting count', () => {
    renderSidebar()

    expect(screen.getByText('Canteiro do Ipê')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('Canteiro do Jacarandá')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('links each region to its overview page', () => {
    renderSidebar()

    expect(screen.getByRole('link', { name: /canteiro do ipê/i })).toHaveAttribute(
      'href',
      '/regions/canteiro-do-ipe',
    )
  })

  it('filters the list as the user types in the search field', () => {
    renderSidebar()

    fireEvent.change(screen.getByRole('searchbox', { name: /buscar região/i }), {
      target: { value: 'jacar' },
    })

    expect(screen.queryByText('Canteiro do Ipê')).not.toBeInTheDocument()
    expect(screen.getByText('Canteiro do Jacarandá')).toBeInTheDocument()
  })

  it('collapses and re-expands on toggle', () => {
    renderSidebar()

    fireEvent.click(screen.getByRole('button', { name: /esconder lista de regiões/i }))
    expect(screen.queryByText('Canteiro do Ipê')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /mostrar lista de regiões/i }))
    expect(screen.getByText('Canteiro do Ipê')).toBeInTheDocument()
  })
})
