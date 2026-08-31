# Region/Planting Frontend Pivot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the map experience around individual `Planting` pins clustered inside `Region` boundaries, with a planting's details opening in a drawer (desktop) / bottom sheet (mobile) instead of a full-page navigation, plus a collapsible region sidebar and a repaginated `RegionPage` overview.

**Architecture:** Depends on the backend plan (`docs/superpowers/plans/2026-08-30-region-planting-backend.md`) being implemented first — every service call in this plan targets `/api/plantings/*` and `/api/qr/{token}`, which don't exist until that plan lands. `PlantingClusterLayer` (new) sits alongside the existing `RegionLayer` inside `PlantingMap`; clicking a pin sets a `?planting=` search param on `/mapa`, which `MapPage` reads to open `PlantingDetailDrawer` — the same mechanism a scanned Planting QR code uses to land directly on the right pin. `PlantingDetailDrawer` is a single `vaul` `Drawer.Root` whose `direction` switches between `'bottom'` and `'right'` by viewport width, rather than two separate drawer implementations.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4, Leaflet/react-leaflet 5, `@tanstack/react-query`, react-router 8, Vitest + Testing Library. New: `react-leaflet-cluster` (marker clustering), `leaflet.markercluster` (its peer, for the cluster CSS), `vaul` (drawer/bottom-sheet primitive).

## Global Constraints

- Code, identifiers, comments in English; user-facing text in Brazilian Portuguese (matches every existing component).
- Run frontend commands from `frontend/` (`npm test`, `npm run build`, `npm run lint`).
- Every task that changes a shared type/service must also fix any existing test file that breaks as a direct result — noted explicitly per task. Two known exceptions, called out where they first appear: `RegionPage.test.tsx` (rewritten whole in Task 10) and the single `AppRoutes.test.tsx` case exercising `/regions/:slug` (fixed alongside it, also Task 10) — both stay red starting Task 1 until then; every other test stays green after every task.
- Reuse `apiFetch` (`services/apiClient.ts`) for every network call — never call `fetch` directly from a component or hook.
- This plan assumes the backend plan is fully implemented and its endpoints (`/api/plantings`, `/api/plantings/{id}`, `/api/plantings/{id}/photos`, `/api/plantings/{id}/qr-code`, `/api/qr/{token}`, `GET /api/regions` returning `planting_count`) are live — Task 1's tests mock `fetch`/the service layer, so nothing here needs a running backend to pass, but manual verification (Task 11's Step 6) does.

---

## Task 1: Types, services, and hooks for `Planting`/QR; `Region` gains `planting_count`

**Files:**
- Modify: `frontend/src/types/api.ts`
- Create: `frontend/src/services/plantings.ts`
- Create: `frontend/src/services/qr.ts`
- Modify: `frontend/src/services/photos.ts`
- Create: `frontend/src/hooks/usePlantings.ts`
- Create: `frontend/src/hooks/usePlanting.ts`
- Create: `frontend/src/hooks/useQrResolution.ts`
- Modify: `frontend/src/hooks/usePhotos.ts`
- Test: `frontend/src/services/plantings.test.ts`
- Test: `frontend/src/services/qr.test.ts`
- Modify: `frontend/src/services/photos.test.ts`
- Modify: `frontend/src/hooks/usePhotos.test.tsx`
- Test: `frontend/src/hooks/usePlantings.test.tsx`
- Test: `frontend/src/hooks/usePlanting.test.tsx`
- Test: `frontend/src/hooks/useQrResolution.test.tsx`
- Modify: `frontend/src/utils/geo.test.ts`, `frontend/src/hooks/useRegion.test.tsx`, `frontend/src/services/regions.test.ts`, `frontend/src/components/map/RegionLayer.test.tsx`, `frontend/src/pages/MapPage.test.tsx`, `frontend/src/AppRoutes.test.tsx` (mechanical `photo_count`/`latest_photo_at` → `planting_count` fixture fix only)

**Interfaces:**
- Produces: `PlantingStatus`, `PlantingGeometry`, `PlantingProperties`, `PlantingFeature`, `PlantingFeatureCollection`, `QrResolution` (all in `types/api.ts`); `fetchPlantings(params?: { regionId?: string }): Promise<PlantingFeatureCollection>`; `fetchPlanting(id: string): Promise<PlantingFeature>`; `resolveQrToken(token: string): Promise<QrResolution>`; `fetchPlantingPhotos(identifier: string, params?: FetchPlantingPhotosParams): Promise<PhotoPage>` (renamed from `fetchRegionPhotos`); `usePlantings(regionId?: string)`; `usePlanting(id: string | null)`; `useQrResolution(token: string)`.
- `RegionProperties.photo_count`/`.latest_photo_at` are removed; `RegionProperties.planting_count: number` is added.

- [ ] **Step 1: Write the failing test for the new `Planting`/QR types and services**

Create `frontend/src/services/plantings.test.ts`:

```tsx
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PlantingFeature, PlantingFeatureCollection } from '../types/api'
import { fetchPlanting, fetchPlantings } from './plantings'

const SAMPLE_FEATURE: PlantingFeature = {
  type: 'Feature',
  id: '1a2b3c4d-5e6f-7890-abcd-ef1234567890',
  geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
  properties: {
    region_id: '0f1c1234-5678-90ab-cdef-1234567890ab',
    species: 'Ipê-amarelo',
    nickname: 'A árvore da Ana',
    planted_by: 'Ana',
    planted_at: '2026-08-01T10:00:00Z',
    status: 'active',
    qr_token: 'k3Zq8xR2mNvA',
    photo_count: 0,
    latest_photo_at: null,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
}

const SAMPLE_COLLECTION: PlantingFeatureCollection = { type: 'FeatureCollection', features: [SAMPLE_FEATURE] }

function stubFetchResolving(body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('fetchPlantings', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests GET /api/plantings with no query params by default', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_COLLECTION)

    const result = await fetchPlantings()

    expect(fetchMock).toHaveBeenCalledWith('/api/plantings', undefined)
    expect(result).toEqual(SAMPLE_COLLECTION)
  })

  it('includes region_id as a query param when given', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_COLLECTION)

    await fetchPlantings({ regionId: '0f1c1234-5678-90ab-cdef-1234567890ab' })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/plantings?region_id=0f1c1234-5678-90ab-cdef-1234567890ab',
      undefined,
    )
  })
})

describe('fetchPlanting', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests GET /api/plantings/{id} and returns the typed feature', async () => {
    const fetchMock = stubFetchResolving(SAMPLE_FEATURE)

    const result = await fetchPlanting('1a2b3c4d-5e6f-7890-abcd-ef1234567890')

    expect(fetchMock).toHaveBeenCalledWith('/api/plantings/1a2b3c4d-5e6f-7890-abcd-ef1234567890', undefined)
    expect(result).toEqual(SAMPLE_FEATURE)
  })
})
```

Create `frontend/src/services/qr.test.ts`:

```tsx
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { QrResolution } from '../types/api'
import { resolveQrToken } from './qr'

describe('resolveQrToken', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests GET /api/qr/{token} and returns the typed resolution', async () => {
    const resolution: QrResolution = { type: 'planting', identifier: '1a2b3c4d-5e6f-7890-abcd-ef1234567890' }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(resolution) } as Response)
    vi.stubGlobal('fetch', fetchMock)

    const result = await resolveQrToken('k3Zq8xR2mNvA')

    expect(fetchMock).toHaveBeenCalledWith('/api/qr/k3Zq8xR2mNvA', undefined)
    expect(result).toEqual(resolution)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- plantings.test.ts qr.test.ts`
Expected: FAIL — `Cannot find module './plantings'` / `'./qr'`.

- [ ] **Step 3: Update `types/api.ts`**

Replace `RegionProperties`:

```tsx
// The `properties` object of a region `Feature`.
// `created_at`/`updated_at` are ISO 8601 strings over the wire — parse with
// `new Date(...)` at the point of use, not here.
export interface RegionProperties {
  slug: string
  name: string
  description: string | null
  status: RegionStatus
  qr_token: string
  planting_count: number
  created_at: string
  updated_at: string
}
```

Append, after the `RegionFeature`/`RegionFeatureCollection` exports:

```tsx
// Mirrors backend/app/schemas/planting.py. A Planting has no slug — it's
// resolved by id only (backend/app/services/planting_service.py).
export type PlantingStatus = 'active' | 'draft' | 'archived'

// Same three shapes `Region` allows (`ck_plantings_geom_type`) — a
// Planting starts as a Point but may become a Polygon later.
export type PlantingGeometry = Point | Polygon | MultiPolygon

export interface PlantingProperties {
  region_id: string
  species: string | null
  nickname: string | null
  planted_by: string | null
  planted_at: string | null
  status: PlantingStatus
  qr_token: string
  photo_count: number
  latest_photo_at: string | null
  created_at: string
  updated_at: string
}

export type PlantingFeature = Feature<PlantingGeometry, PlantingProperties>
export type PlantingFeatureCollection = FeatureCollection<PlantingGeometry, PlantingProperties>

// Mirrors backend/app/api/routes/qr.py::QrResolution — what a scanned QR
// token resolves to. `identifier` is a region's slug or a planting's id;
// the frontend decides the destination path from `type` alone.
export interface QrResolution {
  type: 'region' | 'planting'
  identifier: string
}
```

- [ ] **Step 4: Write `services/plantings.ts` and `services/qr.ts`**

