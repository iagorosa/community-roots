import type { Photo } from '../types/api'
import { formatDateLabel } from './date.ts'

export interface PhotoDateGroup {
  /** The group's `Intl`-formatted day, e.g. "24 de agosto de 2026" — also
   * usable as a React key, since it's unique per day by construction. */
  dateLabel: string
  photos: Photo[]
}

/**
 * Buckets `photos` by calendar day (`uploaded_at`, always present —
 * `captured_at` can be `null` when a photo has no EXIF data), most-recent
 * day first, and most-recent photo first within a day. Sorts its own
 * input rather than trusting caller order: the backend's `/photos`
 * endpoint already returns `uploaded_at DESC`, but this shouldn't silently
 * depend on that to group correctly.
 */
export function groupPhotosByDate(photos: Photo[]): PhotoDateGroup[] {
  const sorted = [...photos].sort(
    (a, b) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime(),
  )

  const groups: PhotoDateGroup[] = []
  for (const photo of sorted) {
    const dateLabel = formatDateLabel(photo.uploaded_at)
    const currentGroup = groups.at(-1)
    if (currentGroup?.dateLabel === dateLabel) {
      currentGroup.photos.push(photo)
    } else {
      groups.push({ dateLabel, photos: [photo] })
    }
  }
  return groups
}
