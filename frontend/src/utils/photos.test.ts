import { describe, expect, it } from 'vitest'
import type { Photo } from '../types/api'
import { groupPhotosByDate } from './photos'

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

describe('groupPhotosByDate', () => {
  it('groups photos by day and orders groups most-recent first, regardless of input order', () => {
    const dayOne = makePhoto({ id: 'a', uploaded_at: '2026-08-23T10:00:00Z' })
    const dayTwoEarlier = makePhoto({ id: 'b', uploaded_at: '2026-08-24T09:00:00Z' })
    const dayTwoLater = makePhoto({ id: 'c', uploaded_at: '2026-08-24T15:00:00Z' })

    const groups = groupPhotosByDate([dayOne, dayTwoEarlier, dayTwoLater])

    expect(groups).toHaveLength(2)
    expect(groups[0].dateLabel).toContain('24 de agosto')
    expect(groups[0].photos.map((p) => p.id)).toEqual(['c', 'b'])
    expect(groups[1].dateLabel).toContain('23 de agosto')
    expect(groups[1].photos.map((p) => p.id)).toEqual(['a'])
  })

  it('returns an empty list of groups for an empty photo list', () => {
    expect(groupPhotosByDate([])).toEqual([])
  })
})
