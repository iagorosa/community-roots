import type { ReactNode } from 'react'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import EmptyState from '../components/feedback/EmptyState.tsx'
import ErrorState from '../components/feedback/ErrorState.tsx'
import LoadingState from '../components/feedback/LoadingState.tsx'
import PlantingMap from '../components/map/PlantingMap.tsx'
import PlantingClusterLayer from '../components/map/PlantingClusterLayer.tsx'
import RegionLayer from '../components/map/RegionLayer.tsx'
import RegionSidebar from '../components/map/RegionSidebar.tsx'
import PlantingDetailDrawer from '../components/plantings/PlantingDetailDrawer.tsx'
import PlantingDetailPanel from '../components/plantings/PlantingDetailPanel.tsx'
import { usePlantings } from '../hooks/usePlantings.ts'
import { useRegions } from '../hooks/useRegions.ts'
import { regionsBounds } from '../utils/geo.ts'

const PLANTING_PARAM = 'planting'

/** Shared chrome for every state below — full-height flex column
 * (docs/architecture.md §2.2/§8) with the page heading, so the heading
 * stays present (and `flex-1` keeps filling the viewport) whether the
 * page is loading, erroring, empty, or showing the map. */
function MapPageShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <h1 className="sr-only">Mapa</h1>
      {children}
    </div>
  )
}

/**
 * `PlantingMap` + `RegionLayer` (region boundaries) + `PlantingClusterLayer`
 * (individual mudas, clustered), with `RegionSidebar` layered on top for
 * name search and per-region planting counts. Clicking a pin — or landing
 * on `/mapa` with `?planting=<id>` already set (`QrRedirectPage`, issue
 * #97, does this for a scanned Planting QR code) — opens
 * `PlantingDetailDrawer`.
 */
function MapPage() {
  const { data: regions, isPending, isError } = useRegions()
  // `plantings`'s own `isPending`/`isError` are deliberately unchecked: a
  // failed or slow Plantings fetch degrades to a region-only map (no pins)
  // rather than blocking the page on a secondary layer — mirroring the
  // `isError` tradeoff above, applied to the less critical dataset.
  const { data: plantings } = usePlantings()
  const bounds = useMemo(() => (regions ? regionsBounds(regions) : undefined), [regions])

  const [searchParams, setSearchParams] = useSearchParams()
  const selectedPlantingId = searchParams.get(PLANTING_PARAM)

  function openPlanting(plantingId: string) {
    setSearchParams(
      (params) => {
        params.set(PLANTING_PARAM, plantingId)
        return params
      },
      { replace: true },
    )
  }

  function closeDrawer() {
    setSearchParams(
      (params) => {
        params.delete(PLANTING_PARAM)
        return params
      },
      { replace: true },
    )
  }

  if (isPending) {
    return (
      <MapPageShell>
        <LoadingState message="Carregando canteiros..." />
      </MapPageShell>
    )
  }

  // Deliberate tradeoff, not an oversight: `isError` also fires for a
  // background refetch that fails *after* a prior successful load (e.g.
  // `refetchOnWindowFocus`, on by default in App.tsx's QueryClient) — a
  // working, possibly-panned map gets replaced by `ErrorState` rather than
  // kept stale. Simpler than partial-failure UI, and still satisfies issue
  // #18's actual requirement: never show a blank page when the backend is
  // down. Revisit with `isLoadingError` instead of `isError` if a flaky
  // background refetch turns out to be disruptive in practice.
  if (isError) {
    return (
      <MapPageShell>
        <ErrorState message="Não foi possível carregar os canteiros. Tente novamente mais tarde." />
      </MapPageShell>
    )
  }

  if (regions.features.length === 0) {
    return (
      <MapPageShell>
        <EmptyState message="Nenhum canteiro cadastrado ainda." />
      </MapPageShell>
    )
  }

  return (
    <MapPageShell>
      {/* `flex flex-col` here (not just `relative`) so `PlantingMap` is a
          direct flex-column item and can take `flex-1` for its height —
          `h-full` doesn't reliably resolve against this div, since ITS OWN
          height only comes from being a flex-grown item one level up, not
          from an explicit/fixed height (see `PlantingMap`'s own doc comment
          on `className`). Confirmed live in a browser: with `h-full` here,
          the map silently rendered at 0 height on every viewport, not just
          mobile — `RegionSidebar`'s absolute overlay was the only thing
          visible. */}
      <div className="relative flex flex-1 flex-col">
        <PlantingMap className="flex-1" bounds={bounds}>
          <RegionLayer data={regions} />
          {plantings && <PlantingClusterLayer data={plantings} onSelect={openPlanting} />}
        </PlantingMap>
        <RegionSidebar regions={regions} />
      </div>

      <PlantingDetailDrawer open={selectedPlantingId !== null} onClose={closeDrawer}>
        {selectedPlantingId && <PlantingDetailPanel plantingId={selectedPlantingId} />}
      </PlantingDetailDrawer>
    </MapPageShell>
  )
}

export default MapPage
