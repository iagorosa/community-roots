import type { Layer, LeafletEventHandlerFn, PathOptions } from 'leaflet'
import ReactDOMServer from 'react-dom/server'
import { GeoJSON } from 'react-leaflet'
import { useNavigate } from 'react-router'
import type { RegionFeature, RegionFeatureCollection } from '../../types/api'
import { isActivationKey } from '../../utils/keyboard.ts'
import RegionPopup from './RegionPopup.tsx'

interface RegionLayerProps {
  data: RegionFeatureCollection
}

const REGION_STYLE: PathOptions = {
  // Targeted by the hover/focus rules in styles/index.css — SVG paths
  // support `:hover`/`:focus-visible` natively, no JS needed for the
  // visual state itself.
  className: 'region-layer-shape',
  color: '#047857',
  weight: 2,
  fillOpacity: 0.3,
}

/** `layer.getElement()` only exists on `Path`/`Marker`, not the base
 * `Layer` type `onEachFeature` is declared with. */
function hasGetElement(layer: Layer): layer is Layer & { getElement(): Element | undefined } {
  return typeof (layer as { getElement?: unknown }).getElement === 'function'
}

/** `bindPopup` isn't documented to expose this, but every `Path`/`Marker`
 * carries it — see the comment where this is used. */
function internalOpenPopupHandler(layer: Layer): LeafletEventHandlerFn | undefined {
  return (layer as { _openPopup?: LeafletEventHandlerFn })._openPopup
}

function RegionLayer({ data }: RegionLayerProps) {
  const navigate = useNavigate()

  function onEachFeature(feature: RegionFeature, layer: Layer) {
    const properties = feature.properties
    const regionPath = `/regions/${properties.slug}`
    const openRegion = () => navigate(regionPath)

    // architecture.md §8: click and keyboard activation both open the
    // canteiro directly; the popup (bound below) is a hover preview, not
    // a required first step.
    layer.on('click', openRegion)
    layer.on('mouseover', () => layer.openPopup())
    layer.on('mouseout', () => layer.closePopup())

    // `RegionPopup`'s content is static (no event handlers of its own —
    // see its own comment) so it's safe to render to a plain HTML string
    // for Leaflet's imperative `bindPopup`, which lives outside the app's
    // React tree.
    layer.bindPopup(ReactDOMServer.renderToStaticMarkup(<RegionPopup properties={properties} />))
    // `bindPopup` also wires its own internal `click` listener that opens
    // the popup — confirmed in Leaflet's source (`Popup.js`, the mixin
    // `bindPopup` applies). Left in place, a click would both navigate
    // away *and* pop the popup open a beat before that happens. Removed
    // so the popup stays hover-only, matching the comment above.
    const openPopupOnClick = internalOpenPopupHandler(layer)
    if (openPopupOnClick) layer.off('click', openPopupOnClick)

    // `getElement()` returns `undefined` here: Leaflet only creates a
    // Path/Marker's DOM element when the layer is actually added to the
    // map (`onAdd`), which hasn't happened yet at `onEachFeature` time —
    // confirmed live in a browser (tabindex/role/aria-label were silently
    // never applied). Deferred to the `add` event, which fires once that
    // element genuinely exists.
    layer.on('add', () => {
      if (!hasGetElement(layer)) return
      const element = layer.getElement()
      if (!element) return

      element.setAttribute('tabindex', '0')
      element.setAttribute('role', 'button')
      element.setAttribute('aria-label', `Abrir canteiro ${properties.name}`)
      // `keydown` isn't in the plain `ElementEventMap` TypeScript ships
      // (it's HTML-only there, even though SVG elements do fire it) —
      // Leaflet's Path layers render as SVG, hence the generic listener
      // and the cast inside.
      element.addEventListener('keydown', (event: Event) => {
        const keyboardEvent = event as KeyboardEvent
        if (!isActivationKey(keyboardEvent)) return
        keyboardEvent.preventDefault()
        openRegion()
      })
    })
  }

  return <GeoJSON data={data} style={REGION_STYLE} onEachFeature={onEachFeature} />
}

export default RegionLayer
