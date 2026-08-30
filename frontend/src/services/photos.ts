import type { PhotoPage } from '../types/api'
import { apiFetch } from './apiClient'

export interface FetchRegionPhotosParams {
  cursor?: string
  limit?: number
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
