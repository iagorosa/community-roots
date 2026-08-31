import { useQuery } from '@tanstack/react-query'
import { fetchPlantings } from '../services/plantings'

export function usePlantings(regionId?: string) {
  return useQuery({
    queryKey: ['plantings', regionId ?? 'all'],
    queryFn: () => fetchPlantings(regionId !== undefined ? { regionId } : undefined),
  })
}
