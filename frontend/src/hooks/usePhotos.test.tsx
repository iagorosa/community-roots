import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import * as photosService from '../services/photos'
import type { PhotoPage } from '../types/api'
import { usePhotos } from './usePhotos'

const SAMPLE_PAGE: PhotoPage = { items: [], next_cursor: null }

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('usePhotos', () => {
  it('fetches the first page of a region photos through the photos service', async () => {
    const fetchSpy = vi.spyOn(photosService, 'fetchPlantingPhotos').mockResolvedValue(SAMPLE_PAGE)

    const { result } = renderHook(() => usePhotos('canteiro-do-ipe'), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(SAMPLE_PAGE)
    expect(fetchSpy).toHaveBeenCalledWith('canteiro-do-ipe')
  })
})