Create `frontend/src/services/plantings.ts`:

```tsx
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
```

Create `frontend/src/services/qr.ts`:

```tsx
import type { QrResolution } from '../types/api'
import { apiFetch } from './apiClient'

export function resolveQrToken(token: string): Promise<QrResolution> {
  return apiFetch<QrResolution>(`/api/qr/${token}`)
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test -- plantings.test.ts qr.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 6: Write the failing test for `usePlantings`/`usePlanting`/`useQrResolution`**

Create `frontend/src/hooks/usePlantings.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import * as plantingsService from '../services/plantings'
import type { PlantingFeatureCollection } from '../types/api'
import { usePlantings } from './usePlantings'

const SAMPLE_COLLECTION: PlantingFeatureCollection = { type: 'FeatureCollection', features: [] }

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('usePlantings', () => {
  it('fetches every planting when no region is given', async () => {
    const fetchSpy = vi.spyOn(plantingsService, 'fetchPlantings').mockResolvedValue(SAMPLE_COLLECTION)

    const { result } = renderHook(() => usePlantings(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchSpy).toHaveBeenCalledWith(undefined)
  })

  it('fetches only a region\'s plantings when regionId is given', async () => {
    const fetchSpy = vi.spyOn(plantingsService, 'fetchPlantings').mockResolvedValue(SAMPLE_COLLECTION)

    const { result } = renderHook(() => usePlantings('0f1c1234-5678-90ab-cdef-1234567890ab'), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchSpy).toHaveBeenCalledWith({ regionId: '0f1c1234-5678-90ab-cdef-1234567890ab' })
  })
})
```

Create `frontend/src/hooks/usePlanting.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import * as plantingsService from '../services/plantings'
import type { PlantingFeature } from '../types/api'
import { usePlanting } from './usePlanting'

const SAMPLE_FEATURE = { type: 'Feature', id: 'p1' } as unknown as PlantingFeature

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('usePlanting', () => {
  it('fetches the planting when an id is given', async () => {
    const fetchSpy = vi.spyOn(plantingsService, 'fetchPlanting').mockResolvedValue(SAMPLE_FEATURE)

    const { result } = renderHook(() => usePlanting('p1'), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchSpy).toHaveBeenCalledWith('p1')
  })

  it('does not fetch when id is null', () => {
    const fetchSpy = vi.spyOn(plantingsService, 'fetchPlanting')

    renderHook(() => usePlanting(null), { wrapper: createWrapper() })

    expect(fetchSpy).not.toHaveBeenCalled()
  })
})
```

Create `frontend/src/hooks/useQrResolution.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import * as qrService from '../services/qr'
import type { QrResolution } from '../types/api'
import { useQrResolution } from './useQrResolution'

const SAMPLE_RESOLUTION: QrResolution = { type: 'region', identifier: 'canteiro-do-ipe' }

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useQrResolution', () => {
  it('resolves the given token through the qr service', async () => {
    const resolveSpy = vi.spyOn(qrService, 'resolveQrToken').mockResolvedValue(SAMPLE_RESOLUTION)

    const { result } = renderHook(() => useQrResolution('k3Zq8xR2mNvA'), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(resolveSpy).toHaveBeenCalledWith('k3Zq8xR2mNvA')
    expect(result.current.data).toEqual(SAMPLE_RESOLUTION)
  })
})
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `npm test -- usePlantings.test.tsx usePlanting.test.tsx useQrResolution.test.tsx`
Expected: FAIL — modules don't exist yet.

- [ ] **Step 8: Write the three hooks**

Create `frontend/src/hooks/usePlantings.ts`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { fetchPlantings } from '../services/plantings'

export function usePlantings(regionId?: string) {
  return useQuery({
    queryKey: ['plantings', regionId ?? 'all'],
    queryFn: () => fetchPlantings(regionId !== undefined ? { regionId } : undefined),
  })
}
```

Create `frontend/src/hooks/usePlanting.ts`:

```tsx
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
```

Create `frontend/src/hooks/useQrResolution.ts`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { resolveQrToken } from '../services/qr'

export function useQrResolution(token: string) {
  return useQuery({
    queryKey: ['qr-resolution', token],
    queryFn: () => resolveQrToken(token),
  })
}
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `npm test -- usePlantings.test.tsx usePlanting.test.tsx useQrResolution.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 10: Rename `fetchRegionPhotos` to `fetchPlantingPhotos` and update its path**

Edit `frontend/src/services/photos.test.ts` — rename every `fetchRegionPhotos` import/call to `fetchPlantingPhotos`, and every expected URL from `/api/regions/canteiro-do-ipe/photos...` to `/api/plantings/canteiro-do-ipe/photos...` (the identifier itself is just a string in these unit tests — swapping the URL segment is enough, no need to change the sample identifier value). Do the same for the `uploadPhoto` describe block's expected path (`/api/plantings/canteiro-do-ipe/photos`).

Edit `frontend/src/hooks/usePhotos.test.tsx` — rename the spied function:

```tsx
const fetchSpy = vi.spyOn(photosService, 'fetchPlantingPhotos').mockResolvedValue(SAMPLE_PAGE)
```

(the rest of that test file is unchanged — same query key, same call pattern).

- [ ] **Step 11: Run tests to verify they fail**

Run: `npm test -- photos.test.ts usePhotos.test.tsx`
Expected: FAIL — `fetchPlantingPhotos` doesn't exist yet in `services/photos.ts`.

- [ ] **Step 12: Update `services/photos.ts`**

```tsx
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
  shareLocation?: boolean
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

  return apiFetch<Photo>(`/api/plantings/${identifier}/photos`, {
    method: 'POST',
    body: formData,
  })
}
```

- [ ] **Step 13: Update `hooks/usePhotos.ts`**

```tsx
import { useQuery } from '@tanstack/react-query'
import { fetchPlantingPhotos } from '../services/photos'

export function usePhotos(identifier: string) {
  return useQuery({
    queryKey: ['photos', identifier],
    queryFn: () => fetchPlantingPhotos(identifier),
  })
}
```

- [ ] **Step 14: Run tests to verify they pass**

Run: `npm test -- photos.test.ts usePhotos.test.tsx`
Expected: PASS

- [ ] **Step 15: Fix the mechanical `RegionProperties` fixture breakage**

In each of these files, replace the two fixture fields `photo_count: <n>, latest_photo_at: null,` with `planting_count: <n>,` (same value `<n>` the old `photo_count` had) everywhere a `RegionProperties`/`RegionFeature`/`RegionFeatureCollection` object literal is built:

- `frontend/src/utils/geo.test.ts` — `BASE_PROPERTIES`.
- `frontend/src/hooks/useRegion.test.tsx` — `SAMPLE_FEATURE`.
- `frontend/src/services/regions.test.ts` — `SAMPLE_FEATURE`.
- `frontend/src/components/map/RegionLayer.test.tsx` — `SAMPLE_COLLECTION`.
- `frontend/src/pages/MapPage.test.tsx` — `SAMPLE_COLLECTION`.
- `frontend/src/AppRoutes.test.tsx` — `SAMPLE_REGION`.

None of these five files' *assertions* reference `photo_count` (only `RegionPopup.test.tsx`/`RegionPage.test.tsx` do, handled in Tasks 3 and 10 respectively), so this is a pure fixture-shape fix — no other line changes in these five files.

- [ ] **Step 16: Run the full suite**

Run: `npm test`
Expected: every file passes except `AppRoutes.test.tsx` — exactly one failing case in it, `resolves /regions/:slug to the region page...` (it renders the real, not-yet-updated `RegionPage`, which still reads `properties.photo_count`; fixed in Task 10) — and `RegionPage.test.tsx`, all of it (rewritten whole in Task 10). Confirm no other file regressed.

- [ ] **Step 17: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/services/plantings.ts frontend/src/services/qr.ts \
  frontend/src/services/photos.ts frontend/src/hooks/usePlantings.ts frontend/src/hooks/usePlanting.ts \
  frontend/src/hooks/useQrResolution.ts frontend/src/hooks/usePhotos.ts \
  frontend/src/services/plantings.test.ts frontend/src/services/qr.test.ts frontend/src/services/photos.test.ts \
  frontend/src/hooks/usePhotos.test.tsx frontend/src/hooks/usePlantings.test.tsx frontend/src/hooks/usePlanting.test.tsx \
  frontend/src/hooks/useQrResolution.test.tsx frontend/src/utils/geo.test.ts frontend/src/hooks/useRegion.test.tsx \
  frontend/src/services/regions.test.ts frontend/src/components/map/RegionLayer.test.tsx \
  frontend/src/pages/MapPage.test.tsx frontend/src/AppRoutes.test.tsx
git commit -m "feat: adiciona camada de API de Planting e migra fotos para planting_id"
```

---

## Task 2: Add `react-leaflet-cluster`, `leaflet.markercluster`, and `vaul`

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`

**Interfaces:**
- Produces: the three packages installed and importable in later tasks.

- [ ] **Step 1: Install**

Run:
```bash
npm install react-leaflet-cluster@4.1.3 leaflet.markercluster@1.5.3 vaul@1.1.2
```

- [ ] **Step 2: Verify the install didn't break the existing build/tests**

