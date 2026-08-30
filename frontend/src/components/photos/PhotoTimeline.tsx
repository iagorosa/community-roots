import type { Photo } from '../../types/api'
import { groupPhotosByDate } from '../../utils/photos.ts'
import PhotoCard from './PhotoCard.tsx'

interface PhotoTimelineProps {
  photos: Photo[]
}

/** A canteiro's photo history (issue #24), grouped into one section per
 * day via `groupPhotosByDate` (`utils/photos.ts`). Presentational only —
 * `RegionPage` owns fetching (`usePhotos`) and the loading/error/empty
 * states, the same split `MapPage`/`RegionLayer` use for regions. */
function PhotoTimeline({ photos }: PhotoTimelineProps) {
  const groups = groupPhotosByDate(photos)

  return (
    <div className="flex flex-col gap-6">
      {groups.map((group) => (
        <section key={group.dateLabel} className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-slate-700">{group.dateLabel}</h3>
          <div className="flex flex-col gap-4">
            {group.photos.map((photo) => (
              <PhotoCard key={photo.id} photo={photo} />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

export default PhotoTimeline
