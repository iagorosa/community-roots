import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Photo } from '../../types/api'
import PhotoTimeline from './PhotoTimeline.tsx'

function makePhoto(overrides: Partial<Photo>): Photo {
  return {
    id: crypto.randomUUID(),
    description: null,
    contributor_name: null,
    captured_at: null,
    uploaded_at: '2026-08-24T12:00:00Z',
    latitude: null,
    longitude: null,
    width: 800,
    height: 600,
    photo_url: '/api/photos/x/file',
    ...overrides,
  }
}

describe('PhotoTimeline', () => {
  it('renders a date heading per group and a PhotoCard per photo within it', () => {
    const photos = [
      makePhoto({ id: 'a', uploaded_at: '2026-08-23T10:00:00Z', description: 'Foto de ontem' }),
      makePhoto({ id: 'b', uploaded_at: '2026-08-24T09:00:00Z', description: 'Foto de hoje cedo' }),
      makePhoto({ id: 'c', uploaded_at: '2026-08-24T15:00:00Z', description: 'Foto de hoje à tarde' }),
    ]

    render(<PhotoTimeline photos={photos} />)

    const headings = screen.getAllByRole('heading', { level: 3 })
    expect(headings).toHaveLength(2)
    expect(headings[0]).toHaveTextContent('24 de agosto de 2026')
    expect(headings[1]).toHaveTextContent('23 de agosto de 2026')

    expect(screen.getByText('Foto de ontem')).toBeInTheDocument()
    expect(screen.getByText('Foto de hoje cedo')).toBeInTheDocument()
    expect(screen.getByText('Foto de hoje à tarde')).toBeInTheDocument()
    expect(screen.getAllByRole('img')).toHaveLength(3)
  })

  it('renders nothing (no group headings) when there are no photos', () => {
    render(<PhotoTimeline photos={[]} />)

    expect(screen.queryAllByRole('heading', { level: 3 })).toHaveLength(0)
  })
})