Run:
```bash
npm run build
npm test
```
Expected: both succeed, unchanged from before this task (this task adds no application code yet — Tasks 5 and 6 are the first to import these packages).

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: adiciona react-leaflet-cluster, leaflet.markercluster e vaul"
```

---

## Task 3: `RegionPopup` shows `planting_count`

**Files:**
- Modify: `frontend/src/components/map/RegionPopup.tsx`
- Modify: `frontend/src/components/map/RegionPopup.test.tsx`

**Interfaces:**
- Consumes: `RegionProperties.planting_count` (Task 1).

- [ ] **Step 1: Update the failing test first**

Edit `frontend/src/components/map/RegionPopup.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { RegionProperties } from '../../types/api'
import RegionPopup from './RegionPopup.tsx'

const PROPERTIES: RegionProperties = {
  slug: 'canteiro-do-ipe',
  name: 'Canteiro do Ipê',
  description: null,
  status: 'active',
  qr_token: 'k3Zq8xR2mNvA',
  planting_count: 3,
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
}

describe('RegionPopup', () => {
  it('shows the region name', () => {
    render(<RegionPopup properties={PROPERTIES} />)

    expect(screen.getByText('Canteiro do Ipê')).toBeInTheDocument()
  })

  it('shows the planting count, pluralized', () => {
    render(<RegionPopup properties={PROPERTIES} />)

    expect(screen.getByText('3 mudas')).toBeInTheDocument()
  })

  it('shows "1 muda" in the singular for exactly one planting', () => {
    render(<RegionPopup properties={{ ...PROPERTIES, planting_count: 1 }} />)

    expect(screen.getByText('1 muda')).toBeInTheDocument()
  })

  it('links to the region page', () => {
    render(<RegionPopup properties={PROPERTIES} />)

    expect(screen.getByRole('link', { name: /ver canteiro/i })).toHaveAttribute(
      'href',
      '/regions/canteiro-do-ipe',
    )
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- RegionPopup.test.tsx`
Expected: FAIL — `getByText('3 mudas')` finds nothing (component still renders "3 fotos").

- [ ] **Step 3: Update `RegionPopup.tsx`**

```tsx
import type { RegionProperties } from '../../types/api'

interface RegionPopupProps {
  properties: RegionProperties
}

/**
 * Static content only — no `onClick`/`<Link>` here. `RegionLayer` renders
 * this to a plain HTML string for Leaflet's imperative `bindPopup`, which
 * sits outside the app's React tree (no Router context to resolve a
 * `<Link>` against), so this is a real `<a href>` instead.
 */
function RegionPopup({ properties }: RegionPopupProps) {
  const plantingCountLabel =
    properties.planting_count === 1 ? '1 muda' : `${properties.planting_count} mudas`

  return (
    <div>
      <p className="font-semibold text-slate-800">{properties.name}</p>
      <p className="text-sm text-slate-600">{plantingCountLabel}</p>
      <a href={`/regions/${properties.slug}`} className="text-sm text-emerald-700 underline">
        Ver canteiro
      </a>
    </div>
  )
}

export default RegionPopup
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- RegionPopup.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/map/RegionPopup.tsx frontend/src/components/map/RegionPopup.test.tsx
git commit -m "feat: RegionPopup mostra contagem de mudas em vez de fotos"
```

---

## Task 4: `useMediaQuery` hook

**Files:**
- Create: `frontend/src/hooks/useMediaQuery.ts`
- Test: `frontend/src/hooks/useMediaQuery.test.tsx`
- Modify: `frontend/src/test/setup.ts`

**Interfaces:**
- Produces: `useMediaQuery(query: string): boolean`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/hooks/useMediaQuery.test.tsx`:

```tsx
import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useMediaQuery } from './useMediaQuery'

// A minimal fake `MediaQueryList` — jsdom has no real layout engine to
// evaluate a media query against, so this stands in for the browser and is
// driven manually per test via `changeListener(...)`.
function fakeMediaQueryList(initialMatches: boolean) {
  let matches = initialMatches
  let changeListener: ((event: MediaQueryListEvent) => void) | undefined

  const list = {
    get matches() {
      return matches
    },
    addEventListener: vi.fn((_event: string, listener: (event: MediaQueryListEvent) => void) => {
      changeListener = listener
    }),
    removeEventListener: vi.fn(),
  }

  return {
    list: list as unknown as MediaQueryList,
    fireChange(nextMatches: boolean) {
      matches = nextMatches
      changeListener?.({ matches: nextMatches } as MediaQueryListEvent)
    },
  }
}

describe('useMediaQuery', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns the media query\'s initial match state', () => {
    const { list } = fakeMediaQueryList(true)
    vi.spyOn(window, 'matchMedia').mockReturnValue(list)

    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))

    expect(result.current).toBe(true)
  })

  it('updates when the media query match state changes', () => {
    const { list, fireChange } = fakeMediaQueryList(false)
    vi.spyOn(window, 'matchMedia').mockReturnValue(list)

    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))
    expect(result.current).toBe(false)

    act(() => fireChange(true))

    expect(result.current).toBe(true)
  })

  it('removes the change listener on unmount', () => {
    const { list } = fakeMediaQueryList(false)
    vi.spyOn(window, 'matchMedia').mockReturnValue(list)

    const { unmount } = renderHook(() => useMediaQuery('(min-width: 768px)'))
    unmount()

    expect(list.removeEventListener).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- useMediaQuery.test.tsx`
Expected: FAIL — `Cannot find module './useMediaQuery'`.

- [ ] **Step 3: Ensure `window.matchMedia` exists in jsdom for every test**

jsdom doesn't implement `window.matchMedia` at all — every consumer (`useMediaQuery` here, and `vaul`'s `Drawer.Root` in Task 6) needs some implementation present, even a no-op one, or it throws `TypeError: window.matchMedia is not a function` the instant it's called, in tests that don't otherwise care about it. Edit `frontend/src/test/setup.ts`, add before the existing `afterEach`:

```tsx
// jsdom has no real layout engine, so it never implements `matchMedia` —
// this default (never matches, does nothing on listen) is a safe stand-in
// for any test that renders something using it but doesn't care about its
// result. Tests that DO care (useMediaQuery.test.tsx, PlantingDetailDrawer's
// tests) override this per-test with `vi.spyOn(window, 'matchMedia')`.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }) as MediaQueryList
}
```

- [ ] **Step 4: Write `useMediaQuery.ts`**

```tsx
import { useEffect, useState } from 'react'

/** Tracks whether `query` currently matches, updating live as the viewport
 * changes — the one place `PlantingDetailDrawer` (Task 6) asks "are we on
 * desktop?" to pick the bottom-sheet vs. right-drawer direction. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)

  useEffect(() => {
    const mediaQueryList = window.matchMedia(query)
    setMatches(mediaQueryList.matches)

    function handleChange(event: MediaQueryListEvent) {
      setMatches(event.matches)
    }

    mediaQueryList.addEventListener('change', handleChange)
    return () => mediaQueryList.removeEventListener('change', handleChange)
  }, [query])

  return matches
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test -- useMediaQuery.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full suite**

Run: `npm test`
Expected: no new failures beyond the two already-known ones from Task 1 Step 16.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/hooks/useMediaQuery.ts frontend/src/hooks/useMediaQuery.test.tsx frontend/src/test/setup.ts
git commit -m "feat: adiciona hook useMediaQuery"
```

---

## Task 5: `PlantingClusterLayer`

**Files:**
- Create: `frontend/src/components/map/PlantingClusterLayer.tsx`
- Test: `frontend/src/components/map/PlantingClusterLayer.test.tsx`

**Interfaces:**
- Consumes: `PlantingFeatureCollection` (Task 1).
- Produces: `<PlantingClusterLayer data={PlantingFeatureCollection} onSelect={(plantingId: string) => void} />`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/map/PlantingClusterLayer.test.tsx`:

```tsx
import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { PlantingFeatureCollection } from '../../types/api'
import PlantingClusterLayer from './PlantingClusterLayer.tsx'

type MarkerProps = { position: [number, number]; eventHandlers?: { click?: () => void } }

let capturedMarkers: MarkerProps[] = []

vi.mock('react-leaflet', () => ({
  Marker: (props: MarkerProps) => {
    capturedMarkers.push(props)
    return null
  },
}))

vi.mock('react-leaflet-cluster', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="cluster-group">{children}</div>,
}))

const SAMPLE_COLLECTION: PlantingFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: 'p1',
      geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
      properties: {
        region_id: 'r1',
        species: null,
        nickname: null,
        planted_by: null,
        planted_at: null,
        status: 'active',
        qr_token: 'tok-1',
        photo_count: 0,
        latest_photo_at: null,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

describe('PlantingClusterLayer', () => {
  it('renders one marker per planting, in [lat, lon] order', () => {
    capturedMarkers = []

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={vi.fn()} />)

    expect(capturedMarkers).toHaveLength(1)
    expect(capturedMarkers[0]?.position).toEqual([-21.8843, -43.3129])
  })

  it('calls onSelect with the planting id when its marker is clicked', () => {
    capturedMarkers = []
    const onSelect = vi.fn()

    render(<PlantingClusterLayer data={SAMPLE_COLLECTION} onSelect={onSelect} />)
    capturedMarkers[0]?.eventHandlers?.click?.()

    expect(onSelect).toHaveBeenCalledWith('p1')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- PlantingClusterLayer.test.tsx`
Expected: FAIL — `Cannot find module './PlantingClusterLayer.tsx'`.

- [ ] **Step 3: Write `PlantingClusterLayer.tsx`**

```tsx
// Imported here, alongside `react-leaflet-cluster`'s own JS — CSS for the
// cluster bubbles it renders. `leaflet/dist/leaflet.css` is already
// imported once, in `PlantingMap.tsx`; these two are that same "import
// once" rule applied to the new library.
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'

import { Marker } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import type { PlantingFeatureCollection } from '../../types/api'

interface PlantingClusterLayerProps {
  data: PlantingFeatureCollection
  onSelect: (plantingId: string) => void
}

function toLatLng(coordinates: [number, number]): [number, number] {
  const [longitude, latitude] = coordinates
  return [latitude, longitude]
}

/** Pins for every Planting, clustered with a count bubble when several sit
 * close together at the current zoom — the map-zoom-levels decision from
 * the pivot design spec. Sits alongside `RegionLayer` inside `PlantingMap`,
 * never inside it: Region boundaries and Planting pins are independent
 * layers on the same map. */
function PlantingClusterLayer({ data, onSelect }: PlantingClusterLayerProps) {
  return (
    <MarkerClusterGroup>
      {data.features.map((feature) => {
        // A Planting's geometry may become a Polygon later (see
        // types/api.ts's PlantingGeometry comment) — today it's always a
        // Point, which is all a marker pin can plot anyway.
        if (feature.geometry.type !== 'Point') return null

        return (
          <Marker
            key={feature.id}
            position={toLatLng(feature.geometry.coordinates)}
            eventHandlers={{ click: () => onSelect(feature.id) }}
          />
        )
      })}
    </MarkerClusterGroup>
  )
}

export default PlantingClusterLayer
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- PlantingClusterLayer.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/map/PlantingClusterLayer.tsx frontend/src/components/map/PlantingClusterLayer.test.tsx
git commit -m "feat: adiciona PlantingClusterLayer com clustering de mudas no mapa"
```

---

## Task 6: `PlantingDetailDrawer`

**Files:**
- Create: `frontend/src/components/plantings/PlantingDetailDrawer.tsx`
- Test: `frontend/src/components/plantings/PlantingDetailDrawer.test.tsx`

**Interfaces:**
- Consumes: `useMediaQuery` (Task 4).
- Produces: `<PlantingDetailDrawer open={boolean} onClose={() => void}>{children}</PlantingDetailDrawer>`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/plantings/PlantingDetailDrawer.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PlantingDetailDrawer from './PlantingDetailDrawer.tsx'

function stubDesktop(isDesktop: boolean) {
  vi.spyOn(window, 'matchMedia').mockReturnValue({
    matches: isDesktop,
    media: '',
    addEventListener: () => {},
    removeEventListener: () => {},
  } as unknown as MediaQueryList)
}

describe('PlantingDetailDrawer', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders its children when open', () => {
    stubDesktop(true)

    render(
      <PlantingDetailDrawer open onClose={vi.fn()}>
        <p>Conteúdo da muda</p>
      </PlantingDetailDrawer>,
    )

    expect(screen.getByText('Conteúdo da muda')).toBeInTheDocument()
  })

  it('does not render its children when closed', () => {
    stubDesktop(true)

    render(
      <PlantingDetailDrawer open={false} onClose={vi.fn()}>
        <p>Conteúdo da muda</p>
      </PlantingDetailDrawer>,
    )

    expect(screen.queryByText('Conteúdo da muda')).not.toBeInTheDocument()
  })

  it('calls onClose when dismissed', () => {
    stubDesktop(true)
    const onClose = vi.fn()

    render(
      <PlantingDetailDrawer open onClose={onClose}>
        <p>Conteúdo da muda</p>
      </PlantingDetailDrawer>,
    )
    // vaul's overlay is the click-outside-to-dismiss target.
    fireEvent.click(screen.getByTestId('drawer-overlay'))

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- PlantingDetailDrawer.test.tsx`
Expected: FAIL — `Cannot find module './PlantingDetailDrawer.tsx'`.

- [ ] **Step 3: Write `PlantingDetailDrawer.tsx`**

```tsx
import type { ReactNode } from 'react'
import { Drawer } from 'vaul'
import { useMediaQuery } from '../../hooks/useMediaQuery.ts'

const DESKTOP_QUERY = '(min-width: 768px)'

interface PlantingDetailDrawerProps {
  open: boolean
  onClose: () => void
  children: ReactNode
}

/** A Planting's details, shown over the map instead of a full-page
 * navigation — the pivot design spec's "drawer (desktop) / bottom sheet
 * (mobile)" decision. One `vaul` `Drawer.Root`, not two implementations:
 * only `direction` changes with viewport width, so both keep the map
 * visible behind them by construction. */
function PlantingDetailDrawer({ open, onClose, children }: PlantingDetailDrawerProps) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)

  return (
    <Drawer.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onClose()
      }}
      direction={isDesktop ? 'right' : 'bottom'}
    >
      <Drawer.Portal>
        <Drawer.Overlay data-testid="drawer-overlay" className="fixed inset-0 z-[1100] bg-black/40" />
        <Drawer.Content
          className={
            isDesktop
              ? 'fixed inset-y-0 right-0 z-[1101] flex w-full max-w-md flex-col bg-white shadow-xl outline-none'
              : 'fixed inset-x-0 bottom-0 z-[1101] flex max-h-[85vh] flex-col rounded-t-2xl bg-white outline-none'
          }
        >
          <Drawer.Title className="sr-only">Detalhes da muda</Drawer.Title>
          <div className="flex-1 overflow-y-auto p-4">{children}</div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  )
}

export default PlantingDetailDrawer
```

(`z-[1100]`/`z-[1101]`: above Leaflet's own panes, which top out around `z-index: 1000` — otherwise the map's zoom controls/attribution can paint over the drawer.)

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- PlantingDetailDrawer.test.tsx`
Expected: PASS (3 tests). If the dismiss test fails because vaul doesn't render `Drawer.Overlay` synchronously with `open`, add `waitFor(() => screen.getByTestId('drawer-overlay'))` around the click in that one test rather than changing the component.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/plantings/PlantingDetailDrawer.tsx frontend/src/components/plantings/PlantingDetailDrawer.test.tsx
git commit -m "feat: adiciona PlantingDetailDrawer (bottom sheet no mobile, drawer no desktop)"
```

---

## Task 7: `PlantingDetailPanel` and `PhotoUploadForm`'s `plantingId` rename

**Files:**
- Create: `frontend/src/components/plantings/PlantingDetailPanel.tsx`
- Test: `frontend/src/components/plantings/PlantingDetailPanel.test.tsx`
- Modify: `frontend/src/components/photos/PhotoUploadForm.tsx`
- Modify: `frontend/src/components/photos/PhotoUploadForm.test.tsx`

**Interfaces:**
- Consumes: `usePlanting`, `usePhotos` (Task 1), `PhotoTimeline`, `PhotoUploadForm` (existing, one prop renamed here).
- Produces: `<PlantingDetailPanel plantingId={string} />`. `<PhotoUploadForm plantingId={string} />` (renamed from `slug`).

- [ ] **Step 1: Update the failing `PhotoUploadForm` test first**

Edit `frontend/src/components/photos/PhotoUploadForm.test.tsx`:

- Replace `render(<PhotoUploadForm slug="canteiro-do-ipe" />, ...)` with `render(<PhotoUploadForm plantingId="1a2b3c4d-5e6f-7890-abcd-ef1234567890" />, ...)`.
- Replace the expected upload path `/api/regions/canteiro-do-ipe/photos` with `/api/plantings/1a2b3c4d-5e6f-7890-abcd-ef1234567890/photos`.
- Replace the expected invalidated query key `['photos', 'canteiro-do-ipe']` with `['photos', '1a2b3c4d-5e6f-7890-abcd-ef1234567890']`.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- PhotoUploadForm.test.tsx`
Expected: FAIL — TypeScript/prop mismatch surfaces as the component receiving no `slug` (its old required prop), so `useUploadPhoto(slug)` is called with `undefined`, and the asserted paths/query keys don't match.

- [ ] **Step 3: Rename the prop in `PhotoUploadForm.tsx`**

Edit `frontend/src/components/photos/PhotoUploadForm.tsx`:

```tsx
interface PhotoUploadFormProps {
  plantingId: string
}
```

```tsx
function PhotoUploadForm({ plantingId }: PhotoUploadFormProps) {
```

```tsx
  const { mutate, isPending, isError, error, reset } = useUploadPhoto(plantingId)
```

(no other line in this file references `slug` — confirm with `grep slug frontend/src/components/photos/PhotoUploadForm.tsx` after editing; it should print nothing.)

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- PhotoUploadForm.test.tsx`
Expected: PASS

- [ ] **Step 5: Write the failing `PlantingDetailPanel` test**

Create `frontend/src/components/plantings/PlantingDetailPanel.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PhotoPage, PlantingFeature } from '../../types/api'
import PlantingDetailPanel from './PlantingDetailPanel.tsx'

const SAMPLE_PLANTING: PlantingFeature = {
  type: 'Feature',
  id: '1a2b3c4d-5e6f-7890-abcd-ef1234567890',
  geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
  properties: {
    region_id: '0f1c1234-5678-90ab-cdef-1234567890ab',
    species: 'Ipê-amarelo',
    nickname: 'A árvore da Ana',
    planted_by: 'Ana',
    planted_at: '2026-08-01T10:00:00Z',
    status: 'active',
    qr_token: 'k3Zq8xR2mNvA',
    photo_count: 0,
    latest_photo_at: null,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
}

const EMPTY_PHOTO_PAGE: PhotoPage = { items: [], next_cursor: null }

function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: () => Promise.resolve(body) } as Response
}

function stubFetch(planting: unknown, photos: unknown = EMPTY_PHOTO_PAGE) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => Promise.resolve(jsonResponse(url.includes('/photos') ? photos : planting))),
  )
}

function renderPanel(plantingId = SAMPLE_PLANTING.id) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <PlantingDetailPanel plantingId={plantingId} />
    </QueryClientProvider>,
  )
}

describe('PlantingDetailPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the nickname as the title, and the species below it', async () => {
    stubFetch(SAMPLE_PLANTING)

    renderPanel()

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'A árvore da Ana' })).toBeInTheDocument(),
    )
    expect(screen.getByText('Ipê-amarelo')).toBeInTheDocument()
  })

  it('falls back to species as the title when there is no nickname', async () => {
    stubFetch({ ...SAMPLE_PLANTING, properties: { ...SAMPLE_PLANTING.properties, nickname: null } })

    renderPanel()

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Ipê-amarelo' })).toBeInTheDocument(),
    )
  })

  it('shows who planted it, when known', async () => {
    stubFetch(SAMPLE_PLANTING)

    renderPanel()

    await waitFor(() => expect(screen.getByText('Plantada por Ana')).toBeInTheDocument())
  })

  it('renders the photo upload form scoped to this planting', async () => {
    stubFetch(SAMPLE_PLANTING)

    renderPanel()

    expect(await screen.findByRole('button', { name: /enviar foto/i })).toBeDisabled()
  })

  it('shows an empty state for the photo timeline when there are no photos', async () => {
    stubFetch(SAMPLE_PLANTING, EMPTY_PHOTO_PAGE)

    renderPanel()

    expect(await screen.findByText(/ainda não tem foto/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npm test -- PlantingDetailPanel.test.tsx`
Expected: FAIL — `Cannot find module './PlantingDetailPanel.tsx'`.

- [ ] **Step 7: Write `PlantingDetailPanel.tsx`**

```tsx
import EmptyState from '../feedback/EmptyState.tsx'
import ErrorState from '../feedback/ErrorState.tsx'
import LoadingState from '../feedback/LoadingState.tsx'
import PhotoTimeline from '../photos/PhotoTimeline.tsx'
import PhotoUploadForm from '../photos/PhotoUploadForm.tsx'
import { usePhotos } from '../../hooks/usePhotos.ts'
import { usePlanting } from '../../hooks/usePlanting.ts'

interface PlantingDetailPanelProps {
  plantingId: string
}

// Same split `RegionPage.tsx` used to have (moved here, generalized to
// Planting): the timeline fails or loads independently of the rest of the
// panel, with its own scoped loading/error/empty states.
function PhotoTimelineSection({ plantingId }: { plantingId: string }) {
  const { data, isPending, isError } = usePhotos(plantingId)

  if (isPending) {
    return <LoadingState message="Carregando fotos..." />
  }
  if (isError) {
    return <ErrorState message="Não foi possível carregar as fotos. Tente novamente mais tarde." />
  }
  if (data.items.length === 0) {
    return (
      <EmptyState message="Essa muda ainda não tem foto, mas em breve você vai poder enviar uma." />
    )
  }
  return <PhotoTimeline photos={data.items} />
}

/** The content of `PlantingDetailDrawer` (Task 6) — everything about one
 * Planting: who planted it, its species, and its photo timeline/upload
 * form. Fetching/loading/error states live here, not in the drawer shell,
 * so the drawer stays a pure presentational container. */
function PlantingDetailPanel({ plantingId }: PlantingDetailPanelProps) {
  const { data, isPending, isError } = usePlanting(plantingId)

  if (isPending) {
    return <LoadingState message="Carregando muda..." />
  }
  if (isError) {
    return <ErrorState message="Não foi possível carregar esta muda. Tente novamente mais tarde." />
  }

  const { properties } = data
  const title = properties.nickname ?? properties.species ?? 'Muda sem nome'
  const showSpeciesLine = Boolean(properties.species) && properties.species !== title

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-2xl font-bold text-emerald-700">{title}</h2>

      {showSpeciesLine && <p className="text-slate-600">{properties.species}</p>}
      {properties.planted_by && <p className="text-sm text-slate-500">Plantada por {properties.planted_by}</p>}

      <PhotoUploadForm plantingId={plantingId} />

      <div className="mt-2 flex flex-col gap-3">
        <h3 className="text-lg font-bold text-emerald-700">Fotos</h3>
        <PhotoTimelineSection plantingId={plantingId} />
      </div>
    </div>
  )
}

export default PlantingDetailPanel
```

- [ ] **Step 8: Run test to verify it passes**

Run: `npm test -- PlantingDetailPanel.test.tsx`
Expected: PASS (5 tests)

- [ ] **Step 9: Run the full suite**

Run: `npm test`
Expected: no new failures beyond the two already-known ones from Task 1 Step 16.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/plantings/PlantingDetailPanel.tsx frontend/src/components/plantings/PlantingDetailPanel.test.tsx \
  frontend/src/components/photos/PhotoUploadForm.tsx frontend/src/components/photos/PhotoUploadForm.test.tsx
git commit -m "feat: adiciona PlantingDetailPanel e renomeia PhotoUploadForm para plantingId"
```

---

## Task 8: `MapPage` wires the cluster layer and the detail drawer

**Files:**
- Modify: `frontend/src/pages/MapPage.tsx`
- Modify: `frontend/src/pages/MapPage.test.tsx`

**Interfaces:**
- Consumes: `usePlantings` (Task 1), `PlantingClusterLayer` (Task 5), `PlantingDetailDrawer` (Task 6), `PlantingDetailPanel` (Task 7).
- Produces: `/mapa?planting=<id>` opens the drawer for that planting on load — the mechanism `QrRedirectPage` (Task 11) reuses for a scanned Planting QR code.

- [ ] **Step 1: Rewrite the failing test first**

Replace `frontend/src/pages/MapPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PlantingFeatureCollection, RegionFeatureCollection } from '../types/api'
import MapPage from './MapPage'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children, ...props }: Record<string, unknown> & { children?: React.ReactNode }) => (
    <div data-testid="map-container" data-props={JSON.stringify(props)}>
      {children}
    </div>
  ),
  TileLayer: () => null,
  GeoJSON: (props: { data: RegionFeatureCollection }) => (
    <div data-testid="region-layer" data-feature-count={props.data.features.length} />
  ),
  Marker: () => null,
  useMap: () => ({ fitBounds: vi.fn() }),
}))

