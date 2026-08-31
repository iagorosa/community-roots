import { useQuery } from '@tanstack/react-query'
import { fetchPlanting } from '../services/plantings'

// `id: string | null` — `MapPage` passes `null` when no pin is selected, so
// this stays disabled instead of fetching a made-up id.
export function usePlanting(id: string | null) {
  return useQuery({
    queryKey: ['planting', id],
    queryFn: () => fetchPlanting(id as string),
    enabled: id !== null,
  })
}
