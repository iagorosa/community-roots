import EmptyState from '../feedback/EmptyState.tsx'
import ErrorState from '../feedback/ErrorState.tsx'
import LoadingState from '../feedback/LoadingState.tsx'
import PhotoTimeline from '../photos/PhotoTimeline.tsx'
import PhotoUploadForm from '../photos/PhotoUploadForm.tsx'
import { usePhotos } from '../../hooks/usePhotos.ts'
import { usePlanting } from '../../hooks/usePlanting.ts'

interface PlantingDetailPanelProps {
  plantingId: string
}

// Same split `RegionPage.tsx` used to have (moved here, generalized to
// Planting): the timeline fails or loads independently of the rest of the
// panel, with its own scoped loading/error/empty states.
function PhotoTimelineSection({ plantingId }: { plantingId: string }) {
  const { data, isPending, isError } = usePhotos(plantingId)

  if (isPending) {
    return <LoadingState message="Carregando fotos..." />
  }
  if (isError) {
    return <ErrorState message="Não foi possível carregar as fotos. Tente novamente mais tarde." />
  }
  if (data.items.length === 0) {
    return (
      <EmptyState message="Essa muda ainda não tem foto, mas em breve você vai poder enviar uma." />
    )
  }
  return <PhotoTimeline photos={data.items} />
}

/** The content of `PlantingDetailDrawer` (Task 6) — everything about one
 * Planting: who planted it, its species, and its photo timeline/upload
 * form. Fetching/loading/error states live here, not in the drawer shell,
 * so the drawer stays a pure presentational container. */
function PlantingDetailPanel({ plantingId }: PlantingDetailPanelProps) {
  const { data, isPending, isError } = usePlanting(plantingId)

  if (isPending) {
    return <LoadingState message="Carregando muda..." />
  }
  if (isError) {
    return <ErrorState message="Não foi possível carregar esta muda. Tente novamente mais tarde." />
  }

  const { properties } = data
  const title = properties.nickname ?? properties.species ?? 'Muda sem nome'
  const showSpeciesLine = Boolean(properties.species) && properties.species !== title

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-2xl font-bold text-emerald-700">{title}</h2>

      {showSpeciesLine && <p className="text-slate-600">{properties.species}</p>}
      {properties.planted_by && <p className="text-sm text-slate-500">Plantada por {properties.planted_by}</p>}

      <PhotoUploadForm plantingId={plantingId} />

      <div className="mt-2 flex flex-col gap-3">
        <h3 className="text-lg font-bold text-emerald-700">Fotos</h3>
        <PhotoTimelineSection plantingId={plantingId} />
      </div>
    </div>
  )
}

export default PlantingDetailPanel