vi.mock('react-leaflet-cluster', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="planting-layer">{children}</div>,
}))

const SAMPLE_REGIONS: RegionFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: '0f1c1234-5678-90ab-cdef-1234567890ab',
      geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
      properties: {
        slug: 'canteiro-do-ipe',
        name: 'Canteiro do Ipê',
        description: null,
        status: 'active',
        qr_token: 'k3Zq8xR2mNvA',
        planting_count: 1,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

const SAMPLE_PLANTINGS: PlantingFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: '1a2b3c4d-5e6f-7890-abcd-ef1234567890',
      geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
      properties: {
        region_id: '0f1c1234-5678-90ab-cdef-1234567890ab',
        species: 'Ipê-amarelo',
        nickname: null,
        planted_by: null,
        planted_at: null,
        status: 'active',
        qr_token: 'tok-planting',
        photo_count: 0,
        latest_photo_at: null,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: () => Promise.resolve(body) } as Response
}

function stubFetch(options: { regions: unknown; plantings?: unknown; planting?: unknown }) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.startsWith('/api/plantings/')) return Promise.resolve(jsonResponse(options.planting))
      if (url.startsWith('/api/plantings')) {
        return Promise.resolve(jsonResponse(options.plantings ?? { type: 'FeatureCollection', features: [] }))
      }
      return Promise.resolve(jsonResponse(options.regions))
    }),
  )
}

