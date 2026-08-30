import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import * as photosService from '../services/photos'
import type { Photo } from '../types/api'
import { useUploadPhoto } from './useUploadPhoto'

const SAMPLE_PHOTO: Photo = {
  id: '0f1c1234-5678-90ab-cdef-1234567890ab',
  description: null,
  contributor_name: null,
  captured_at: null,
  uploaded_at: '2026-08-24T14:05:00Z',
  latitude: null,
  longitude: null,
  width: 1080,
  height: 1350,
  photo_url: '/api/photos/0f1c1234-5678-90ab-cdef-1234567890ab/file',
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useUploadPhoto', () => {
  it('calls the photos service with the given identifier and params', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const uploadSpy = vi.spyOn(photosService, 'uploadPhoto').mockResolvedValue(SAMPLE_PHOTO)
    const file = new File(['fake-image-bytes'], 'canteiro.jpg', { type: 'image/jpeg' })

    const { result } = renderHook(() => useUploadPhoto('canteiro-do-ipe'), {
      wrapper: createWrapper(queryClient),
    })
    result.current.mutate({ file })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(uploadSpy).toHaveBeenCalledWith('canteiro-do-ipe', { file })
  })

  // The whole point of this hook over calling the service directly: the
  // timeline (`usePhotos`, keyed `['photos', identifier]`) must refetch on
  // its own once an upload succeeds, with no manual refresh/navigation.
  it('invalidates the photos query for this identifier on success', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    vi.spyOn(photosService, 'uploadPhoto').mockResolvedValue(SAMPLE_PHOTO)
    const file = new File(['fake-image-bytes'], 'canteiro.jpg', { type: 'image/jpeg' })

    const { result } = renderHook(() => useUploadPhoto('canteiro-do-ipe'), {
      wrapper: createWrapper(queryClient),
    })
    result.current.mutate({ file })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['photos', 'canteiro-do-ipe'] })
  })
})
