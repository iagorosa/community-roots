import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { PlantingFeatureCollection } from '../../types/api'
import PlantingClusterLayer from './PlantingClusterLayer.tsx'

type FakeMarkerEvent = { target: FakeMarkerLayer }
type MarkerProps = {
  position: [number, number]
  eventHandlers?: { click?: () => void; add?: (event: FakeMarkerEvent) => void }
}

// A minimal stand-in for a Leaflet `Marker`'s DOM lifecycle — same
// `getElement()`-is-`undefined`-until-`add` shape `RegionLayer.test.tsx`'s
// `FakeLayer` uses, since `PlantingClusterLayer` relies on the exact same
// Leaflet behavior for its individual pins.
class FakeMarkerLayer {
  element = document.createElement('div')
  private added = false

  getElement(): HTMLElement | undefined {
    return this.added ? this.element : undefined
  }

  fireAdd() {
    this.added = true
  }
}

let capturedMarkers: MarkerProps[] = []

// `PlantingClusterLayer` reads the map's DOM container via `useMap()` to
// scope its `MutationObserver` for cluster-bubble labeling (see the
// component's own comment on why a `MutationObserver`, not a
// `leaflet.markercluster` event, is what does that job). This fake map
// hands back a real, detached `<div>` — `MutationObserver` and
// `querySelectorAll` both work the same on a detached node as on one
// attached to `document`.
const fakeMapContainer = document.createElement('div')

vi.mock('react-leaflet', () => ({
  Marker: (props: MarkerProps) => {
    capturedMarkers.push(props)
    return null
  },
  useMap: () => ({ getContainer: () => fakeMapContainer }),
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
        nickname: 'Ipê-branco',
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

// `MutationObserver` callbacks fire as a microtask, after the mutation —
// a real `await` (even of nothing) lets that microtask queue drain before
// assertions run.
function flushMicrotasks(): Promise<void> {
  return new Promise((resolve) => queueMicrotask(resolve))
}

function appendClusterBubble(count: number): HTMLElement {
  const bubble = document.createElement('div')
  bubble.className = 'marker-cluster marker-cluster-small'
  bubble.innerHTML = `<div><span>${count}</span></div>`
  fakeMapContainer.appendChild(bubble)
  return bubble
}

describe('PlantingClusterLayer', () => {
  it('renders one marker per planting, in [lat, lon] order', () => {
    capturedMarkers = []
    fakeMapContainer.replaceChildren()

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={vi.fn()} />)

    expect(capturedMarkers).toHaveLength(1)
    expect(capturedMarkers[0]?.position).toEqual([-21.8843, -43.3129])
  })

  it('calls onSelect with the planting id when its marker is clicked', () => {
    capturedMarkers = []
    fakeMapContainer.replaceChildren()
    const onSelect = vi.fn()

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={onSelect} />)
    capturedMarkers[0]?.eventHandlers?.click?.()

    expect(onSelect).toHaveBeenCalledWith('p1')
  })

  it('makes each pin keyboard-focusable with an accessible label once added to the map', () => {
    capturedMarkers = []
    fakeMapContainer.replaceChildren()

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={vi.fn()} />)
    const layer = new FakeMarkerLayer()
    layer.fireAdd()
    capturedMarkers[0]?.eventHandlers?.add?.({ target: layer })

    expect(layer.element.getAttribute('tabindex')).toBe('0')
    expect(layer.element.getAttribute('role')).toBe('button')
    expect(layer.element.getAttribute('aria-label')).toContain('Ipê-branco')
  })

  it('does not touch the marker element before it is added to the map', () => {
    capturedMarkers = []
    fakeMapContainer.replaceChildren()

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={vi.fn()} />)
    const layer = new FakeMarkerLayer()
    // Deliberately not calling `fireAdd()` — same regression this guards
    // against in `RegionLayer.test.tsx`: `getElement()` returns `undefined`
    // until Leaflet genuinely adds the layer.
    capturedMarkers[0]?.eventHandlers?.add?.({ target: layer })

    expect(layer.element.getAttribute('tabindex')).toBeNull()
  })

  it('opens the planting on Enter/Space keydown', () => {
    capturedMarkers = []
    fakeMapContainer.replaceChildren()
    const onSelect = vi.fn()

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={onSelect} />)
    const layer = new FakeMarkerLayer()
    layer.fireAdd()
    capturedMarkers[0]?.eventHandlers?.add?.({ target: layer })

    layer.element.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }))

    expect(onSelect).toHaveBeenCalledWith('p1')
  })

  it('ignores keydown for keys other than Enter/Space', () => {
    capturedMarkers = []
    fakeMapContainer.replaceChildren()
    const onSelect = vi.fn()

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={onSelect} />)
    const layer = new FakeMarkerLayer()
    layer.fireAdd()
    capturedMarkers[0]?.eventHandlers?.add?.({ target: layer })

    layer.element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))

    expect(onSelect).not.toHaveBeenCalled()
  })

  it('labels a cluster bubble already on the map when the layer mounts', async () => {
    capturedMarkers = []
    fakeMapContainer.replaceChildren()
    const bubble = appendClusterBubble(3)

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={vi.fn()} />)
    await flushMicrotasks()

    expect(bubble.getAttribute('aria-label')).toBe('Ampliar grupo com 3 mudas')
  })

  it('labels a cluster bubble added to the map later (e.g. after a zoom change)', async () => {
    capturedMarkers = []
    fakeMapContainer.replaceChildren()

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={vi.fn()} />)
    const bubble = appendClusterBubble(1)
    await flushMicrotasks()

    expect(bubble.getAttribute('aria-label')).toBe('Ampliar grupo com 1 muda')
  })

  it('does not label a non-cluster element added to the map container', async () => {
    capturedMarkers = []
    fakeMapContainer.replaceChildren()

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={vi.fn()} />)
    const plainPin = document.createElement('div')
    plainPin.className = 'leaflet-marker-icon'
    fakeMapContainer.appendChild(plainPin)
    await flushMicrotasks()

    expect(plainPin.getAttribute('aria-label')).toBeNull()
  })
})