function renderMapPage(initialEntry = '/mapa') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <MapPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('MapPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state while the regions are being fetched', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    renderMapPage()

    expect(screen.getByRole('status')).toHaveTextContent(/carregando/i)
  })

  it('shows an error state instead of a blank page when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    renderMapPage()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.queryByTestId('map-container')).not.toBeInTheDocument()
  })

  it('shows an empty state when there are no canteiros to display', async () => {
    stubFetch({ regions: { type: 'FeatureCollection', features: [] } })

    renderMapPage()

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/nenhum canteiro/i))
  })

  it('renders the region layer and the planting cluster layer with the fetched data', async () => {
    stubFetch({ regions: SAMPLE_REGIONS, plantings: SAMPLE_PLANTINGS })

    renderMapPage()

    await waitFor(() => expect(screen.getByTestId('map-container')).toBeInTheDocument())
    expect(screen.getByTestId('region-layer')).toHaveAttribute('data-feature-count', '1')
    await waitFor(() => expect(screen.getByTestId('planting-layer')).toBeInTheDocument())
  })

  it('opens the planting drawer when ?planting= is present on load', async () => {
    stubFetch({ regions: SAMPLE_REGIONS, plantings: SAMPLE_PLANTINGS, planting: SAMPLE_PLANTINGS.features[0] })

    renderMapPage('/mapa?planting=1a2b3c4d-5e6f-7890-abcd-ef1234567890')

    await waitFor(() => expect(screen.getByText('Ipê-amarelo')).toBeInTheDocument())
  })

  it('keeps the page heading visible in every state', async () => {
    stubFetch({ regions: SAMPLE_REGIONS, plantings: SAMPLE_PLANTINGS })

    renderMapPage()

    expect(screen.getByRole('heading', { name: /mapa/i })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('map-container')).toBeInTheDocument())
    expect(screen.getByRole('heading', { name: /mapa/i })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- MapPage.test.tsx`
Expected: FAIL — no `planting-layer` testid rendered, `?planting=` doesn't open anything yet.

- [ ] **Step 3: Rewrite `MapPage.tsx`**

```tsx
import type { ReactNode } from 'react'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import EmptyState from '../components/feedback/EmptyState.tsx'
import ErrorState from '../components/feedback/ErrorState.tsx'
import LoadingState from '../components/feedback/LoadingState.tsx'
import PlantingMap from '../components/map/PlantingMap.tsx'
import PlantingClusterLayer from '../components/map/PlantingClusterLayer.tsx'
import RegionLayer from '../components/map/RegionLayer.tsx'
import PlantingDetailDrawer from '../components/plantings/PlantingDetailDrawer.tsx'
import PlantingDetailPanel from '../components/plantings/PlantingDetailPanel.tsx'
import { usePlantings } from '../hooks/usePlantings.ts'
import { useRegions } from '../hooks/useRegions.ts'
import { regionsBounds } from '../utils/geo.ts'

const PLANTING_PARAM = 'planting'

function MapPageShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <h1 className="sr-only">Mapa</h1>
      {children}
    </div>
  )
}

