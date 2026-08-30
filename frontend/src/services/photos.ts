import type { Photo, PhotoPage } from '../types/api'
import { apiFetch } from './apiClient'

export interface FetchRegionPhotosParams {
  cursor?: string
  limit?: number
}

export interface UploadPhotoParams {
  file: File
  description?: string
  contributorName?: string
  // Opt-in, defaults to false either way — but spelled out explicitly here
  // (rather than relying on the backend's own `Form(default=False)`)
  // because the checkbox this comes from must start unchecked
  // (docs/architecture.md §6.2), and this makes that the caller's default
  // too, not just the UI's.
  shareLocation?: boolean
}

// `identifier` accepts either a slug or a UUID, same as `fetchRegion`
// (backend/app/services/region_service.py::get_region resolves both, and
// this route delegates to it — backend/app/services/photo_service.py).
export function fetchRegionPhotos(
  identifier: string,
  params?: FetchRegionPhotosParams,
): Promise<PhotoPage> {
  const query = new URLSearchParams()
  if (params?.cursor !== undefined) {
    query.set('cursor', params.cursor)
  }
  if (params?.limit !== undefined) {
    query.set('limit', String(params.limit))
  }

  const queryString = query.toString()
  const path = `/api/regions/${identifier}/photos${queryString ? `?${queryString}` : ''}`
  return apiFetch<PhotoPage>(path)
}

// Sends `FormData`, not JSON — the endpoint is multipart
// (backend/app/api/routes/photos.py::upload_photo). `apiFetch` is passed the
// `FormData` as-is with no `Content-Type` header set, so the browser fills
// it in itself with the multipart boundary the backend needs to parse the
// body; setting it manually here would omit that boundary and break parsing.
export function uploadPhoto(identifier: string, params: UploadPhotoParams): Promise<Photo> {
  const formData = new FormData()
  formData.set('file', params.file)
  if (params.description) {
    formData.set('description', params.description)
  }
  if (params.contributorName) {
    formData.set('contributor_name', params.contributorName)
  }
  formData.set('share_location', String(params.shareLocation ?? false))

  return apiFetch<Photo>(`/api/regions/${identifier}/photos`, {
    method: 'POST',
    body: formData,
  })
}
