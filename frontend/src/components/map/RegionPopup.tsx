import type { RegionProperties } from '../../types/api'

interface RegionPopupProps {
  properties: RegionProperties
}

/**
 * Static content only — no `onClick`/`<Link>` here. `RegionLayer` renders
 * this to a plain HTML string for Leaflet's imperative `bindPopup`, which
 * sits outside the app's React tree (no Router context to resolve a
 * `<Link>` against), so this is a real `<a href>` instead.
 */
function RegionPopup({ properties }: RegionPopupProps) {
  const plantingCountLabel =
    properties.planting_count === 1 ? '1 muda' : `${properties.planting_count} mudas`

  return (
    <div>
      <p className="font-semibold text-slate-800">{properties.name}</p>
      <p className="text-sm text-slate-600">{plantingCountLabel}</p>
      <a href={`/regions/${properties.slug}`} className="text-sm text-emerald-700 underline">
        Ver canteiro
      </a>
    </div>
  )
}

export default RegionPopup
