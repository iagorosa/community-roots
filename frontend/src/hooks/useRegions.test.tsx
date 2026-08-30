import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import * as regionsService from '../services/regions'
import type { RegionFeatureCollection } from '../types/api'
import { useRegions } from './useRegions'

const SAMPLE_COLLECTION: RegionFeatureCollection = { type: 'FeatureCollection', features: [] }

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useRegions', () => {
  it('fetches the region collection through the regions service', async () => {
    vi.spyOn(regionsService, 'fetchRegions').mockResolvedValue(SAMPLE_COLLECTION)

    const { result } = renderHook(() => useRegions(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(SAMPLE_COLLECTION)
  })
})
