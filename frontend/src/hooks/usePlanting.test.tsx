import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
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
  // Without this, the second test's spy inherits the first test's call
  // history (`vi.spyOn` on an already-spied method doesn't reset it), so
  // `not.toHaveBeenCalled()` fails on a leftover call from the prior test.
  afterEach(() => {
    vi.restoreAllMocks()
  })

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