/**
 * `PlantingMap` + `RegionLayer` (region boundaries) + `PlantingClusterLayer`
 * (individual mudas, clustered). Clicking a pin — or landing on `/mapa` with
 * `?planting=<id>` already set (`QrRedirectPage`, Task 11, does this for a
 * scanned Planting QR code) — opens `PlantingDetailDrawer`.
 */
function MapPage() {
  const { data: regions, isPending, isError } = useRegions()
  const { data: plantings } = usePlantings()
  const bounds = useMemo(() => (regions ? regionsBounds(regions) : undefined), [regions])

  const [searchParams, setSearchParams] = useSearchParams()
  const selectedPlantingId = searchParams.get(PLANTING_PARAM)

  function openPlanting(plantingId: string) {
    setSearchParams(
      (params) => {
        params.set(PLANTING_PARAM, plantingId)
        return params
      },
      { replace: true },
    )
  }

  function closeDrawer() {
    setSearchParams(
      (params) => {
        params.delete(PLANTING_PARAM)
        return params
      },
      { replace: true },
    )
  }

  if (isPending) {
    return (
      <MapPageShell>
        <LoadingState message="Carregando canteiros..." />
      </MapPageShell>
    )
  }

  // Deliberate tradeoff, not an oversight: `isError` also fires for a
  // background refetch that fails *after* a prior successful load (e.g.
  // `refetchOnWindowFocus`, on by default in App.tsx's QueryClient) — a
  // working, possibly-panned map gets replaced by `ErrorState` rather than
  // kept stale. Simpler than partial-failure UI.
  if (isError) {
    return (
      <MapPageShell>
        <ErrorState message="Não foi possível carregar os canteiros. Tente novamente mais tarde." />
      </MapPageShell>
    )
  }

  if (regions.features.length === 0) {
    return (
      <MapPageShell>
        <EmptyState message="Nenhum canteiro cadastrado ainda." />
      </MapPageShell>
    )
  }

  return (
    <MapPageShell>
      <PlantingMap className="flex-1" bounds={bounds}>
        <RegionLayer data={regions} />
        {plantings && <PlantingClusterLayer data={plantings} onSelect={openPlanting} />}
      </PlantingMap>

      <PlantingDetailDrawer open={selectedPlantingId !== null} onClose={closeDrawer}>
        {selectedPlantingId && <PlantingDetailPanel plantingId={selectedPlantingId} />}
      </PlantingDetailDrawer>
    </MapPageShell>
  )
}

export default MapPage
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- MapPage.test.tsx`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full suite**

Run: `npm test`
Expected: no new failures beyond the two already-known ones from Task 1 Step 16.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/MapPage.tsx frontend/src/pages/MapPage.test.tsx
git commit -m "feat: MapPage renderiza mudas clusterizadas e abre o drawer de detalhe"
```

---

## Task 9: `RegionSidebar`

**Files:**
- Create: `frontend/src/components/map/RegionSidebar.tsx`
- Test: `frontend/src/components/map/RegionSidebar.test.tsx`
- Modify: `frontend/src/pages/MapPage.tsx`
- Modify: `frontend/src/pages/MapPage.test.tsx`

**Interfaces:**
- Consumes: `RegionFeatureCollection` (existing).
- Produces: `<RegionSidebar regions={RegionFeatureCollection} />`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/map/RegionSidebar.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { RegionFeatureCollection } from '../../types/api'
import RegionSidebar from './RegionSidebar.tsx'

const REGIONS: RegionFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: 'r1',
      geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
      properties: {
        slug: 'canteiro-do-ipe',
        name: 'Canteiro do Ipê',
        description: null,
        status: 'active',
        qr_token: 'tok-1',
        planting_count: 12,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
    {
      type: 'Feature',
      id: 'r2',
      geometry: { type: 'Point', coordinates: [-43.32, -21.9] },
      properties: {
        slug: 'canteiro-do-jacaranda',
        name: 'Canteiro do Jacarandá',
        description: null,
        status: 'active',
        qr_token: 'tok-2',
        planting_count: 5,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

function renderSidebar() {
  return render(
    <MemoryRouter>
      <RegionSidebar regions={REGIONS} />
    </MemoryRouter>,
  )
}

describe('RegionSidebar', () => {
  it('lists every region with its planting count', () => {
    renderSidebar()

    expect(screen.getByText('Canteiro do Ipê')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('Canteiro do Jacarandá')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('links each region to its overview page', () => {
    renderSidebar()

    expect(screen.getByRole('link', { name: /canteiro do ipê/i })).toHaveAttribute(
      'href',
      '/regions/canteiro-do-ipe',
    )
  })

  it('filters the list as the user types in the search field', () => {
    renderSidebar()

    fireEvent.change(screen.getByRole('searchbox', { name: /buscar região/i }), {
      target: { value: 'jacar' },
    })

    expect(screen.queryByText('Canteiro do Ipê')).not.toBeInTheDocument()
    expect(screen.getByText('Canteiro do Jacarandá')).toBeInTheDocument()
  })

  it('collapses and re-expands on toggle', () => {
    renderSidebar()

    fireEvent.click(screen.getByRole('button', { name: /esconder lista de regiões/i }))
    expect(screen.queryByText('Canteiro do Ipê')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /mostrar lista de regiões/i }))
    expect(screen.getByText('Canteiro do Ipê')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- RegionSidebar.test.tsx`
Expected: FAIL — `Cannot find module './RegionSidebar.tsx'`.

- [ ] **Step 3: Write `RegionSidebar.tsx`**

```tsx
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import type { RegionFeatureCollection } from '../../types/api'

interface RegionSidebarProps {
  regions: RegionFeatureCollection
}

/** Collapsible list of regions over the map, with a name filter and each
 * region's planting count — the pivot design spec's sidebar decision.
 * Filtering by city is out of scope for now: `Region` has no `city` field
 * yet (see the spec), and there's only one city in the data today. */
function RegionSidebar({ regions }: RegionSidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [search, setSearch] = useState('')

  const filteredFeatures = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return regions.features
    return regions.features.filter((feature) => feature.properties.name.toLowerCase().includes(query))
  }, [regions, search])

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        aria-label="Mostrar lista de regiões"
        className="absolute left-2 top-2 z-[1000] rounded-md bg-white px-3 py-2 text-sm font-semibold text-emerald-700 shadow"
      >
        Regiões
      </button>
    )
  }

  return (
    <aside className="absolute left-2 top-2 z-[1000] flex max-h-[calc(100%-1rem)] w-64 flex-col gap-3 overflow-y-auto rounded-md bg-white p-3 shadow">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-emerald-700">Regiões</h2>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          aria-label="Esconder lista de regiões"
          className="text-sm text-slate-500"
        >
          Esconder
        </button>
      </div>

      <input
        type="search"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Buscar região..."
        aria-label="Buscar região"
        className="rounded-md border border-slate-300 px-2 py-1 text-sm"
      />

      <ul className="flex flex-col gap-1">
        {filteredFeatures.map((feature) => (
          <li key={feature.id}>
            <Link
              to={`/regions/${feature.properties.slug}`}
              className="flex items-center justify-between rounded px-2 py-1 text-sm text-slate-700 hover:bg-emerald-50"
            >
              <span>{feature.properties.name}</span>
              <span className="text-slate-400">{feature.properties.planting_count}</span>
            </Link>
          </li>
        ))}
        {filteredFeatures.length === 0 && (
          <li className="text-sm text-slate-400">Nenhuma região encontrada.</li>
        )}
      </ul>
    </aside>
  )
}

export default RegionSidebar
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- RegionSidebar.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Wire it into `MapPage.tsx`**

`RegionSidebar` is `absolute`-positioned, so it needs a `position: relative` ancestor sized to the map. Edit `frontend/src/pages/MapPage.tsx`'s success-path return:

```tsx
  return (
    <MapPageShell>
      <div className="relative flex-1">
        <PlantingMap className="h-full" bounds={bounds}>
          <RegionLayer data={regions} />
          {plantings && <PlantingClusterLayer data={plantings} onSelect={openPlanting} />}
        </PlantingMap>
        <RegionSidebar regions={regions} />
      </div>

      <PlantingDetailDrawer open={selectedPlantingId !== null} onClose={closeDrawer}>
        {selectedPlantingId && <PlantingDetailPanel plantingId={selectedPlantingId} />}
      </PlantingDetailDrawer>
    </MapPageShell>
  )
```

(`PlantingMap`'s own `className` switches from `flex-1` to `h-full` — it now fills its new `relative` wrapper, which is the thing that's `flex-1` instead.) Add the import:

```tsx
import RegionSidebar from '../components/map/RegionSidebar.tsx'
```

- [ ] **Step 6: Update `MapPage.test.tsx`'s map-container size assertion, if any, and add sidebar coverage**

Append to `frontend/src/pages/MapPage.test.tsx`'s `describe('MapPage', ...)` block:

```tsx
  it('renders the region sidebar alongside the map', async () => {
    stubFetch({ regions: SAMPLE_REGIONS, plantings: SAMPLE_PLANTINGS })

    renderMapPage()

    await waitFor(() => expect(screen.getByText('Canteiro do Ipê')).toBeInTheDocument())
  })
```

- [ ] **Step 7: Run the full suite**

Run: `npm test`
Expected: no new failures beyond the two already-known ones from Task 1 Step 16.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/map/RegionSidebar.tsx frontend/src/components/map/RegionSidebar.test.tsx \
  frontend/src/pages/MapPage.tsx frontend/src/pages/MapPage.test.tsx
git commit -m "feat: adiciona RegionSidebar com busca por região e contagem de mudas"
```

---

## Task 10: `RegionPage` becomes a region overview

**Files:**
- Modify: `frontend/src/pages/RegionPage.tsx`
- Modify: `frontend/src/pages/RegionPage.test.tsx`
- Modify: `frontend/src/AppRoutes.test.tsx` (the one case left red since Task 1)

**Interfaces:**
- Consumes: `usePlantings(regionId)` (Task 1).
- Produces: `RegionPage` shows the region's name/description/`planting_count`, a mini-map, a QR-code download link, and a list of its plantings (each linking to `/mapa?planting=<id>`) — no photo upload/timeline here anymore (that's `PlantingDetailPanel`'s job).

- [ ] **Step 1: Rewrite the failing test first**

Replace `frontend/src/pages/RegionPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PlantingFeatureCollection, RegionFeature } from '../types/api'
import RegionPage from './RegionPage'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children, ...props }: Record<string, unknown> & { children?: ReactNode }) => (
    <div data-testid="map-container" data-props={JSON.stringify(props)}>
      {children}
    </div>
  ),
  TileLayer: () => null,
  useMap: () => ({ fitBounds: vi.fn() }),
}))

