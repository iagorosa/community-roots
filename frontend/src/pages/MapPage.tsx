import PlantingMap from '../components/map/PlantingMap.tsx'
import RegionLayer from '../components/map/RegionLayer.tsx'
import { useRegions } from '../hooks/useRegions.ts'

/**
 * Minimal wiring for issues #16/#17 (`PlantingMap`, `RegionLayer`). Real
 * `fitBounds` and `LoadingState`/`ErrorState`/`EmptyState` are issue #18 —
 * this crude `data && ...` check is only here so #17's map interactions
 * are reachable for manual QA in a real browser.
 */
function MapPage() {
  const { data } = useRegions()

  return (
    <div className="flex flex-1 flex-col">
      <h1 className="sr-only">Mapa</h1>
      <PlantingMap className="flex-1">{data && <RegionLayer data={data} />}</PlantingMap>
    </div>
  )
}

export default MapPage
