import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import * as regionsService from '../services/regions'
import type { RegionFeature } from '../types/api'
import { useRegion } from './useRegion'

const SAMPLE_FEATURE: RegionFeature = {
  type: 'Feature',
  id: '0f1c1234-5678-90ab-cdef-1234567890ab',
  geometry: { type: 'Point', coordinates: [-43.3129, -21.8843] },
  properties: {
    slug: 'canteiro-do-ipe',
    name: 'Canteiro do Ipê',
    description: null,
    status: 'active',
    qr_token: 'k3Zq8xR2mNvA',
    planting_count: 0,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
}

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useRegion', () => {
  it('fetches the single region through the regions service, keyed by identifier', async () => {
    const fetchRegionSpy = vi.spyOn(regionsService, 'fetchRegion').mockResolvedValue(SAMPLE_FEATURE)

    const { result } = renderHook(() => useRegion('canteiro-do-ipe'), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(SAMPLE_FEATURE)
    expect(fetchRegionSpy).toHaveBeenCalledWith('canteiro-do-ipe')
  })
})
