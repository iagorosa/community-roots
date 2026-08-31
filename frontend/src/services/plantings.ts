import type { PlantingFeature, PlantingFeatureCollection } from '../types/api'
import { apiFetch } from './apiClient'

export interface FetchPlantingsParams {
  regionId?: string
}

export function fetchPlantings(params?: FetchPlantingsParams): Promise<PlantingFeatureCollection> {
  const query = new URLSearchParams()
  if (params?.regionId !== undefined) {
    query.set('region_id', params.regionId)
  }
  const queryString = query.toString()
  return apiFetch<PlantingFeatureCollection>(`/api/plantings${queryString ? `?${queryString}` : ''}`)
}

export function fetchPlanting(id: string): Promise<PlantingFeature> {
  return apiFetch<PlantingFeature>(`/api/plantings/${id}`)
}
