import type { RegionFeature, RegionFeatureCollection } from '../types/api'
import { apiFetch } from './apiClient'

export function fetchRegions(): Promise<RegionFeatureCollection> {
  return apiFetch<RegionFeatureCollection>('/api/regions')
}

// `identifier` accepts either a slug or a UUID — the backend resolves both
// (backend/app/services/region_service.py::get_region). A 404 surfaces as
// an `ApiError` with `status: 404`, which `RegionPage` distinguishes from
// other failures to show `NotFoundPage` instead of a generic error.
export function fetchRegion(identifier: string): Promise<RegionFeature> {
  return apiFetch<RegionFeature>(`/api/regions/${identifier}`)
}
