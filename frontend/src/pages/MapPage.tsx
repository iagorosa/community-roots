import type { ReactNode } from 'react'
import { useMemo } from 'react'
import EmptyState from '../components/feedback/EmptyState.tsx'
import ErrorState from '../components/feedback/ErrorState.tsx'
import LoadingState from '../components/feedback/LoadingState.tsx'
import PlantingMap from '../components/map/PlantingMap.tsx'
import RegionLayer from '../components/map/RegionLayer.tsx'
import { useRegions } from '../hooks/useRegions.ts'
import { regionsBounds } from '../utils/geo.ts'

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
 * `PlantingMap` (issue #16) + `RegionLayer` (issue #17), now wired to real
 * loading/error/empty feedback (issue #18): a dead backend renders
 * `ErrorState`, not a blank page, and the map fits its viewport to the
 * fetched canteiros' bounding box on load.
 */
function MapPage() {
  const { data, isPending, isError } = useRegions()
  const bounds = useMemo(() => (data ? regionsBounds(data) : undefined), [data])

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

  if (data.features.length === 0) {
    return (
      <MapPageShell>
        <EmptyState message="Nenhum canteiro cadastrado ainda." />
      </MapPageShell>
    )
  }

  return (
    <MapPageShell>
      <PlantingMap className="flex-1" bounds={bounds}>
        <RegionLayer data={data} />
      </PlantingMap>
    </MapPageShell>
  )
}

export default MapPage
