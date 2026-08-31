import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
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
  // Keeps each test's spy call history isolated (see usePlanting.test.tsx
  // for the failure this prevents).
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('resolves the given token through the qr service', async () => {
    const resolveSpy = vi.spyOn(qrService, 'resolveQrToken').mockResolvedValue(SAMPLE_RESOLUTION)

    const { result } = renderHook(() => useQrResolution('k3Zq8xR2mNvA'), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(resolveSpy).toHaveBeenCalledWith('k3Zq8xR2mNvA')
    expect(result.current.data).toEqual(SAMPLE_RESOLUTION)
  })
})
