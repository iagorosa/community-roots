import { describe, expect, it } from 'vitest'
import type { RegionFeature, RegionFeatureCollection } from '../types/api'
import { regionCenter, regionsBounds } from './geo'

const BASE_PROPERTIES = {
  description: null,
  status: 'active' as const,
  qr_token: 'k3Zq8xR2mNvA',
  planting_count: 0,
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
}

function pointFeature(slug: string, lon: number, lat: number): RegionFeature {
  return {
    type: 'Feature',
    id: slug,
    geometry: { type: 'Point', coordinates: [lon, lat] },
    properties: { ...BASE_PROPERTIES, slug, name: slug },
  }
}

function polygonFeature(slug: string): RegionFeature {
  // A 0.01°-square polygon (roughly the size of a real canteiro) centered
  // on (-43.31, -21.88), for checking `regionCenter` doesn't just echo the
  // first coordinate.
  return {
    type: 'Feature',
    id: slug,
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [-43.315, -21.885],
          [-43.305, -21.885],
          [-43.305, -21.875],
          [-43.315, -21.875],
          [-43.315, -21.885],
        ],
      ],
    },
    properties: { ...BASE_PROPERTIES, slug, name: slug },
  }
}

describe('regionsBounds', () => {
  it('collapses to a single point when only one feature is given', () => {
    const collection: RegionFeatureCollection = {
      type: 'FeatureCollection',
      features: [pointFeature('canteiro-a', -43.3129, -21.8843)],
    }

    const bounds = regionsBounds(collection)

    expect(bounds.getSouthWest().equals(bounds.getNorthEast())).toBe(true)
    expect(bounds.getCenter().lat).toBeCloseTo(-21.8843)
    expect(bounds.getCenter().lng).toBeCloseTo(-43.3129)
  })

  it('extends to cover every feature in the collection', () => {
    const collection: RegionFeatureCollection = {
      type: 'FeatureCollection',
      features: [
        pointFeature('canteiro-a', -43.3129, -21.8843),
        pointFeature('canteiro-b', -43.35, -21.9),
      ],
    }

    const bounds = regionsBounds(collection)

    expect(bounds.contains([-21.8843, -43.3129])).toBe(true)
    expect(bounds.contains([-21.9, -43.35])).toBe(true)
    // A bounding box spanning two distinct points has more than a single
    // coordinate — regression check against `regionsBounds` collapsing
    // everything to just the first feature.
    expect(bounds.getSouthWest().equals(bounds.getNorthEast())).toBe(false)
  })
})

describe('regionCenter', () => {
  it('returns the point itself for a Point geometry', () => {
    const center = regionCenter(pointFeature('canteiro-a', -43.3129, -21.8843))

    expect(center[0]).toBeCloseTo(-21.8843)
    expect(center[1]).toBeCloseTo(-43.3129)
  })

  it('returns the bounding-box center for a Polygon geometry, not a raw vertex', () => {
    const center = regionCenter(polygonFeature('canteiro-b'))

    expect(center[0]).toBeCloseTo(-21.88)
    expect(center[1]).toBeCloseTo(-43.31)
  })
})
