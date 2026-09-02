import { Link, useParams } from 'react-router'
import EmptyState from '../components/feedback/EmptyState.tsx'
import ErrorState from '../components/feedback/ErrorState.tsx'
import LoadingState from '../components/feedback/LoadingState.tsx'
import PlantingMap from '../components/map/PlantingMap.tsx'
import { usePlantings } from '../hooks/usePlantings.ts'
import { useRegion } from '../hooks/useRegion.ts'
import { ApiError } from '../services/apiClient.ts'
import { regionCenter } from '../utils/geo.ts'
import NotFoundPage from './NotFoundPage.tsx'

// The planting list fails or loads independently of the rest of the page —
// same split the old photo timeline used, generalized: a slow/broken
// plantings endpoint shouldn't take down a region page whose name and map
// already loaded fine.
function PlantingListSection({ regionId }: { regionId: string }) {
  const { data, isPending, isError } = usePlantings(regionId)

  if (isPending) {
    return <LoadingState message="Carregando mudas..." />
  }
  if (isError) {
    return <ErrorState message="Não foi possível carregar as mudas. Tente novamente mais tarde." />
  }
  if (data.features.length === 0) {
    return <EmptyState message="Essa região ainda não tem muda cadastrada." />
  }

  return (
    <ul className="flex flex-col gap-2">
      {data.features.map((feature) => (
        <li key={feature.id}>
          {/* `hover:border-emerald-600`, not `-400` (issue #35): `-400`
              measures 1.92:1 against this white background, under WCAG
              1.4.11's 3:1 floor for a UI-component boundary; `-600` clears
              it at 3.77:1 and matches the border color used elsewhere in
              the app (e.g. PhotoUploadForm's file-picker button). */}
          <Link
            to={`/mapa?planting=${feature.id}`}
            className="flex flex-col rounded-md border border-slate-200 p-3 text-slate-700 hover:border-emerald-600"
          >
            <span className="font-semibold">
              {feature.properties.nickname ?? feature.properties.species ?? 'Muda sem nome'}
            </span>
            {feature.properties.species && feature.properties.nickname && (
              <span className="text-sm text-slate-500">{feature.properties.species}</span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  )
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

  if (isError) {
    if (error instanceof ApiError && error.status === 404) {
      return <NotFoundPage />
    }
    return <ErrorState message="Não foi possível carregar este canteiro. Tente novamente mais tarde." />
  }

  const { properties } = data
  const plantingCountLabel =
    properties.planting_count === 1 ? '1 muda' : `${properties.planting_count} mudas`

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-4 bg-slate-50 px-4 py-8">
      <h1 className="text-3xl font-bold text-emerald-700">{properties.name}</h1>

      {properties.description && (
        <p data-testid="region-description" className="text-slate-700">
          {properties.description}
        </p>
      )}

      <p className="text-slate-600">{plantingCountLabel}</p>

      <div className="aspect-video w-full overflow-hidden rounded-lg">
        <PlantingMap className="h-full" center={regionCenter(data)} />
      </div>

      {/* `flex min-h-11 items-center` (issue #34): the bare underlined text
          measured ~20px tall, well under the 44px touch-target floor. */}
      <div className="flex flex-col">
        <a
          href={`/api/regions/${slug}/qr-code`}
          target="_blank"
          rel="noreferrer"
          className="flex min-h-11 items-center text-sm text-emerald-700 underline"
        >
          Baixar QR Code da região
        </a>
        {/* Issue #135: folha imprimível com um QR Code por muda, em vez do
            caminho manual (baixar cada QR individualmente e montar a folha
            num editor de texto). */}
        <Link
          to={`/regions/${slug}/print`}
          className="flex min-h-11 items-center text-sm text-emerald-700 underline"
        >
          Imprimir folha de QR Codes
        </Link>
      </div>

      <div className="mt-4 flex flex-col gap-3">
        <h2 className="text-xl font-bold text-emerald-700">Mudas</h2>
        <PlantingListSection regionId={data.id} />
      </div>
    </div>
  )
}

export default RegionPage
