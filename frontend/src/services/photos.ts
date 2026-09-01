import type { Photo, PhotoPage } from '../types/api'
import { apiFetch } from './apiClient'

export interface FetchPlantingPhotosParams {
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
  // Issue #38 (LGPD, docs/architecture.md §9): the two `PhotoUploadForm`
  // checkboxes — "this photo includes an identifiable person" and "I have
  // the guardian's authorization" — both default to false for the same
  // reason `shareLocation` does above. The backend
  // (`photo_upload_service.upload_photo`) re-validates the pairing; this
  // type only carries the values through.
  includesIdentifiablePerson?: boolean
  identifiablePersonConsentConfirmed?: boolean
}

// `identifier` is a Planting id (no slug — see types/api.ts's PlantingProperties comment).
export function fetchPlantingPhotos(
  identifier: string,
  params?: FetchPlantingPhotosParams,
): Promise<PhotoPage> {
  const query = new URLSearchParams()
  if (params?.cursor !== undefined) {
    query.set('cursor', params.cursor)
  }
  if (params?.limit !== undefined) {
    query.set('limit', String(params.limit))
  }

  const queryString = query.toString()
  const path = `/api/plantings/${identifier}/photos${queryString ? `?${queryString}` : ''}`
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
  formData.set('includes_identifiable_person', String(params.includesIdentifiablePerson ?? false))
  formData.set(
    'identifiable_person_consent_confirmed',
    String(params.identifiablePersonConsentConfirmed ?? false),
  )

  return apiFetch<Photo>(`/api/plantings/${identifier}/photos`, {
    method: 'POST',
    body: formData,
  })
}
