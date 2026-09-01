import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import type { RegionFeatureCollection } from '../../types/api'

interface RegionSidebarProps {
  regions: RegionFeatureCollection
}

/** Collapsible list of regions over the map, with a name filter and each
 * region's planting count — the pivot design spec's sidebar decision.
 * Filtering by city is out of scope for now: `Region` has no `city` field
 * yet (see the spec), and there's only one city in the data today. */
function RegionSidebar({ regions }: RegionSidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [search, setSearch] = useState('')

  const filteredFeatures = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return regions.features
    return regions.features.filter((feature) => feature.properties.name.toLowerCase().includes(query))
  }, [regions, search])

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        aria-label="Mostrar lista de regiões"
        className="absolute left-2 top-2 z-[1000] rounded-md bg-white px-3 py-2 text-sm font-semibold text-emerald-700 shadow"
      >
        Regiões
      </button>
    )
  }

  return (
    <aside className="absolute left-2 top-2 z-[1000] flex max-h-[calc(100%-1rem)] w-64 flex-col gap-3 overflow-y-auto rounded-md bg-white p-3 shadow">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-emerald-700">Regiões</h2>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          aria-label="Esconder lista de regiões"
          className="text-sm text-slate-500"
        >
          Esconder
        </button>
      </div>

      <input
        type="search"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Buscar região..."
        aria-label="Buscar região"
        className="rounded-md border border-slate-300 px-2 py-1 text-sm"
      />

      <ul className="flex flex-col gap-1">
        {filteredFeatures.map((feature) => (
          <li key={feature.id}>
            <Link
              to={`/regions/${feature.properties.slug}`}
              className="flex items-center justify-between rounded px-2 py-1 text-sm text-slate-700 hover:bg-emerald-50"
            >
              <span>{feature.properties.name}</span>
              <span className="text-slate-400">{feature.properties.planting_count}</span>
            </Link>
          </li>
        ))}
        {filteredFeatures.length === 0 && (
          <li className="text-sm text-slate-400">Nenhuma região encontrada.</li>
        )}
      </ul>
    </aside>
  )
}

export default RegionSidebar