const SAMPLE_FEATURE: RegionFeature = {
  type: 'Feature',
  id: '0f1c1234-5678-90ab-cdef-1234567890ab',
  geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
  properties: {
    slug: 'canteiro-do-ipe',
    name: 'Canteiro do Ipê',
    description: 'Um canteiro cheio de ipês amarelos.',
    status: 'active',
    qr_token: 'k3Zq8xR2mNvA',
    planting_count: 1,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
}

const SAMPLE_PLANTINGS: PlantingFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: '1a2b3c4d-5e6f-7890-abcd-ef1234567890',
      geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
      properties: {
        region_id: '0f1c1234-5678-90ab-cdef-1234567890ab',
        species: 'Ipê-amarelo',
        nickname: 'A árvore da Ana',
        planted_by: 'Ana',
        planted_at: '2026-08-01T10:00:00Z',
        status: 'active',
        qr_token: 'tok-planting',
        photo_count: 2,
        latest_photo_at: null,
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      },
    },
  ],
}

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response
}

function stubFetch(options: { region: { body: unknown; status?: number }; plantings?: { body: unknown } }) {
  const fetchMock = vi.fn((url: string) => {
    if (url.startsWith('/api/plantings')) {
      const plantings = options.plantings ?? { body: { type: 'FeatureCollection', features: [] } }
      return Promise.resolve(jsonResponse(plantings.body))
    }
    return Promise.resolve(jsonResponse(options.region.body, options.region.status))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderRegionPage(slug = 'canteiro-do-ipe') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/regions/${slug}`]}>
        <Routes>
          <Route path="/regions/:slug" element={<RegionPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RegionPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state while the region is being fetched', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    renderRegionPage()

    expect(screen.getByRole('status')).toHaveTextContent(/carregando/i)
  })

  it('shows the name, description, and planting count on success', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
    expect(screen.getByText('Um canteiro cheio de ipês amarelos.')).toBeInTheDocument()
    expect(screen.getByText('1 muda')).toBeInTheDocument()
  })

  it('omits the description paragraph when the API returns a null description', async () => {
    const featureWithoutDescription: RegionFeature = {
      ...SAMPLE_FEATURE,
      properties: { ...SAMPLE_FEATURE.properties, description: null },
    }
    stubFetch({ region: { body: featureWithoutDescription } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
    expect(screen.queryByTestId('region-description')).not.toBeInTheDocument()
  })

  it('uses the plural "mudas" when the planting count is not exactly one', async () => {
    const featureWithManyPlantings: RegionFeature = {
      ...SAMPLE_FEATURE,
      properties: { ...SAMPLE_FEATURE.properties, planting_count: 4 },
    }
    stubFetch({ region: { body: featureWithManyPlantings } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByText('4 mudas')).toBeInTheDocument())
  })

  it('renders the mini-map centered on the region', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE } })

    renderRegionPage()

    await waitFor(() => expect(screen.getByTestId('map-container')).toBeInTheDocument())
    const props = JSON.parse(screen.getByTestId('map-container').dataset.props ?? '{}')
    expect(props.center[0]).toBeCloseTo(-21.8843)
    expect(props.center[1]).toBeCloseTo(-43.3129)
  })

  it('links to the region\'s QR code image', async () => {
    stubFetch({ region: { body: SAMPLE_FEATURE } })

    renderRegionPage()

    const link = await screen.findByRole('link', { name: /baixar qr code da região/i })
    expect(link).toHaveAttribute('href', '/api/regions/canteiro-do-ipe/qr-code')
  })

  it('renders NotFoundPage, not a generic error, when the region does not exist', async () => {
    stubFetch({
      region: {
        body: { detail: 'Nenhum canteiro encontrado para "inexistente".', code: 'region_not_found' },
        status: 404,
      },
    })

    renderRegionPage('inexistente')

    await waitFor(() => expect(screen.getByRole('heading', { name: /página não encontrada/i })).toBeInTheDocument())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a generic error state for a non-404 failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    renderRegionPage()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.queryByRole('heading', { name: /página não encontrada/i })).not.toBeInTheDocument()
  })

  describe('planting list', () => {
    it('shows an empty state when the region has no plantings yet', async () => {
      stubFetch({ region: { body: SAMPLE_FEATURE }, plantings: { body: { type: 'FeatureCollection', features: [] } } })

      renderRegionPage()

      await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
      expect(await screen.findByText(/ainda não tem muda/i)).toBeInTheDocument()
    })

    it('lists each planting, linking to its pin on the map', async () => {
      stubFetch({ region: { body: SAMPLE_FEATURE }, plantings: { body: SAMPLE_PLANTINGS } })

      renderRegionPage()

      const link = await screen.findByRole('link', { name: /a árvore da ana/i })
      expect(link).toHaveAttribute('href', '/mapa?planting=1a2b3c4d-5e6f-7890-abcd-ef1234567890')
    })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- RegionPage.test.tsx`
Expected: FAIL — old component still shows "1 foto"/photo timeline, not "1 muda"/planting list.

- [ ] **Step 3: Rewrite `RegionPage.tsx`**

```tsx
import { Link, useParams } from 'react-router'
import EmptyState from '../components/feedback/EmptyState.tsx'
import ErrorState from '../components/feedback/ErrorState.tsx'
import LoadingState from '../components/feedback/LoadingState.tsx'
import PlantingMap from '../components/map/PlantingMap.tsx'
import { usePlantings } from '../hooks/usePlantings.ts'
import { useRegion } from '../hooks/useRegion.ts'
import { ApiError } from '../services/apiClient.ts'
import { regionCenter } from '../utils/geo.ts'
import NotFoundPage from './NotFoundPage.tsx'

// The planting list fails or loads independently of the rest of the page —
// same split the old photo timeline used, generalized: a slow/broken
// plantings endpoint shouldn't take down a region page whose name and map
// already loaded fine.
function PlantingListSection({ regionId }: { regionId: string }) {
  const { data, isPending, isError } = usePlantings(regionId)

  if (isPending) {
    return <LoadingState message="Carregando mudas..." />
  }
  if (isError) {
    return <ErrorState message="Não foi possível carregar as mudas. Tente novamente mais tarde." />
  }
  if (data.features.length === 0) {
    return <EmptyState message="Essa região ainda não tem muda cadastrada." />
  }

  return (
    <ul className="flex flex-col gap-2">
      {data.features.map((feature) => (
        <li key={feature.id}>
          <Link
            to={`/mapa?planting=${feature.id}`}
            className="flex flex-col rounded-md border border-slate-200 p-3 text-slate-700 hover:border-emerald-400"
          >
            <span className="font-semibold">
              {feature.properties.nickname ?? feature.properties.species ?? 'Muda sem nome'}
            </span>
            {feature.properties.species && feature.properties.nickname && (
              <span className="text-sm text-slate-500">{feature.properties.species}</span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  )
}

function RegionPage() {
  const { slug } = useParams<{ slug: string }>()
  // `useRegion` always gets a defined `identifier`: the route only matches
  // with a `:slug` segment present (`AppRoutes.tsx`), so `slug` is never
  // actually undefined at render time — the fallback just satisfies the
  // (string | undefined) type from `useParams`.
  const { data, error, isPending, isError } = useRegion(slug ?? '')

  if (isPending) {
    return <LoadingState message="Carregando canteiro..." />
  }

  if (isError) {
    if (error instanceof ApiError && error.status === 404) {
      return <NotFoundPage />
    }
    return <ErrorState message="Não foi possível carregar este canteiro. Tente novamente mais tarde." />
  }

  const { properties } = data
  const plantingCountLabel =
    properties.planting_count === 1 ? '1 muda' : `${properties.planting_count} mudas`

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-4 bg-slate-50 px-4 py-8">
      <h1 className="text-3xl font-bold text-emerald-700">{properties.name}</h1>

      {properties.description && (
        <p data-testid="region-description" className="text-slate-700">
          {properties.description}
        </p>
      )}

      <p className="text-slate-600">{plantingCountLabel}</p>

      <div className="aspect-video w-full overflow-hidden rounded-lg">
        <PlantingMap className="h-full" center={regionCenter(data)} />
      </div>

      <a
        href={`/api/regions/${slug}/qr-code`}
        target="_blank"
        rel="noreferrer"
        className="text-sm text-emerald-700 underline"
      >
        Baixar QR Code da região
      </a>

      <div className="mt-4 flex flex-col gap-3">
        <h2 className="text-xl font-bold text-emerald-700">Mudas</h2>
        <PlantingListSection regionId={data.id} />
      </div>
    </div>
  )
}

export default RegionPage
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- RegionPage.test.tsx`
Expected: PASS (11 tests)

- [ ] **Step 5: Fix the one `AppRoutes.test.tsx` case left red since Task 1**

Edit `frontend/src/AppRoutes.test.tsx`'s `it('resolves /regions/:slug to the region page with the region matching the slug from the URL', ...)` test. It currently only stubs one `fetch` response for every call; `RegionPage` now also fetches `/api/plantings?region_id=...`, so route the stub by URL like the other tests in this plan do:

```tsx
  it('resolves /regions/:slug to the region page with the region matching the slug from the URL', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        const body = url.startsWith('/api/plantings')
          ? { type: 'FeatureCollection', features: [] }
          : SAMPLE_REGION
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response)
      }),
    )

    renderAtPath('/regions/canteiro-do-ipe')

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
  })
```

Also update `SAMPLE_REGION`'s `properties` in this file: replace `photo_count: 0, latest_photo_at: null,` with `planting_count: 0,` (this was already flagged as a Task 1 fixture fix — confirm it's applied; if Task 1 already did it, this step is a no-op).

- [ ] **Step 6: Run the full suite**

Run: `npm test`
Expected: every test in the entire suite passes — no known-red tests remain.

- [ ] **Step 7: Run the build and lint**

Run:
```bash
npm run build
npm run lint
```
Expected: both succeed with no errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/RegionPage.tsx frontend/src/pages/RegionPage.test.tsx frontend/src/AppRoutes.test.tsx
git commit -m "feat: RegionPage vira overview com lista de mudas em vez de timeline de fotos"
```

---

## Task 11: `QrRedirectPage` resolves via `GET /api/qr/{token}`

**Files:**
- Modify: `frontend/src/pages/QrRedirectPage.tsx`
- Test: `frontend/src/pages/QrRedirectPage.test.tsx`
- Modify: `frontend/src/AppRoutes.test.tsx`

**Interfaces:**
- Consumes: `useQrResolution` (Task 1).
- Produces: `/r/:qrToken` navigates to `/regions/{slug}` for a region token, or `/mapa?planting={id}` for a planting token (opening that planting's drawer via `MapPage`'s Task 8 wiring).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/QrRedirectPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import QrRedirectPage from './QrRedirectPage'

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response
}

function renderAtToken(token: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/r/${token}`]}>
        <Routes>
          <Route path="/r/:qrToken" element={<QrRedirectPage />} />
          <Route path="/regions/:slug" element={<div>Página da região {`{slug}`}</div>} />
          <Route path="/mapa" element={<div data-testid="mapa-page">Mapa</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('QrRedirectPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state while the token is being resolved', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    renderAtToken('k3Zq8xR2mNvA')

    expect(screen.getByRole('status')).toHaveTextContent(/carregando/i)
  })

  it('navigates to /regions/:slug for a region token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ type: 'region', identifier: 'canteiro-do-ipe' })),
    )

    renderAtToken('k3Zq8xR2mNvA')

    await waitFor(() => expect(screen.getByText('Página da região {slug}')).toBeInTheDocument())
  })

  it('navigates to /mapa?planting=<id> for a planting token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ type: 'planting', identifier: '1a2b3c4d-5e6f-7890-abcd-ef1234567890' }),
      ),
    )

    renderAtToken('tok-planting')

    await waitFor(() => expect(screen.getByTestId('mapa-page')).toBeInTheDocument())
  })

  it('shows an error state, not a navigation, for an unknown token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Nenhum QR code encontrado.', code: 'qr_token_not_found' }, 404)),
    )

    renderAtToken('nao-existe')

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- QrRedirectPage.test.tsx`
Expected: FAIL — the current placeholder just shows the raw token text, never navigates.

- [ ] **Step 3: Rewrite `QrRedirectPage.tsx`**

```tsx
import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router'
import ErrorState from '../components/feedback/ErrorState.tsx'
import LoadingState from '../components/feedback/LoadingState.tsx'
import { useQrResolution } from '../hooks/useQrResolution.ts'

