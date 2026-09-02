import { useParams } from 'react-router'
import EmptyState from '../components/feedback/EmptyState.tsx'
import ErrorState from '../components/feedback/ErrorState.tsx'
import LoadingState from '../components/feedback/LoadingState.tsx'
import { usePlantings } from '../hooks/usePlantings.ts'
import { useRegion } from '../hooks/useRegion.ts'
import { ApiError } from '../services/apiClient.ts'
import type { PlantingFeature } from '../types/api'
import NotFoundPage from './NotFoundPage.tsx'

// One printable card, shared shape for both the region's own QR code (the
// "entrance sign") and each planting's QR code below it. `break-inside-avoid`
// (print-only, but harmless on screen too) is the one rule this whole page
// exists for: without it, a browser's paginator is free to slice a card
// across the page boundary, leaving half a QR code unscannable on paper.
function PrintableCard({ qrSrc, alt, title, subtitle }: { qrSrc: string; alt: string; title: string; subtitle?: string }) {
  return (
    <div className="flex break-inside-avoid flex-col items-center gap-2 rounded-lg border border-slate-200 p-4 text-center print:border-slate-400">
      <img src={qrSrc} alt={alt} className="h-40 w-40" />
      <span className="font-semibold text-slate-800">{title}</span>
      {subtitle && <span className="text-sm text-slate-500">{subtitle}</span>}
    </div>
  )
}

// Split from `RegionPrintPage` the same way `RegionPage` splits off
// `PlantingListSection`: the plantings request fails or loads independently
// of the region itself, so a slow/broken plantings endpoint shouldn't block
// the region's own QR card (or a region with zero plantings) from printing.
function PrintablePlantingsSection({ regionId }: { regionId: string }) {
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
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 print:grid-cols-2">
      {data.features.map((feature: PlantingFeature) => {
        const label = feature.properties.nickname ?? feature.properties.species ?? 'Muda sem nome'
        return (
          <PrintableCard
            key={feature.id}
            qrSrc={`/api/plantings/${feature.id}/qr-code`}
            alt={`QR Code da muda ${label}`}
            title={label}
            subtitle={
              feature.properties.species && feature.properties.nickname ? feature.properties.species : undefined
            }
          />
        )
      })}
    </div>
  )
}

// Route `/regions/:slug/print` (issue #135) — a printable A4 sheet with one
// card per active `Planting` in the region, plus an optional card for the
// region's own QR code (an "entrance sign" for the whole area). Replaces the
// manual "download each QR code and paste it into a slideshow" workflow that
// `docs/organizer-guide.md` documented while this page didn't exist yet.
function RegionPrintPage() {
  const { slug } = useParams<{ slug: string }>()
  // Same non-null assertion rationale as `RegionPage`: the route only
  // matches with a `:slug` segment present (`AppRoutes.tsx`).
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

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 bg-slate-50 px-4 py-8 print:bg-white print:px-0 print:py-0">
      {/* `print:hidden`: page chrome that only makes sense on screen —
          Layout's header is hidden separately, in index.css, since it lives
          outside this component's subtree. */}
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-3xl font-bold text-emerald-700">{properties.name}</h1>
          <p className="text-slate-600">Folha de impressão de QR Codes</p>
        </div>
        {/* `min-h-11 min-w-11` (issue #34 convention, see RegionPage.tsx). */}
        <button
          type="button"
          onClick={() => window.print()}
          className="flex min-h-11 min-w-11 items-center justify-center rounded-md bg-emerald-700 px-4 text-sm font-semibold text-white hover:bg-emerald-800"
        >
          Imprimir
        </button>
      </div>

      {/* `flex justify-center`, not the plantings grid below: the entrance
          sign is a single card and reads as more intentional standing on
          its own row than sharing a 2/3-column grid with empty cells beside
          it (code review, issue #135). */}
      <div className="flex justify-center">
        <PrintableCard
          qrSrc={`/api/regions/${slug}/qr-code`}
          alt={`QR Code do canteiro ${properties.name}`}
          title={properties.name}
          subtitle="Placa de entrada do canteiro"
        />
      </div>

      <h2 className="text-xl font-bold text-emerald-700 print:hidden">Mudas</h2>
      <PrintablePlantingsSection regionId={data.id} />
    </div>
  )
}

export default RegionPrintPage
