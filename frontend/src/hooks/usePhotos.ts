import { useQuery } from '@tanstack/react-query'
import { fetchPlantingPhotos } from '../services/photos'

// Fetches only the first page (the backend's default `limit`, currently
// 20 — `backend/app/services/photo_service.py::DEFAULT_PAGE_SIZE`), with
// no "load more"/infinite-scroll UI. Issue #24's literal scope never
// mentions in-UI pagination, a fresh canteiro's timeline realistically
// stays well under one page for a long time, and keyset pagination is
// already exercised end-to-end by the backend tests — so a "load more"
// control would add UI and test surface without the issue asking for it.
// Revisit if canteiros start regularly exceeding one page.
export function usePhotos(identifier: string) {
  return useQuery({
    queryKey: ['photos', identifier],
    queryFn: () => fetchPlantingPhotos(identifier),
  })
}
