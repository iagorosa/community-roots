import { useParams } from 'react-router'
import EmptyState from '../components/feedback/EmptyState.tsx'
import ErrorState from '../components/feedback/ErrorState.tsx'
import LoadingState from '../components/feedback/LoadingState.tsx'
import PlantingMap from '../components/map/PlantingMap.tsx'
import PhotoTimeline from '../components/photos/PhotoTimeline.tsx'
import { usePhotos } from '../hooks/usePhotos.ts'
import { useRegion } from '../hooks/useRegion.ts'
import { ApiError } from '../services/apiClient.ts'
import { regionCenter } from '../utils/geo.ts'
import NotFoundPage from './NotFoundPage.tsx'

// Photo upload lands in Fase 5 (issue #69 tracks the backend `photo_count`
// gap this page just displays as-is). Disabled here rather than hidden, so
// a visiting family knows the feature exists and is coming, not that it's
// missing — architecture.md §8: interface text stays in plain Portuguese,
// no internal phase numbers.
function PhotoUploadSection() {
  return (
    <div className="mt-6">
      <button
        type="button"
        disabled
        className="cursor-not-allowed rounded-lg bg-slate-300 px-6 py-3 font-semibold text-slate-500"
      >
        Enviar foto
      </button>
      <p className="mt-2 text-sm text-slate-500">Em breve você vai poder enviar fotos daqui.</p>
    </div>
  )
}

// The photo timeline (issue #24) fails or loads independently of the rest
// of the page: a slow/broken photos endpoint shouldn't take down a canteiro
// page whose name, description, and map already loaded fine. So this gets
// its own scoped loading/error/empty states, separate from `RegionPage`'s
// (which only ever concern the region itself).
function PhotoTimelineSection({ identifier }: { identifier: string }) {
  const { data, isPending, isError } = usePhotos(identifier)

  if (isPending) {
    return <LoadingState message="Carregando fotos..." />
  }

  if (isError) {
    return <ErrorState message="Não foi possível carregar as fotos. Tente novamente mais tarde." />
  }

  if (data.items.length === 0) {
    return (
      <EmptyState message="Esse canteiro ainda não tem foto, mas em breve você vai poder enviar uma." />
    )
  }

  return <PhotoTimeline photos={data.items} />
}

function RegionPage() {
  const { slug } = useParams<{ slug: string }>()
  // `useRegion` always gets a defined `identifier`: the route only matches
  // with a `:slug` segment present (`AppRoutes.tsx`), so `slug` is never
  // actually undefined at render time — the fallback just satisfies the
  // (string | undefined) type from `useParams`.
  const { data, error, isPending, isError } = useRegion(slug ?? '')

  if (isPending) {
    return <LoadingState message="Carregando canteiro..." />
  }

  // `isError` also fires for a background refetch that fails *after* a
  // prior successful load (e.g. `refetchOnWindowFocus`, on by default in
  // App.tsx's QueryClient) — same tradeoff `MapPage.tsx` makes, but more
  // jarring here: a loaded canteiro swaps to a full-page `NotFoundPage`
  // rather than a map staying stale. Accepted for now since it only bites
  // when a region goes from active to hidden/deleted mid-visit; revisit
  // with `isLoadingError` if that turns out to be disruptive in practice.
  if (isError) {
    if (error instanceof ApiError && error.status === 404) {
      return <NotFoundPage />
    }
    return <ErrorState message="Não foi possível carregar este canteiro. Tente novamente mais tarde." />
  }

  const { properties } = data
  const photoCountLabel = properties.photo_count === 1 ? '1 foto' : `${properties.photo_count} fotos`

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-4 bg-slate-50 px-4 py-8">
      <h1 className="text-3xl font-bold text-emerald-700">{properties.name}</h1>

      {properties.description && (
        <p data-testid="region-description" className="text-slate-700">
          {properties.description}
        </p>
      )}

      <p className="text-slate-600">{photoCountLabel}</p>

      <div className="aspect-video w-full overflow-hidden rounded-lg">
        <PlantingMap className="h-full" center={regionCenter(data)} />
      </div>

      <PhotoUploadSection />

      <div className="mt-4 flex flex-col gap-3">
        <h2 className="text-xl font-bold text-emerald-700">Fotos</h2>
        <PhotoTimelineSection identifier={slug ?? ''} />
      </div>
    </div>
  )
}

export default RegionPage
