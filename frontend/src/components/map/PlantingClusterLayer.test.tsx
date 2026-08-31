import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { PlantingFeatureCollection } from '../../types/api'
import PlantingClusterLayer from './PlantingClusterLayer.tsx'

type MarkerProps = { position: [number, number]; eventHandlers?: { click?: () => void } }

let capturedMarkers: MarkerProps[] = []

vi.mock('react-leaflet', () => ({
  Marker: (props: MarkerProps) => {
    capturedMarkers.push(props)
    return null
  },
}))

vi.mock('react-leaflet-cluster', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="cluster-group">{children}</div>,
}))

const SAMPLE_COLLECTION: PlantingFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: 'p1',
      geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
      properties: {
        region_id: 'r1',
        species: null,
        nickname: null,
        planted_by: null,
        planted_at: null,
        status: 'active',
        qr_token: 'tok-1',
        photo_count: 0,
        latest_photo_at: null,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

describe('PlantingClusterLayer', () => {
  it('renders one marker per planting, in [lat, lon] order', () => {
    capturedMarkers = []

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={vi.fn()} />)

    expect(capturedMarkers).toHaveLength(1)
    expect(capturedMarkers[0]?.position).toEqual([-21.8843, -43.3129])
  })

  it('calls onSelect with the planting id when its marker is clicked', () => {
    capturedMarkers = []
    const onSelect = vi.fn()

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={onSelect} />)
    capturedMarkers[0]?.eventHandlers?.click?.()

    expect(onSelect).toHaveBeenCalledWith('p1')
  })
})
