import { useQuery } from '@tanstack/react-query'
import { fetchRegion } from '../services/regions'

// Separate from `useRegions` (plural) rather than one hook with an
// optional param: the two have different query keys, error handling
// (`RegionPage` special-cases a 404 into `NotFoundPage`), and callers.
export function useRegion(identifier: string) {
  return useQuery({
    queryKey: ['region', identifier],
    queryFn: () => fetchRegion(identifier),
  })
}
