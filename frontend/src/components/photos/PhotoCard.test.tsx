import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Photo } from '../../types/api'
import PhotoCard from './PhotoCard.tsx'

const BASE_PHOTO: Photo = {
  id: '0f1c1234-5678-90ab-cdef-1234567890ab',
  description: 'Primeira muda plantada.',
  contributor_name: 'Ana',
  captured_at: '2026-08-24T14:00:00Z',
  uploaded_at: '2026-08-24T14:05:00Z',
  latitude: -21.8843,
  longitude: -43.3129,
  width: 1080,
  height: 1350,
  photo_url: '/api/photos/0f1c1234-5678-90ab-cdef-1234567890ab/file',
}

describe('PhotoCard', () => {
  it('renders the image with the width/height from the API, its date, contributor, and description', () => {
    render(<PhotoCard photo={BASE_PHOTO} />)

    const image = screen.getByRole('img')
    expect(image).toHaveAttribute('src', BASE_PHOTO.photo_url)
    expect(image).toHaveAttribute('width', '1080')
    expect(image).toHaveAttribute('height', '1350')
    expect(screen.getByText('Ana')).toBeInTheDocument()
    expect(screen.getByText('Primeira muda plantada.')).toBeInTheDocument()
  })

  it('omits the contributor and description when the API returns them as null', () => {
    const photo: Photo = { ...BASE_PHOTO, contributor_name: null, description: null }

    render(<PhotoCard photo={photo} />)

    expect(screen.queryByText('Ana')).not.toBeInTheDocument()
    expect(screen.queryByText('Primeira muda plantada.')).not.toBeInTheDocument()
    expect(screen.queryByText('null')).not.toBeInTheDocument()
  })
})
