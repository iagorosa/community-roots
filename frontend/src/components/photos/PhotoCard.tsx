import type { Photo } from '../../types/api'
import { formatDateTimeLabel } from '../../utils/date.ts'

interface PhotoCardProps {
  photo: Photo
}

/** One photo in a canteiro's timeline (issue #24).
 *
 * **Layout-shift prevention**: `width`/`height` are set as the `<img>`
 * element's native HTML attributes (not just CSS) — that's what lets the
 * browser compute and reserve the image's aspect-ratio box before any bytes
 * arrive, so the page around it doesn't jump once it loads. `className="h-
 * auto w-full"` then makes the rendered image responsive (full card width,
 * proportional height) without fighting that reserved box.
 */
function PhotoCard({ photo }: PhotoCardProps) {
  return (
    <figure className="overflow-hidden rounded-lg bg-white shadow-sm">
      <img
        src={photo.photo_url}
        width={photo.width}
        height={photo.height}
        alt={photo.description ?? 'Foto do canteiro'}
        className="h-auto w-full"
      />
      <figcaption className="flex flex-col gap-1 p-3 text-sm">
        <span className="text-slate-500">{formatDateTimeLabel(photo.uploaded_at)}</span>
        {photo.contributor_name && <span className="text-slate-600">{photo.contributor_name}</span>}
        {photo.description && <p className="text-slate-700">{photo.description}</p>}
      </figcaption>
    </figure>
  )
}

export default PhotoCard
