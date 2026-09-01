import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
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
  // Keeps each test's spy call history isolated (see usePlanting.test.tsx
  // for the failure this prevents).
  afterEach(() => {
    vi.restoreAllMocks()
  })

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
