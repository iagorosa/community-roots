import PlantingMap from '../components/map/PlantingMap.tsx'

/**
 * Minimal wiring for issue #16 (the `PlantingMap` component itself). Real
 * data — `RegionLayer`, `fitBounds`, loading/error/empty states — is
 * issue #18.
 */
function MapPage() {
  return (
    <div className="flex flex-1 flex-col">
      <h1 className="sr-only">Mapa</h1>
      {/* `flex-1`, not `h-full`: this wrapper is `flex-col`, and a
          percentage height doesn't reliably resolve against a flex-grown
          ancestor — that mismatch is the real "half-gray map" bug
          architecture.md §2.2 warns about (reproduced and confirmed live
          in a browser while building this). */}
      <PlantingMap className="flex-1" />
    </div>
  )
}

export default MapPage
