import type { RegionFeatureCollection } from '../types/api'
import { apiFetch } from './apiClient'

export function fetchRegions(): Promise<RegionFeatureCollection> {
  return apiFetch<RegionFeatureCollection>('/api/regions')
}
