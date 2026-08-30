import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { RegionFeature, RegionFeatureCollection } from '../../types/api'
import RegionLayer from './RegionLayer.tsx'

const mockNavigate = vi.fn()
vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

type OnEachFeature = (feature: RegionFeature, layer: FakeLayer) => void

let capturedOnEachFeature: OnEachFeature | undefined
let capturedData: unknown

vi.mock('react-leaflet', () => ({
  GeoJSON: (props: { data: unknown; onEachFeature: OnEachFeature }) => {
    capturedOnEachFeature = props.onEachFeature
    capturedData = props.data
    return null
  },
}))

// A minimal stand-in for `L.Layer` — real Leaflet layers need a live map
// and jsdom's layout support to construct (see PlantingMap.test.tsx's
// comment on why map tests stay shallow), so `onEachFeature` is exercised
// directly against this fake instead.
//
// `getElement()` deliberately mirrors Leaflet's real behavior — it
// returns `undefined` until the layer has fired `add` — because a
// version of this fake that returned the element unconditionally masked
// a real bug where `onEachFeature` set attributes on an element that
// didn't exist yet.
class FakeLayer {
  element = document.createElement('div')
  bindPopup = vi.fn()
  openPopup = vi.fn()
  closePopup = vi.fn()
  off = vi.fn((event: string, handler: () => void) => {
    this.handlers[event] = (this.handlers[event] ?? []).filter((h) => h !== handler)
    return this
  })
  // Real `Path`/`Marker` layers always carry this once `bindPopup` runs
  // (see RegionLayer.tsx's comment on `internalOpenPopupHandler`) — present
  // unconditionally here so the fake can't accidentally hide a broken
  // `off()` call behind a missing property.
  _openPopup = vi.fn()
  private added = false
  private handlers: Record<string, (() => void)[]> = {}

  getElement(): HTMLElement | undefined {
    return this.added ? this.element : undefined
  }

  on(event: string, handler: () => void) {
    this.handlers[event] ??= []
    this.handlers[event].push(handler)
    return this
  }

  fire(event: string) {
    if (event === 'add') this.added = true
    for (const handler of this.handlers[event] ?? []) handler()
  }
}

const SAMPLE_COLLECTION: RegionFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: '0f1c1234-5678-90ab-cdef-1234567890ab',
      geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
      properties: {
        slug: 'canteiro-do-ipe',
        name: 'Canteiro do Ipê',
        description: null,
        status: 'active',
        qr_token: 'k3Zq8xR2mNvA',
        photo_count: 0,
        latest_photo_at: null,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

function renderRegionLayer() {
  return render(
    <MemoryRouter>
      <RegionLayer data={SAMPLE_COLLECTION} />
    </MemoryRouter>,
  )
}

// Mirrors Leaflet's real lifecycle: `onEachFeature` runs before the layer
// has a DOM element (`getElement()` is `undefined` then — confirmed live
// in a browser), which only exists once the layer fires `add`. A version
// of this fake that returned `getElement()` synchronously masked that
// exact bug, so `add` is fired here deliberately, not skipped for
// convenience.
function mountFeature(): FakeLayer {
  const layer = new FakeLayer()
  capturedOnEachFeature?.(SAMPLE_COLLECTION.features[0], layer)
  layer.fire('add')
  return layer
}

describe('RegionLayer', () => {
  beforeEach(() => {
    mockNavigate.mockClear()
    capturedOnEachFeature = undefined
    capturedData = undefined
  })

  it('passes the feature collection through to <GeoJSON>', () => {
    renderRegionLayer()

    expect(capturedData).toBe(SAMPLE_COLLECTION)
  })

  it('navigates to the region page on click', () => {
    renderRegionLayer()
    const layer = mountFeature()

    layer.fire('click')

    expect(mockNavigate).toHaveBeenCalledWith('/regions/canteiro-do-ipe')
  })

  it('navigates to the region page on Enter/Space keydown', () => {
    renderRegionLayer()
    const layer = mountFeature()

    layer.element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))

    expect(mockNavigate).toHaveBeenCalledWith('/regions/canteiro-do-ipe')
  })

  it('ignores keydown for keys other than Enter/Space', () => {
    renderRegionLayer()
    const layer = mountFeature()

    layer.element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))

    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('makes the feature keyboard-focusable with an accessible label', () => {
    renderRegionLayer()
    const layer = mountFeature()

    expect(layer.element.getAttribute('tabindex')).toBe('0')
    expect(layer.element.getAttribute('role')).toBe('button')
    expect(layer.element.getAttribute('aria-label')).toContain('Canteiro do Ipê')
  })

  it('does not touch the element before the layer is added to the map', () => {
    renderRegionLayer()
    const layer = new FakeLayer()

    capturedOnEachFeature?.(SAMPLE_COLLECTION.features[0], layer)

    // Regression check for a real bug: `getElement()` returns `undefined`
    // until Leaflet actually adds the layer, so `onEachFeature` itself
    // must not set attributes directly — only the `add` handler may.
    expect(layer.element.getAttribute('tabindex')).toBeNull()
  })

  it('binds a popup with the region name and a link to its page', () => {
    renderRegionLayer()
    const layer = mountFeature()

    expect(layer.bindPopup).toHaveBeenCalledTimes(1)
    const popupContent = layer.bindPopup.mock.calls[0]?.[0] as string
    expect(popupContent).toContain('Canteiro do Ipê')
    expect(popupContent).toContain('/regions/canteiro-do-ipe')
  })

  it('opens the popup on hover and closes it when the pointer leaves', () => {
    renderRegionLayer()
    const layer = mountFeature()

    layer.fire('mouseover')
    expect(layer.openPopup).toHaveBeenCalledTimes(1)

    layer.fire('mouseout')
    expect(layer.closePopup).toHaveBeenCalledTimes(1)
  })

  it('removes bindPopup\'s own click-to-open handler, so a click only navigates', () => {
    // `bindPopup` wires an internal `click` listener (Leaflet's own
    // `Popup` mixin) that would otherwise pop the popup open a beat
    // before navigation carries the page away. See RegionLayer.tsx.
    renderRegionLayer()
    const layer = mountFeature()

    expect(layer.off).toHaveBeenCalledWith('click', layer._openPopup)
  })
})
