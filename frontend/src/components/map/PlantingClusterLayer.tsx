// Imported here, alongside `react-leaflet-cluster`'s own JS — CSS for the
// cluster bubbles it renders. `leaflet/dist/leaflet.css` is already
// imported once, in `PlantingMap.tsx`; these two are that same "import
// once" rule applied to the new library.
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'

import type { Layer } from 'leaflet'
import { useEffect } from 'react'
import { Marker, useMap } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import type { PlantingFeature, PlantingFeatureCollection } from '../../types/api'
import { isActivationKey } from '../../utils/keyboard.ts'

interface PlantingClusterLayerProps {
  data: PlantingFeatureCollection
  onSelect: (plantingId: string) => void
}

function toLatLng(coordinates: [number, number]): [number, number] {
  const [longitude, latitude] = coordinates
  return [latitude, longitude]
}

/** Same fallback `PlantingDetailPanel.tsx` and `RegionPage.tsx`'s planting
 * list use for a human-readable name — a Planting only has `nickname` and
 * `species` as free text, and either may be missing. */
function plantingLabel(feature: PlantingFeature): string {
  return feature.properties.nickname ?? feature.properties.species ?? 'Muda sem nome'
}

/** `layer.getElement()` only exists on `Path`/`Marker`, not the base
 * `Layer` type `eventHandlers.add` is declared with — same situation
 * `RegionLayer.tsx`'s `hasGetElement` handles for GeoJSON paths. */
function hasGetElement(layer: Layer): layer is Layer & { getElement(): Element | undefined } {
  return typeof (layer as { getElement?: unknown }).getElement === 'function'
}

/** Wires up one Planting pin's marker element for keyboard use, once it
 * genuinely has a DOM element (`getElement()` is `undefined` before the
 * layer's `add` event — confirmed in RegionLayer.tsx's own version of this
 * problem). Leaflet's default `Marker` already sets `tabindex`/`role` on
 * its icon on its own (the `keyboard: true` default option) — set again
 * here anyway, so this pin's accessibility doesn't silently depend on that
 * option never changing, matching `RegionLayer`'s own explicit approach for
 * region shapes. What Leaflet's default genuinely lacks: an accessible name
 * (`alt=""`) and Space as an activation key (only Enter, via its internal
 * `keypress`/`clusterkeypress` plumbing) — both fixed here directly. */
function makeMarkerFocusable(layer: Layer, label: string, onActivate: () => void) {
  if (!hasGetElement(layer)) return
  const element = layer.getElement()
  if (!element) return

  element.setAttribute('tabindex', '0')
  element.setAttribute('role', 'button')
  element.setAttribute('aria-label', `Abrir muda ${label}`)
  element.addEventListener('keydown', (event: Event) => {
    const keyboardEvent = event as KeyboardEvent
    if (!isActivationKey(keyboardEvent)) return
    keyboardEvent.preventDefault()
    onActivate()
  })
}

/** A cluster bubble's own count, read back from its rendered text (the
 * default `iconCreateFunction`'s `<span>{count}</span>`) rather than from
 * any `leaflet.markercluster` API — see the comment on `labelClusterBubbles`
 * below for why nothing in that library's own event system reaches this
 * element at a point where a `MarkerCluster` instance is available. */
function clusterChildCount(element: Element): number | null {
  const count = Number.parseInt(element.textContent ?? '', 10)
  return Number.isNaN(count) ? null : count
}

/** Cluster bubbles already get keyboard focus and Enter-key activation for
 * free — `MarkerCluster` extends `Marker`, so the `keyboard: true` default
 * applies to it too, and `leaflet.markercluster` itself wires Enter to
 * zoom/spiderfy (its `clusterclick`/`clusterkeypress` handling, confirmed
 * in `leaflet.markercluster-src.js`). What's missing is an accessible name:
 * the bubble's only text is its bare count (e.g. "5"), which a screen
 * reader announces with no context.
 *
 * Getting that name onto the element is harder than it sounds: cluster
 * bubbles are created and destroyed by the clustering library itself as the
 * map zooms, never rendered as JSX, and `leaflet.markercluster`'s only
 * public event for a newly-added layer (`layeradd` on the group) fires
 * exclusively for individual leaf markers, never for the cluster icons
 * themselves (confirmed by reading `addLayers()` in
 * `leaflet.markercluster-src.js` — the `MarkerCluster` instances are added
 * to a private internal `FeatureGroup`, never through the path that fires
 * `layeradd` on the public group). A `MutationObserver` on the map's DOM
 * sidesteps needing to hook the right internal event entirely: it sees
 * every `.marker-cluster` element the moment it's attached, regardless of
 * which internal code path put it there. */
function labelClusterBubbles(root: Element) {
  const elements = root.matches('.marker-cluster') ? [root] : Array.from(root.querySelectorAll('.marker-cluster'))
  for (const element of elements) {
    const count = clusterChildCount(element)
    if (count === null) continue

    const countLabel = count === 1 ? '1 muda' : `${count} mudas`
    element.setAttribute('aria-label', `Ampliar grupo com ${countLabel}`)
  }
}

/** Pins for every Planting, clustered with a count bubble when several sit
 * close together at the current zoom — the map-zoom-levels decision from
 * the pivot design spec. Sits alongside `RegionLayer` inside `PlantingMap`,
 * never inside it: Region boundaries and Planting pins are independent
 * layers on the same map. */
function PlantingClusterLayer({ data, onSelect }: PlantingClusterLayerProps) {
  const map = useMap()

  useEffect(() => {
    const container = map.getContainer()

    // Covers bubbles already on the map when this effect first runs — the
    // observer below only sees mutations from this point forward, and
    // react-leaflet mounts the initial markers synchronously (a
    // `useLayoutEffect` in `@react-leaflet/core`), before this component's
    // own `useEffect` gets a turn.
    labelClusterBubbles(container)

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node instanceof Element) labelClusterBubbles(node)
        }
      }
    })
    observer.observe(container, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [map])

  return (
    <MarkerClusterGroup>
      {data.features.map((feature) => {
        // A Planting's geometry may become a Polygon later (see
        // types/api.ts's PlantingGeometry comment) — today it's always a
        // Point, which is all a marker pin can plot anyway.
        if (feature.geometry.type !== 'Point') return null

        const label = plantingLabel(feature)
        const openPlanting = () => onSelect(feature.id)

        return (
          <Marker
            key={feature.id}
            position={toLatLng(feature.geometry.coordinates)}
            eventHandlers={{
              click: openPlanting,
              add: (event) => makeMarkerFocusable(event.target, label, openPlanting),
            }}
          />
        )
      })}
    </MarkerClusterGroup>
  )
}

export default PlantingClusterLayer