/** Resolves a scanned QR token (`GET /api/qr/{token}`) and immediately
 * redirects: a region token goes to its overview page, a planting token
 * goes to `/mapa?planting=<id>` — the same query param `MapPage` (Task 8)
 * reads to open that planting's drawer on load. */
function QrRedirectPage() {
  const { qrToken } = useParams<{ qrToken: string }>()
  const navigate = useNavigate()
  const { data, isPending, isError } = useQrResolution(qrToken ?? '')

  useEffect(() => {
    if (!data) return
    const destination = data.type === 'region' ? `/regions/${data.identifier}` : `/mapa?planting=${data.identifier}`
    navigate(destination, { replace: true })
  }, [data, navigate])

  if (isPending) {
    return (
      <div className="flex flex-1 items-center justify-center bg-slate-50">
        <LoadingState message="Abrindo..." />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-1 items-center justify-center bg-slate-50">
        <ErrorState message="Não foi possível reconhecer este código. Tente escanear novamente." />
      </div>
    )
  }

  // `data` is set: a redirect is already in flight via the effect above.
  // Nothing to render — the destination page takes over on the next tick.
  return null
}

export default QrRedirectPage
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- QrRedirectPage.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Update `AppRoutes.test.tsx`'s QR redirect test**

The existing test `resolves /r/:qrToken to the QR redirect page with the token from the URL` asserted the old placeholder's raw-token text — replace it:

```tsx
  it('resolves /r/:qrToken to a region page after the token resolves', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        const body = url.startsWith('/api/qr/')
          ? { type: 'region', identifier: 'canteiro-do-ipe' }
          : SAMPLE_REGION
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response)
      }),
    )

    renderAtPath('/r/k3Zq8xR2mNvA')

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Canteiro do Ipê' })).toBeInTheDocument())
  })
```

(This exercises the same `fetch`-routing pattern Step 5 of Task 10 already introduced in this file, now covering three URL shapes: `/api/qr/*`, `/api/plantings*`, and the region fallback.)

- [ ] **Step 6: Run the full suite, build, and lint**

Run:
```bash
npm test
npm run build
npm run lint
```
Expected: every test passes, build succeeds, lint is clean.

- [ ] **Step 7: Manual verification against a running backend**

With the backend plan (`docs/superpowers/plans/2026-08-30-region-planting-backend.md`) implemented and both dev servers running (`cd backend && uvicorn app.main:app --reload`, `cd frontend && npm run dev`, after `python backend/scripts/seed.py`):

1. Open `http://localhost:5173/mapa` — confirm region boundaries and clustered planting pins both render, and clicking a pin opens the drawer (right-side on a wide window, bottom sheet on a narrow one — resize to check both).
2. Open a region's overview at `/regions/{slug}` — confirm it lists its plantings and the "Baixar QR Code da região" link opens a scannable image.
3. Copy a planting's QR image URL (`/api/plantings/{id}/qr-code`) from the drawer's network request or `curl` it, decode the token it encodes, and visit `/r/{token}` directly — confirm it lands on `/mapa` with that planting's drawer already open.
4. Use the sidebar's search field to filter regions by name, and toggle it collapsed/expanded.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/QrRedirectPage.tsx frontend/src/pages/QrRedirectPage.test.tsx frontend/src/AppRoutes.test.tsx
git commit -m "feat: QrRedirectPage resolve o token via API e redireciona pra região ou muda"
```
